# SPDX-License-Identifier: MIT
"""End-to-end: the patched production node vs the unpatched live snapshot.

Each test gets a fresh SQLite file. The node module is loaded once per source
(patched / live) and re-pointed at the test DB. External-risk subsystems
(P2P, replay module, hardware binding, fleet immune, warthog) are stubbed, the
same way the upstream welcome-bonus tests do.
"""
import json
import sqlite3
import time

import pytest

from sg_helpers import NODE_DIR, baseline_dir, load_node

EPOCH = 296
SOURCE = "founder_community"
BONUS_I64 = 500_000


@pytest.fixture(scope="module")
def nodes(tmp_path_factory):
    d = tmp_path_factory.mktemp("load")
    out = {"patched": load_node(d / "p.db", "patched", NODE_DIR)}
    # "live" = main before this change (from git); comparisons are skipped
    # when it cannot be materialised (shallow checkout).
    if baseline_dir() is not None:
        out["live"] = load_node(d / "l.db", "live", baseline_dir())
    return out


def _configure(node, db_path):
    node.DB_PATH = str(db_path)
    node.UTXO_DUAL_WRITE = False
    node.HW_BINDING_V2 = False
    node.HW_PROOF_AVAILABLE = False
    node.HAVE_REPLAY_DEFENSE = False
    node.HAVE_FLEET_IMMUNE = False
    node.HAVE_WARTHOG = False
    node.check_ip_rate_limit = lambda client_ip, miner_id: (True, "ok")
    node._check_hardware_binding = lambda *a, **k: (True, "ok", "")
    node._check_oui_gate = lambda macs: (True, {"ok": True})
    node.wallet_review_gate_response = lambda miner: None
    node.record_macs = lambda *a, **k: None
    node.auto_induct_to_hall = lambda *a, **k: None
    node.current_slot = lambda: EPOCH * 144 + 5
    node.slot_to_epoch = lambda slot: EPOCH


def _prepare_db(node, db_path, nonces):
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        node.attest_ensure_tables(conn)
        for n in nonces:
            conn.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (n, now + 3600))
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT);
            CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER);
            CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER NOT NULL, miner_pk TEXT NOT NULL,
                weight INTEGER NOT NULL, PRIMARY KEY(epoch, miner_pk));
            CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, miner_pk TEXT,
                amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                epoch INTEGER, miner_id TEXT NOT NULL, delta_i64 INTEGER NOT NULL, reason TEXT);
            CREATE TABLE IF NOT EXISTS miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER,
                device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT, signing_pubkey TEXT,
                fingerprint_checks_json TEXT);
            CREATE TABLE IF NOT EXISTS miner_attest_history (id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL, ts_ok INTEGER NOT NULL, device_family TEXT, device_arch TEXT,
                entropy_score REAL DEFAULT 0.0, fingerprint_passed INTEGER DEFAULT 0,
                fingerprint_checks_json TEXT);
            """
        )
        conn.execute("INSERT OR IGNORE INTO epoch_state(epoch, settled) VALUES (?, 0)", (EPOCH,))
        conn.commit()
        if hasattr(node, "sybil_guard"):  # patched node: startup-only schema
            node.sybil_guard.init_schema(conn)
        conn.execute("INSERT INTO balances(miner_id, miner_pk, amount_i64, balance_rtc) VALUES (?, ?, ?, ?)",
                     (SOURCE, SOURCE, 100 * BONUS_I64, 50.0))
        conn.commit()


def _g4_payload(miner, nonce, profile, arch="g4", cpu="PowerPC G4 7447A"):
    """Shape of the incident payload: self-reported G4 evidence."""
    return {
        "miner": miner, "miner_id": miner, "nonce": nonce,
        "device": {"family": "PowerPC", "arch": arch, "cpu": cpu, "model": "PowerMac3,6", "cores": 1},
        "signals": {"hostname": "powermac"},
        "report": {"nonce": nonce, "commitment": "c"},
        "fingerprint": {
            "all_passed": True,
            "checks": {
                "anti_emulation": {"passed": True, "data": {"vm_indicators": [], "is_likely_vm": False}},
                "clock_drift": {"passed": True, "data": {"cv": profile["clock_drift_cv"], "samples": 500}},
                "simd_identity": {"passed": True, "data": {"has_altivec": True, "has_sse": False,
                                                           "has_avx": False, "x86_features": []}},
                "cache_timing": {"passed": True, "data": {"l2_l1_ratio": profile["cache_hierarchy_ratio"]}},
                "thermal_drift": {"passed": True, "data": {"drift_ratio": profile["thermal_variance"]}},
                "instruction_jitter": {"passed": True, "data": {"cv": profile["jitter_cv"]}},
            },
        },
    }


def _enrolled_weight(node, db, miner):
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (EPOCH, miner)).fetchone()
    return None if row is None else node.epoch_weight_units_to_display(row[0])


def _bonus_rows(db, miner):
    with sqlite3.connect(db) as c:
        return c.execute("SELECT COUNT(*) FROM ledger WHERE miner_id=? AND delta_i64>0 AND "
                         "reason LIKE 'welcome_bonus:%'", (miner,)).fetchone()[0]


def _attest(node, db, payload, ip="203.0.113.10"):
    with node.app.test_client() as client:
        resp = client.post("/attest/submit", json=payload, environ_base={"REMOTE_ADDR": ip})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


# ---------------------------------------------------------------------------

def test_incident_reproduces_on_live_and_is_stopped_by_patch(nodes, tmp_path, sybil_rows):
    row = sybil_rows[0]
    profile = json.loads(row["profile_json"])
    results = {}
    for name, node in nodes.items():
        db = tmp_path / f"{name}.db"
        _configure(node, db)
        _prepare_db(node, db, ["n1"])
        body = _attest(node, db, _g4_payload(row["miner"], "n1", profile))
        results[name] = (_enrolled_weight(node, db, row["miner"]), _bonus_rows(db, row["miner"]), body)
    pat_w, pat_bonus, body = results["patched"]
    if "live" in results:
        live_w, live_bonus, _ = results["live"]
        assert live_w == pytest.approx(1.75) and live_bonus == 1  # the incident, reproduced on pre-patch main
    assert pat_w == 0 and pat_bonus == 0                           # needs_review hold, no bonus
    assert body["probation"]["state"] == "probation"
    with sqlite3.connect(tmp_path / "patched.db") as c:
        esc = c.execute("SELECT epoch, would_be_weight_units FROM sybil_review_escrow WHERE miner=?",
                        (row["miner"],)).fetchall()
    assert esc == [(EPOCH, nodes["patched"].epoch_weight_to_units(1.0))]


def test_every_flagged_wallet_first_attestation_patched(nodes, tmp_path, sybil_rows):
    node = nodes["patched"]
    db = tmp_path / "all.db"
    _configure(node, db)
    first = {}
    for r in sorted(sybil_rows, key=lambda r: r["ts"]):
        first.setdefault(r["miner"], r)
    _prepare_db(node, db, [f"n{i}" for i in range(len(first))])
    for i, (miner, r) in enumerate(first.items()):
        _attest(node, db, _g4_payload(miner, f"n{i}", json.loads(r["profile_json"])), ip=r["source_ip"])
    with sqlite3.connect(db) as c:
        weights = [w for (w,) in c.execute("SELECT weight FROM epoch_enroll WHERE epoch=?", (EPOCH,))]
        bonus = c.execute("SELECT COUNT(*) FROM ledger WHERE reason LIKE 'welcome_bonus:%'").fetchone()[0]
        states = dict(c.execute("SELECT state, COUNT(*) FROM miner_probation GROUP BY state").fetchall())
    assert len(weights) == 120 and set(weights) == {0}
    assert bonus == 0
    assert states.get("trusted", 0) == 0 and states.get("grandfathered", 0) == 0
    print(f"\n120 flagged wallets: states={states}, all enrolled at weight 0, bonuses=0")


def _seed_established(db, miner, n=40):
    start = 1790208000 - 30 * 86400
    with sqlite3.connect(db) as c:
        for k in range(n):
            c.execute("INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES (?, ?, 1)",
                      (miner, start + k * 6 * 3600))
        c.commit()


@pytest.mark.parametrize("arch,cpu,profile", [
    ("g4", "PowerPC G4 7447A", {"clock_drift_cv": 0.0123, "thermal_variance": 0.0, "jitter_cv": 0.0,
                                "cache_hierarchy_ratio": 2.0}),          # lab G4 legacy client
    ("g5", "PowerPC G5 970", {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
                              "cache_hierarchy_ratio": 2.34914}),       # honest G5 fixture row
])
def test_grandfathered_miner_identical_on_live_and_patched(nodes, tmp_path, arch, cpu, profile):
    out = {}
    for name, node in nodes.items():
        db = tmp_path / f"gf_{name}.db"
        _configure(node, db)
        _prepare_db(node, db, ["g1", "g2"])
        _seed_established(db, "lab-g4-example")
        _attest(node, db, _g4_payload("lab-g4-example", "g1", profile, arch=arch, cpu=cpu), ip="192.0.2.125")
        out[name] = (_enrolled_weight(node, db, "lab-g4-example"), _bonus_rows(db, "lab-g4-example"))
    if "live" in out:
        assert out["patched"] == out["live"], out
    assert out["patched"][0] > 1.0  # still earns its vintage premium


def test_dead_anomaly_call_now_runs(nodes, tmp_path, monkeypatch):
    node = nodes["patched"]
    db = tmp_path / "dead.db"
    _configure(node, db)
    _prepare_db(node, db, ["d1"])
    seen = {}
    monkeypatch.setattr(node, "HAVE_REPLAY_DEFENSE", True)
    monkeypatch.setattr(node, "compute_fingerprint_hash", lambda fp: "h", raising=False)
    monkeypatch.setattr(node, "compute_entropy_profile_hash", lambda fp: "e", raising=False)
    monkeypatch.setattr(node, "check_fingerprint_replay", lambda **k: (False, "", None), raising=False)
    monkeypatch.setattr(node, "check_entropy_collision", lambda **k: (False, "", None), raising=False)
    monkeypatch.setattr(node, "check_fingerprint_rate_limit", lambda **k: (True, "", None), raising=False)

    def anomalies(**k):
        seen["anomaly_called"] = True
        return False, []

    def record(**k):
        seen["attestation_valid"] = k.get("attestation_valid")

    monkeypatch.setattr(node, "detect_fingerprint_anomalies", anomalies, raising=False)
    monkeypatch.setattr(node, "record_fingerprint_submission", record, raising=False)
    prof = {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
            "cache_hierarchy_ratio": 2.34914}
    _attest(node, db, _g4_payload("RTCdeadcode", "d1", prof, arch="g5", cpu="PowerPC G5 970"))
    assert seen == {"anomaly_called": True, "attestation_valid": True}


def test_temporal_gate_signature_is_backward_compatible(nodes):
    node = nodes["patched"]
    review = {"reason": "insufficient_history"}
    assert node.apply_temporal_consistency_to_weight(2.5, review) == pytest.approx(1.75)
    assert node.apply_temporal_consistency_to_weight(2.5, review, {"state": "probation"}) == 1.0
    assert node.apply_temporal_consistency_to_weight(2.5, review, {"state": "grandfathered"}) == pytest.approx(1.75)
    assert node.apply_temporal_consistency_to_weight(2.5, review, None) == 1.0  # fail closed
    assert node.apply_temporal_consistency_to_weight(0.8, review, {"state": "probation"}) == 0.8


def test_welcome_bonus_paid_once_at_graduation_only(nodes, tmp_path):
    node = nodes["patched"]
    db = tmp_path / "bonus.db"
    _configure(node, db)
    _prepare_db(node, db, [])
    assert node._check_welcome_bonus("m", {"state": "probation"}) is False
    assert node._check_welcome_bonus("m", None) is False
    assert node._check_welcome_bonus("m", {"state": "trusted", "needs_review": 1}) is False
    assert _bonus_rows(db, "m") == 0
    assert node._check_welcome_bonus("m", {"state": "trusted"}) is False   # nothing persisted: withheld
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, updated_at) "
                  "VALUES ('m', 'trusted', 1, 1, 1)")
    assert node._check_welcome_bonus("m", {"state": "trusted"}) is True
    assert node._check_welcome_bonus("m", {"state": "trusted"}) is False
    assert _bonus_rows(db, "m") == 1
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (SOURCE,)).fetchone()[0] == 99 * BONUS_I64


def test_welcome_bonus_grandfathered_keeps_legacy_rule(nodes, tmp_path):
    node = nodes["patched"]
    db = tmp_path / "bonus_gf.db"
    _configure(node, db)
    _prepare_db(node, db, [])
    _seed_established(db, "old", n=10)
    assert node._check_welcome_bonus("old", {"state": "grandfathered"}) is False
    assert _bonus_rows(db, "old") == 0


def test_finalize_epoch_holds_needs_review_miner(nodes, tmp_path):
    node = nodes["patched"]
    db = tmp_path / "fin.db"
    _configure(node, db)
    _prepare_db(node, db, [])
    import sybil_guard as sg
    u = node.epoch_weight_to_units(1.0)
    with sqlite3.connect(db, isolation_level=None) as c:
        sg.ensure_probation_tables(c)
        c.execute("INSERT INTO epoch_enroll VALUES (?, 'good', ?)", (EPOCH, u))
        c.execute("INSERT INTO epoch_enroll VALUES (?, 'held', ?)", (EPOCH, u))
        c.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, updated_at) "
                  "VALUES ('held', 'probation', 1, 1, 1, 1)")
        c.execute("INSERT INTO balances(miner_id, miner_pk, amount_i64) VALUES ('good','good',0),('held','held',0)")
    node.finalize_epoch(EPOCH, 1.5 / 144)
    with sqlite3.connect(db) as c:
        bal = dict(c.execute("SELECT miner_id, amount_i64 FROM balances WHERE miner_id IN ('good','held')"))
        esc = c.execute("SELECT miner, would_be_weight_units, reason FROM sybil_review_escrow").fetchall()
    print(f"\nfinalize_epoch balances={bal} escrow={esc}")
    assert bal["held"] == 0 and bal["good"] > 0
    assert esc == [("held", u, "settlement_hold")]


def test_rip200_settlement_guard(tmp_path):
    import sybil_guard as sg
    import rip_200_round_robin_1cpu1vote as rr
    db = tmp_path / "rr.db"
    u = rr._weight_to_units(1.0)
    with sqlite3.connect(db, isolation_level=None) as c:
        sg.ensure_probation_tables(c)
        c.execute("CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER)")
        c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_arch TEXT, "
                  "fingerprint_passed INTEGER)")
        for m in ("good", "held"):
            c.execute("INSERT INTO epoch_enroll VALUES (?, ?, ?)", (EPOCH, m, u))
            c.execute("INSERT INTO miner_attest_recent VALUES (?, 'modern', 1)", (m,))
        c.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, updated_at) "
                  "VALUES ('held', 'probation', 1, 1, 1, 1)")
    rewards = rr.calculate_epoch_rewards_time_aged(str(db), EPOCH, 150_000_000, EPOCH * 144)
    print(f"\nrip200 rewards={rewards}")
    assert rewards.get("held", 0) == 0 and rewards["good"] > 0


# ---------------------------------------------------------------------------
# Round 2
# ---------------------------------------------------------------------------

def _finalize_db(node, tmp_path, name, held):
    db = tmp_path / name
    _configure(node, db)
    _prepare_db(node, db, [])
    u = node.epoch_weight_to_units(1.0)
    with sqlite3.connect(db) as c:
        for m in ("good", "held"):
            c.execute("INSERT INTO epoch_enroll VALUES (?, ?, ?)", (EPOCH, m, u))
            c.execute("INSERT INTO balances(miner_id, miner_pk, amount_i64) VALUES (?, ?, 0)", (m, m))
        for m in held:
            c.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, "
                      "updated_at) VALUES (?, 'probation', 1, 1, 1, 1)", (m,))
        c.commit()
    return db


def test_finalize_epoch_reads_hold_inside_write_lock(nodes, tmp_path, monkeypatch):
    node = nodes["patched"]
    db = _finalize_db(node, tmp_path, "finlock.db", held=[])
    import sybil_guard as sg
    real = sg.settlement_held_miners
    seen = {}

    def late_flag(conn, miners, epoch=None):
        # A concurrent writer tries to flag 'held' at exactly this moment.
        seen["in_txn"] = conn.in_transaction
        other = sqlite3.connect(db, timeout=0)
        try:
            other.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, "
                          "updated_at) VALUES ('held', 'probation', 1, 1, 1, 1)")
            other.commit()
            seen["other"] = "committed"
        except sqlite3.OperationalError as exc:
            seen["other"] = str(exc)
        finally:
            other.close()
        return real(conn, miners, epoch)

    monkeypatch.setattr(sg, "settlement_held_miners", late_flag)
    node.finalize_epoch(EPOCH, 1.5 / 144)
    assert seen["in_txn"] is True and "locked" in seen["other"]


def test_finalize_epoch_all_held_leaves_epoch_unsettled(nodes, tmp_path):
    node = nodes["patched"]
    db = _finalize_db(node, tmp_path, "finall.db", held=["good", "held"])
    node.finalize_epoch(EPOCH, 1.5 / 144)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT settled FROM epoch_state WHERE epoch=?", (EPOCH,)).fetchone()[0] == 0
        assert sum(r[0] for r in c.execute("SELECT amount_i64 FROM balances WHERE miner_id IN ('good','held')")) == 0


def test_attest_request_path_runs_no_guard_ddl(nodes, tmp_path, sybil_rows):
    node = nodes["patched"]
    db = tmp_path / "ddl.db"
    _configure(node, db)
    _prepare_db(node, db, ["q1"])
    stmts = []
    real_connect = sqlite3.connect

    def tracing_connect(*a, **k):
        conn = real_connect(*a, **k)
        conn.set_trace_callback(stmts.append)
        return conn

    row = sybil_rows[0]
    node.sqlite3.connect = tracing_connect
    try:
        _attest(node, db, _g4_payload(row["miner"], "q1", json.loads(row["profile_json"])))
    finally:
        node.sqlite3.connect = real_connect
    guard_ddl = [s for s in stmts if s.lstrip().upper().startswith(("CREATE", "ALTER"))
                 and ("miner_probation" in s or "sybil_review_escrow" in s)]
    assert stmts and not guard_ddl


def test_hold_applies_even_when_fingerprint_failed(nodes, tmp_path, sybil_rows, monkeypatch):
    node = nodes["patched"]
    db = tmp_path / "fpfail.db"
    _configure(node, db)
    _prepare_db(node, db, ["f1"])
    monkeypatch.setattr(node, "validate_fingerprint_data", lambda fp, claimed_device=None: (False, "test_fail"))
    row = sybil_rows[0]
    _attest(node, db, _g4_payload(row["miner"], "f1", json.loads(row["profile_json"])))
    with sqlite3.connect(db) as c:
        w = c.execute("SELECT weight FROM epoch_enroll WHERE miner_pk=?", (row["miner"],)).fetchone()[0]
        esc = c.execute("SELECT would_be_weight_units FROM sybil_review_escrow WHERE miner=?",
                        (row["miner"],)).fetchall()
    assert w == 0 and esc == [(node.FAILED_FINGERPRINT_WEIGHT_UNITS,)]


def test_stored_history_flag_survives_non_incident_profile(nodes, tmp_path, sybil_rows):
    """A cohort wallet that re-attests with an honest-looking profile is still
    held (flag seeded from its stored pre-deploy history)."""
    node = nodes["patched"]
    db = tmp_path / "stored.db"
    _configure(node, db)
    _prepare_db(node, db, ["h1"])
    row = sybil_rows[0]
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE IF NOT EXISTS miner_fingerprint_history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "miner TEXT NOT NULL, ts INTEGER NOT NULL, profile_json TEXT NOT NULL)")
        c.execute("INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
                  (row["miner"], 1, row["profile_json"]))
        c.commit()
    honest = {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
              "cache_hierarchy_ratio": 2.34914}
    _attest(node, db, _g4_payload(row["miner"], "h1", honest, arch="g5", cpu="PowerPC G5 970"))
    assert _enrolled_weight(node, db, row["miner"]) == 0


def test_admission_queued_identity_enrolls_at_zero(nodes, tmp_path):
    node = nodes["patched"]
    db = tmp_path / "adm_q.db"
    _configure(node, db)
    _prepare_db(node, db, ["a0", "a1", "a2"])
    honest = {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
              "cache_hierarchy_ratio": 2.34914}
    for i in range(3):
        _attest(node, db, _g4_payload(f"RTCnew{i}", f"a{i}", honest, arch="g5", cpu="PowerPC G5 970"),
                ip="198.51.100.77")
    ws = [_enrolled_weight(node, db, f"RTCnew{i}") for i in range(3)]
    assert ws[0] == ws[1] == pytest.approx(1.0) and ws[2] == 0


def _break_classification(monkeypatch, sg, established_lookup_ok=True):
    def boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(sg, "observe_attestation", boom)
    monkeypatch.setattr(sg, "get_probation_status", boom)
    if not established_lookup_ok:
        monkeypatch.setattr(sg, "has_pre_cutoff_history", boom)


def test_classification_failure_keeps_established_weight(nodes, tmp_path, monkeypatch):
    """Established miner + guard error -> exactly the live weight, never reduced."""
    import sybil_guard as sg
    out = {}
    prof = {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
            "cache_hierarchy_ratio": 2.34914}
    for name, node in nodes.items():
        db = tmp_path / f"cf_{name}.db"
        _configure(node, db)
        _prepare_db(node, db, ["c1"])
        _seed_established(db, "old-g5", n=1)
        with monkeypatch.context() as mp:
            if name == "patched":
                _break_classification(mp, sg)
            _attest(node, db, _g4_payload("old-g5", "c1", prof, arch="g5", cpu="PowerPC G5 970"))
        out[name] = _enrolled_weight(node, db, "old-g5")
    assert out["patched"] > 1.0
    if "live" in out:
        assert out["patched"] == out["live"]


def test_classification_failure_with_unknown_establishment_uses_live_weight(nodes, tmp_path, monkeypatch):
    """Round 2b (GLM): if even the establishment query fails, enrollment uses
    the LIVE weight (CRITICAL log) instead of deferring every miner."""
    import sybil_guard as sg
    prof = {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
            "cache_hierarchy_ratio": 2.34914}
    out = {}
    for name, node in nodes.items():
        db = tmp_path / f"unk_{name}.db"
        _configure(node, db)
        _prepare_db(node, db, ["d9"])
        with monkeypatch.context() as mp:
            if name == "patched":
                _break_classification(mp, sg, established_lookup_ok=False)
            body = _attest(node, db, _g4_payload("who", "d9", prof, arch="g5", cpu="PowerPC G5 970"))
        assert body["ok"] is True
        out[name] = _enrolled_weight(node, db, "who")
    assert out["patched"] is not None
    if "live" in out:
        assert out["patched"] == out["live"]


def test_unreachable_db_defers_enrollment(nodes, tmp_path, monkeypatch):
    import sybil_guard as sg
    node = nodes["patched"]
    db = tmp_path / "defer.db"
    _configure(node, db)
    _prepare_db(node, db, ["d8"])
    _break_classification(monkeypatch, sg, established_lookup_ok=False)
    real = sg.fallback_status
    monkeypatch.setattr(sg, "fallback_status", lambda conn, miner: real(None, miner))
    prof = {"clock_drift_cv": 0.0110244, "thermal_variance": 0.44862, "jitter_cv": 0.0,
            "cache_hierarchy_ratio": 2.34914}
    body = _attest(node, db, _g4_payload("who2", "d8", prof, arch="g5", cpu="PowerPC G5 970"))
    assert body["ok"] is True and _enrolled_weight(node, db, "who2") is None


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), "nan", "Infinity"])
def test_non_finite_binding_is_rejected(nodes, duration):
    node = nodes["patched"]
    nonce = "abcd1234"
    b = {"nonce": nonce, "iterations": node.derive_measurement_workload(nonce), "duration_ns": duration}
    v = node.verify_measurement_binding(nonce, b)
    assert v["state"] == "malformed" and v["ok"] is False
    # live accepted these as "bound"
    if "live" in nodes:
        assert nodes["live"].verify_measurement_binding(nonce, b)["state"] == "bound"



# ---------------------------------------------------------------------------
# Round 3
# ---------------------------------------------------------------------------

def _bonus_db(node, tmp_path, name, state="trusted"):
    db = tmp_path / name
    _configure(node, db)
    _prepare_db(node, db, [])
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, updated_at) "
                  "VALUES ('g', ?, 1, 1, 1)", (state,))
    return db


def test_hold_committed_after_observation_blocks_bonus(nodes, tmp_path):
    """The attestation observed 'trusted'; before payment another writer set
    needs_review. The in-transaction re-read must withhold."""
    node = nodes["patched"]
    db = _bonus_db(node, tmp_path, "race.db")
    stale_status = {"state": "trusted"}                     # what observe returned
    with sqlite3.connect(db) as c:                         # hold lands in between
        c.execute("UPDATE miner_probation SET needs_review = 1, review_reason = 'operator' WHERE miner='g'")
    assert node._check_welcome_bonus("g", stale_status) is False
    assert _bonus_rows(db, "g") == 0
    with sqlite3.connect(db) as c:                         # retryable once cleared
        c.execute("UPDATE miner_probation SET needs_review = 0 WHERE miner='g'")
    assert node._check_welcome_bonus("g", stale_status) is True


def test_cohort_insert_after_trusted_row_blocks_bonus_and_holds(nodes, tmp_path):
    node = nodes["patched"]
    import sybil_guard as sg
    db = _bonus_db(node, tmp_path, "cohort.db")
    with sqlite3.connect(db) as c:
        c.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT PRIMARY KEY)")
        c.execute(f"INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES ('g')")
    assert node._check_welcome_bonus("g", {"state": "trusted"}) is False
    assert _bonus_rows(db, "g") == 0
    with sqlite3.connect(db, isolation_level=None) as c:
        st = sg.get_probation_status(c, "g")                   # read path picks it up
        assert sg.needs_review(st) and sg.enrollment_weight(2.5, st) == 0.0
        st2 = sg.observe_attestation(c, "g", {"clock_drift_cv": 0.05}, "192.0.2.9", now=1790400000)
        assert st2["needs_review"] == 1 and st2["review_reason"] == sg.REVIEW_COHORT   # persisted
        assert sg.review_held_miners(c, ["g"]) == {"g"}


def test_bonus_withheld_when_eligibility_undeterminable(nodes, tmp_path, monkeypatch):
    node = nodes["patched"]
    import sybil_guard as sg
    db = _bonus_db(node, tmp_path, "undet.db")
    real = sg._cohort_members

    def boom(conn, miners):
        raise sqlite3.OperationalError("disk I/O error")

    with sqlite3.connect(db) as c:
        c.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT PRIMARY KEY)")
    monkeypatch.setattr(sg, "_cohort_members", boom)
    assert node._check_welcome_bonus("g", {"state": "trusted"}) is False
    monkeypatch.setattr(sg, "_cohort_members", real)
    assert node._check_welcome_bonus("g", {"state": "trusted"}) is True


def test_grandfathered_bonus_behaviour_unchanged(nodes, tmp_path):
    """Established miners: live never pays (history > 1); a grandfathered miner
    with a single pre-cutoff row + persisted row follows the legacy rule."""
    node = nodes["patched"]
    db = _bonus_db(node, tmp_path, "gf.db", state="grandfathered")
    _seed_established(db, "g", n=1)
    assert node._check_welcome_bonus("g", {"state": "grandfathered"}) is True   # first attestation only
    db2 = _bonus_db(node, tmp_path, "gf2.db", state="grandfathered")
    _seed_established(db2, "g", n=5)
    assert node._check_welcome_bonus("g", {"state": "grandfathered"}) is False


def test_node_bonus_paid_with_absent_cohort_and_withheld_with_malformed(nodes, tmp_path):
    """Round 3b end to end through _check_welcome_bonus."""
    node = nodes["patched"]
    import sybil_guard as sg
    db = _bonus_db(node, tmp_path, "c3b.db")
    db2 = _bonus_db(node, tmp_path, "c3b_bad.db")
    with sqlite3.connect(db2) as c:
        c.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (wallet_x TEXT)")
    assert node._check_welcome_bonus("g", {"state": "trusted"}) is False    # db2 is current DB_PATH
    assert _bonus_rows(db2, "g") == 0
    _configure(node, db)
    assert node._check_welcome_bonus("g", {"state": "trusted"}) is True     # absent table: paid
