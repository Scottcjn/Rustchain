# SPDX-License-Identifier: MIT
"""Regression: payout worker must not refund funds it never debited.

process_withdrawal() debits balance inside a single BEGIN IMMEDIATE
transaction, then broadcasts. If ANY exception is raised on the debiting
path with no tx_hash yet, the outer handler credits ``amount + fee`` back to
the account -- assuming the debit happened. But the debit transaction can be
rolled back (e.g. SQLITE_BUSY at COMMIT under concurrency), in which case the
funds were never debited and the "refund" creates money out of thin air,
violating the module's own stated invariant ("cannot leave funds ... credited
without a matching debit").
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import payout_worker
from payout_worker import PayoutWorker


def _create_schema(conn):
    conn.execute(
        "CREATE TABLE accounts (public_key TEXT PRIMARY KEY, balance REAL NOT NULL)"
    )
    conn.execute(
        """
        CREATE TABLE withdrawals (
            withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT NOT NULL,
            amount REAL NOT NULL, fee REAL DEFAULT 0, destination TEXT,
            status TEXT NOT NULL, created_at INTEGER, processed_at INTEGER,
            tx_hash TEXT, error_msg TEXT
        )
        """
    )


class _FlakyConn:
    """Wraps a real connection; makes the debit transaction's COMMIT fail once.

    Models the realistic production case where the debit BEGIN IMMEDIATE
    transaction cannot commit (database busy/locked). The worker's own
    ``except`` then ROLLBACKs the debit -- so the funds were never debited.
    """

    def __init__(self, real, fail_flag):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_fail_flag", fail_flag)
        object.__setattr__(self, "_saw_debit", False)

    def execute(self, sql, *args):
        if "balance = balance - " in sql:
            object.__setattr__(self, "_saw_debit", True)
        if sql.strip() == "COMMIT" and self._saw_debit and self._fail_flag[0]:
            self._fail_flag[0] = False
            raise sqlite3.OperationalError("database is locked")
        return self._real.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def __enter__(self):
        self._real.__enter__()
        return self

    def __exit__(self, *exc):
        return self._real.__exit__(*exc)


def test_no_phantom_refund_when_debit_transaction_rolled_back(tmp_path, monkeypatch):
    db_path = tmp_path / "payout.db"
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute("INSERT INTO accounts VALUES ('miner-1', 100.0)")
        conn.execute(
            "INSERT INTO withdrawals "
            "(withdrawal_id, miner_pk, amount, fee, destination, status, created_at) "
            "VALUES ('wd-1', 'miner-1', 10.0, 1.0, 'dest', 'pending', 1)"
        )

    fail_flag = [True]
    real_connect = sqlite3.connect

    def flaky_connect(*a, **k):
        return _FlakyConn(real_connect(*a, **k), fail_flag)

    monkeypatch.setattr(payout_worker, "MOCK_MODE", True)
    monkeypatch.setattr(payout_worker.sqlite3, "connect", flaky_connect)

    worker = PayoutWorker()
    worker.db_path = str(db_path)

    result = worker.process_withdrawal(
        {
            "withdrawal_id": "wd-1",
            "miner_pk": "miner-1",
            "amount": 10.0,
            "fee": 1.0,
            "destination": "dest",
            "created_at": 1,
        }
    )

    assert result is False

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE public_key = 'miner-1'"
        ).fetchone()[0]

    # The debit was rolled back, so NO funds left the account and NO funds may
    # be refunded. Balance must be exactly the original 100.0, never inflated.
    assert balance == 100.0, f"phantom refund created money: balance={balance}"
