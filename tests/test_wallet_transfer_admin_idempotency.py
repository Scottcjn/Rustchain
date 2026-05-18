# SPDX-License-Identifier: MIT
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest


integrated_node = sys.modules["integrated_node"]


def _init_wallet_transfer_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
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

        CREATE UNIQUE INDEX idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def admin_transfer_client(monkeypatch):
    tmp_dir = Path(__file__).parent / ".tmp_wallet_transfer_admin"
    tmp_dir.mkdir(exist_ok=True)
    db_path = tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_wallet_transfer_db(db_path)

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setenv("RC_ADMIN_KEY", "a" * 32)

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client, db_path

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def test_admin_transfer_idempotency_key_reuses_pending_transfer(admin_transfer_client):
    client, db_path = admin_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("founder_community", 3_000_000),
        )
        conn.commit()

    payload = {
        "from_miner": "founder_community",
        "to_miner": "contributor",
        "amount_rtc": 1.0,
        "idempotency_key": "owner-repo-123-payment",
    }

    first = client.post("/wallet/transfer", json=payload, headers={"X-Admin-Key": "a" * 32})
    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["ok"] is True

    retry = client.post("/wallet/transfer", json=payload, headers={"X-Admin-Key": "a" * 32})
    assert retry.status_code == 200
    retry_body = retry.get_json()
    assert retry_body["ok"] is True

    assert retry_body["pending_id"] == first_body["pending_id"]
    assert retry_body["tx_hash"] == first_body["tx_hash"]

    with sqlite3.connect(db_path) as conn:
        pending_count, pending_total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_i64), 0) FROM pending_ledger"
        ).fetchone()

    assert pending_count == 1
    assert pending_total == 1_000_000


def test_admin_transfer_idempotency_key_rejects_changed_transfer(admin_transfer_client):
    client, db_path = admin_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("founder_community", 3_000_000),
        )
        conn.commit()

    payload = {
        "from_miner": "founder_community",
        "to_miner": "contributor",
        "amount_rtc": 1.0,
        "idempotency_key": "owner-repo-123-payment",
    }

    first = client.post("/wallet/transfer", json=payload, headers={"X-Admin-Key": "a" * 32})
    assert first.status_code == 200

    changed = dict(payload)
    changed["amount_rtc"] = 2.0
    conflict = client.post("/wallet/transfer", json=changed, headers={"X-Admin-Key": "a" * 32})
    assert conflict.status_code == 409
    assert conflict.get_json()["error"] == "idempotency_key_conflict"

    with sqlite3.connect(db_path) as conn:
        pending_count, pending_total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_i64), 0) FROM pending_ledger"
        ).fetchone()

    assert pending_count == 1
    assert pending_total == 1_000_000
