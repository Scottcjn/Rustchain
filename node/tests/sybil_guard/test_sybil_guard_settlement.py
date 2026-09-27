# SPDX-License-Identifier: MIT
"""Round-2: the review hold on EVERY settlement path, end to end.

settle_epoch_rip200 (ADM preferred, standard fallback) is run for real against
a synthetic DB. The live snapshot is exercised in a subprocess
(tools/settle_probe.py) so the two module sets never share sys.modules.
"""
import json
import sqlite3
import subprocess
import sys

import pytest

import sg_helpers  # noqa: F401  (node/ on sys.path)
import anti_double_mining as adm
import rewards_implementation_rip200 as ri
import sybil_guard as sg
from sg_helpers import HERE, NODE_DIR, baseline_dir

EPOCH = 290
U = 1_000_000_000          # epoch weight units per 1.0x
POT = ri.PER_EPOCH_URTC    # 1.5 RTC in uRTC

HONEST_G4 = {"clock_drift_cv": 0.0123, "thermal_variance": 0.0, "jitter_cv": 0.0, "cache_hierarchy_ratio": 2.0}
HONEST_X86 = {"clock_drift_cv": 0.0812345, "thermal_variance": 0.98, "jitter_cv": 0.04, "cache_hierarchy_ratio": 1.013}


def _sybil_profile(i):
    return {"clock_drift_cv": 0.02 + i / 1000, "thermal_variance": 3.1234, "jitter_cv": 0.1,
            "cache_hierarchy_ratio": 2.5}


def make_db(path, miners, held=(), cohort=(), escrow_table=True):
    """miners: [(id, arch, weight_units, profile)]"""
    c = sqlite3.connect(path)
    c.executescript(
        """
        CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER);
        CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER, PRIMARY KEY(epoch, miner_pk));
        CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT,
            device_arch TEXT, entropy_score REAL DEFAULT 0, fingerprint_passed INTEGER DEFAULT 1,
            fingerprint_checks_json TEXT, warthog_bonus REAL);
        CREATE TABLE miner_fingerprint_history (id INTEGER PRIMARY KEY AUTOINCREMENT, miner TEXT, ts INTEGER,
            profile_json TEXT);
        CREATE TABLE miner_attest_history (id INTEGER PRIMARY KEY AUTOINCREMENT, miner TEXT, ts_ok INTEGER,
            fingerprint_passed INTEGER);
        CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0);
        CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, epoch INTEGER, miner_id TEXT,
            delta_i64 INTEGER, reason TEXT);
        CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER);
        """
    )
    for m, arch, w, p in miners:
        c.execute("INSERT INTO epoch_enroll VALUES (?,?,?)", (EPOCH, m, w))
        c.execute("INSERT INTO miner_attest_recent (miner, ts_ok, device_arch, fingerprint_passed, "
                  "fingerprint_checks_json) VALUES (?,?,?,1,'{}')", (m, 1, arch))
        c.execute("INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?,?,?)",
                  (m, 1, json.dumps(p)))
    if escrow_table:
        sg.init_schema(c)
        for m in held:
            c.execute("INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, "
                      "review_reason, updated_at) VALUES (?, 'probation', 1, 1, 1, 't', 1)", (m,))
    if cohort:
        c.execute(f"CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner_id TEXT PRIMARY KEY, source_ip TEXT)")
        c.executemany(f"INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES (?, 'x')", [(m,) for m in cohort])
    c.commit()
    c.close()


def balances(path):
    with sqlite3.connect(path) as c:
        return dict(c.execute("SELECT miner_id, amount_i64 FROM balances"))


def escrow(path):
    with sqlite3.connect(path) as c:
        return sorted(c.execute("SELECT miner, would_be_weight_units, reason FROM sybil_review_escrow "
                                "WHERE epoch = ?", (EPOCH,)).fetchall())


def settled(path):
    with sqlite3.connect(path) as c:
        row = c.execute("SELECT settled FROM epoch_state WHERE epoch=?", (EPOCH,)).fetchone()
    return bool(row and row[0])


@pytest.fixture
def base_miners():
    return [("honest-g4", "g4", 2 * U + U // 2, HONEST_G4),
            ("honest-x86", "modern", U, HONEST_X86),
            ("late-flag", "g4", U, _sybil_profile(0))]   # probation-capped, flagged AFTER enrolling


@pytest.mark.parametrize("use_adm", [True, False])
def test_settle_epoch_rip200_holds_post_enroll_flag(tmp_path, base_miners, use_adm):
    db = str(tmp_path / "s.db")
    make_db(db, base_miners, held=["late-flag"])
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=use_adm)
    assert res["ok"] is True
    assert ("anti_double_mining_telemetry" in res) is use_adm   # the ADM path really ran
    bal = balances(db)
    assert "late-flag" not in bal
    # exact payout arithmetic: pot split 2.5 : 1.0 between the honest miners
    assert bal["honest-g4"] + bal["honest-x86"] == POT
    assert abs(bal["honest-g4"] - POT * 2.5 / 3.5) <= 1
    assert escrow(db) == [("late-flag", U, "settlement_hold")]
    assert settled(db)


@pytest.mark.parametrize("use_adm", [True, False])
def test_cohort_membership_holds_without_probation_row(tmp_path, base_miners, use_adm):
    db = str(tmp_path / "c.db")
    make_db(db, base_miners, cohort=["late-flag"])
    ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=use_adm)
    assert "late-flag" not in balances(db)


@pytest.mark.parametrize("use_adm", [True, False])
def test_all_held_epoch_pays_nothing_and_stays_unsettled(tmp_path, use_adm):
    db = str(tmp_path / "a.db")
    miners = [(f"s{i}", "g4", U, _sybil_profile(i)) for i in range(3)]
    make_db(db, miners, held=[m[0] for m in miners])
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=use_adm)
    assert res["ok"] is False and res["error"] == "no_eligible_miners"
    assert balances(db) == {} and not settled(db)


def test_adm_held_miner_cannot_displace_unheld_alias(tmp_path):
    """Same machine identity (arch + profile): the held miner has the higher
    enrolled weight, but the unheld alias must be the one paid."""
    db = str(tmp_path / "d.db")
    make_db(db, [("honest-x86", "modern", U, HONEST_X86),
                 ("alias-honest", "g4", U, HONEST_G4),
                 ("alias-held", "g4", 2 * U, HONEST_G4)], held=["alias-held"])
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=True)
    bal = balances(db)
    assert "anti_double_mining_telemetry" in res
    assert "alias-held" not in bal and bal["alias-honest"] > 0


def test_rip200_index3_is_zeroed_not_fingerprint(tmp_path, base_miners, monkeypatch):
    """Astra: the round-1 guard overwrote tuple index 2 (fingerprint_passed).
    A held miner must reach the weight step with fingerprint_ok intact and
    enrolled_weight == 0 (so the arch fallback cannot re-weight it)."""
    import rip_200_round_robin_1cpu1vote as rr
    db = str(tmp_path / "r.db")
    make_db(db, base_miners, held=["late-flag"])
    seen = {}
    real = rr._distribute_reward_by_weight

    def spy(weighted, total):
        seen.update(dict(weighted))
        return real(weighted, total)

    monkeypatch.setattr(rr, "_distribute_reward_by_weight", spy)
    out = rr.calculate_epoch_rewards_time_aged(db, EPOCH, POT, EPOCH * 144)
    assert seen["late-flag"] == 0 and "late-flag" not in out
    assert seen["honest-g4"] == 2 * U + U // 2


def test_hold_is_read_inside_the_settlement_write_lock(tmp_path, base_miners, monkeypatch):
    """The hold lookup runs while settle_epoch_rip200 holds BEGIN IMMEDIATE; a
    concurrent writer trying to flag a miner at that moment is locked out, so
    no hold can land between the read and the credits."""
    db = str(tmp_path / "l.db")
    make_db(db, base_miners)
    observed = {}
    real = sg.settlement_held_miners

    def wrapped(conn, miners, epoch=None):
        observed["in_txn"] = conn.in_transaction
        other = sqlite3.connect(db, timeout=0)
        try:
            other.execute("UPDATE miner_probation SET needs_review = 1")
            other.commit()
            observed["other_write"] = "succeeded"
        except sqlite3.OperationalError as exc:
            observed["other_write"] = str(exc)
        finally:
            other.close()
        return real(conn, miners, epoch)

    monkeypatch.setattr(sg, "settlement_held_miners", wrapped)
    ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=True)
    assert observed["in_txn"] is True
    assert "locked" in observed["other_write"]


def test_adm_weight_read_error_does_not_fail_open(tmp_path, base_miners):
    """Round 1 finding: ADM swallowed sqlite errors reading epoch weights and
    fell back to ARCH multipliers (2.5x for a held G4). Now it propagates."""
    db = str(tmp_path / "e.db")
    make_db(db, base_miners)

    class Boom:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, sql, *a):
            if "SELECT miner_pk, weight FROM epoch_enroll" in sql:
                raise sqlite3.OperationalError("disk I/O error")
            return self.conn.execute(sql, *a)

    with sqlite3.connect(db) as c:
        with pytest.raises(sqlite3.OperationalError):
            adm._get_epoch_enrolled_weights(Boom(c), EPOCH)


def test_broken_probation_table_never_halts_settlement(tmp_path, base_miners):
    """Incompatible miner_probation (e.g. hand-made) -> the lookup falls back to
    escrow rows, logs CRITICAL, and settlement still completes."""
    db = str(tmp_path / "b.db")
    make_db(db, base_miners)
    with sqlite3.connect(db) as c:
        c.execute("DROP TABLE miner_probation")
        c.execute("CREATE TABLE miner_probation (miner TEXT)")   # no needs_review column
        c.execute("INSERT INTO sybil_review_escrow VALUES (?, 'late-flag', 5, 'enroll', 1)", (EPOCH,))
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=True)
    assert res["ok"] is True and settled(db)
    assert "late-flag" not in balances(db)   # held via the escrow-row fallback


def test_no_probation_table_means_no_holds_but_settles(tmp_path, base_miners):
    db = str(tmp_path / "n.db")
    # g5 so ADM does not group it with honest-g4 as one machine
    miners = base_miners[:2] + [("late-flag", "g5", U, _sybil_profile(0))]
    make_db(db, miners, escrow_table=False)
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=True)
    assert res["ok"] is True and balances(db)["late-flag"] > 0


def _probe(src, db, adm_flag):
    out = subprocess.run([sys.executable, str(HERE / "settle_probe.py"), str(src), db,
                          str(EPOCH), "1" if adm_flag else "0"], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("src", ["live", "patched"])
@pytest.mark.parametrize("use_adm", [True, False])
def test_epoch296_style_zeroed_rows_pay_zero(tmp_path, src, use_adm):
    """Tonight's containment (83 rows set to weight 0) on BOTH the unpatched
    production code and the patch, ADM and standard paths."""
    db = str(tmp_path / f"z_{src}_{use_adm}.db")
    miners = [("honest-g4", "g4", 2 * U + U // 2, HONEST_G4), ("honest-x86", "modern", U, HONEST_X86)]
    miners += [(f"sybil-{i}", "g4", 0, _sybil_profile(i)) for i in range(3)]
    make_db(db, miners, escrow_table=(src == "patched"))
    if src == "live" and baseline_dir() is None:
        pytest.skip("pre-patch baseline not available from git")
    got = _probe(baseline_dir() if src == "live" else NODE_DIR, db, use_adm)
    assert got["ok"] is True and got["adm"] is use_adm
    assert set(got["balances"]) == {"honest-g4", "honest-x86"}
    assert sum(got["balances"].values()) == POT


def test_escrow_weight_read_error_does_not_abort_adm_settlement(tmp_path, base_miners, monkeypatch):
    """GLM round 2: the escrow-weight read inside the hold must be fail-SAFE.
    First call to _get_epoch_enrolled_weights is the hold's escrow lookup."""
    db = str(tmp_path / "ew.db")
    make_db(db, base_miners, held=["late-flag"])
    real = adm._get_epoch_enrolled_weights
    calls = {"n": 0}

    def flaky(conn, epoch):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return real(conn, epoch)

    monkeypatch.setattr(adm, "_get_epoch_enrolled_weights", flaky)
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=True)
    assert res["ok"] is True and "anti_double_mining_telemetry" in res
    assert "late-flag" not in balances(db)       # hold still applied
    assert escrow(db) == []                      # only the escrow record was skipped


@pytest.mark.parametrize("require_adm", [False, True])
def test_payout_weight_read_error_stays_fail_loud(tmp_path, base_miners, monkeypatch, require_adm):
    """The payout weights are NOT fail-safe: ADM aborts. Without RC_REQUIRE_ADM
    the existing fallback settles via the standard path (still holding);
    with it, the epoch stays unsettled."""
    db = str(tmp_path / f"pw{require_adm}.db")
    make_db(db, base_miners, held=["late-flag"])

    def always(conn, epoch):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(adm, "_get_epoch_enrolled_weights", always)
    if require_adm:
        monkeypatch.setenv("RC_REQUIRE_ADM", "1")
    res = ri.settle_epoch_rip200(db, EPOCH, enable_anti_double_mining=True)
    if require_adm:
        assert res["ok"] is False and res["error"] == "adm_required_failed" and not settled(db)
    else:
        assert res["ok"] is True and "anti_double_mining_telemetry" not in res
        assert "late-flag" not in balances(db) and escrow(db) == [("late-flag", U, "settlement_hold")]
