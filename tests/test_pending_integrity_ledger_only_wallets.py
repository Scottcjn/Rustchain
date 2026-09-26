# SPDX-License-Identifier: MIT
"""Regression: /pending/integrity must see wallets that exist only in the ledger.

The check walked the ``balances`` table and compared each row to its ledger
sum. A wallet with ledger credits but no balance row was never visited, so RTC
the ledger says was paid — but that no balance row holds — reported
``ok: true``. The check must cover the union of both sides.
"""
import sqlite3
import sys
from contextlib import closing

import pytest

integrated_node = sys.modules["integrated_node"]

ADMIN_KEY = "test-admin-key-integrity"


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
        # A consistent wallet: balance == ledger sum.
        conn.execute("INSERT INTO balances VALUES ('alice', 3000000)")
        conn.execute("INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) "
                     "VALUES (1, 1, 'alice', 3000000, 'epoch_1_reward')")
        conn.commit()
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setattr(integrated_node, "send_sophiacheck_alert", lambda *a, **k: None)
    integrated_node.app.config["TESTING"] = True
    # The admin rate limiter is per-process and keyed by client IP; clear it so
    # these admin calls neither trip it nor leak budget into later tests.
    integrated_node._ADMIN_RATE_LIMIT_BUCKETS.clear()
    with integrated_node.app.test_client() as c:
        c.db_path = db_path
        yield c
    integrated_node._ADMIN_RATE_LIMIT_BUCKETS.clear()


def _check(client):
    resp = client.get("/pending/integrity", headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 200
    return resp.get_json()


def test_consistent_books_are_ok(client):
    body = _check(client)
    assert body["ok"] is True
    assert body["mismatches"] is None
    assert body["total_miners_checked"] == 1


def test_ledger_credit_without_balance_row_is_a_mismatch(client):
    with closing(sqlite3.connect(client.db_path)) as conn:
        conn.execute("INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) "
                     "VALUES (2, 1, 'bob', 5000000, 'transfer_in:alice:tx')")
        conn.commit()

    body = _check(client)

    assert body["ok"] is False, "5 RTC in the ledger with no balance row must not pass"
    assert body["total_miners_checked"] == 2
    assert body["mismatches"] == [{
        "miner_id": "bob",
        "balance_rtc": 0.0,
        "ledger_sum_rtc": 5.0,
        "diff_rtc": -5.0,
        "balance_row_missing": True,
    }]


def test_balance_without_ledger_is_still_a_mismatch(client):
    with closing(sqlite3.connect(client.db_path)) as conn:
        conn.execute("INSERT INTO balances VALUES ('carol', 700000)")
        conn.commit()

    body = _check(client)

    assert body["ok"] is False
    assert body["mismatches"] == [{
        "miner_id": "carol",
        "balance_rtc": 0.7,
        "ledger_sum_rtc": 0.0,
        "diff_rtc": 0.7,
    }]


def test_ledger_entries_netting_to_zero_without_balance_row_are_ok(client):
    with closing(sqlite3.connect(client.db_path)) as conn:
        conn.executemany(
            "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, 1, 'dave', ?, 'x')",
            [(3, 1000), (4, -1000)],
        )
        conn.commit()

    body = _check(client)
    assert body["ok"] is True
    assert body["total_miners_checked"] == 2
