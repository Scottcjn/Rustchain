# SPDX-License-Identifier: MIT
import os
import sqlite3
import sys


integrated_node = sys.modules["integrated_node"]


def _init_wallet_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL,
                balance_rtc REAL DEFAULT 0
            );
            CREATE TABLE pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                epoch INTEGER,
                from_miner TEXT,
                to_miner TEXT,
                amount_i64 INTEGER,
                reason TEXT,
                status TEXT,
                created_at INTEGER,
                confirms_at INTEGER,
                confirmed_at INTEGER,
                voided_by TEXT,
                voided_reason TEXT,
                tx_hash TEXT
            );
            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                epoch INTEGER,
                miner_id TEXT,
                delta_i64 INTEGER,
                reason TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
            ("victim", 10_000_000, 10.0),
        )


def _pending_count(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0]


def test_wallet_transfer_fails_closed_when_admin_key_unset(tmp_path, monkeypatch):
    db_path = tmp_path / "wallet.db"
    _init_wallet_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", None, raising=False)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    monkeypatch.setattr(integrated_node, "send_sophiacheck_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)

    integrated_node.app.config["TESTING"] = True
    client = integrated_node.app.test_client()

    response = client.post(
        "/wallet/transfer",
        json={
            "from_miner": "victim",
            "to_miner": "attacker",
            "amount_rtc": 5,
        },
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized - admin key required"
    assert _pending_count(db_path) == 0


def test_pending_confirm_fails_closed_when_admin_key_unset(tmp_path, monkeypatch):
    db_path = tmp_path / "wallet.db"
    _init_wallet_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", None, raising=False)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    integrated_node.app.config["TESTING"] = True
    client = integrated_node.app.test_client()

    response = client.post("/pending/confirm")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_wallet_transfer_still_accepts_configured_admin_key(tmp_path, monkeypatch):
    db_path = tmp_path / "wallet.db"
    _init_wallet_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", "expected-admin-key", raising=False)
    monkeypatch.setattr(integrated_node, "send_sophiacheck_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)

    integrated_node.app.config["TESTING"] = True
    client = integrated_node.app.test_client()

    response = client.post(
        "/wallet/transfer",
        headers={"X-Admin-Key": "expected-admin-key"},
        json={
            "from_miner": "victim",
            "to_miner": "recipient",
            "amount_rtc": 1,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["phase"] == "pending"
    assert _pending_count(db_path) == 1
