# SPDX-License-Identifier: MIT
"""tools/probation_admin.py on a synthetic DB."""
import sg_helpers  # noqa: F401  (node/ on sys.path)
import importlib.util
import io
import json
import sqlite3
from pathlib import Path

import pytest

import sybil_guard as sg

TOOLS = Path(__file__).resolve().parents[3] / "tools"
spec = importlib.util.spec_from_file_location("probation_admin", TOOLS / "probation_admin.py")
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)

PROTECTED = ("balances", "ledger", "epoch_enroll", "sybil_review_escrow", sg.INCIDENT_COHORT_TABLE)


def _row(c, miner, state, needs_review=0, review=None):
    c.execute("INSERT INTO miner_probation (miner, state, reason, first_seen, last_seen, attest_count, "
              "needs_review, review_reason, updated_at) VALUES (?, ?, 'r', 1790300000, 1790300500, 3, ?, ?, 1)",
              (miner, state, needs_review, review))


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "n.db"
    c = sqlite3.connect(path)
    c.executescript(f"""
        CREATE TABLE miner_attest_history (id INTEGER PRIMARY KEY, miner TEXT, ts_ok INTEGER, fingerprint_passed INTEGER);
        CREATE TABLE miner_fingerprint_history (id INTEGER PRIMARY KEY AUTOINCREMENT, miner TEXT, ts INTEGER, profile_json TEXT);
        CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER);
        CREATE TABLE ledger (id INTEGER PRIMARY KEY, ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT);
        CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER);
        CREATE TABLE {sg.INCIDENT_COHORT_TABLE} (miner TEXT PRIMARY KEY);
        INSERT INTO balances VALUES ('held-new', 5), ('old-g4', 7);
        INSERT INTO ledger VALUES (1, 1, 1, 'old-g4', 7, 'x');
        INSERT INTO epoch_enroll VALUES (297, 'held-new', 0), (297, 'old-g4', 0);
        INSERT INTO {sg.INCIDENT_COHORT_TABLE} VALUES ('syb-1');
        INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES ('old-g4', {sg.GRANDFATHER_CUTOFF_TS - 86400}, 1);
    """)
    sg.init_schema(c)
    _row(c, "held-new", sg.STATE_PROBATION, 1, sg.REVIEW_LIVE)
    _row(c, "old-g4", sg.STATE_GRANDFATHERED, 1, sg.REVIEW_STORED)
    _row(c, "syb-1", sg.STATE_ADMISSION_QUEUED, 1, sg.REVIEW_COHORT)
    _row(c, "fine", sg.STATE_PROBATION)
    _row(c, "grad", sg.STATE_TRUSTED)
    sg.record_review_escrow(c, 297, "held-new", 1_000_000_000, "enroll", now=1)
    sg.record_review_escrow(c, 298, "held-new", 1_000_000_000, "enroll", now=2)
    c.commit()
    c.close()
    return path


def _dump(path, tables):
    with sqlite3.connect(path) as c:
        return {t: sorted(c.execute(f"SELECT * FROM {t}")) for t in tables}


def run(db, *argv):
    buf = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(buf):
        rc = pa.main(["--db", str(db), "--root", str(TOOLS.parent), *argv])
    return rc, buf.getvalue()


def test_list_shows_held_and_probation_with_escrow(db):
    rows = pa.cmd_list(str(db), sg, out=io.StringIO())
    by = {r["miner"]: r for r in rows}
    assert set(by) == {"held-new", "old-g4", "syb-1", "fine"}      # trusted 'grad' not listed
    assert by["held-new"]["escrow_units"] == 2_000_000_000 and by["held-new"]["escrow_epochs"] == 2
    assert by["syb-1"]["cohort"] is True and by["old-g4"]["needs_review"] is True


def test_show_reports_everything_read_only(db):
    before = _dump(db, ("miner_probation",) + PROTECTED)
    info = pa.cmd_show(str(db), sg, "old-g4", out=io.StringIO())
    assert info["pre_cutoff_history"] is True and info["probation_row"]["needs_review"] == 1
    assert _dump(db, ("miner_probation",) + PROTECTED) == before


def test_release_default_is_dry_run(db):
    before = _dump(db, ("miner_probation",) + PROTECTED)
    rc, out = run(db, "release", "held-new", "--reason", "checked")
    assert rc == 0 and '"DRY_RUN": true' in out
    assert _dump(db, ("miner_probation",) + PROTECTED) == before
    with sqlite3.connect(db) as c:
        assert not c.execute(f"SELECT 1 FROM sqlite_master WHERE name='{pa.AUDIT_TABLE}'").fetchone()


def test_release_grandfathered_and_audit(db):
    protected = _dump(db, PROTECTED)
    rc, out = run(db, "release", "old-g4", "--reason", "owner verified", "--operator", "scott", "--apply")
    assert rc == 0
    with sqlite3.connect(db) as c:
        st = sg._load(c, "old-g4")
        audit = c.execute(f"SELECT operator, action, miner, reason, before_json, after_json FROM {pa.AUDIT_TABLE}").fetchall()
    assert st["needs_review"] == 0 and st["state"] == sg.STATE_GRANDFATHERED
    assert audit[0][:4] == ("scott", "release", "old-g4", "owner verified")
    assert json.loads(audit[0][4])["needs_review"] == 1 and json.loads(audit[0][5])["needs_review"] == 0
    assert _dump(db, PROTECTED) == protected                      # never touches money tables
    assert sg.enrollment_weight(2.5, st) == 2.5


def test_release_new_miner_keeps_state_unless_trust(db):
    run(db, "release", "held-new", "--reason", "r", "--apply")
    with sqlite3.connect(db) as c:
        st = sg._load(c, "held-new")
    assert st["state"] == sg.STATE_PROBATION and st["needs_review"] == 0
    assert sg.enrollment_weight(2.5, st) == 1.0
    run(db, "release", "held-new", "--reason", "lab box", "--trust", "--apply")
    with sqlite3.connect(db) as c:
        assert sg._load(c, "held-new")["state"] == sg.STATE_TRUSTED


def test_cohort_member_refused_without_force_and_warned_with_it(db):
    before = _dump(db, ("miner_probation",) + PROTECTED)
    rc, out = run(db, "release", "syb-1", "--reason", "r", "--apply")
    assert rc == 2 and "--force-cohort" in out
    assert _dump(db, ("miner_probation",) + PROTECTED) == before
    rc, out = run(db, "release", "syb-1", "--reason", "appeal upheld", "--force-cohort", "--apply")
    assert rc == 0 and "settlement will KEEP holding" in out
    with sqlite3.connect(db) as c:
        assert c.execute(f"SELECT COUNT(*) FROM {sg.INCIDENT_COHORT_TABLE}").fetchone()[0] == 1   # not touched
        assert c.execute(f"SELECT action FROM {pa.AUDIT_TABLE}").fetchone()[0] == "release+force_cohort"
        # the settlement guard still holds it via the cohort table
        assert sg.review_held_miners(c, ["syb-1"]) == {"syb-1"}


def test_release_requires_reason_and_known_miner(db):
    rc, out = run(db, "release", "nobody", "--reason", "r", "--apply")
    assert rc == 2 and "no miner_probation row" in out
    rc, out = run(db, "release", "held-new", "--reason", "   ", "--apply")
    assert rc == 2


def test_allowlist_guidance(db):
    rc, out = run(db, "allowlist")
    assert rc == 0 and sg.PROBATION_ALLOWLIST_ENV in out
