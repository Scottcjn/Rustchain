# SPDX-License-Identifier: MIT
"""
PoC: lock_ledger.create_lock/release_lock 500 on schema-A nodes.

Schema A (legacy):  balances(miner_pk TEXT PRIMARY KEY, balance_rtc REAL)
Schema B (current): balances(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)

init_db() bootstraps a fresh node with schema A ("NOTE: Production DBs may
already have a different balances schema; this table is additive."), while
lock_ledger.py was written assuming schema B unconditionally. Before the fix,
create_lock()/release_lock() ran `UPDATE balances SET amount_i64 = ... WHERE
miner_id = ?` against a schema-A table, which raises sqlite3.OperationalError
(no such column: miner_id/amount_i64). The outer `except sqlite3.Error` turns
that into a plain "Database error", so a schema-A node can never lock or
release a bridge deposit -- exactly the class of bug governance.py's
_balance_rtc_for_miner / _deduct_proposal_fee were already fixed for.

After the fix, _balances_columns/_ensure_balance_row/_adjust_balance_i64/
_read_balance_i64 probe the live table and use whichever column pair it
actually has, so both schemas work.
"""

import sqlite3
import time
import unittest

import lock_ledger


def _schema_a_db(miner_id: str, balance_rtc: float) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
        (miner_id, balance_rtc),
    )
    conn.execute(
        """
        CREATE TABLE lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bridge_transfer_id INTEGER,
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            lock_type TEXT NOT NULL,
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER NOT NULL,
            unlocked_at INTEGER,
            status TEXT NOT NULL DEFAULT 'locked',
            created_at INTEGER NOT NULL,
            released_by TEXT,
            release_tx_hash TEXT
        )
        """
    )
    conn.commit()
    return conn


def _schema_b_db(miner_id: str, amount_i64: int) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
        (miner_id, amount_i64),
    )
    conn.execute(
        """
        CREATE TABLE lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bridge_transfer_id INTEGER,
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            lock_type TEXT NOT NULL,
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER NOT NULL,
            unlocked_at INTEGER,
            status TEXT NOT NULL DEFAULT 'locked',
            created_at INTEGER NOT NULL,
            released_by TEXT,
            release_tx_hash TEXT
        )
        """
    )
    conn.commit()
    return conn


class TestCreateLockBothSchemas(unittest.TestCase):

    def test_schema_a_create_lock_debits_and_succeeds(self):
        conn = _schema_a_db("deadbeef01", 50.0)
        ok, result = lock_ledger.create_lock(
            conn, "deadbeef01", 10_000_000, "bridge_deposit",
            unlock_at=int(time.time()) + 3600,
        )
        self.assertTrue(ok, result)
        row = conn.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?", ("deadbeef01",)
        ).fetchone()
        self.assertAlmostEqual(row[0], 40.0)
        conn.close()

    def test_schema_b_create_lock_debits_and_succeeds(self):
        conn = _schema_b_db("deadbeef01", 50_000_000)
        ok, result = lock_ledger.create_lock(
            conn, "deadbeef01", 10_000_000, "bridge_deposit",
            unlock_at=int(time.time()) + 3600,
        )
        self.assertTrue(ok, result)
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", ("deadbeef01",)
        ).fetchone()
        self.assertEqual(row[0], 40_000_000)
        conn.close()

    def test_schema_a_insufficient_balance_rolls_back(self):
        conn = _schema_a_db("deadbeef01", 1.0)
        ok, result = lock_ledger.create_lock(
            conn, "deadbeef01", 10_000_000, "bridge_deposit",
            unlock_at=int(time.time()) + 3600,
        )
        self.assertFalse(ok)
        self.assertIn("insufficient", result.get("error", "").lower())
        row = conn.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?", ("deadbeef01",)
        ).fetchone()
        self.assertAlmostEqual(row[0], 1.0)
        conn.close()


class TestReleaseLockBothSchemas(unittest.TestCase):

    def _create_then_release(self, conn, expect_col, expect_table_key):
        ok, created = lock_ledger.create_lock(
            conn, "deadbeef01", 10_000_000, "bridge_deposit",
            unlock_at=int(time.time()) + 3600,
        )
        self.assertTrue(ok, created)
        ok, released = lock_ledger.release_lock(
            conn, created["lock_id"], released_by="admin",
        )
        self.assertTrue(ok, released)
        return released

    def test_schema_a_release_lock_credits_back(self):
        conn = _schema_a_db("deadbeef01", 50.0)
        self._create_then_release(conn, "balance_rtc", "miner_pk")
        row = conn.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?", ("deadbeef01",)
        ).fetchone()
        self.assertAlmostEqual(row[0], 50.0)  # back to original after debit+credit
        conn.close()

    def test_schema_b_release_lock_credits_back(self):
        conn = _schema_b_db("deadbeef01", 50_000_000)
        self._create_then_release(conn, "amount_i64", "miner_id")
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", ("deadbeef01",)
        ).fetchone()
        self.assertEqual(row[0], 50_000_000)
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
