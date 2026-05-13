#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Genesis Migration TOCTOU Race Condition Fix — Regression Tests
Issue: #2819 — Red Team UTXO Implementation

Before the fix, ``migrate()`` called ``check_existing_genesis()`` on a
separate connection from the migration transaction.  Two concurrent
migrations could both pass the check and each create genesis boxes,
violating the determinism guarantee.

This module tests that the fix (genesis-existence check moved inside
the migrate transaction) prevents that window.

Severity: LOW (25 RTC)
"""

import os
import sqlite3
import tempfile
import threading
import time
import unittest
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import (
    migrate, check_existing_genesis, rollback_genesis,
    GENESIS_HEIGHT, ACCOUNT_TO_UTXO_SCALE,
)


def _seed_accounts(db_path):
    """Create the account-model table with two wallets."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS balances "
        "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO balances (miner_id, amount_i64) VALUES "
        "('alice', 100000000), ('bob', 50000000)"
    )
    conn.commit()
    conn.close()


class TestGenesisMigrationFix(unittest.TestCase):
    """Verify the genesis-existence check is inside the transaction."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _seed_accounts(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_fix_moves_check_inside_transaction(self):
        """After first migration, a second concurrent attempt is blocked."""
        # First migration succeeds
        result1 = migrate(self.db_path)
        self.assertNotIn('error', result1)

        utxo_db = UtxoDB(self.db_path)
        # check_existing_genesis now returns True (as before)
        self.assertTrue(check_existing_genesis(utxo_db))

        # The new path also detects existing genesis inside the transaction
        # and returns error — no double-creation.
        result2 = migrate(self.db_path)
        self.assertIn('error', result2)
        self.assertEqual(result2['error'], 'genesis_already_exists')

        # Verify exactly 2 genesis boxes (one per wallet), not 4
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM utxo_boxes WHERE creation_height = ?",
            (GENESIS_HEIGHT,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 2,
                         "Should have 2 genesis boxes, not duplicated")

    def test_concurrent_safety(self):
        """Two migrations started concurrently — only one may succeed."""

        results = []
        ready = threading.Barrier(2, timeout=10)

        def worker():
            ready.wait()  # both threads start together
            r = migrate(self.db_path)
            results.append(r)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(5)
        t2.join(5)

        successes = [r for r in results if 'error' not in r]
        failures = [r for r in results if 'error' in r]

        # Exactly one migration succeeds, one fails
        self.assertEqual(len(successes), 1,
                         f"Expected 1 success, got {len(successes)}: {results}")
        self.assertEqual(len(failures), 1,
                         f"Expected 1 failure, got {len(failures)}: {results}")

        # Verify no double-creation
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM utxo_boxes WHERE creation_height = ?",
            (GENESIS_HEIGHT,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 2,
                         "Concurrent migrations must not create duplicates")


if __name__ == '__main__':
    unittest.main()
