# SPDX-License-Identifier: MIT
import sqlite3

import pytest

from node import payout_worker


def withdrawal():
    return {
        "withdrawal_id": "wd-1",
        "miner_pk": "miner-pubkey",
        "amount": 10,
        "fee": 1,
        "destination": "RTCdest",
        "created_at": 1234567890,
    }


def test_production_execute_withdrawal_raises_instead_of_returning_none(monkeypatch):
    monkeypatch.setattr(payout_worker, "MOCK_MODE", False)
    worker = payout_worker.PayoutWorker()

    with pytest.raises(payout_worker.ProductionWithdrawalNotConfigured) as exc:
        worker.execute_withdrawal(withdrawal())

    assert "not configured" in str(exc.value)
    assert "transaction hash" in str(exc.value)


def test_process_withdrawal_leaves_pending_when_production_broadcast_is_not_configured(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(payout_worker, "MOCK_MODE", False)
    db_path = str(tmp_path / "payout_worker.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE accounts (public_key TEXT PRIMARY KEY, balance INTEGER)")
        conn.execute(
            "CREATE TABLE withdrawals ("
            "withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT, amount INTEGER, fee INTEGER, "
            "destination TEXT, status TEXT, error_msg TEXT, processed_at INTEGER, "
            "tx_hash TEXT, created_at INTEGER)"
        )
        conn.execute(
            "INSERT INTO accounts (public_key, balance) VALUES (?, ?)",
            ("miner-pubkey", 100),
        )
        conn.execute(
            "INSERT INTO withdrawals "
            "(withdrawal_id, miner_pk, amount, fee, destination, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("wd-1", "miner-pubkey", 10, 1, "RTCdest", "pending", 1234567890),
        )

    worker = payout_worker.PayoutWorker()
    worker.db_path = db_path

    assert worker.process_withdrawal(withdrawal()) is False

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = ?",
            ("miner-pubkey",),
        ).fetchone()[0]
        status, error_msg, tx_hash = conn.execute(
            "SELECT status, error_msg, tx_hash FROM withdrawals WHERE withdrawal_id = ?",
            ("wd-1",),
        ).fetchone()

    assert balance == 100
    assert status == "pending"
    assert "not configured" in error_msg
    assert tx_hash is None


def test_process_withdrawal_does_not_refund_after_broadcast_tx_hash(
    tmp_path, monkeypatch
):
    class BroadcastThenCompletionUpdateFailsWorker(payout_worker.PayoutWorker):
        def execute_withdrawal(self, withdrawal):
            return "tx-broadcasted"

    monkeypatch.setattr(payout_worker, "MOCK_MODE", True)
    db_path = str(tmp_path / "payout_worker.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE accounts (public_key TEXT PRIMARY KEY, balance INTEGER)")
        conn.execute(
            "CREATE TABLE withdrawals ("
            "withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT, amount INTEGER, fee INTEGER, "
            "destination TEXT, status TEXT, error_msg TEXT, tx_hash TEXT, created_at INTEGER)"
        )
        conn.execute(
            "INSERT INTO accounts (public_key, balance) VALUES (?, ?)",
            ("miner-pubkey", 100),
        )
        conn.execute(
            "INSERT INTO withdrawals "
            "(withdrawal_id, miner_pk, amount, fee, destination, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("wd-1", "miner-pubkey", 10, 1, "RTCdest", "pending", 1234567890),
        )

    worker = BroadcastThenCompletionUpdateFailsWorker()
    worker.db_path = db_path

    assert worker.process_withdrawal(withdrawal()) is False

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = ?",
            ("miner-pubkey",),
        ).fetchone()[0]
        status, error_msg, tx_hash = conn.execute(
            "SELECT status, error_msg, tx_hash FROM withdrawals WHERE withdrawal_id = ?",
            ("wd-1",),
        ).fetchone()

    assert balance == 89
    assert status == "processing"
    assert tx_hash == "tx-broadcasted"
    assert "manual reconciliation required" in error_msg
