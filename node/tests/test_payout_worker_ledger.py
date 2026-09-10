# SPDX-License-Identifier: MIT
"""Regression tests for the payout-worker ledger correctness fix (#2, 2026-09-10).

The RTC balance is debited (amount + fee) at REQUEST time by the node against the
canonical `balances` ledger. The worker must therefore:
  * NOT debit again (the old code debited a phantom `accounts` table = latent
    double-debit),
  * on successful broadcast, leave `balances` untouched (already debited),
  * on pre-broadcast failure, REFUND amount + fee back to `balances`, exactly once.
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKER_PATH = os.path.join(NODE_DIR, "payout_worker.py")


def _load_worker(db_path, mock=True):
    os.environ["RUSTCHAIN_MOCK_MODE"] = "1" if mock else "0"
    spec = importlib.util.spec_from_file_location(f"payout_worker_test_{id(db_path)}", WORKER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = db_path
    return mod


class TestPayoutWorkerLedger(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        with sqlite3.connect(self.db_path) as conn:
            # canonical integer micro-RTC schema
            conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)")
            conn.execute("""CREATE TABLE withdrawals (withdrawal_id TEXT PRIMARY KEY, miner_pk TEXT NOT NULL,
                amount REAL NOT NULL, fee REAL NOT NULL, destination TEXT NOT NULL, signature TEXT DEFAULT '',
                status TEXT DEFAULT 'pending', created_at INTEGER NOT NULL, processed_at INTEGER,
                tx_hash TEXT, error_msg TEXT)""")
            # request-time debit already happened: wallet had 100, requested 10 (+0.01 fee) -> 89.99 left
            conn.execute("INSERT INTO balances VALUES ('minerA', ?)", (int(round(89.99 * 1_000_000)),))
            conn.execute("""INSERT INTO withdrawals (withdrawal_id, miner_pk, amount, fee, destination, status, created_at)
                VALUES ('w1', 'minerA', 10.0, 0.01, 'dest', 'pending', ?)""", (int(time.time()),))

    def tearDown(self):
        os.environ.pop("RUSTCHAIN_MOCK_MODE", None)
        try:
            os.unlink(self.db_path)
        except (FileNotFoundError, PermissionError):
            pass

    def _balance_micro(self, miner_id="minerA"):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (miner_id,)).fetchone()
        return row[0] if row else None

    def _status(self, wid="w1"):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT status FROM withdrawals WHERE withdrawal_id=?", (wid,)).fetchone()[0]

    def test_worker_does_not_have_accounts_table_reference(self):
        """The phantom `accounts` table must not be queried anywhere in the worker."""
        src = open(WORKER_PATH).read()
        # allow the word only inside comments; assert no SQL touches it
        for kw in ("FROM accounts", "UPDATE accounts", "INTO accounts"):
            self.assertNotIn(kw, src, f"worker still references phantom table via {kw!r}")

    def test_successful_payout_does_not_double_debit(self):
        """On success the worker must leave `balances` exactly as the request-time
        debit left it (89.99) — no second deduction."""
        mod = _load_worker(self.db_path, mock=True)
        worker = mod.PayoutWorker()
        worker.execute_withdrawal = lambda w: "0xdeadbeef"  # force a successful broadcast
        ok = worker.process_withdrawal({
            "withdrawal_id": "w1", "miner_pk": "minerA", "amount": 10.0, "fee": 0.01, "destination": "dest",
        })
        self.assertTrue(ok)
        self.assertEqual(self._status(), "completed")
        self.assertEqual(self._balance_micro(), int(round(89.99 * 1_000_000)))  # unchanged by worker

    def test_pre_broadcast_failure_refunds_to_balances(self):
        """If broadcast fails before a tx hash, the request-time debit (amount+fee)
        is refunded to `balances`, and the row is marked failed."""
        mod = _load_worker(self.db_path, mock=True)
        worker = mod.PayoutWorker()

        def boom(_w):
            raise RuntimeError("broadcast down")

        worker.execute_withdrawal = boom
        ok = worker.process_withdrawal({
            "withdrawal_id": "w1", "miner_pk": "minerA", "amount": 10.0, "fee": 0.01, "destination": "dest",
        })
        self.assertFalse(ok)
        self.assertEqual(self._status(), "failed")
        # 89.99 + refund(10.01) == 100.00
        self.assertEqual(self._balance_micro(), int(round(100.0 * 1_000_000)))

    def test_refund_is_exactly_once(self):
        """A second process attempt on an already-failed row must not refund again."""
        mod = _load_worker(self.db_path, mock=True)
        worker = mod.PayoutWorker()
        worker.execute_withdrawal = lambda _w: (_ for _ in ()).throw(RuntimeError("down"))
        worker.process_withdrawal({"withdrawal_id": "w1", "miner_pk": "minerA", "amount": 10.0, "fee": 0.01, "destination": "dest"})
        after_first = self._balance_micro()
        # row is now 'failed'; a re-attempt can't re-claim (WHERE status='pending') -> no refund
        worker.process_withdrawal({"withdrawal_id": "w1", "miner_pk": "minerA", "amount": 10.0, "fee": 0.01, "destination": "dest"})
        self.assertEqual(self._balance_micro(), after_first)


if __name__ == "__main__":
    unittest.main()
