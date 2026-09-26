# SPDX-License-Identifier: MIT
"""Regression: /pending/confirm must not report ``ok: true`` when rows failed.

From 2026-09-22 every confirm on the production node raised inside its
savepoint (``mirror_exceeds_balance``) and was rolled back, so no payout was
delivered. The handler still answered ``{"ok": true, "confirmed_count": 0}``
— a caller that checks ``ok`` read a total delivery stall as a healthy empty
pass. A row that raised stays ``pending`` and was not delivered; ``ok`` must
say so, and the failed ids must be surfaced.
"""
import sqlite3
import sys
import time
from contextlib import closing

import pytest

integrated_node = sys.modules["integrated_node"]

ADMIN_KEY = "test-admin-key-pending-confirm"
SENDER = "RTC" + "a" * 40
RECIPIENT = "RTC" + "b" * 40


def _init_db(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL
            );
            CREATE TABLE pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                from_miner TEXT NOT NULL,
                to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                confirms_at INTEGER NOT NULL,
                tx_hash TEXT,
                voided_by TEXT,
                voided_reason TEXT,
                confirmed_at INTEGER
            );
            """
        )
        conn.execute("INSERT INTO balances VALUES (?, ?)", (SENDER, 10_000_000))
        now = int(time.time())
        for i, amount in enumerate((1_000_000, 2_000_000), start=1):
            conn.execute(
                """
                INSERT INTO pending_ledger
                    (ts, epoch, from_miner, to_miner, amount_i64, reason,
                     created_at, confirms_at, tx_hash)
                VALUES (?, 1, ?, ?, ?, 'test', ?, ?, ?)
                """,
                (now - 100, SENDER, RECIPIENT, amount, now - 100, now - 1, f"tx{i}"),
            )
        conn.commit()


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "confirm.sqlite3"
    _init_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    alerts = []
    monkeypatch.setattr(
        integrated_node, "send_sophiacheck_alert",
        lambda level, msg, data=None: alerts.append((level, msg)),
    )
    integrated_node.app.config["TESTING"] = True
    # The admin rate limiter is per-process and keyed by client IP; clear it so
    # these admin calls neither trip it nor leak budget into later tests.
    integrated_node._ADMIN_RATE_LIMIT_BUCKETS.clear()
    with integrated_node.app.test_client() as c:
        c.db_path = db_path
        c.alerts = alerts
        yield c
    integrated_node._ADMIN_RATE_LIMIT_BUCKETS.clear()


def _statuses(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return dict(conn.execute("SELECT id, status FROM pending_ledger").fetchall())


def test_all_rows_failing_is_not_ok(client, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("mirror_exceeds_balance:simulated")

    monkeypatch.setattr(integrated_node, "_settle_account_transfer_in_utxo", _boom)
    resp = client.post("/pending/confirm", headers={"X-Admin-Key": ADMIN_KEY})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["confirmed_count"] == 0
    assert body["ok"] is False, "a pass that delivered nothing because every row raised is not ok"
    assert body["failed_count"] == 2
    assert body["failed_ids"] == [1, 2]
    assert _statuses(client.db_path) == {1: "pending", 2: "pending"}
    assert any(level == "critical" for level, _ in client.alerts)


def test_partial_failure_is_not_ok(client, monkeypatch):
    real = integrated_node._settle_account_transfer_in_utxo

    def _fail_second(c, from_m, to_m, amount, epoch, tx_hash, now):
        if tx_hash == "tx2":
            raise RuntimeError("simulated")
        return real(c, from_m, to_m, amount, epoch, tx_hash, now)

    monkeypatch.setattr(integrated_node, "_settle_account_transfer_in_utxo", _fail_second)
    body = client.post("/pending/confirm", headers={"X-Admin-Key": ADMIN_KEY}).get_json()

    assert body["confirmed_ids"] == [1]
    assert body["failed_ids"] == [2]
    assert body["ok"] is False
    assert _statuses(client.db_path) == {1: "confirmed", 2: "pending"}


def test_clean_pass_is_ok(client):
    body = client.post("/pending/confirm", headers={"X-Admin-Key": ADMIN_KEY}).get_json()

    assert body["ok"] is True
    assert body["confirmed_ids"] == [1, 2]
    assert body["failed_count"] == 0
    assert body["failed_ids"] == []
    assert not any(level == "critical" for level, _ in client.alerts)


def test_insufficient_balance_void_is_a_resolution_not_a_failure(client):
    with closing(sqlite3.connect(client.db_path)) as conn:
        conn.execute("UPDATE balances SET amount_i64 = 0")
        conn.commit()

    body = client.post("/pending/confirm", headers={"X-Admin-Key": ADMIN_KEY}).get_json()

    assert body["ok"] is True
    assert body["failed_count"] == 0
    assert [e["error"] for e in body["errors"]] == ["insufficient_balance"] * 2
    assert _statuses(client.db_path) == {1: "voided", 2: "voided"}
