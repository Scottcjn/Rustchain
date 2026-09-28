# SPDX-License-Identifier: MIT
import sqlite3

import pytest

from node import payout_worker

# balances.amount_i64 is micro-RTC. Wallet held 100 RTC; the node's /withdraw
# endpoint already debited amount (10) + fee (1) at request time.
AFTER_REQUEST_DEBIT_I64 = (100 - 10 - 1) * payout_worker.ACCOUNT_UNIT


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
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute(
            "CREATE TABLE withdrawals ("
            "withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT, amount INTEGER, fee INTEGER, "
            "destination TEXT, status TEXT, error_msg TEXT, processed_at INTEGER, "
            "tx_hash TEXT, created_at INTEGER)"
        )
        # The node debits amount + fee from `balances` at REQUEST time
        # (100 RTC - 10 - 1 fee = 89 RTC left); the worker must not touch it.
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("miner-pubkey", AFTER_REQUEST_DEBIT_I64),
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
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("miner-pubkey",),
        ).fetchone()[0]
        status, error_msg, tx_hash = conn.execute(
            "SELECT status, error_msg, tx_hash FROM withdrawals WHERE withdrawal_id = ?",
            ("wd-1",),
        ).fetchone()

    # Not configured -> left pending: no second debit and no refund.
    assert balance == AFTER_REQUEST_DEBIT_I64
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
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute(
            "CREATE TABLE withdrawals ("
            "withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT, amount INTEGER, fee INTEGER, "
            "destination TEXT, status TEXT, error_msg TEXT, tx_hash TEXT, created_at INTEGER)"
        )
        # The node debits amount + fee from `balances` at REQUEST time
        # (100 RTC - 10 - 1 fee = 89 RTC left); the worker must not touch it.
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("miner-pubkey", AFTER_REQUEST_DEBIT_I64),
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
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("miner-pubkey",),
        ).fetchone()[0]
        status, error_msg, tx_hash = conn.execute(
            "SELECT status, error_msg, tx_hash FROM withdrawals WHERE withdrawal_id = ?",
            ("wd-1",),
        ).fetchone()

    # Broadcast hash exists -> must NOT refund (funds may have left), and the
    # worker must not debit a second time either.
    assert balance == AFTER_REQUEST_DEBIT_I64
    assert status == "processing"
    assert tx_hash == "tx-broadcasted"
    assert "manual reconciliation required" in error_msg
