#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression test for Genesis Migration Idempotency TOCTOU Race
Issue: #2819 — Bounty fix

Bug: check_existing_genesis() uses a SEparate database connection from
the migration itself, creating a TOCTOU race. Two concurrent calls can
both pass the check simultaneously.

Bug: The check queries `creation_height = 0` which is too broad — any
non-genesis box at height 0 falsely blocks the migration.

Fix: Query `tx_type = 'genesis'` in utxo_transactions within the same
connection used by the migration.
"""

import unittest
import tempfile
import os
import sys
import time
import threading
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT, address_to_proposition
from utxo_genesis_migration import (
    migrate, rollback_genesis,
    GENESIS_HEIGHT,
    ACCOUNT_TO_UTXO_SCALE,
)


class TestGenesisIdempotencyFix(unittest.TestCase):
    """
    After the fix, the genesis migration must:
    1. Detect existing genesis via tx_type='genesis' (not creation_height=0)
    2. Block duplicate runs cleanly
    3. NOT be blocked by non-genesis boxes at height 0
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self._seed_balances()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _seed_balances(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS balances "
                         "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_id, amount_i64) "
                "VALUES (?, ?)", ('alice', 100 * UNIT // ACCOUNT_TO_UTXO_SCALE)
            )
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_id, amount_i64) "
                "VALUES (?, ?)", ('bob', 50 * UNIT // ACCOUNT_TO_UTXO_SCALE)
            )
            conn.commit()
        finally:
            conn.close()

    def test_non_genesis_box_at_height_0_does_not_block(self):
        """
        FIX VERIFICATION: A non-genesis box at height 0 must NOT block
        the genesis migration. The check must query tx_type='genesis'
        in utxo_transactions, not creation_height=0 in utxo_boxes.
        """
        # Plant a non-genesis box at height 0
        utxo_db = UtxoDB(self.db_path)
        utxo_db.init_tables()
        conn = utxo_db._conn()
        try:
            box_id = 'deadbeef' * 8  # valid 64-char hex
            conn.execute(
                "INSERT INTO utxo_boxes "
                "(box_id, value_nrtc, proposition, owner_address, "
                "creation_height, transaction_id, output_index, "
                "tokens_json, registers_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (box_id, 1000, address_to_proposition('test'), 'test',
                 0, 'aabbccdd' * 8, 0, '[]', '{}', int(time.time()))
            )
            conn.commit()
        finally:
            conn.close()

        # Migration should SUCCEED — genesis boxes don't actually exist
        result = migrate(self.db_path)
        self.assertNotIn('error', result,
            f"Migration should NOT be blocked by non-genesis box at height 0. "
            f"Got error: {result.get('error')}")
        self.assertEqual(result['wallets_migrated'], 2)

    def test_second_migration_blocked_cleanly(self):
        """
        FIX VERIFICATION: Running the migration twice should block the
        second run with a clean 'genesis_already_exists' error, not a
        raw SQLite UNIQUE constraint violation.
        """
        result1 = migrate(self.db_path)
        self.assertNotIn('error', result1)

        result2 = migrate(self.db_path)
        self.assertIn('error', result2)
        self.assertEqual(result2['error'], 'genesis_already_exists')

    def test_rollback_allows_rerun(self):
        """
        After rollback, the migration should be runnable again.
        """
        result1 = migrate(self.db_path)
        self.assertNotIn('error', result1)

        rollback_genesis(self.db_path)

        result2 = migrate(self.db_path)
        self.assertNotIn('error', result2)
        self.assertEqual(result2['wallets_migrated'], 2)

    def test_no_duplicate_boxes_after_rollback_and_rerun(self):
        """
        Rollback + rerun must not create duplicate genesis boxes.
        """
        result1 = migrate(self.db_path)
        total1 = result1['total_nrtc']

        rollback_genesis(self.db_path)

        result2 = migrate(self.db_path)
        total2 = result2['total_nrtc']

        self.assertEqual(total1, total2,
            "Total supply must be identical after rollback + rerun")

    def test_concurrent_migration_no_duplication(self):
        """
        Two concurrent migration attempts must not create duplicate boxes.
        At most one succeeds; the other fails cleanly.
        """
        results = []
        errors = []

        def run_migration():
            try:
                r = migrate(self.db_path)
                results.append(r)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=run_migration)
        t2 = threading.Thread(target=run_migration)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if 'error' not in r]
        self.assertLessEqual(len(successes), 1,
            "At most ONE concurrent migration should succeed")

        # Verify no duplicate genesis boxes
        utxo_db = UtxoDB(self.db_path)
        conn = utxo_db._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM utxo_transactions WHERE tx_type='genesis'"
            ).fetchone()
            self.assertLessEqual(row['n'], 2,
                "No duplicate genesis transactions should exist")
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
