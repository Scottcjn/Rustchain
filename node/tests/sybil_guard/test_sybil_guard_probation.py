# SPDX-License-Identifier: MIT
"""sybil_guard probation state machine, driven by the (synthetic) incident fixtures.

Pure module + in-memory SQLite: no node import, no network. Time is simulated
by passing `now` explicitly.
"""
import collections
import json
import random
import sqlite3

import pytest

import sg_helpers  # noqa: F401  (node/ on sys.path)
import sybil_guard as sg

T0 = sg.GRANDFATHER_CUTOFF_TS + 7 * 86400  # a week after the cutoff
HOUR = 3600


def _db():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.executescript(
        """
        CREATE TABLE miner_attest_history (id INTEGER PRIMARY KEY AUTOINCREMENT, miner TEXT,
            ts_ok INTEGER, device_family TEXT, device_arch TEXT, entropy_score REAL,
            fingerprint_passed INTEGER, fingerprint_checks_json TEXT);
        CREATE TABLE miner_fingerprint_history (id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner TEXT NOT NULL, ts INTEGER NOT NULL, profile_json TEXT NOT NULL);
        """
    )
    sg.init_schema(conn)
    return conn


def _attest(conn, miner, profile, ip, now, **kw):
    """Mimic record_attestation_success (history + snapshot, keep last 10) then observe."""
    conn.execute("INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES (?, ?, 1)",
                 (miner, now))
    conn.execute("INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
                 (miner, now, json.dumps(sg.normalize_profile(profile))))
    conn.execute(
        "DELETE FROM miner_fingerprint_history WHERE miner = ? AND id NOT IN "
        "(SELECT id FROM miner_fingerprint_history WHERE miner = ? ORDER BY ts DESC, id DESC LIMIT 10)",
        (miner, miner))
    return sg.observe_attestation(conn, miner, profile, ip, now=now, **kw)


def _profiles(rows):
    by = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: r["ts"]):
        by[r["miner"]].append(json.loads(r["profile_json"]))
    return by


def _unique_ip(i):
    return f"198.{18 + (i // 65536) % 2}.{(i // 256) % 256}.{i % 256}"


# --------------------------------------------------------------------------
# Flagged wallets
# --------------------------------------------------------------------------

def test_every_sybil_wallet_replayed_for_72h_never_exits(sybil_rows):
    """Each of the 120 wallets re-sends its recorded profile every 30 min for
    72 h from its own unique IP (i.e. even without the IP caps)."""
    conn = _db()
    by = _profiles(sybil_rows)
    assert len(by) == 120
    for i, (miner, profiles) in enumerate(by.items()):
        st = None
        for k in range(144):
            st = _attest(conn, miner, profiles[k % len(profiles)], _unique_ip(i), T0 + k * 1800)
            assert st["state"] != sg.STATE_TRUSTED
            assert sg.enrollment_weight(2.5, st) <= sg.PROBATION_WEIGHT_CAP
        assert st["needs_review"] == 1
        assert sg.enrollment_weight(2.5, st) == 0.0
        assert sg.needs_review(st)


def test_sybil_wallets_from_recorded_ips_hit_admission_cap(sybil_rows):
    conn = _db()
    first = {}
    for r in sorted(sybil_rows, key=lambda r: r["ts"]):
        first.setdefault(r["miner"], r)
    states = collections.Counter()
    for miner, r in first.items():
        st = _attest(conn, miner, json.loads(r["profile_json"]), r["source_ip"], r["ts"] + 30 * 86400)
        states[st["state"]] += 1
    # 3 source IPs x NEW_MINERS_PER_IP_PER_DAY admitted; everyone else queued.
    assert states[sg.STATE_PROBATION] == 3 * sg.NEW_MINERS_PER_IP_PER_DAY
    assert states[sg.STATE_ADMISSION_QUEUED] == 120 - 3 * sg.NEW_MINERS_PER_IP_PER_DAY
    assert states[sg.STATE_TRUSTED] == 0


def test_redrawing_generator_never_exits():
    """Smarter attacker: redraw round(uniform, 4) inside the box every time."""
    conn = _db()
    rng = random.Random(11)
    for i in range(20):
        miner, st = f"RTCredraw{i:02d}", None
        for k in range(144):
            prof = {m: round(rng.uniform(lo, hi), 4) for m, (lo, hi) in sg.INCIDENT_20260924_BOX.items()}
            st = _attest(conn, miner, prof, _unique_ip(1000 + i), T0 + k * 1800)
            assert st["state"] != sg.STATE_TRUSTED
        assert st["needs_review"] == 1


def test_known_limit_full_precision_random_walk_can_graduate():
    """Honesty test: a generator that emits full-precision values inside honest
    ranges and drifts slowly DOES graduate. Probation is a cost, not a proof."""
    conn = _db()
    rng = random.Random(3)
    prof = {"clock_drift_cv": 0.0731234, "thermal_variance": 0.98, "jitter_cv": 0.0412345678901,
            "cache_hierarchy_ratio": 1.013}
    st = None
    for k in range(60):
        prof = {m: v * (1 + rng.uniform(-0.03, 0.03)) for m, v in prof.items()}
        st = _attest(conn, "RTCcarefulforger", prof, "203.0.113.9", T0 + k * 1800)
    assert st["state"] == sg.STATE_TRUSTED


# --------------------------------------------------------------------------
# Honest miners
# --------------------------------------------------------------------------

def test_honest_varying_miners_graduate_as_new_miners(honest_rows):
    """Replay each honest miner's real sequence as if it were NEW: cycled every
    20 min for 30 h from its own IP. Miners whose client varies must graduate."""
    by = _profiles(honest_rows)
    graduated, stuck = [], []
    for i, (miner, profiles) in enumerate(by.items()):
        distinct = {json.dumps(p, sort_keys=True) for p in profiles}
        if len(distinct) < 4:
            # static series are covered by the next test; 2-3 distinct samples
            # are too few to replay for 30 h without inventing A-B-A-B jumps.
            continue
        conn = _db()
        st = None
        for k in range(90):
            st = _attest(conn, miner, profiles[k % len(profiles)], _unique_ip(5000 + i), T0 + k * 1200)
        (graduated if st["state"] == sg.STATE_TRUSTED else stuck).append((miner, st["blockers"]))
    print(f"\nhonest varying miners graduated: {len(graduated)}/{len(graduated) + len(stuck)}; stuck={stuck}")
    assert graduated, "no honest miner could graduate"
    # Cycling a short real sequence creates artificial jumps at the wrap point,
    # so allow at most one miner to be held by the redraw test for that reason.
    assert len(stuck) <= 1, stuck
    for _, blockers in stuck:
        assert all(b.startswith("memoryless_redraw") for b in blockers), blockers


def test_static_honest_miner_as_new_stays_at_baseline_but_keeps_mining():
    conn = _db()
    lab_g4 = {"clock_drift_cv": 0.0123, "thermal_variance": 0.0, "jitter_cv": 0.0,
              "cache_hierarchy_ratio": 2.0}
    st = None
    for k in range(100):
        st = _attest(conn, "brand-new-static-g4", lab_g4, "192.0.2.10", T0 + k * 1800)
    assert st["state"] == sg.STATE_PROBATION
    assert st["needs_review"] == 0 and not st["anomalies"]
    assert sg.enrollment_weight(2.5, st) == 1.0   # baseline, never 0


def _seed_history(conn, miner, start, n, step):
    for k in range(n):
        conn.execute("INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES (?, ?, 1)",
                     (miner, start + k * step))


def test_established_lab_g4_with_constant_profile_is_grandfathered():
    conn = _db()
    _seed_history(conn, "lab-g4-example", sg.GRANDFATHER_CUTOFF_TS - 30 * 86400, 200, 3 * HOUR)
    lab_g4 = {"clock_drift_cv": 0.0123, "thermal_variance": 0.0, "jitter_cv": 0.0,
              "cache_hierarchy_ratio": 2.0}
    for k in range(20):
        st = _attest(conn, "lab-g4-example", lab_g4, "192.0.2.125", T0 + k * 1800)
        assert st["state"] == sg.STATE_GRANDFATHERED
        assert sg.enrollment_weight(2.5, st) == 2.5
        assert sg.enrollment_weight(1.3, st) == 1.3


def test_grandfathered_miner_IS_held_when_incident_detector_fires():
    """Round 2: grandfathering keeps today's behaviour EXCEPT for the detector."""
    conn = _db()
    _seed_history(conn, "old-miner", sg.GRANDFATHER_CUTOFF_TS - 10 * 86400, 50, 4 * HOUR)
    st = _attest(conn, "old-miner", {"clock_drift_cv": 0.02, "thermal_variance": 3.1234,
                                     "jitter_cv": 0.1, "cache_hierarchy_ratio": 2.5},
                 "192.0.2.1", T0)
    # Round 2b: ONE matching sample is not enough for an established miner.
    assert st["state"] == sg.STATE_GRANDFATHERED and not sg.needs_review(st)
    assert sg.enrollment_weight(2.5, st) == 2.5
    st = _attest(conn, "old-miner", {"clock_drift_cv": 0.021, "thermal_variance": 3.1235,
                                     "jitter_cv": 0.1, "cache_hierarchy_ratio": 2.5},
                 "192.0.2.1", T0 + 600)
    assert st["state"] == sg.STATE_GRANDFATHERED
    assert sg.needs_review(st) and st["review_reason"] == sg.REVIEW_STORED
    assert sg.enrollment_weight(2.5, st) == 0.0
    assert sg.review_held_miners(conn, ["old-miner"]) == {"old-miner"}


def test_grandfathered_honest_profile_keeps_weight():
    conn = _db()
    _seed_history(conn, "old-honest", sg.GRANDFATHER_CUTOFF_TS - 10 * 86400, 1, HOUR)
    st = _attest(conn, "old-honest", {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862,
                                      "jitter_cv": 0.0, "cache_hierarchy_ratio": 2.34914},
                 "192.0.2.1", T0)
    assert st["state"] == sg.STATE_GRANDFATHERED and not sg.needs_review(st)
    assert sg.enrollment_weight(2.5, st) == 2.5


def test_any_pre_cutoff_attestation_grandfathers():
    """Round 2 decision: one attestation before the cutoff is enough (the
    9/13-14 recon probes are therefore grandfathered; the detector/cohort still
    holds them if they match)."""
    conn = _db()
    _seed_history(conn, "recon-probe-003", sg.GRANDFATHER_CUTOFF_TS - 11 * 86400, 1, HOUR)
    st = _attest(conn, "recon-probe-003", {"clock_drift_cv": 0.0123}, "198.51.100.77", T0)
    assert st["state"] == sg.STATE_GRANDFATHERED
    assert sg.has_pre_cutoff_history(conn, "recon-probe-003")


def test_attestation_after_cutoff_does_not_grandfather():
    conn = _db()
    _seed_history(conn, "late", sg.GRANDFATHER_CUTOFF_TS + 60, 50, 60)
    assert not sg.has_pre_cutoff_history(conn, "late")


# --------------------------------------------------------------------------
# Population caps
# --------------------------------------------------------------------------

def _varying(k, base=1.0):
    return {"clock_drift_cv": 0.05 + 0.001 * (k % 7) + 0.0000013 * k,
            "thermal_variance": base + 0.01 * (k % 5) + 0.0000017 * k,
            "jitter_cv": 0.041234567890123 + 0.0001 * (k % 3),
            "cache_hierarchy_ratio": 1.001 + 0.001 * (k % 4)}


def test_admission_cap_queues_third_new_miner_then_admits_next_day():
    conn = _db()
    s = [_attest(conn, f"m{i}", _varying(0), "192.0.2.50", T0 + i) for i in range(3)]
    assert [x["state"] for x in s] == [sg.STATE_PROBATION, sg.STATE_PROBATION, sg.STATE_ADMISSION_QUEUED]
    # re-attestations of the admitted two are unaffected
    assert _attest(conn, "m0", _varying(1), "192.0.2.50", T0 + 600)["state"] == sg.STATE_PROBATION
    assert _attest(conn, "m2", _varying(1), "192.0.2.50", T0 + 3600)["state"] == sg.STATE_ADMISSION_QUEUED
    assert _attest(conn, "m2", _varying(2), "192.0.2.50", T0 + 86400 + 10)["state"] == sg.STATE_PROBATION
    # a different /32 in the same /24 is admitted independently
    assert _attest(conn, "m3", _varying(0), "192.0.2.51", T0 + 5)["state"] == sg.STATE_PROBATION


def test_exit_cap_per_slash24_queues_excess_then_releases():
    conn = _db()
    miners = [f"lab{i}" for i in range(3)]
    for k in range(60):  # 3 miners, distinct /32s, same /24, all eligible at the same time
        for i, m in enumerate(miners):
            _attest(conn, m, _varying(k, base=0.5 + i), f"192.0.2.{60 + i}", T0 + k * 1800 + i)
    states = collections.Counter(sg.get_probation_status(conn, m)["state"] for m in miners)
    assert states[sg.STATE_TRUSTED] == 3  # queued one released an hour later
    rows = conn.execute("SELECT miner, exited_at FROM miner_probation ORDER BY exited_at").fetchall()
    assert rows[2][1] - rows[0][1] >= 3600, rows


def test_exit_cap_blocks_same_hour():
    conn = _db()
    miners = [f"q{i}" for i in range(3)]
    last = {}
    for k in range(49):
        for i, m in enumerate(miners):
            last[m] = _attest(conn, m, _varying(k, base=0.5 + i), f"192.0.2.{70 + i}", T0 + k * 1800 + i)
    got = collections.Counter(s["state"] for s in last.values())
    assert got[sg.STATE_QUEUED] == 1 and got[sg.STATE_TRUSTED] == 2, got


def test_correlated_cluster_blocks_exit():
    conn = _db()
    calls = []

    def fake_cluster(c, members):
        calls.append(list(members))
        return {"state": "correlated", "spread": 0.1}

    st = None
    for k in range(60):
        st = _attest(conn, "clustered", _varying(k), "192.0.2.90", T0 + k * 1800, cluster_check=fake_cluster)
    assert st["state"] == sg.STATE_PROBATION
    assert any(b.startswith("cluster_correlated") for b in st["blockers"])
    assert calls


# --------------------------------------------------------------------------
# Weight rules, anomaly extension, binding
# --------------------------------------------------------------------------

def test_anomaly_extends_probation():
    conn = _db()
    for k in range(50):
        st = _attest(conn, "hot", _varying(k), "192.0.2.100", T0 + k * 1800)
    assert st["state"] == sg.STATE_TRUSTED
    conn2 = _db()
    for k in range(50):
        prof = _varying(k)
        if k == 45:
            prof = dict(prof, thermal_variance=4.2)  # out of honest range once
        st = _attest(conn2, "hot", prof, "192.0.2.100", T0 + k * 1800)
    assert st["state"] == sg.STATE_PROBATION
    assert any(b.startswith("anomaly_extension_until") for b in st["blockers"])
    assert st["needs_review"] == 0  # extension only, not a hold


def test_failed_fingerprint_attestations_do_not_count():
    conn = _db()
    for k in range(60):
        st = _attest(conn, "vm", _varying(k), "192.0.2.110", T0 + k * 1800, fingerprint_passed=False)
    assert st["state"] == sg.STATE_PROBATION and st["attest_count"] == 0


@pytest.mark.parametrize("status,weight,expected", [
    ({"state": sg.STATE_PROBATION}, 2.5, 1.0),
    ({"state": sg.STATE_PROBATION}, 0.8, 0.8),
    ({"state": sg.STATE_PROBATION}, 0.0005, 0.0005),
    ({"state": sg.STATE_ADMISSION_QUEUED}, 4.0, 0.0),
    ({"state": sg.STATE_ADMISSION_QUEUED}, 0.8, 0.0),
    ({"state": sg.STATE_UNAVAILABLE, "established": True}, 2.5, 2.5),
    ({"state": sg.STATE_UNAVAILABLE, "established": False}, 2.5, 1.0),
    ({"state": sg.STATE_UNAVAILABLE}, 2.5, 1.0),
    (None, 2.5, 1.0),
    ({"state": sg.STATE_PROBATION, "needs_review": 1}, 2.5, 0.0),
    ({"state": sg.STATE_GRANDFATHERED, "needs_review": 1}, 2.5, 0.0),
    ({"state": sg.STATE_GRANDFATHERED}, 2.5, 2.5),
    # REQUIRE_MEASUREMENT_BINDING_FOR_NEW_PREMIUM defaults to False (Scott, 2026-09-24):
    # probation alone gates the premium, so a graduated miner keeps it without a binding.
    ({"state": sg.STATE_TRUSTED, "reason": "probation_exit", "last_binding_state": "absent"}, 2.5, 2.5),
    ({"state": sg.STATE_TRUSTED, "reason": "probation_exit", "last_binding_state": "bound"}, 2.5, 2.5),
    ({"state": sg.STATE_TRUSTED, "reason": "operator_allowlist", "last_binding_state": None}, 2.5, 2.5),
])
def test_enrollment_weight_table(status, weight, expected):
    assert sg.enrollment_weight(weight, status) == expected


def test_binding_requirement_when_enabled(monkeypatch):
    """With the flag on, a graduated miner needs a 'bound' measurement for premium."""
    monkeypatch.setattr(sg, "REQUIRE_MEASUREMENT_BINDING_FOR_NEW_PREMIUM", True)
    absent = {"state": sg.STATE_TRUSTED, "reason": "probation_exit", "last_binding_state": "absent"}
    bound = {"state": sg.STATE_TRUSTED, "reason": "probation_exit", "last_binding_state": "bound"}
    allow = {"state": sg.STATE_TRUSTED, "reason": "operator_allowlist", "last_binding_state": None}
    assert sg.enrollment_weight(2.5, absent) == 1.0
    assert sg.enrollment_weight(2.5, bound) == 2.5
    assert sg.enrollment_weight(2.5, allow) == 2.5


def test_allowlist_env(monkeypatch):
    monkeypatch.setenv(sg.PROBATION_ALLOWLIST_ENV, "new-lab-g4, other")
    conn = _db()
    st = _attest(conn, "new-lab-g4", {"clock_drift_cv": 0.0123}, "192.0.2.99", T0)
    assert st["state"] == sg.STATE_TRUSTED and st["reason"] == "operator_allowlist"


def test_review_held_miners_and_escrow():
    conn = _db()
    _attest(conn, "bad", {"clock_drift_cv": 0.02, "thermal_variance": 3.1234, "jitter_cv": 0.1,
                          "cache_hierarchy_ratio": 2.5}, "192.0.2.120", T0)
    _attest(conn, "good", _varying(0), "192.0.2.121", T0)
    assert sg.review_held_miners(conn, ["bad", "good", "unknown"]) == {"bad"}
    sg.record_review_escrow(conn, 297, "bad", 1_000_000_000, "t", now=T0)
    sg.record_review_escrow(conn, 297, "bad", 5, "t2", now=T0)  # first wins
    assert conn.execute("SELECT would_be_weight_units FROM sybil_review_escrow").fetchall() == [(1_000_000_000,)]
    assert sg.review_held_miners(_db(), ["bad"]) == set()  # no table -> nothing held


# --------------------------------------------------------------------------
# Round 2
# --------------------------------------------------------------------------

INCIDENT = {"clock_drift_cv": 0.02, "thermal_variance": 3.1234, "jitter_cv": 0.1, "cache_hierarchy_ratio": 2.5}


def test_needs_review_seeded_from_stored_history():
    """Grok: a Sybil that stops sending the box must still be held. Its STORED
    fingerprint history (pre-deploy rows) seeds the sticky flag."""
    conn = _db()
    conn.execute("INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
                 ("RTCsyb", T0 - 86400, json.dumps(INCIDENT)))
    st = _attest(conn, "RTCsyb", _varying(0), "198.51.100.7", T0)
    assert st["needs_review"] == 1 and st["review_reason"] == sg.REVIEW_STORED
    assert sg.enrollment_weight(2.5, st) == 0.0


def test_needs_review_seeded_from_cohort_table_any_id_column():
    for col in ("miner", "miner_id", "wallet"):
        conn = _db()
        conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} ({col} TEXT, source_ip TEXT)")
        conn.execute(f"INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES ('RTCc', '203.0.113.10')")
        st = _attest(conn, "RTCc", _varying(0), "198.51.100.8", T0)
        assert st["review_reason"] == sg.REVIEW_COHORT, col
        # read-only status used by /epoch/enroll for a miner with no row yet
        assert sg.get_probation_status(conn, "RTCc")["needs_review"] == 1


def test_cohort_table_absent_or_unrecognised_is_fail_safe():
    conn = _db()
    assert sg.stored_review_reason(conn, "x") is None
    conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (foo TEXT)")
    assert sg.stored_review_reason(conn, "x") is None


def test_get_probation_status_for_unseen_miner_uses_stored_data():
    conn = _db()
    conn.execute("INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES ('u', 1, ?)",
                 (json.dumps(INCIDENT),))
    st = sg.get_probation_status(conn, "u")
    assert st["state"] == sg.STATE_PROBATION and sg.needs_review(st)


def test_varied_metrics_judged_over_whole_window():
    """Grok: a last sample of clock-only must not drop the 2-metric requirement,
    and a metric must move at least METRIC_MIN_MOVES times."""
    conn = _db()
    st = None
    for k in range(60):
        prof = {"clock_drift_cv": 0.05 + 0.001 * (k % 7), "thermal_variance": 1.0,
                "jitter_cv": 0.041234567, "cache_hierarchy_ratio": 1.001}
        if k >= 30:  # a single step in thermal (one move), then constant
            prof["thermal_variance"] = 1.0001
        if k >= 55:  # final samples report clock only
            prof = {"clock_drift_cv": prof["clock_drift_cv"]}
        st = _attest(conn, "wiggle", prof, "198.51.100.9", T0 + k * 1800)
    assert st["state"] == sg.STATE_PROBATION
    assert any(b.startswith("varied_metrics:1/2") for b in st["blockers"]), st["blockers"]


def test_exit_cap_charged_to_admission_prefix():
    """Grok: leaving from another /24 must not dodge the admission /24's cap."""
    conn = _db()
    for i in range(2):  # fill 192.0.2.0/24's exit cap
        for k in range(49):
            _attest(conn, f"a{i}", _varying(k, base=0.5 + i), f"192.0.2.{10 + i}", T0 + k * 1800 + i)
    last = None
    for k in range(49):  # admitted in 192.0.2.0/24, later attests from 203.0.113.0/24
        ip = "192.0.2.30" if k == 0 else "203.0.113.30"
        last = _attest(conn, "mover", _varying(k, base=2.2), ip, T0 + k * 1800 + 5)
    assert last["state"] == sg.STATE_QUEUED
    assert any("192.0.2.0/24" in b for b in last["blockers"])


def test_observe_does_no_ddl_and_raises_without_tables():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    stmts = []
    conn.set_trace_callback(stmts.append)
    with pytest.raises(sqlite3.OperationalError):
        sg.observe_attestation(conn, "m", _varying(0), "192.0.2.1", now=T0)
    assert not [s for s in stmts if s.lstrip().upper().startswith(("CREATE", "ALTER", "DROP"))]


def test_init_schema_rejects_incompatible_table():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE miner_probation (miner TEXT PRIMARY KEY)")
    with pytest.raises(sg.SchemaError):
        sg.init_schema(conn)


def test_fallback_status_and_defer():
    conn = _db()
    _seed_history(conn, "old", sg.GRANDFATHER_CUTOFF_TS - 86400, 1, HOUR)
    old = sg.fallback_status(conn, "old")
    new = sg.fallback_status(conn, "new")
    unreachable = sg.fallback_status(None, "x")
    assert old["established"] is True and sg.enrollment_weight(2.5, old) == 2.5
    assert new["established"] is False and sg.enrollment_weight(2.5, new) == 1.0
    assert sg.should_defer_enrollment(unreachable)          # only a dead DB defers
    assert not sg.should_defer_enrollment(old) and not sg.should_defer_enrollment(new)


def test_history_query_failure_falls_back_to_live_not_defer():
    """GLM: a missing ts_ok column must not 503 every miner. It raises
    SchemaError in the normal path, and fallback_status then uses LIVE weight."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE miner_attest_history (id INTEGER PRIMARY KEY, miner TEXT, ts INTEGER)")
    with pytest.raises(sg.SchemaError):
        sg.has_pre_cutoff_history(conn, "m")
    st = sg.fallback_status(conn, "m")
    assert st["established"] is None and not sg.should_defer_enrollment(st)
    assert sg.enrollment_weight(2.5, st) == 2.5


def test_single_stored_match_does_not_flag_grandfathered_but_cohort_does():
    conn = _db()
    _seed_history(conn, "gf", sg.GRANDFATHER_CUTOFF_TS - 86400, 1, HOUR)
    conn.execute("INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES ('gf', 1, ?)",
                 (json.dumps(INCIDENT),))
    assert sg.stored_review_reason(conn, "gf", grandfathered=True) is None
    assert sg.stored_review_reason(conn, "gf", grandfathered=False) == sg.REVIEW_STORED
    st = _attest(conn, "gf", _varying(0), "192.0.2.3", T0)
    assert st["state"] == sg.STATE_GRANDFATHERED and not sg.needs_review(st)
    conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT)")
    conn.execute(f"INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES ('gf2')")
    _seed_history(conn, "gf2", sg.GRANDFATHER_CUTOFF_TS - 86400, 1, HOUR)
    st2 = _attest(conn, "gf2", _varying(0), "192.0.2.4", T0)
    assert st2["state"] == sg.STATE_GRANDFATHERED and st2["review_reason"] == sg.REVIEW_COHORT


def test_grandfathered_flag_logs_critical(caplog):
    conn = _db()
    conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT)")
    conn.execute(f"INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES ('gf3')")
    _seed_history(conn, "gf3", sg.GRANDFATHER_CUTOFF_TS - 86400, 1, HOUR)
    with caplog.at_level("CRITICAL", logger="sybil_guard"):
        _attest(conn, "gf3", _varying(0), "192.0.2.5", T0)
    assert any("GRANDFATHERED miner gf3 put in needs_review" in r.getMessage() for r in caplog.records)



def test_exit_cap_charged_to_current_prefix_too():
    """Round 3: three miners admitted from three different /24s, graduating
    through ONE shared current /24 within an hour -> the third queues."""
    conn = _db()
    shared = "203.0.113.{}"
    last = {}
    for i, adm_ip in enumerate(("192.0.2.10", "198.51.100.10", "100.64.7.10")):
        for k in range(49):
            ip = adm_ip if k == 0 else shared.format(20 + i)
            last[i] = _attest(conn, f"x{i}", _varying(k, base=0.5 + i), ip, T0 + k * 1800 + i)
    states = [last[i]["state"] for i in range(3)]
    assert states.count(sg.STATE_TRUSTED) == 2 and states.count(sg.STATE_QUEUED) == 1, states
    q = [last[i] for i in range(3) if last[i]["state"] == sg.STATE_QUEUED][0]
    assert any("203.0.113.0/24" in b for b in q["blockers"])
    rows = conn.execute("SELECT exit_prefix, exit_current_prefix FROM miner_probation "
                        "WHERE exited_at IS NOT NULL").fetchall()
    assert all(cur == "203.0.113.0/24" for _, cur in rows)


def test_exit_cap_counts_identical_prefixes_once():
    """Admission /24 == current /24: one exit counts once (not twice)."""
    conn = _db()
    last = {}
    for i in range(2):
        for k in range(49):
            last[i] = _attest(conn, f"s{i}", _varying(k, base=0.5 + i), f"192.0.2.{40 + i}", T0 + k * 1800 + i)
    assert last[0]["state"] == sg.STATE_TRUSTED and last[1]["state"] == sg.STATE_TRUSTED


def test_exit_cap_ipv6_48_both_prefixes():
    conn = _db()
    last = {}
    for i, adm in enumerate(("2001:db8:1::5", "2001:db8:2::5", "2001:db8:3::5")):
        for k in range(49):
            ip = adm if k == 0 else f"2001:db8:ff::{i + 1}"
            last[i] = _attest(conn, f"v6{i}", _varying(k, base=0.5 + i), ip, T0 + k * 1800 + i)
    states = [last[i]["state"] for i in range(3)]
    assert states.count(sg.STATE_QUEUED) == 1, states


def test_init_schema_on_empty_db_has_new_column():
    conn = sqlite3.connect(":memory:")
    sg.init_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(miner_probation)")}
    assert "exit_current_prefix" in cols and not sg.verify_schema(conn)


# --------------------------------------------------------------------------
# Round 3b: cohort table absent / malformed / unreadable
# --------------------------------------------------------------------------

def _trusted_row(conn, miner, state=sg.STATE_TRUSTED):
    conn.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, updated_at) "
                 "VALUES (?, ?, 1, 1, 1)", (miner, state))


def test_bonus_eligible_when_cohort_table_absent():
    conn = _db()
    _trusted_row(conn, "t")
    assert sg.bonus_eligibility_in_txn(conn, "t") == (True, sg.STATE_TRUSTED, "ok")


def test_bonus_withheld_when_cohort_table_malformed(caplog):
    conn = _db()
    _trusted_row(conn, "t")
    conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (wallet_x TEXT)")
    with caplog.at_level("CRITICAL", logger="sybil_guard"):
        ok, _, why = sg.bonus_eligibility_in_txn(conn, "t")
    assert ok is False and why.startswith("cohort_undeterminable")
    assert any("WITHHELD" in r.getMessage() for r in caplog.records)


def test_bonus_withheld_on_cohort_read_error(monkeypatch):
    conn = _db()
    _trusted_row(conn, "t")
    conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT)")
    real = sg._cohort_members

    def boom(c, miners, strict=False):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(sg, "_cohort_members", boom)
    ok, _, why = sg.bonus_eligibility_in_txn(conn, "t")
    assert ok is False and why.startswith("cohort_undeterminable")
    monkeypatch.setattr(sg, "_cohort_members", real)
    assert sg.bonus_eligibility_in_txn(conn, "t")[0] is True


def test_grandfathered_bonus_eligibility_unchanged_by_cohort_policy():
    conn = _db()
    _trusted_row(conn, "gf", state=sg.STATE_GRANDFATHERED)
    assert sg.bonus_eligibility_in_txn(conn, "gf") == (True, sg.STATE_GRANDFATHERED, "ok")
    conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT)")
    assert sg.bonus_eligibility_in_txn(conn, "gf")[0] is True
    conn.execute(f"INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES ('gf')")
    assert sg.bonus_eligibility_in_txn(conn, "gf") == (False, sg.STATE_GRANDFATHERED, "cohort_member")


@pytest.mark.parametrize("kind", ["malformed", "read_error"])
def test_settlement_keeps_probation_holds_when_cohort_undeterminable(kind, monkeypatch, caplog):
    conn = _db()
    conn.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, updated_at) "
                 "VALUES ('held', 'probation', 1, 1, 1, 1)")
    _trusted_row(conn, "ok")
    if kind == "malformed":
        conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (wallet_x TEXT)")
    else:
        conn.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT)")

        def boom(c, miners, strict=False):
            raise sqlite3.OperationalError("disk I/O error")
        monkeypatch.setattr(sg, "_cohort_members", boom)
    with caplog.at_level("CRITICAL", logger="sybil_guard"):
        held = sg.settlement_held_miners(conn, ["held", "ok"], epoch=297)
    assert held == {"held"}
    assert any(r.levelname == "CRITICAL" for r in caplog.records)


# --------------------------------------------------------------------------
# falsegreen fixes (2026-09-25): the cluster check and a missing metrics
# record must fail CLOSED (block graduation), never open.
# --------------------------------------------------------------------------

def _run_to_eligible(conn, miner, ip, cluster_check):
    st = None
    for k in range(60):
        st = _attest(conn, miner, _varying(k), ip, T0 + k * 1800, cluster_check=cluster_check)
    return st


def test_cluster_check_raising_blocks_exit(caplog):
    def boom(c, members):
        raise RuntimeError("clustering backend down")

    conn = _db()
    with caplog.at_level("ERROR", logger="sybil_guard"):
        st = _run_to_eligible(conn, "fg-raise", "192.0.2.91", boom)
    assert st["state"] == sg.STATE_PROBATION
    assert any(b.startswith("cluster_check_unavailable:RuntimeError") for b in st["blockers"])
    assert sg.enrollment_weight(2.5, st) <= sg.PROBATION_WEIGHT_CAP
    assert any("cluster_check failed" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("verdict", [{}, None])
def test_cluster_check_empty_verdict_blocks_exit(verdict):
    conn = _db()
    st = _run_to_eligible(conn, "fg-empty", "192.0.2.92", lambda c, m: verdict)
    assert st["state"] == sg.STATE_PROBATION
    assert "cluster_check_unavailable:empty_verdict" in st["blockers"]


def test_cluster_check_independent_verdict_still_allows_exit():
    conn = _db()
    st = _run_to_eligible(conn, "fg-ok", "192.0.2.93",
                          lambda c, m: {"state": "too_small_to_judge", "members": len(m)})
    assert st["state"] == sg.STATE_TRUSTED


@pytest.mark.parametrize("seen", [None, "absent"])
def test_missing_metrics_seen_requires_full_varied_metrics(seen):
    st = {"metric_moves": {"clock_drift_cv": 99}}
    if seen is None:
        st["metrics_seen"] = None
    assert sg.required_varied_metrics(st) == sg.PROBATION_MIN_VARIED_METRICS == 2
    assert len(sg.counted_varied_metrics(st)) < sg.required_varied_metrics(st)


def test_real_clock_only_metrics_seen_keeps_cobalt_qube_relaxation():
    st = {"metrics_seen": ["clock_drift_cv"], "metric_moves": {"clock_drift_cv": 99}}
    assert sg.required_varied_metrics(st) == 1
    assert sg.counted_varied_metrics(st) == ["clock_drift_cv"]


def test_missing_metric_moves_counts_none():
    assert sg.counted_varied_metrics({}) == []
    assert sg.counted_varied_metrics({"metric_moves": None}) == []


def test_null_metrics_seen_in_db_loads_as_missing_not_empty_list():
    conn = _db()
    _attest(conn, "fg-null", _varying(0), "192.0.2.94", T0)
    conn.execute("UPDATE miner_probation SET metrics_seen = 'garbage' WHERE miner = 'fg-null'")
    st = sg.get_probation_status(conn, "fg-null")
    assert st["metrics_seen"] is None
    assert sg.required_varied_metrics(st) == 2
