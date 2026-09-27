# SPDX-License-Identifier: MIT
"""/pending/integrity: a frozen historical difference is listed, not alarmed.

The baseline must never become a blind spot. A known wallet whose difference
moves by one unit, or any wallet not in the baseline, is still a mismatch.
"""
import sqlite3
import sys
from contextlib import closing

import pytest

integrated_node = sys.modules["integrated_node"]

ADMIN_KEY = "test-admin-key-integrity-baseline"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "integrity.sqlite3"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL, miner_id TEXT NOT NULL,
                delta_i64 INTEGER NOT NULL, reason TEXT
            );
            CREATE TABLE pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT, from_miner TEXT,
                amount_i64 INTEGER, status TEXT
            );
            """
        )
        # 'legacy' holds 5 RTC with no ledger rows: a +5 RTC historical difference.
        conn.execute("INSERT INTO balances VALUES ('legacy', 5000000)")
        conn.commit()
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setattr(integrated_node, "send_sophiacheck_alert", lambda *a, **k: None)
    monkeypatch.setattr(integrated_node.integrity_baseline, "KNOWN_LEGACY_DRIFT",
                        {"legacy": (5000000, "test: historical writer")})
    integrated_node.app.config["TESTING"] = True
    integrated_node._ADMIN_RATE_LIMIT_BUCKETS.clear()
    with integrated_node.app.test_client() as c:
        c.db_path = db_path
        yield c
    integrated_node._ADMIN_RATE_LIMIT_BUCKETS.clear()


def _check(client):
    resp = client.get("/pending/integrity", headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 200
    return resp.get_json()


def _sql(client, stmt):
    with closing(sqlite3.connect(client.db_path)) as conn:
        conn.execute(stmt)
        conn.commit()


def test_exact_baseline_difference_is_listed_not_alarmed(client):
    body = _check(client)
    assert body["ok"] is True
    assert body["mismatches"] is None
    assert body["known_legacy_count"] == 1
    assert body["known_legacy"] == [
        {"miner_id": "legacy", "diff_rtc": 5.0, "reason": "test: historical writer"}]


def test_known_wallet_that_moves_one_unit_alarms_again(client):
    _sql(client, "UPDATE balances SET amount_i64 = amount_i64 + 1 WHERE miner_id = 'legacy'")
    body = _check(client)
    assert body["ok"] is False
    assert body["known_legacy_count"] == 0
    (m,) = body["mismatches"]
    assert m["miner_id"] == "legacy"
    assert m["baseline_diff_rtc"] == 5.0
    assert m["drift_since_baseline_rtc"] == 0.000001


def test_balanced_ledger_activity_keeps_the_baseline(client):
    # Normal audited transfers move balance and ledger together.
    _sql(client, "UPDATE balances SET amount_i64 = amount_i64 + 2000000 WHERE miner_id = 'legacy'")
    _sql(client, "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) "
                 "VALUES (1, 1, 'legacy', 2000000, 'transfer_in:x:tx')")
    body = _check(client)
    assert body["ok"] is True
    assert body["known_legacy_count"] == 1


def test_unlisted_wallet_still_alarms(client):
    _sql(client, "INSERT INTO balances VALUES ('newcomer', 700000)")
    body = _check(client)
    assert body["ok"] is False
    assert [m["miner_id"] for m in body["mismatches"]] == ["newcomer"]
    assert "baseline_diff_rtc" not in body["mismatches"][0]
    assert body["known_legacy_count"] == 1


def test_real_baseline_table_is_well_formed():
    table = sys.modules["integrated_node"].integrity_baseline
    real = table.__dict__["KNOWN_LEGACY_DRIFT"]
    assert len(real) == 24
    for miner_id, (diff, reason) in real.items():
        assert isinstance(diff, int) and diff != 0, miner_id
        assert isinstance(reason, str) and reason, miner_id
