#!/usr/bin/env python3
"""
RIP-202 — deterministic producer-enrollment derivation (Phase B1).

PURE, side-effect-free core (except the explicit sealing helper, which takes a
caller-supplied connection). Nothing in the live node calls this yet — it is the
deterministic foundation that block-apply (B2) and epoch sealing (B3) will use.

Design constraints (see rips/docs/RIP-0202):
  * Producer selection is deterministic consensus. This module must compute the
    SAME enrollment on every node from the SAME committed block attestations.
  * Weights are carried as INTEGER fixed-point units, never raw floats, so the
    snapshot hash is identical across architectures (no float-repr divergence).
  * The hardware-weight policy is NOT duplicated here: ``derive_verified_device``
    and the ``HARDWARE_WEIGHTS`` table are INJECTED, so the one source of truth
    in the main node stays authoritative.

Scope (operator decision 2026-05-31, option (a)): eligibility is ATTESTATION-LEVEL
— a miner is eligible iff its fingerprint passed AND its derived hardware weight
is positive. The RIP-309 temporal fingerprint-rotation ``active_ratio`` is OUT OF
SCOPE for RIP-202 and deferred to a follow-up RIP; this module derives the base
hardware weight only.

Contracts & intentional decisions (settled across tri-brain review rounds):
  * FAIL-CLOSED policy divergence (intentional): an empty / unrecognised derived
    family yields weight 0 (excluded) here, NOT the live reward path's 1.0
    fallback. This is a SEPARATE consensus path (producer eligibility), not the
    reward-weight computation, and an unrecognised identity means derivation
    failed — failing closed is correct for a gate. Legit miners always derive to
    a known family, so this never excludes real hardware.
  * B0 INPUT CONTRACT: committed attestations are deserialised from the block's
    JSON (the ``attestations_hash`` payload), so ``device``/``fingerprint`` are
    always JSON-primitive structures — ``json.dumps(sort_keys=True)`` is therefore
    deterministic for all real inputs. The repr fallback in ``_attestation_tiebreak``
    is a defensive non-abort path for impossible-in-practice malformed data.
  * ``finalized_at`` is AUDIT METADATA, not consensus-bound: it is NOT part of
    ``snapshot_hash``, so a divergent value across nodes does not fork consensus
    (the eligible set, captured in ``snapshot_hash``, is what binds). B3 should
    still pass a chain-derived value for clean audit.
  * INTEGRATION (B2/B3) REQUIREMENTS, not satisfiable in this dormant module:
    (1) call ``ensure_epoch_enroll_state_schema`` ONCE at node/DB init (NOT in a
    consensus tx — DDL implicit-commit); (2) wire the REAL ``derive_verified_device``
    + ``HARDWARE_WEIGHTS`` and add integration tests over real committed shapes;
    (3) the snapshot-hash field set + WEIGHT_SCALE + threshold become an immutable
    consensus contract once any epoch is sealed — change them only behind the
    on-chain activation height (PREREQ-A).
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from typing import Callable, Dict, List, Mapping, Optional

# Fixed-point scale for weights. 1e6 keeps the legitimate weight ladder exact
# (e.g. 0.0005 -> 500 units, 2.5 -> 2_500_000) while the ~1e-9 failed-fingerprint
# value rounds to 0 units, so it is excluded without a special case.
WEIGHT_SCALE = 1_000_000

# A miner is eligible iff its derived weight is at least this many units.
# 1 unit (= 1e-6) is below every legitimate hardware weight (min 0.0005 = 500u)
# and above the rounded failed-fingerprint value (0u), so it cleanly excludes
# VMs/emulators while admitting all real hardware classes.
DEFAULT_ELIGIBILITY_THRESHOLD_UNITS = 1


def to_weight_units(weight: float) -> int:
    """Canonicalise a float hardware weight to deterministic integer units.

    Non-numeric / NaN / negative weights canonicalise to 0 units (excluded) so
    a malformed injected weight fails closed rather than crashing or admitting a
    miner with a bogus weight.
    """
    try:
        w = float(weight)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(w) or w < 0:  # NaN / +-inf / negative -> excluded
        return 0
    return int(round(w * WEIGHT_SCALE))


def _strict_int(value):
    """Return value as int iff it is a genuine int (not bool/float/str), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _safe_int(value, default: int = 0) -> int:
    """Coerce to int, falling back to ``default`` on any malformed value."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: int(float("inf")) — a malformed committed timestamp must
        # not abort the whole-block sort; fall back to the default.
        return default


def _coerce_dict(value) -> dict:
    """Return ``value`` if it is a dict, else an empty dict (fail-closed)."""
    return value if isinstance(value, dict) else {}


def _attestation_tiebreak(attestation: Mapping) -> str:
    """Deterministic content digest of an attestation's consensus fields.

    Used as the FINAL sort tiebreaker so two attestations for the same miner
    with the same timestamp resolve identically on every node (total order).
    Truly-identical attestations hash equally and are interchangeable.
    """
    payload = {
        "device": _coerce_dict(attestation.get("device")),
        "fingerprint": _coerce_dict(attestation.get("fingerprint")),
        "fingerprint_passed": attestation.get("fingerprint_passed") is True,
    }
    try:
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Non-JSON-safe content (e.g. non-string dict keys) must not abort the
        # whole block's enrollment from inside the sort key. Fall back to a
        # deterministic repr-based digest of the sorted items.
        canonical = repr(sorted((str(k), str(v)) for k, v in payload.items()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_threshold(threshold_units: int) -> int:
    """Eligibility threshold must be >= 1 unit, else INV-2 can be defeated."""
    if isinstance(threshold_units, bool) or not isinstance(threshold_units, int) or threshold_units < 1:
        raise ValueError("threshold_units must be an int >= 1")
    return threshold_units


def _lookup_hardware_weight(weight_table: Mapping, family: str, arch: str) -> float:
    """Mirror the live lookup: HARDWARE_WEIGHTS[family][arch] with default fallback.

    Matches ``HARDWARE_WEIGHTS.get(family, {}).get(arch, ...default...)`` used in
    the main node. Unknown family/arch falls back to the family default, then 1.0.
    """
    # Fail CLOSED on an unrecognised / empty derived identity: an empty family
    # (derivation produced junk) or a family absent from the table must NOT be
    # admitted via a positive default — that is the fail-open hole. Only a KNOWN
    # family falls back to its own "default" arch weight.
    if not family:
        return 0.0
    fam = weight_table.get(family)
    if not isinstance(fam, Mapping):
        return 0.0  # unknown family or malformed table -> excluded
    if arch in fam:
        return fam[arch]
    return fam.get("default", 0.0)  # known family, unknown arch -> family default


def attestation_weight_units(
    attestation: Mapping,
    derive_fn: Callable[[dict, dict, bool], dict],
    weight_table: Mapping,
) -> int:
    """Deterministic base hardware weight (in units) for one committed attestation.

    ``attestation`` is a block-committed record carrying ``device`` (dict),
    ``fingerprint`` (dict) and ``fingerprint_passed`` (bool) — the B0 format.
    A failed fingerprint yields 0 units (excluded), mirroring the live
    FAILED_FINGERPRINT path. Otherwise the verified (family, arch) from
    ``derive_fn`` drives the ``weight_table`` lookup.
    """
    if attestation.get("fingerprint_passed") is not True:
        return 0  # failed/ambiguous fingerprint (VM/emulator) -> excluded
    device = attestation.get("device")
    fingerprint = attestation.get("fingerprint")
    # Malformed or missing device/fingerprint -> EXCLUDE (fail closed). Do NOT
    # coerce to {} and let the table default admit the miner — that fails OPEN.
    if not isinstance(device, dict) or not isinstance(fingerprint, dict):
        return 0
    verified = _coerce_dict(derive_fn(device, fingerprint, True))
    family = verified.get("device_family", "")
    arch = verified.get("device_arch", "")
    weight = _lookup_hardware_weight(weight_table, family, arch)
    units = to_weight_units(weight)
    return units if units > 0 else 0


def derive_block_enrollment(
    attestations: List[Mapping],
    derive_fn: Callable[[dict, dict, bool], dict],
    weight_table: Mapping,
) -> Dict[str, int]:
    """Deterministically map committed block attestations -> {miner: weight_units}.

    PURE and fully order-independent. Results are keyed by miner; duplicate
    attestations for one miner are resolved by a TOTAL ordering — (miner id,
    committed timestamp ascending, content digest) — and the last in that order
    wins, so every node resolves duplicates (including same-timestamp ones)
    identically. Non-Mapping items and miner-less records are skipped.
    """
    # miner ID must be a non-empty STRING — accepting truthy non-strings and
    # str()-coercing would collide distinct identities (e.g. 1 vs "1").
    valid = [
        a for a in attestations
        if isinstance(a, Mapping)
        and isinstance(a.get("miner"), str)
        and a.get("miner")
    ]
    # Total order: miner, then timestamp asc, then a deterministic content
    # digest so same-(miner,timestamp) attestations cannot resolve by input
    # order (which would diverge snapshot_hash across nodes -> fork).
    ordered = sorted(
        valid,
        key=lambda a: (
            str(a.get("miner")),
            _safe_int(a.get("timestamp"), 0),
            _attestation_tiebreak(a),
        ),
    )
    enrollment: Dict[str, int] = {}
    for att in ordered:
        miner = att["miner"]  # guaranteed non-empty str by the filter above
        # Per-attestation containment: a single attestation that makes the
        # injected derive_fn raise must NOT abort the whole block's enrollment.
        # On any error, exclude that miner (weight 0) and continue — fail closed.
        try:
            enrollment[miner] = attestation_weight_units(att, derive_fn, weight_table)
        except Exception:
            enrollment[miner] = 0
    return enrollment


def eligible_miners(
    enrollment: Mapping[str, int],
    threshold_units: int = DEFAULT_ELIGIBILITY_THRESHOLD_UNITS,
) -> List[str]:
    """Sorted list of producer-eligible miners (weight >= threshold).

    Weights are coerced to int units (the module contract) so a stray float
    cannot be counted eligible at one value but hashed at another.
    """
    _validate_threshold(threshold_units)
    return sorted(m for m, w in enrollment.items() if _safe_int(w, 0) >= threshold_units)


def enrollment_snapshot_hash(
    enrollment: Mapping[str, int],
    threshold_units: int = DEFAULT_ELIGIBILITY_THRESHOLD_UNITS,
) -> str:
    """Deterministic SHA-256 over the eligible (miner, weight_units) set.

    Integer units + sorted canonical JSON => identical on every node/arch.
    Excluded miners (weight < threshold) are omitted so the hash reflects the
    eligible set the consensus rule actually uses.
    """
    _validate_threshold(threshold_units)
    eligible = [
        [m, _safe_int(enrollment[m], 0)]
        for m in sorted(enrollment)
        if _safe_int(enrollment[m], 0) >= threshold_units
    ]
    # Embed the threshold so a sealed hash is unambiguous if policy ever changes.
    canonical = {"threshold_units": threshold_units, "eligible": eligible}
    blob = json.dumps(canonical, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- Epoch enrollment sealing (B3 core; INV-2/INV-3) ------------------------

EPOCH_ENROLL_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS epoch_enroll_state (
    epoch          INTEGER PRIMARY KEY,
    finalized      INTEGER NOT NULL DEFAULT 0,
    snapshot_hash  TEXT,
    finalized_at   INTEGER
)
"""


def ensure_epoch_enroll_state_schema(conn: sqlite3.Connection) -> None:
    """Create the epoch_enroll_state table if absent.

    Call this ONCE at node/DB init (migration), NOT inside a consensus tx —
    SQLite DDL can implicit-commit and would break a caller's transaction
    atomicity. ``seal_epoch_enrollment`` assumes the table already exists.
    """
    conn.execute(EPOCH_ENROLL_STATE_SCHEMA)


def is_epoch_finalized(conn: sqlite3.Connection, epoch: int) -> bool:
    """True iff epoch ``epoch``'s enrollment snapshot is sealed (finalized == 1).

    Absent table/row/column -> False (not finalized). Never raises into a
    consensus hot path: a transient/missing-state read is treated as not sealed.
    """
    try:
        row = conn.execute(
            "SELECT finalized FROM epoch_enroll_state WHERE epoch = ?",
            (epoch,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if row is None:
        return False
    try:
        return row[0] == 1
    except (KeyError, IndexError, TypeError):
        return False


def seal_epoch_enrollment(
    conn: sqlite3.Connection,
    epoch: int,
    enrollment: Mapping[str, int],
    finalized_at: int,
    threshold_units: int = DEFAULT_ELIGIBILITY_THRESHOLD_UNITS,
) -> bool:
    """Seal epoch ``epoch``'s enrollment snapshot. Returns True iff sealed.

    INV-2: NEVER seal an empty / all-excluded snapshot — a finalized snapshot
    must contain at least one eligible producer, so the fail-closed gate can
    never strand the chain without a producer. Returns False (does not seal)
    when no miner clears the threshold.

    ``finalized_at`` MUST be a deterministic, chain-derived value (e.g. the
    sealing block height/slot) — NOT node-local wall-clock — or finalization
    would diverge across nodes (INV-1). The caller supplies it.

    A sealed epoch is IMMUTABLE: re-sealing an already-finalized (finalized==1)
    epoch is refused (returns False), so a later call cannot swap the snapshot.
    A pre-existing UNsealed row (finalized==0) IS upgraded to sealed (it would
    otherwise strand the epoch forever).

    The table must already exist (call ``ensure_epoch_enroll_state_schema`` at
    init). This writes within the caller's transaction; the CALLER must commit.
    ``True`` means "written in this tx", not yet durable until commit.
    """
    _validate_threshold(threshold_units)
    # epoch / finalized_at must be genuine ints (not bool/float/str): a float
    # epoch=1.9 must NOT silently seal epoch 1.
    epoch_i = _strict_int(epoch)
    finalized_at_i = _strict_int(finalized_at)
    if epoch_i is None or finalized_at_i is None or epoch_i < 0 or finalized_at_i < 0:
        return False  # malformed chain-derived inputs -> fail closed, do not seal

    eligible = eligible_miners(enrollment, threshold_units)
    if not eligible:
        return False  # INV-2: refuse to finalize an empty eligible set
    snapshot_hash = enrollment_snapshot_hash(enrollment, threshold_units)

    # Atomic, TOCTOU-free seal (no separate finalized SELECT to race against):
    #   * pre-existing finalized==0 row -> the conditional UPDATE upgrades it
    #   * no row                        -> the INSERT OR IGNORE creates it
    #   * already finalized==1          -> UPDATE no-ops (WHERE finalized=0) AND
    #     INSERT OR IGNORE no-ops (PK conflict) -> returns False (IMMUTABLE)
    try:
        upd = conn.execute(
            "UPDATE epoch_enroll_state SET finalized=1, snapshot_hash=?, finalized_at=? "
            "WHERE epoch=? AND finalized=0",
            (snapshot_hash, finalized_at_i, epoch_i),
        )
        if upd.rowcount == 1:
            return True
        ins = conn.execute(
            "INSERT OR IGNORE INTO epoch_enroll_state "
            "(epoch, finalized, snapshot_hash, finalized_at) VALUES (?, 1, ?, ?)",
            (epoch_i, snapshot_hash, finalized_at_i),
        )
        return ins.rowcount == 1
    except sqlite3.OperationalError:
        # Table missing/locked: not sealed. Caller must run
        # ensure_epoch_enroll_state_schema() at init. Fail closed, don't crash.
        return False
