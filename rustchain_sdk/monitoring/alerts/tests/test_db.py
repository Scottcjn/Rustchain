"""Tests for AlertDB."""

import time
import pytest

from rustchain_alerts.db import AlertDB


@pytest.fixture
def db(tmp_path):
    return AlertDB(tmp_path / "test.db")


def test_upsert_and_get_miner(db):
    db.upsert_miner("miner-1", last_attest=1000, balance_rtc=5.0)
    row = db.get_miner("miner-1")
    assert row is not None
    assert row["miner_id"] == "miner-1"
    assert row["last_attest"] == 1000
    assert row["balance_rtc"] == 5.0
    assert row["offline_alerted"] == 0


def test_upsert_updates_existing(db):
    db.upsert_miner("miner-1", last_attest=1000, balance_rtc=5.0)
    db.upsert_miner("miner-1", last_attest=2000, balance_rtc=10.0)
    row = db.get_miner("miner-1")
    assert row["last_attest"] == 2000
    assert row["balance_rtc"] == 10.0


def test_set_offline_alerted(db):
    db.upsert_miner("miner-1", last_attest=1000, balance_rtc=5.0)
    db.set_offline_alerted("miner-1", True)
    row = db.get_miner("miner-1")
    assert row["offline_alerted"] == 1

    db.set_offline_alerted("miner-1", False)
    row = db.get_miner("miner-1")
    assert row["offline_alerted"] == 0


def test_was_alerted_recently_false_when_empty(db):
    assert db.was_alerted_recently("miner-1", "offline") is False


def test_was_alerted_recently_true_after_record(db):
    db.record_alert("miner-1", "offline", "Test alert")
    assert db.was_alerted_recently("miner-1", "offline", within_seconds=3600) is True


def test_was_alerted_recently_false_after_window(db):
    # Manually insert an old alert
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    old_ts = int(time.time()) - 7200  # 2 hours ago
    conn.execute(
        "INSERT INTO alert_history(miner_id, alert_type, message, fired_at) VALUES(?,?,?,?)",
        ("miner-1", "offline", "old alert", old_ts),
    )
    conn.commit()
    conn.close()

    assert db.was_alerted_recently("miner-1", "offline", within_seconds=3600) is False


def test_record_alert_and_history(db):
    db.record_alert("miner-1", "reward", "Got 5 RTC")
    db.record_alert("miner-2", "offline", "Offline for 15m")
    rows = db.recent_alerts(limit=10)
    assert len(rows) == 2
    types = {r["alert_type"] for r in rows}
    assert "reward" in types
    assert "offline" in types


def test_get_nonexistent_miner_returns_none(db):
    assert db.get_miner("does-not-exist") is None
