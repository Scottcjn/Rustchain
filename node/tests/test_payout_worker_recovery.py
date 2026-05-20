# SPDX-License-Identifier: MIT

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
