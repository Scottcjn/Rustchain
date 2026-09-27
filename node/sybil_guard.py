# SPDX-License-Identifier: MIT
"""sybil_guard -- new-miner probation for the RIP-200 attestation node.

Incident 2026-09-24: 120 fresh wallets from 3 source IPs attested as PowerPC G4
with fingerprint_passed=1. Each was paid the 0.5 RTC welcome bonus on its first
attestation and auto-enrolled at 1.75x (the 2.5x G4 tier, halved by
TEMPORAL_UNVERIFIED_BONUS_FRACTION because it had <3 samples). The existing
temporal review could not stop it: it scores a miner against its OWN history,
and a brand-new identity has none, so "insufficient_history" still paid half
the vintage premium, and the welcome bonus never consulted it at all.

Design (Scott's intent): trust is EARNED by showing natural, evolving entropy
over time, not by a single snapshot.

  GRANDFATHER Any miner with at least one attestation before
              GRANDFATHER_CUTOFF_TS keeps today's behaviour exactly (weight,
              bonus rule). Honest legacy clients (Python 2.3/2.5 Macs, the lab
              G4 client's constant 0.0123/0/0/2.0) must not be punished. The
              only exception is REVIEW below.
  ADMISSION   A first-seen miner is admitted to probation at most
              NEW_MINERS_PER_IP_PER_DAY per source /32 (IPv6 /64) per 24h.
              Excess identities are ADMISSION-QUEUED: enrollment weight 0 and
              no probation clock until admitted; retried on every attestation.
  PROBATION   No welcome bonus; enrollment weight capped at
              PROBATION_WEIGHT_CAP. Exit needs PROBATION_MIN_ATTESTATIONS
              fingerprint-passing attestations over >= PROBATION_MIN_SPAN_HOURS
              in >= PROBATION_MIN_DISTINCT_HOURS distinct hours; at least
              PROBATION_MIN_VARIED_SUBMISSIONS submissions that moved; every
              required metric (judged over the whole window) moved in at least
              METRIC_MIN_MOVES submissions; a thermal series that is not a
              memoryless redraw; no anomaly in the last
              ANOMALY_PROBATION_EXTENSION_HOURS; and not part of a correlated
              same-/24 cluster of new identities (RIP-309d).
  EXIT CAP    At most NEW_MINER_EXITS_PER_PREFIX_PER_HOUR exits per /24 (IPv6
              /48) -- counted on the miner's ADMISSION prefix and on the
              current request prefix -- and NEW_MINER_EXITS_GLOBAL_PER_HOUR
              overall; excess -> QUEUED. The bonus is paid at exit.
  REVIEW      A sticky needs_review flag -- set from the live profile, from any
              STORED fingerprint-history profile, or from membership in the
              operator's incident cohort table -- holds enrollment and
              settlement weight at 0 for every state, grandfathered included.
              The would-be weight is recorded in sybil_review_escrow. Escrow is
              a record of WEIGHT, not reserved funds (see record_review_escrow).

What this can NOT prove: every metric is self-reported JSON. A careful
adversary can emit a slowly drifting random walk at realistic precision from
many residential IPs and wait out probation. This converts "one POST = 1.75x +
0.5 RTC" into "sustained, varied, non-anomalous behaviour for a day per
identity, throttled per IP, per /24 and per hour" -- a cost, not a proof.

Schema: tables are created ONCE at node startup (init_schema). Request and
settlement paths never run DDL. Pure-Python and Flask-free.
"""

import ipaddress
import json
import logging
import math
import os
import sqlite3
import statistics
import time

log = logging.getLogger("sybil_guard")

# ---------------------------------------------------------------------------
# Constants (reasoning for each value is in NOTES.md)
# ---------------------------------------------------------------------------

#: N -- fingerprint-passing attestations required before probation can end.
PROBATION_MIN_ATTESTATIONS = 8
#: H -- first-to-latest span. 24h = one diurnal/thermal cycle and one epoch, so
#: a wave cannot reach vintage weight or the bonus in the epoch it appears.
PROBATION_MIN_SPAN_HOURS = 24
#: Distinct UTC hour-buckets the counted attestations must fall in, so the span
#: cannot be met by one attestation, a 24h wait, then a burst.
PROBATION_MIN_DISTINCT_HOURS = 6
#: Submissions whose profile moved materially vs the previous submission.
PROBATION_MIN_VARIED_SUBMISSIONS = 3
#: Distinct metrics that must have moved, capped at the number of metrics the
#: miner reported non-zero at ANY point in its probation window (a clock-only
#: Cobalt Qube cannot move four; dropping metrics on the last sample does not
#: lower the requirement).
PROBATION_MIN_VARIED_METRICS = 2
#: A metric counts as varied only if it moved in at least this many submissions,
#: so one wiggle is not enough.
METRIC_MIN_MOVES = 2
#: Relative change that counts as "moved". Honest G5s move cache_hierarchy_ratio
#: by ~5e-5 relative between samples (1e-4 would block 3/12 honest miners);
#: the Sybil generator re-sent byte-identical values.
VARIATION_MIN_REL_CHANGE = 1e-5
#: An anomalous submission pushes the earliest possible exit this far out.
ANOMALY_PROBATION_EXTENSION_HOURS = 48

#: Enrollment weight cap while in probation. 1.0 is the baseline the existing
#: apply_temporal_consistency_to_weight already treats as the floor; min() only,
#: so a miner already below it (x86_64 0.8, aarch64 0.0005) is untouched.
PROBATION_WEIGHT_CAP = 1.0

#: Admission: first-time identities per exact source address per rolling 24h.
NEW_MINERS_PER_IP_PER_DAY = 2
#: Exit caps (the only route to vintage weight + bonus for a new miner).
NEW_MINER_EXITS_PER_PREFIX_PER_HOUR = 2
NEW_MINER_EXITS_GLOBAL_PER_HOUR = 12
IPV4_ADMISSION_PREFIX_LEN = 32
IPV6_ADMISSION_PREFIX_LEN = 64
IPV4_PREFIX_LEN = 24
IPV6_PREFIX_LEN = 48

#: A graduated (non-grandfathered, non-allowlisted) miner earns a multiplier
#: above PROBATION_WEIGHT_CAP only when its latest attestation carried a
#: RIP-309c measurement binding in state "bound".
#: 2026-09-24: Scott chose False -- probation alone gates new vintage premium.
#: The binding is client-reported (duration_ns) and forgeable, so do not treat
#: "bound" as proof if this is ever re-enabled.
REQUIRE_MEASUREMENT_BINDING_FOR_NEW_PREMIUM = False

#: 2026-09-24T00:00:00Z -- before the first Sybil submission (18:43Z). ANY
#: attestation before it grandfathers the miner (round-2 decision).
GRANDFATHER_CUTOFF_TS = 1790208000

#: Operator-recorded incident cohort (node table). Membership -> needs_review.
#: Optional: if the table is absent, nothing is flagged from it.
INCIDENT_COHORT_TABLE = "sybil_cohort_20260924"
_COHORT_ID_COLUMNS = ("miner", "miner_id", "miner_pk", "wallet", "wallet_id", "address")

#: Operator escape hatch: comma-separated miner ids that skip probation (e.g. a
#: NEW lab machine running a static-profile legacy client).
PROBATION_ALLOWLIST_ENV = "RC_PROBATION_ALLOWLIST"

TEMPORAL_METRICS = (
    "clock_drift_cv",
    "thermal_variance",
    "jitter_cv",
    "cache_hierarchy_ratio",
)

#: Empirical upper bounds from honest_profiles.json (maxima 2.3689 / 3.0611 /
#: 0.6464 / 4.0) plus ~14-30% margin. Upper bounds only: honest miners send 0.0
#: for what they cannot measure, and the low tails overlap the attack range.
ANOMALY_RANGE_MAX = {
    "clock_drift_cv": 3.0,
    "thermal_variance": 3.5,
    "jitter_cv": 0.8,
    "cache_hierarchy_ratio": 5.0,
}

#: Fixed-precision signature: all four metrics non-zero, none with more than
#: FIXED_PRECISION_MAX_DECIMALS decimals, and at least FIXED_PRECISION_MIN_AT_MAX
#: of them at exactly that many. Honest producers mix precisions.
FIXED_PRECISION_MAX_DECIMALS = 4
FIXED_PRECISION_MIN_AT_MAX = 1

#: 2026-09-24 generator box (min/max of the 136 Sybil rows). With "all
#: non-zero and <= 4 decimals" it is the needs_review signature.
INCIDENT_20260924_BOX = {
    # Widened 2026-09-25 to the generator's likely bounds (Scott-approved):
    # wave 1 (120 wallets) + wave 2 (24 wallets) observed extremes were
    # clock 0.0080-0.0299, thermal 0.8123-5.9022, jitter 0.0153-0.2473,
    # cache 1.8034-2.8961; each edge rounded OUTWARD to the nearest plausible
    # round(uniform(lo, hi), 4) bound. The old box was fit to wave-1 min/max and
    # missed 4/24 wave-2 wallets sitting just outside it.
    "clock_drift_cv": (0.008, 0.030),
    "thermal_variance": (0.8, 6.0),
    "jitter_cv": (0.015, 0.25),
    "cache_hierarchy_ratio": (1.8, 2.9),
}

#: A grandfathered (pre-cutoff) miner is put in needs_review from its stored
#: history only when at least this many stored profiles match the incident
#: signature (round-2 FP guard). Cohort membership flags on its own. New
#: miners flag on a single match.
GRANDFATHERED_MIN_STORED_MATCHES = 2

#: Memoryless-redraw test on the slow metric (honest median relative step
#: <= 0.154; independent redraws ~0.38).
SHAPE_MAX_MEDIAN_STEP = {"thermal_variance": 0.25}
SHAPE_MIN_STEPS = 3

STATE_GRANDFATHERED = "grandfathered"
STATE_TRUSTED = "trusted"
STATE_PROBATION = "probation"
STATE_QUEUED = "queued"                      # exit-eligible, over the exit cap
STATE_ADMISSION_QUEUED = "admission_queued"  # over the first-seen admission cap
STATE_UNAVAILABLE = "unavailable"            # classification failed

ESTABLISHED_STATES = frozenset({STATE_GRANDFATHERED, STATE_TRUSTED})

REVIEW_LIVE = "incident_20260924_signature"
REVIEW_STORED = "incident_20260924_signature_stored_history"
REVIEW_COHORT = "incident_20260924_cohort"


class SchemaError(RuntimeError):
    """miner_probation / sybil_review_escrow exist but do not match this code."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _as_float(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(f):
        return 0.0
    return f


def normalize_profile(profile):
    """Return {metric: float} for the four temporal metrics (missing -> 0.0)."""
    p = profile if isinstance(profile, dict) else {}
    return {m: _as_float(p.get(m, 0.0)) for m in TEMPORAL_METRICS}


def decimal_digits(value):
    """Decimal digits in the shortest repr of a float (0.0 -> 0, sci -> 99)."""
    s = repr(float(value))
    if "e" in s or "E" in s:
        return 99
    if "." not in s:
        return 0
    frac = s.split(".", 1)[1]
    return 0 if frac == "0" else len(frac)


def _all_short_nonzero(p):
    return all(p[m] > 0 for m in TEMPORAL_METRICS) and all(
        decimal_digits(p[m]) <= FIXED_PRECISION_MAX_DECIMALS for m in TEMPORAL_METRICS)


def profile_anomalies(profile):
    """Anomaly flags for ONE incoming profile. They extend probation only."""
    p = normalize_profile(profile)
    flags = []
    for metric, upper in ANOMALY_RANGE_MAX.items():
        if p[metric] > upper:
            flags.append(f"out_of_range:{metric}")
    if _all_short_nonzero(p):
        at_max = sum(1 for m in TEMPORAL_METRICS
                     if decimal_digits(p[m]) == FIXED_PRECISION_MAX_DECIMALS)
        if at_max >= FIXED_PRECISION_MIN_AT_MAX:
            flags.append("fixed_precision_signature")
    return flags


def matches_incident_signature(profile):
    """2026-09-24 generator: all non-zero, <= 4 decimals, inside the box."""
    p = normalize_profile(profile)
    if not _all_short_nonzero(p):
        return False
    return all(lo <= p[m] <= hi for m, (lo, hi) in INCIDENT_20260924_BOX.items())


def varied_metrics(previous, current):
    """Metrics that moved by >= VARIATION_MIN_REL_CHANGE between two samples.
    A metric that is 0.0 on either side is ignored ("could not measure")."""
    if previous is None:
        return []
    a, b = normalize_profile(previous), normalize_profile(current)
    return [m for m in TEMPORAL_METRICS
            if a[m] > 0 and b[m] > 0
            and abs(b[m] - a[m]) / max(a[m], b[m]) >= VARIATION_MIN_REL_CHANGE]


def _rel_steps(values):
    return [abs(y - x) / max(x, y) for x, y in zip(values, values[1:])
            if x > 0 and y > 0 and x != y]


def shape_blockers(profiles):
    """Memoryless-redraw test over the retained sequence (probation exit only)."""
    seq = [normalize_profile(p) for p in profiles]
    out = []
    for metric, limit in SHAPE_MAX_MEDIAN_STEP.items():
        steps = _rel_steps([p[metric] for p in seq])
        if len(steps) >= SHAPE_MIN_STEPS and statistics.median(steps) > limit:
            out.append(f"memoryless_redraw:{metric}")
    return out


def lag1_autocorrelation(values):
    xs = [v for v in values if v > 0]
    if len(xs) < 4:
        return None
    mean = sum(xs) / len(xs)
    den = sum((x - mean) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((xs[i] - mean) * (xs[i + 1] - mean) for i in range(len(xs) - 1)) / den


def _pearson(xs, ys):
    n = len(xs)
    if n < 4:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


def shape_scores(profiles):
    """Informational only (NOT gates): lag-1 autocorrelation and co-movement.

    The consensus proposed gating on lag-1 autocorrelation in [0.2, 0.95]; on
    honest_profiles.json that gate would block most honest miners (NOTES.md).
    """
    seq = [normalize_profile(p) for p in profiles]
    scores = {}
    for m in ("thermal_variance", "clock_drift_cv"):
        ac = lag1_autocorrelation([p[m] for p in seq])
        scores[f"lag1_{m}"] = None if ac is None else round(ac, 4)
    pairs = [(p["thermal_variance"], p["cache_hierarchy_ratio"]) for p in seq
             if p["thermal_variance"] > 0 and p["cache_hierarchy_ratio"] > 0]
    corr = _pearson([a for a, _ in pairs], [b for _, b in pairs])
    scores["comove_thermal_cache"] = None if corr is None else round(corr, 4)
    return scores


def _ip(ip):
    try:
        addr = ipaddress.ip_address(str(ip or "").strip())
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr


def _net(ip, v4len, v6len):
    addr = _ip(ip)
    if addr is None:
        return "unknown"
    plen = v4len if addr.version == 4 else v6len
    return str(ipaddress.ip_network(f"{addr}/{plen}", strict=False))


def source_prefix(ip):
    """Group a source address by /24 (IPv4) or /48 (IPv6)."""
    return _net(ip, IPV4_PREFIX_LEN, IPV6_PREFIX_LEN)


def admission_key(ip):
    """Exact source for admission (/32); IPv6 grouped by /64."""
    return _net(ip, IPV4_ADMISSION_PREFIX_LEN, IPV6_ADMISSION_PREFIX_LEN)


def probation_allowlist():
    raw = os.environ.get(PROBATION_ALLOWLIST_ENV, "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def is_in_probation(status):
    """True when vintage weight and the welcome bonus must be withheld.
    Fail closed: a missing/garbled status counts as probation."""
    if not isinstance(status, dict):
        return True
    return status.get("state") not in ESTABLISHED_STATES


def needs_review(status):
    """Sticky incident hold. Applies to every state, grandfathered included."""
    return isinstance(status, dict) and bool(status.get("needs_review"))


def should_defer_enrollment(status):
    """True only when the database could not even be opened for
    classification (fallback_status(None, ...)). Then the enrollment write
    would almost certainly fail too; the next attestation retries.

    Round 2b: an error in the establishment QUERY (e.g. a schema surprise)
    does NOT defer -- that would turn one bad column into a 503 for every
    miner. It falls back to today's (live) weight instead; see
    fallback_status."""
    return (isinstance(status, dict)
            and status.get("state") == STATE_UNAVAILABLE
            and bool(status.get("db_unreachable")))


def enrollment_weight(hw_weight, status):
    """Apply the guard to an enrollment weight (already temporal-adjusted).

    needs_review (any state)  -> 0.0 (caller records escrow)
    grandfathered             -> unchanged (today's behaviour)
    unavailable, established True or unknown -> unchanged (live behaviour;
                                 never reduce on an error)
    admission_queued          -> 0.0 (not admitted yet)
    probation/queued/other    -> min(weight, PROBATION_WEIGHT_CAP)
    trusted (graduated)       -> unchanged, unless
                                 REQUIRE_MEASUREMENT_BINDING_FOR_NEW_PREMIUM
    Never raises a weight.
    """
    try:
        weight = float(hw_weight)
    except (TypeError, ValueError):
        return hw_weight
    if needs_review(status):
        return 0.0
    if not isinstance(status, dict):
        return min(weight, PROBATION_WEIGHT_CAP)
    state = status.get("state")
    if state == STATE_GRANDFATHERED:
        return weight
    if state == STATE_UNAVAILABLE and status.get("established", False) is not False:
        return weight
    if state == STATE_ADMISSION_QUEUED:
        return 0.0
    if state != STATE_TRUSTED:
        return min(weight, PROBATION_WEIGHT_CAP)
    if (status.get("reason") != "operator_allowlist"
            and REQUIRE_MEASUREMENT_BINDING_FOR_NEW_PREMIUM
            and status.get("last_binding_state") != "bound"):
        return min(weight, PROBATION_WEIGHT_CAP)
    return weight


def unguarded_status(status):
    """The same status with the review hold removed: used to compute the
    would-be weight that is escrowed for a held miner."""
    if not isinstance(status, dict):
        return status
    out = dict(status)
    out["needs_review"] = 0
    return out


# ---------------------------------------------------------------------------
# Persistence -- schema is created/verified ONCE at startup (init_schema)
# ---------------------------------------------------------------------------

_COLUMNS = (
    "miner", "state", "reason", "first_seen", "admitted_at", "admit_key",
    "last_seen", "attest_count", "distinct_hours", "last_hour_bucket",
    "varied_count", "metric_moves", "metrics_seen", "last_profile_json",
    "anomaly_count", "last_anomaly_ts", "last_anomaly_flags", "needs_review",
    "review_reason", "first_prefix", "exit_prefix", "exit_current_prefix", "exited_at",
    "last_binding_state", "updated_at",
)
_JSON_COLUMNS = {"metric_moves": dict, "metrics_seen": list}
_ESCROW_COLUMNS = ("epoch", "miner", "would_be_weight_units", "reason", "created_at")
SCHEMA_VERSION = 2


def _create_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS miner_probation (
            miner TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            reason TEXT,
            first_seen INTEGER NOT NULL,
            admitted_at INTEGER,
            admit_key TEXT,
            last_seen INTEGER NOT NULL,
            attest_count INTEGER NOT NULL DEFAULT 0,
            distinct_hours INTEGER NOT NULL DEFAULT 0,
            last_hour_bucket INTEGER,
            varied_count INTEGER NOT NULL DEFAULT 0,
            metric_moves TEXT NOT NULL DEFAULT '{}',
            metrics_seen TEXT NOT NULL DEFAULT '[]',
            last_profile_json TEXT,
            anomaly_count INTEGER NOT NULL DEFAULT 0,
            last_anomaly_ts INTEGER,
            last_anomaly_flags TEXT,
            needs_review INTEGER NOT NULL DEFAULT 0,
            review_reason TEXT,
            first_prefix TEXT,
            exit_prefix TEXT,
            exit_current_prefix TEXT,
            exited_at INTEGER,
            last_binding_state TEXT,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sybil_review_escrow (
            epoch INTEGER NOT NULL,
            miner TEXT NOT NULL,
            would_be_weight_units INTEGER NOT NULL,
            reason TEXT,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (epoch, miner)
        )
        """
    )


def _create_indexes(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mp_exit ON miner_probation(exited_at, exit_prefix)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mp_exit_cur ON miner_probation(exited_at, exit_current_prefix)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mp_admit ON miner_probation(admit_key, admitted_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mp_prefix ON miner_probation(first_prefix)")


def verify_schema(conn):
    """Return a list of problems (empty == compatible). Read-only."""
    problems = []
    for table, cols in (("miner_probation", _COLUMNS), ("sybil_review_escrow", _ESCROW_COLUMNS)):
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}  # fetchall-ok: pragma-result
        if not have:
            problems.append(f"{table}: missing")
            continue
        missing = [c for c in cols if c not in have]
        if missing:
            problems.append(f"{table}: missing columns {missing}")
    return problems


def init_schema(db_path_or_conn):
    """Create (if absent) and verify the guard tables. Call ONCE at startup.

    Raises SchemaError if an existing table is incompatible: CREATE TABLE IF
    NOT EXISTS does not upgrade a table, and running the node with a guard
    that cannot read its own state would silently degrade (fail loudly).
    """
    own = isinstance(db_path_or_conn, str)
    conn = sqlite3.connect(db_path_or_conn, timeout=30) if own else db_path_or_conn
    try:
        _create_tables(conn)
        conn.commit()
        problems = verify_schema(conn)
        if problems:
            raise SchemaError("; ".join(problems))
        _create_indexes(conn)
        conn.commit()
    finally:
        if own:
            conn.close()


def ensure_probation_tables(conn):
    """Startup-only (tests/tools): create tables and indexes, no verification."""
    _create_tables(conn)
    _create_indexes(conn)


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def has_pre_cutoff_history(conn, miner, cutoff=None):
    """True if the miner attested at least once before the cutoff.

    Returns False when the history table does not exist (fresh DB).
    Raises on other DB errors so callers can tell "unknown" from "no".
    """
    cutoff = GRANDFATHER_CUTOFF_TS if cutoff is None else cutoff
    if not _table_exists(conn, "miner_attest_history"):
        return False
    cols = {r[1] for r in conn.execute("PRAGMA table_info(miner_attest_history)").fetchall()}  # fetchall-ok: pragma-result
    if not {"miner", "ts_ok"} <= cols:
        raise SchemaError(f"miner_attest_history lacks miner/ts_ok (has {sorted(cols)})")
    return conn.execute(
        "SELECT 1 FROM miner_attest_history WHERE miner = ? AND ts_ok < ? LIMIT 1",
        (miner, int(cutoff)),
    ).fetchone() is not None


# Kept for callers/tests written against round 1.
is_established_before_cutoff = has_pre_cutoff_history


class CohortUndeterminable(RuntimeError):
    """The cohort table exists but membership cannot be determined."""


def _cohort_members(conn, miners, strict=False):
    """Subset of `miners` listed in the incident cohort table.

    Three cases (round 3b):
      (a) table ABSENT -> authoritative empty set. POLICY: the cohort table is
          a one-off, operator-created record of the 2026-09-24 incident; a DB
          that never had it (fresh node, other environments) has no cohort.
          Dropping it is an explicit operator decision, not a fault.
      (b) table PRESENT with a recognised id column (_COHORT_ID_COLUMNS) ->
          normal membership check.
      (c) table PRESENT but no recognised id column -> UNDETERMINABLE:
          strict=True raises CohortUndeterminable (money paths withhold);
          strict=False logs CRITICAL and returns an empty set (callers that can
          only ADD holds). Read errors (sqlite3.Error) always propagate.
    """
    miners = [m for m in (miners or []) if m]
    if not miners or not _table_exists(conn, INCIDENT_COHORT_TABLE):
        return set()
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({INCIDENT_COHORT_TABLE})").fetchall()]  # fetchall-ok: pragma-result
    col = next((c for c in _COHORT_ID_COLUMNS if c in cols), None)
    if col is None:
        msg = (f"{INCIDENT_COHORT_TABLE} has no recognised id column {list(_COHORT_ID_COLUMNS)} "
               f"(has {cols}); cohort membership UNDETERMINABLE")
        if strict:
            raise CohortUndeterminable(msg)
        log.critical("[SYBIL-GUARD] %s", msg)
        return set()
    out = set()
    for i in range(0, len(miners), 500):
        chunk = miners[i:i + 500]
        rows = conn.execute(
            f"SELECT {col} FROM {INCIDENT_COHORT_TABLE} WHERE {col} IN "
            f"({', '.join('?' for _ in chunk)})", chunk).fetchall()  # fetchall-ok: already-paginated (chunked IN, <=500 ids)
        out.update(r[0] for r in rows)
    return out


def _cohort_member_safe(conn, miner):
    """Cohort membership for one miner; absent/unreadable table -> False
    (logged). Used on hot paths that must not raise."""
    try:
        return bool(_cohort_members(conn, [miner]))
    except sqlite3.Error as exc:
        log.critical("[SYBIL-GUARD] cohort lookup failed for %s: %s (no cohort flag added)",
                     str(miner)[:20], exc)
        return False


def bonus_eligibility_in_txn(conn, miner):
    """Authorise the welcome bonus INSIDE the caller's write transaction.

    Re-reads the PERSISTED miner_probation row and the CURRENT incident-cohort
    membership on `conn` (which must already hold BEGIN IMMEDIATE), so a hold
    committed after the attestation's observation but before payment is seen.
    Returns (eligible: bool, state_or_None, why: str). Fails closed: any
    uncertainty -> not eligible (the bonus stays unpaid and retryable).
    """
    try:
        if not _table_exists(conn, "miner_probation"):
            return False, None, "no_probation_table"
        row = conn.execute(
            "SELECT state, needs_review FROM miner_probation WHERE miner = ?", (miner,)).fetchone()
        if row is None:
            return False, None, "no_probation_row"
        state, nr = row[0], int(row[1] or 0)
        if nr:
            return False, state, "needs_review"
        if state not in ESTABLISHED_STATES:
            return False, state, f"state:{state}"
        # Cohort: absent table -> no cohort (policy, see _cohort_members);
        # present-but-malformed or unreadable -> undeterminable -> withhold.
        try:
            if _cohort_members(conn, [miner], strict=True):
                return False, state, "cohort_member"
        except (CohortUndeterminable, sqlite3.Error) as exc:
            log.critical("[SYBIL-GUARD] welcome bonus WITHHELD for %s: cohort membership "
                         "undeterminable (%s); retryable", str(miner)[:20], exc)
            return False, state, f"cohort_undeterminable:{exc}"
        return True, state, "ok"
    except Exception as exc:  # noqa: BLE001 - cannot determine -> withhold
        log.error("[SYBIL-GUARD] bonus eligibility undeterminable for %s: %s", str(miner)[:20], exc)
        return False, None, f"undeterminable:{exc}"


def fetch_profiles(conn, miner):
    if not _table_exists(conn, "miner_fingerprint_history"):
        return []
    out = []
    for (pj,) in conn.execute(
        "SELECT profile_json FROM miner_fingerprint_history WHERE miner = ? ORDER BY ts ASC, id ASC",
        (miner,),
    ).fetchall():  # fetchall-ok: bounded-by-schema (<=10 rows/miner, TEMPORAL_HISTORY_LIMIT)
        try:
            out.append(normalize_profile(json.loads(pj or "{}")))
        except (TypeError, ValueError):
            continue
    return out


def stored_review_reason(conn, miner, grandfathered=False):
    """needs_review reason from STORED data (cohort table, stored history), or
    None. Cohort membership flags on its own. Stored history flags on one
    matching profile for a new miner, on >= GRANDFATHERED_MIN_STORED_MATCHES
    for a grandfathered one. Fail-safe: an unreadable cohort table is logged
    and skipped."""
    try:
        if _cohort_members(conn, [miner]):
            return REVIEW_COHORT
    except sqlite3.Error as exc:
        log.error("[SYBIL-GUARD] cohort lookup failed for %s: %s", str(miner)[:20], exc)
    need = GRANDFATHERED_MIN_STORED_MATCHES if grandfathered else 1
    matches = sum(1 for p in fetch_profiles(conn, miner) if matches_incident_signature(p))
    if matches >= need:
        return REVIEW_STORED
    return None


def _set_review(st, reason):
    """Set the sticky flag; CRITICAL when it lands on a grandfathered miner
    (an established miner going to weight 0 must never be silent)."""
    st["needs_review"], st["review_reason"] = 1, reason
    if st.get("state") == STATE_GRANDFATHERED:
        log.critical("[SYBIL-GUARD] GRANDFATHERED miner %s put in needs_review (%s) -- weight 0 "
                     "until an operator clears miner_probation.needs_review", st.get("miner"), reason)


def _load(conn, miner):
    row = conn.execute(
        f"SELECT {', '.join(_COLUMNS)} FROM miner_probation WHERE miner = ?", (miner,)
    ).fetchone()
    if not row:
        return None
    st = dict(zip(_COLUMNS, row))
    for col, typ in _JSON_COLUMNS.items():
        raw = st.get(col)
        try:
            val = json.loads(raw) if raw is not None else None
        except (TypeError, ValueError):
            val = None
        if col == "metrics_seen":
            # falsegreen fix: NULL/unreadable is "no record", which must NOT
            # relax the varied-metric requirement (see required_varied_metrics).
            st[col] = val if isinstance(val, list) else None
        else:
            st[col] = val if isinstance(val, typ) else typ()
    return st


def _save(conn, st):
    cols = [c for c in _COLUMNS if c != "miner"]
    vals = [json.dumps(st[c]) if c in _JSON_COLUMNS else st.get(c) for c in cols]
    conn.execute(
        f"INSERT INTO miner_probation (miner, {', '.join(cols)}) "
        f"VALUES (?, {', '.join('?' for _ in cols)}) ON CONFLICT(miner) DO UPDATE SET "
        + ", ".join(f"{c}=excluded.{c}" for c in cols),
        [st["miner"]] + vals,
    )


def _admission_full(conn, key, now):
    if key == "unknown":
        return False
    n = conn.execute(
        "SELECT COUNT(*) FROM miner_probation WHERE admit_key = ? AND admitted_at >= ? "
        "AND state NOT IN (?, ?)",
        (key, int(now) - 86400, STATE_GRANDFATHERED, STATE_ADMISSION_QUEUED),
    ).fetchone()[0]
    return n >= NEW_MINERS_PER_IP_PER_DAY


def required_varied_metrics(st):
    """Varied metrics required to exit probation.

    A REAL metrics_seen list relaxes the requirement to what the miner can
    measure (a Cobalt Qube reporting only clock -> 1). A missing/None record
    is not evidence of a limited device: require the full
    PROBATION_MIN_VARIED_METRICS (fail closed; falsegreen FG005 fix).
    """
    seen = st.get("metrics_seen")
    if not isinstance(seen, list):
        return PROBATION_MIN_VARIED_METRICS
    return max(1, min(PROBATION_MIN_VARIED_METRICS, len(seen)))


def counted_varied_metrics(st):
    """Metrics that moved often enough. A missing record counts as NONE moved,
    which blocks exit (fail closed), never as a pass."""
    moves = st.get("metric_moves")
    if not isinstance(moves, dict):
        return []
    return sorted(m for m, n in moves.items() if int(n) >= METRIC_MIN_MOVES)


def _exit_blockers(st, now):
    blockers = []
    if st["attest_count"] < PROBATION_MIN_ATTESTATIONS:
        blockers.append(f"attestations:{st['attest_count']}/{PROBATION_MIN_ATTESTATIONS}")
    start = st.get("admitted_at") or st["first_seen"]
    span_h = (int(now) - int(start)) / 3600.0
    if span_h < PROBATION_MIN_SPAN_HOURS:
        blockers.append(f"span_hours:{span_h:.1f}/{PROBATION_MIN_SPAN_HOURS}")
    if int(st.get("distinct_hours") or 0) < PROBATION_MIN_DISTINCT_HOURS:
        blockers.append(f"distinct_hours:{st.get('distinct_hours')}/{PROBATION_MIN_DISTINCT_HOURS}")
    if st["varied_count"] < PROBATION_MIN_VARIED_SUBMISSIONS:
        blockers.append(f"varied_submissions:{st['varied_count']}/{PROBATION_MIN_VARIED_SUBMISSIONS}")
    need = required_varied_metrics(st)
    have = len(counted_varied_metrics(st))
    if have < need:
        blockers.append(f"varied_metrics:{have}/{need}")
    if st.get("last_anomaly_ts") is not None:
        until = int(st["last_anomaly_ts"]) + ANOMALY_PROBATION_EXTENSION_HOURS * 3600
        if int(now) < until:
            blockers.append(f"anomaly_extension_until:{until}")
    if st.get("needs_review"):
        blockers.append(f"needs_review:{st.get('review_reason')}")
    return blockers


def _cap_blockers(conn, prefixes, now):
    since = int(now) - 3600
    out = []
    for prefix in sorted({p for p in prefixes if p and p != "unknown"}):
        # Round 3: an exit is charged to BOTH its admission prefix and the
        # prefix it graduated from. OR (not a sum) so an exit whose two
        # prefixes are identical is counted once.
        n = conn.execute(
            "SELECT COUNT(*) FROM miner_probation WHERE exited_at >= ? "
            "AND (exit_prefix = ? OR exit_current_prefix = ?)",
            (since, prefix, prefix),
        ).fetchone()[0]
        if n >= NEW_MINER_EXITS_PER_PREFIX_PER_HOUR:
            out.append(f"prefix_cap:{prefix}:{n}/{NEW_MINER_EXITS_PER_PREFIX_PER_HOUR}")
    global_n = conn.execute(
        "SELECT COUNT(*) FROM miner_probation WHERE exited_at >= ? AND exit_prefix IS NOT NULL",
        (since,),
    ).fetchone()[0]
    if global_n >= NEW_MINER_EXITS_GLOBAL_PER_HOUR:
        out.append(f"global_cap:{global_n}/{NEW_MINER_EXITS_GLOBAL_PER_HOUR}")
    return out


def _cluster_blockers(conn, st, cluster_check):
    """RIP-309d: new identities from the same /24 must look independent."""
    if cluster_check is None or st.get("first_prefix") in (None, "unknown"):
        return []
    peers = [r[0] for r in conn.execute(
        "SELECT miner FROM miner_probation WHERE first_prefix = ? AND state != ? "
        "AND COALESCE(reason, '') != 'operator_allowlist' ORDER BY first_seen DESC LIMIT 200",
        (st["first_prefix"], STATE_GRANDFATHERED),
    ).fetchall()]  # fetchall-ok: already-paginated (LIMIT 200)
    members = list(dict.fromkeys([st["miner"]] + peers))
    try:
        verdict = cluster_check(conn, members)
    except Exception as exc:
        # falsegreen fix: an unavailable check must not ALLOW exit. Blocking
        # only delays graduation (weight stays <= PROBATION_WEIGHT_CAP).
        log.error("cluster_check failed for %s: %s", st.get("miner"), exc)
        return [f"cluster_check_unavailable:{type(exc).__name__}"]
    if not isinstance(verdict, dict) or not verdict:
        log.error("cluster_check returned no verdict for %s: %r", st.get("miner"), verdict)
        return ["cluster_check_unavailable:empty_verdict"]
    if verdict.get("state") == "correlated":
        return [f"cluster_correlated:{st['first_prefix']}:spread={verdict.get('spread')}"]
    return []


def _new_row(conn, miner, prefix, akey, now):
    if miner in probation_allowlist():
        state, reason = STATE_TRUSTED, "operator_allowlist"
    elif has_pre_cutoff_history(conn, miner):
        state, reason = STATE_GRANDFATHERED, "attested_before_cutoff"
    elif _admission_full(conn, akey, now):
        state, reason = STATE_ADMISSION_QUEUED, f"admission_cap:{akey}"
    else:
        state, reason = STATE_PROBATION, "new_miner"
    review = stored_review_reason(conn, miner, grandfathered=(state == STATE_GRANDFATHERED))
    row = {
        "miner": miner, "state": state, "reason": reason, "first_seen": int(now),
        "admitted_at": int(now) if state == STATE_PROBATION else None,
        "admit_key": akey, "last_seen": int(now), "attest_count": 0,
        "distinct_hours": 0, "last_hour_bucket": None, "varied_count": 0,
        "metric_moves": {}, "metrics_seen": [], "last_profile_json": None,
        "anomaly_count": 0, "last_anomaly_ts": None, "last_anomaly_flags": None,
        "needs_review": 0, "review_reason": None,
        "first_prefix": prefix, "exit_prefix": None, "exit_current_prefix": None, "exited_at": None,
        "last_binding_state": None, "updated_at": int(now),
    }
    if review:
        _set_review(row, review)
    return row


def observe_attestation(conn, miner, profile, source_ip, now=None,
                        fingerprint_passed=True, binding_state=None,
                        cluster_check=None):
    """Record one attestation and advance the miner's probation state.

    Call AFTER record_attestation_success (so miner_fingerprint_history holds
    this profile) and BEFORE the welcome bonus / auto-enroll. Runs under BEGIN
    IMMEDIATE so admission and exit caps are counted atomically across gunicorn
    workers; `conn` must be opened with isolation_level=None. No DDL: the
    tables must exist (init_schema at startup); a missing table raises and the
    caller's error boundary takes over.

    On a miner's first observation, needs_review is seeded from STORED data
    (incident cohort table, stored fingerprint history), so an identity cannot
    shed the flag by no longer sending the incident profile.
    """
    now = int(time.time() if now is None else now)
    prof = normalize_profile(profile)
    prefix = source_prefix(source_ip)
    akey = admission_key(source_ip)
    anomalies = profile_anomalies(prof)
    incident = matches_incident_signature(prof)

    conn.execute("BEGIN IMMEDIATE")
    try:
        st = _load(conn, miner) or _new_row(conn, miner, prefix, akey, now)
        just_exited = False
        blockers = []

        # Round 3: cohort membership is evaluated on EVERY observation, so a
        # wallet added to the cohort table after its row exists is held too.
        if not st.get("needs_review") and _cohort_member_safe(conn, miner):
            _set_review(st, REVIEW_COHORT)
        if not st.get("needs_review"):
            if st["state"] == STATE_GRANDFATHERED:
                # One live match is not enough for an established miner: it
                # must repeat (>= GRANDFATHERED_MIN_STORED_MATCHES stored
                # samples; this attestation is already stored) or be in the
                # cohort table.
                if incident:
                    review = stored_review_reason(conn, miner, grandfathered=True)
                    if review:
                        _set_review(st, review)
            elif incident:
                _set_review(st, REVIEW_LIVE)

        if st["state"] == STATE_ADMISSION_QUEUED and not _admission_full(conn, st["admit_key"], now):
            st["state"], st["reason"], st["admitted_at"] = STATE_PROBATION, "admitted", now

        st["last_binding_state"] = binding_state
        if st["state"] in (STATE_PROBATION, STATE_QUEUED):
            if fingerprint_passed:
                try:
                    prev = json.loads(st.get("last_profile_json") or "null")
                except (TypeError, ValueError):
                    prev = None
                moved = varied_metrics(prev, prof)
                st["attest_count"] = int(st["attest_count"]) + 1
                bucket = now // 3600
                if st.get("last_hour_bucket") != bucket:
                    st["distinct_hours"] = int(st.get("distinct_hours") or 0) + 1
                    st["last_hour_bucket"] = bucket
                if moved:
                    st["varied_count"] = int(st["varied_count"]) + 1
                    moves = dict(st.get("metric_moves") or {})
                    for m in moved:
                        moves[m] = int(moves.get(m, 0)) + 1
                    st["metric_moves"] = moves
                st["metrics_seen"] = sorted(set(st.get("metrics_seen") or ())
                                            | {m for m in TEMPORAL_METRICS if prof[m] > 0})
                st["last_profile_json"] = json.dumps(prof, separators=(",", ":"))
            if anomalies:
                st["anomaly_count"] = int(st.get("anomaly_count") or 0) + 1
                st["last_anomaly_ts"] = now
                st["last_anomaly_flags"] = json.dumps(anomalies)

            blockers = _exit_blockers(st, now)
            if not fingerprint_passed:
                blockers.append("fingerprint_failed")
            if not blockers:
                blockers = shape_blockers(fetch_profiles(conn, miner))
            if not blockers:
                blockers = _cluster_blockers(conn, st, cluster_check)
            if not blockers:
                cap = _cap_blockers(conn, [st.get("first_prefix"), prefix], now)
                if cap:
                    st["state"], st["reason"] = STATE_QUEUED, cap[0]
                    blockers = cap
                else:
                    st["state"], st["reason"] = STATE_TRUSTED, "probation_exit"
                    # Exit is charged to the ADMISSION prefix, so leaving from a
                    # different /24 does not dodge that prefix's cap.
                    st["exited_at"] = now
                    st["exit_prefix"] = st.get("first_prefix") or prefix
                    st["exit_current_prefix"] = prefix
                    just_exited = True
            else:
                st["reason"] = blockers[0]
                if st["state"] == STATE_QUEUED:
                    st["state"] = STATE_PROBATION
        elif st["state"] == STATE_ADMISSION_QUEUED:
            blockers = [st["reason"]]
        else:
            # Grandfathered / trusted: today's behaviour; just track.
            st["attest_count"] = int(st["attest_count"]) + 1
            if st.get("needs_review"):
                blockers = [f"needs_review:{st.get('review_reason')}"]

        st["last_seen"] = st["updated_at"] = now
        _save(conn, st)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    st.update({
        "in_probation": st["state"] not in ESTABLISHED_STATES,
        "just_exited": just_exited,
        "anomalies": anomalies,
        "incident_signature": incident,
        "blockers": blockers,
    })
    return st


def get_probation_status(conn, miner, now=None):
    """Read-only status for /epoch/enroll. Never writes.

    A miner without a row is classified on the fly (allowlist, pre-cutoff
    history, stored-data review) so a Sybil that enrolls without attesting
    after deploy is still held. Unknown new miner -> probation (fail closed).
    """
    if _table_exists(conn, "miner_probation"):
        st = _load(conn, miner)
        if st is not None:
            st["in_probation"] = st["state"] not in ESTABLISHED_STATES
            # Round 3: pick up cohort membership added after the row existed
            # (read-only; the next attestation persists it).
            if not st.get("needs_review") and _cohort_member_safe(conn, miner):
                st["needs_review"], st["review_reason"] = 1, REVIEW_COHORT
                if st["state"] == STATE_GRANDFATHERED:
                    log.critical("[SYBIL-GUARD] GRANDFATHERED miner %s held at enrollment (%s)",
                                 miner, REVIEW_COHORT)
            return st
    if miner in probation_allowlist():
        state, reason = STATE_TRUSTED, "operator_allowlist"
    elif has_pre_cutoff_history(conn, miner):
        state, reason = STATE_GRANDFATHERED, "attested_before_cutoff"
    else:
        state, reason = STATE_PROBATION, "no_probation_row"
    review = stored_review_reason(conn, miner, grandfathered=(state == STATE_GRANDFATHERED))
    if review and state == STATE_GRANDFATHERED:
        log.critical("[SYBIL-GUARD] GRANDFATHERED miner %s held at enrollment (%s)", miner, review)
    return {"miner": miner, "state": state, "reason": reason,
            "needs_review": 1 if review else 0, "review_reason": review,
            "in_probation": state not in ESTABLISHED_STATES}


def fallback_status(conn, miner):
    """Status to use when observe_attestation / get_probation_status failed.

    Never raises. Enrollment never REDUCES an established miner's weight
    because of an error:
      established True  -> today's (live) weight
      established False -> probation cap (a known-new miner)
      established None  -> the history query failed: today's (live) weight,
                           logged CRITICAL (fail to live behaviour, not to a
                           503 for every miner)
      conn None         -> database unreachable: enrollment deferred
    Stored-data review (cohort / stored history) is still applied if readable.
    """
    if conn is None:
        return {"miner": miner, "state": STATE_UNAVAILABLE, "reason": "db_unreachable",
                "established": None, "db_unreachable": True, "in_probation": True}
    try:
        established = has_pre_cutoff_history(conn, miner)
    except Exception as exc:  # noqa: BLE001 - classification must never raise
        log.critical("[SYBIL-GUARD] establishment check failed for %s (%s): using LIVE "
                     "weight behaviour for this enrollment", str(miner)[:20], exc)
        established = None
    review = None
    try:
        review = stored_review_reason(conn, miner, grandfathered=established is not False)
    except Exception as exc:  # noqa: BLE001
        log.error("[SYBIL-GUARD] stored review lookup failed for %s: %s", str(miner)[:20], exc)
    return {"miner": miner, "state": STATE_UNAVAILABLE, "reason": "classification_failed",
            "established": established, "db_unreachable": False,
            "needs_review": 1 if review else 0, "review_reason": review, "in_probation": True}


def record_review_escrow(conn, epoch, miner, would_be_weight_units, reason, now=None):
    """Record what a held miner would have been weighted at (first wins).

    ESCROW IS A RECORD OF WEIGHT, NOT RESERVED FUNDS. The held miner's share of
    the epoch pot is redistributed to the other miners at settlement; nothing
    is set aside. Restoring a wrongly-held miner means an operator transfer
    from a founder/ops wallet sized from these rows -- a manual payment, not a
    release. No DDL here (table created at startup).
    """
    conn.execute(
        "INSERT OR IGNORE INTO sybil_review_escrow "
        "(epoch, miner, would_be_weight_units, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (int(epoch), miner, int(would_be_weight_units), reason,
         int(time.time() if now is None else now)),
    )


def record_review_escrow_safe(conn, epoch, miner, would_be_weight_units, reason, now=None):
    """record_review_escrow inside a SAVEPOINT; never raises (settlement path).

    The escrow row is an audit record: failing to write it must not abort or
    poison the caller's settlement transaction."""
    try:
        conn.execute("SAVEPOINT sybil_escrow")
    except Exception as exc:  # noqa: BLE001
        log.error("[SYBIL-GUARD] escrow savepoint failed for %s: %s", str(miner)[:20], exc)
        return False
    try:
        record_review_escrow(conn, epoch, miner, would_be_weight_units, reason, now=now)
        conn.execute("RELEASE sybil_escrow")
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            conn.execute("ROLLBACK TO sybil_escrow")
            conn.execute("RELEASE sybil_escrow")
        except Exception:  # noqa: BLE001
            pass
        log.error("[SYBIL-GUARD] escrow write failed for %s epoch %s: %s",
                  str(miner)[:20], epoch, exc)
        return False


def hold_for_settlement(conn, epoch, miners, weights=None, record=True,
                        reason="settlement_hold"):
    """Held subset of `miners` for this settlement; optionally escrows each
    held miner's positive would-be weight on `conn` (the settlement
    transaction). Never raises.

    `weights`: {miner: weight_units}, or a zero-argument callable returning
    one. A callable is evaluated INSIDE this guard: if the weight read fails,
    the hold is still applied (held miners still settle at 0) and only the
    escrow record is skipped, logged. The caller's PAYOUT weights are read
    separately and stay fail-loud."""
    held = settlement_held_miners(conn, miners, epoch)
    if record and held and callable(weights):
        try:
            weights = weights()
        except Exception as exc:  # noqa: BLE001
            log.error("[SYBIL-GUARD] epoch %s: escrow weight read failed (%s); hold applied, "
                      "escrow rows NOT written", epoch, exc)
            weights = None
            record = False
    if record and held:
        for m in held:
            w = (weights or {}).get(m)
            try:
                units = int(w) if w is not None else 0
            except (TypeError, ValueError):
                units = 0
            if units > 0:
                record_review_escrow_safe(conn, epoch, m, units, reason)
    if held:
        log.warning("[SYBIL-GUARD] epoch %s: %d needs_review miner(s) held at 0", epoch, len(held))
    return held


def review_held_miners(conn, miners):
    """Subset of `miners` flagged needs_review in miner_probation or listed in
    the incident cohort table. Read-only. Raises on DB errors; settlement code
    must use settlement_held_miners, which never raises."""
    miners = [m for m in (miners or []) if m]
    if not miners:
        return set()
    held = set()
    if _table_exists(conn, "miner_probation"):
        for i in range(0, len(miners), 500):
            chunk = miners[i:i + 500]
            rows = conn.execute(
                "SELECT miner FROM miner_probation WHERE needs_review = 1 "
                f"AND miner IN ({', '.join('?' for _ in chunk)})",
                chunk,
            ).fetchall()  # fetchall-ok: already-paginated (chunked IN, <=500 ids)
            held.update(r[0] for r in rows)
    else:
        log.critical("[SYBIL-GUARD] miner_probation table does not exist -- no probation holds "
                     "applied (expected only before the guarded node has started once)")
    # Round 3b: a malformed/unreadable cohort table must not discard the
    # needs_review holds already collected above (it can only ADD holds).
    try:
        held |= _cohort_members(conn, miners)
    except sqlite3.Error as exc:
        log.critical("[SYBIL-GUARD] cohort table unreadable at settlement (%s); "
                     "applying miner_probation holds only", exc)
    return held


def settlement_held_miners(conn, miners, epoch=None):
    """Settlement-safe hold lookup. NEVER raises.

    Order of evidence:
      1. miner_probation needs_review + incident cohort (review_held_miners).
      2. On a DB error: miners with a sybil_review_escrow row for this epoch
         (written when the hold was applied at enrollment).
      3. If that fails too: empty set, logged CRITICAL. Settlement then pays
         the stored epoch_enroll weights, which are already 0 for every miner
         held at enrollment time; only a miner flagged after enrolling (at a
         probation-capped weight) would be paid. Settlement is never halted.
    """
    try:
        return review_held_miners(conn, miners)
    except Exception as exc:  # noqa: BLE001
        log.critical("[SYBIL-GUARD] settlement hold lookup failed (%s); falling back to escrow rows", exc)
    try:
        if epoch is None:
            return set()
        miners = [m for m in (miners or []) if m]
        held = set()
        for i in range(0, len(miners), 500):
            chunk = miners[i:i + 500]
            rows = conn.execute(
                "SELECT miner FROM sybil_review_escrow WHERE epoch = ? "
                f"AND miner IN ({', '.join('?' for _ in chunk)})",
                [int(epoch)] + chunk,
            ).fetchall()  # fetchall-ok: already-paginated (chunked IN, <=500 ids)
            held.update(r[0] for r in rows)
        return held
    except Exception as exc:  # noqa: BLE001
        log.critical("[SYBIL-GUARD] escrow fallback failed too (%s); settling on stored "
                     "enrollment weights only", exc)
        return set()


def public_status(status):
    """Compact, non-sensitive view for the /attest/submit response."""
    if not isinstance(status, dict):
        return {"state": STATE_UNAVAILABLE}
    return {
        "state": status.get("state"),
        "attestations": status.get("attest_count"),
        "varied_submissions": status.get("varied_count"),
        "blockers": list(status.get("blockers") or [])[:6],
        "requirements": {
            "attestations": PROBATION_MIN_ATTESTATIONS,
            "span_hours": PROBATION_MIN_SPAN_HOURS,
            "distinct_hours": PROBATION_MIN_DISTINCT_HOURS,
            "varied_submissions": PROBATION_MIN_VARIED_SUBMISSIONS,
            "varied_metrics": PROBATION_MIN_VARIED_METRICS,
            "moves_per_metric": METRIC_MIN_MOVES,
        },
    }
