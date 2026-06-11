# SPDX-License-Identifier: MIT

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import payout_worker
from payout_worker import PayoutWorker


def _create_schema(conn):
    conn.execute("""
        CREATE TABLE accounts (
            public_key TEXT PRIMARY KEY,
            balance REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE withdrawals (
            withdrawal_id TEXT PRIMARY KEY,
            miner_pk TEXT NOT NULL,
            amount REAL NOT NULL,
            fee REAL DEFAULT 0,
            destination TEXT,
            status TEXT NOT NULL,
            created_at INTEGER,
            processed_at INTEGER,
            tx_hash TEXT,
            error_msg TEXT
        )
    """)


def test_recover_orphans_flags_ambiguous_processing_withdrawal_without_refund(tmp_path):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 89.0)")
        conn.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination, status, created_at
            ) VALUES ('wd-1', 'miner-1', 10.0, 1.0, 'dest', 'processing', 1)
        """)

    worker = PayoutWorker()
    worker.db_path = str(db_path)
    worker.recover_orphans()

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]
        status, error_msg = conn.execute(
            "SELECT status, error_msg FROM withdrawals WHERE withdrawal_id = 'wd-1'"
        ).fetchone()

    assert balance == 89.0
    assert status == "processing"
    assert error_msg == "Processing without tx_hash; manual reconciliation required before refund"


def test_recover_orphans_does_not_refund_broadcast_withdrawal_requiring_reconciliation(tmp_path):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 89.0)")
        conn.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination, status,
                created_at, tx_hash, error_msg
            ) VALUES (
                'wd-1', 'miner-1', 10.0, 1.0, 'dest', 'processing',
                1, '0xalready_broadcast', 'manual reconciliation required'
            )
        """)

    worker = PayoutWorker()
    worker.db_path = str(db_path)
    worker.recover_orphans()

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]
        status, tx_hash, error_msg = conn.execute(
            "SELECT status, tx_hash, error_msg FROM withdrawals WHERE withdrawal_id = 'wd-1'"
        ).fetchone()

    assert balance == 89.0
    assert status == "processing"
    assert tx_hash == "0xalready_broadcast"
    assert error_msg == "manual reconciliation required"


def test_reconcile_broadcast_withdrawals_completes_confirmed_tx_hash(tmp_path, monkeypatch):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 89.0)")
        conn.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination, status,
                created_at, tx_hash, error_msg
            ) VALUES (
                'wd-1', 'miner-1', 10.0, 1.0, 'dest', 'processing',
                1, '0xconfirmed', 'manual reconciliation required'
            )
        """)

    worker = PayoutWorker()
    worker.db_path = str(db_path)
    monkeypatch.setattr(worker, "lookup_withdrawal_status", lambda tx_hash: True)
    worker.reconcile_broadcast_withdrawals()

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]
        status, tx_hash, error_msg = conn.execute(
            "SELECT status, tx_hash, error_msg FROM withdrawals WHERE withdrawal_id = 'wd-1'"
        ).fetchone()

    assert balance == 89.0
    assert status == "completed"
    assert tx_hash == "0xconfirmed"
    assert error_msg is None


def test_reconcile_broadcast_withdrawals_marks_failed_tx_terminal_without_refund(tmp_path, monkeypatch):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 89.0)")
        conn.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination, status,
                created_at, tx_hash, error_msg
            ) VALUES (
                'wd-1', 'miner-1', 10.0, 1.0, 'dest', 'processing',
                1, '0xfailed', 'manual reconciliation required'
            )
        """)

    worker = PayoutWorker()
    worker.db_path = str(db_path)
    monkeypatch.setattr(worker, "lookup_withdrawal_status", lambda tx_hash: False)
    worker.reconcile_broadcast_withdrawals()

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]
        status, tx_hash, error_msg = conn.execute(
            "SELECT status, tx_hash, error_msg FROM withdrawals WHERE withdrawal_id = 'wd-1'"
        ).fetchone()

    assert balance == 89.0
    assert status == "failed"
    assert tx_hash == "0xfailed"
    assert error_msg == "Broadcast transaction not found or failed; manual refund required"


def test_reconcile_broadcast_withdrawals_preserves_unknown_tx_hash(tmp_path):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 89.0)")
        conn.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination, status,
                created_at, tx_hash, error_msg
            ) VALUES (
                'wd-1', 'miner-1', 10.0, 1.0, 'dest', 'processing',
                1, '0xunknown', 'manual reconciliation required'
            )
        """)

    worker = PayoutWorker()
    worker.db_path = str(db_path)
    worker.reconcile_broadcast_withdrawals()

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]
        status, tx_hash, error_msg = conn.execute(
            "SELECT status, tx_hash, error_msg FROM withdrawals WHERE withdrawal_id = 'wd-1'"
        ).fetchone()

    assert balance == 89.0
    assert status == "processing"
    assert tx_hash == "0xunknown"
    assert error_msg == "manual reconciliation required"


def test_process_withdrawal_claims_pending_row_once_before_debit(tmp_path, monkeypatch):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 100.0)")
        conn.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination, status, created_at
            ) VALUES ('wd-1', 'miner-1', 10.0, 1.0, 'dest', 'pending', 1)
        """)

    broadcasts = []

    class CountingWorker(PayoutWorker):
        def execute_withdrawal(self, withdrawal):
            broadcasts.append(withdrawal["withdrawal_id"])
            return f"tx-{len(broadcasts)}"

    monkeypatch.setattr(payout_worker, "MOCK_MODE", True)
    withdrawal = {
        "withdrawal_id": "wd-1",
        "miner_pk": "miner-1",
        "amount": 10.0,
        "fee": 1.0,
        "destination": "dest",
        "created_at": 1,
    }

    first = CountingWorker()
    first.db_path = str(db_path)
    second = CountingWorker()
    second.db_path = str(db_path)

    assert first.process_withdrawal(withdrawal) is True
    assert second.process_withdrawal(withdrawal) is False

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]
        status, tx_hash = conn.execute(
            "SELECT status, tx_hash FROM withdrawals WHERE withdrawal_id = 'wd-1'"
        ).fetchone()

    assert broadcasts == ["wd-1"]
    assert balance == 89.0
    assert status == "completed"
    assert tx_hash == "tx-1"
