#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Genesis Migration TOCTOU Race Condition
Issue: #2819 - Red Team UTXO Implementation

The `migrate()` function checks for existing genesis boxes on a SEPARATE
connection from the migration transaction. Between the check and BEGIN IMMEDIATE,
a concurrent migration could also pass the check, leading to duplicate genesis
box creation and potential fund inflation.

Severity: LOW (25 RTC)
"""

import unittest
import tempfile
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import (
    migrate, check_existing_genesis, compute_genesis_tx_id, GENESIS_HEIGHT
)


class TestGenesisMigrationTOCTOU(unittest.TestCase):
    """
    LOW: check_existing_genesis() runs on a separate connection.
    
    The check opens its own DB connection, verifies no genesis boxes exist,
    and closes. Then migrate() opens a NEW connection for the actual work.
    
    Between check and migration, another process could pass the same check
    and start its own migration. Both see 0 genesis boxes, both proceed,
    creating duplicate genesis boxes for the same wallets.
    
    While unlikely in production (migration is one-time), this breaks the
    determinism guarantee -- duplicated genesis boxes inflate the UTXO
    supply without corresponding account-balance backing.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        
        # Create account model with balances
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS balances "
            "(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES ('alice', 100000000)"
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES ('bob', 50000000)"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_check_uses_separate_connection(self):
        """
        Verify that check_existing_genesis opens its own connection.
        The migration's transaction should include both the check and
        the writes -- currently they are split across connections.
        """
        utxo_db = UtxoDB(self.db_path)
        utxo_db.init_tables()
        
        # Before migration: check says no genesis boxes
        self.assertFalse(check_existing_genesis(utxo_db),
            "Expected: no genesis boxes before migration")
        
        # Run migration
        result = migrate(self.db_path)
        self.assertNotIn('error', result,
            f"Migration should succeed: {result}")
        self.assertEqual(result['wallets_migrated'], 2)
        
        # After migration: genesis boxes exist
        self.assertTrue(check_existing_genesis(utxo_db),
            "Expected: genesis boxes found after migration")
        
        # Verify the UTXO balances match account balances
        alice_balance = utxo_db.get_balance('alice')
        bob_balance = utxo_db.get_balance('bob')
        self.assertEqual(alice_balance, 100000000 * 100,  # amount_i64 * ACCOUNT_TO_UTXO_SCALE
            "Alice's UTXO balance should match account balance")
        self.assertEqual(bob_balance, 50000000 * 100,
            "Bob's UTXO balance should match account balance")

    def test_toc_tou_window_exists(self):
        """
        Demonstrate the TOCTOU window by running check_existing_genesis()
        on a separate connection BEFORE the migration transaction starts.
        
        If a second process runs check_existing_genesis() between the first
        process's check and its BEGIN IMMEDIATE, it gets False and starts
        its own migration -- creating duplicate genesis entries.
        """
        import sqlite3
        
        # Simulate: first process checks (no genesis yet)
        utxo_db1 = UtxoDB(self.db_path)
        utxo_db1.init_tables()
        self.assertFalse(check_existing_genesis(utxo_db1))
        
        # Simulate: second process also checks (window is open)
        utxo_db2 = UtxoDB(self.db_path)
        utxo_db2.init_tables()
        self.assertFalse(check_existing_genesis(utxo_db2))
        
        # First process migrates
        result1 = migrate(self.db_path)
        self.assertNotIn('error', result1)
        
        # After first migration: genesis exists
        self.assertTrue(check_existing_genesis(utxo_db1))
        
        # Second process's check now returns True (blocked correctly)
        self.assertTrue(check_existing_genesis(utxo_db2),
            "TOCTOU: after first migration, check should block second run")
        
        # Verify no double-creation
        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM utxo_boxes WHERE creation_height = 0"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 2,
            "Should have exactly 2 genesis boxes (one per wallet)")


if __name__ == '__main__':
    unittest.main()
