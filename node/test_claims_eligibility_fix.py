#!/usr/bin/env python3
"""
Test suite for Claims Eligibility Security Fix #3960
=====================================================
Tests the epoch settlement logic bypass vulnerability fix.

Vulnerability: is_epoch_settled() ignored db_path and used only time-based heuristic,
allowing claims for epochs that were never actually settled.

Fix: Check epoch_state.settled in database first, only fall back to time heuristic
when no record exists for the epoch.
"""

import sqlite3
import sys
import os
import tempfile
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claims_eligibility import is_epoch_settled


class TestEpochSettlementFix(unittest.TestCase):
    """Test the epoch settlement logic fix"""

    def setUp(self):
        """Create temporary database for each test"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def tearDown(self):
        """Clean up temporary database"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_epoch_state_table(self, schema='settled'):
        """Create epoch_state table with specified schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if schema == 'settled':
                cursor.execute("""
                    CREATE TABLE epoch_state (
                        epoch INTEGER PRIMARY KEY,
                        settled INTEGER DEFAULT 0,
                        settled_ts INTEGER
                    )
                """)
            elif schema == 'finalized':
                cursor.execute("""
                    CREATE TABLE epoch_state (
                        epoch INTEGER PRIMARY KEY,
                        accepted_blocks INTEGER DEFAULT 0,
                        finalized INTEGER DEFAULT 0
                    )
                """)
            conn.commit()

    def test_settled_epoch_in_database(self):
        """Test: epoch with settled=1 in database should return True"""
        self._create_epoch_state_table(schema='settled')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
                (100, 1700000000)
            )
        
        # Even though current_slot says epoch 100 is way in the past,
        # the database should be authoritative
        result = is_epoch_settled(self.db_path, epoch=100, current_slot=14400)
        self.assertTrue(result, "Settled epoch (settled=1) should return True")

    def test_unsettled_epoch_in_database(self):
        """Test: epoch with settled=0 in database should return False"""
        self._create_epoch_state_table(schema='settled')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 0, NULL)",
                (100,)
            )
        
        # Even though time heuristic would say it's settled, database says no
        result = is_epoch_settled(self.db_path, epoch=100, current_slot=14400)
        self.assertFalse(result, "Unsettled epoch (settled=0) should return False")

    def test_no_record_fallback_to_time_heuristic(self):
        """Test: no record in database should fall back to time heuristic"""
        self._create_epoch_state_table(schema='settled')
        
        # No record for epoch 100
        current_slot = 14400  # epoch 100
        settled_epoch = max(0, current_slot // 144 - 2)  # epoch 98
        
        # Epoch 98 should be settled (2 epochs in the past)
        result = is_epoch_settled(self.db_path, epoch=98, current_slot=current_slot)
        self.assertTrue(result, "Epoch 98 should be settled by time heuristic")
        
        # Epoch 100 should NOT be settled (current epoch)
        result = is_epoch_settled(self.db_path, epoch=100, current_slot=current_slot)
        self.assertFalse(result, "Current epoch should not be settled")

    def test_legacy_finalized_column(self):
        """Test: legacy 'finalized' column should work as fallback"""
        self._create_epoch_state_table(schema='finalized')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO epoch_state (epoch, accepted_blocks, finalized) VALUES (?, 5, 1)",
                (100,)
            )
        
        result = is_epoch_settled(self.db_path, epoch=100, current_slot=14400)
        self.assertTrue(result, "Finalized epoch (finalized=1) should return True")

    def test_legacy_unfinalized_epoch(self):
        """Test: legacy 'finalized=0' should return False"""
        self._create_epoch_state_table(schema='finalized')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO epoch_state (epoch, accepted_blocks, finalized) VALUES (?, 3, 0)",
                (100,)
            )
        
        result = is_epoch_settled(self.db_path, epoch=100, current_slot=14400)
        self.assertFalse(result, "Unfinalized epoch (finalized=0) should return False")

    def test_no_epoch_state_table(self):
        """Test: no epoch_state table should fall back to time heuristic"""
        # Don't create any table
        current_slot = 14400
        
        result = is_epoch_settled(self.db_path, epoch=98, current_slot=current_slot)
        self.assertTrue(result, "Should fall back to time heuristic")

    def test_database_unavailable(self):
        """Test: database errors should fall back to time heuristic"""
        # Use non-existent path
        result = is_epoch_settled('/nonexistent/path.db', epoch=98, current_slot=14400)
        self.assertTrue(result, "Should fall back to time heuristic on DB error")

    def test_attack_scenario_prevented(self):
        """
        Test the original attack scenario from #3960:
        
        1. Epoch N completes, but settle_epoch_rip200() fails (no eligible miners)
        2. epoch_state table has no row for epoch N
        3. After 2 epochs pass, old is_epoch_settled() returns True based on time alone
        4. Attacker submits claim for epoch N
        5. With fix: should NOT allow claim if settlement explicitly failed
        
        We simulate this by inserting a row with settled=0 (settlement ran but failed)
        """
        self._create_epoch_state_table(schema='settled')
        
        # Simulate: settlement ran but found no eligible miners, so settled=0
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 0, ?)",
                (95, 1700000000)
            )
        
        # Current slot is way past epoch 95, time heuristic would say it's settled
        current_slot = 14400  # epoch 100
        
        # With fix: should return False because database explicitly says settled=0
        result = is_epoch_settled(self.db_path, epoch=95, current_slot=current_slot)
        self.assertFalse(result, 
            "Attack prevented: epoch with settled=0 should NOT be considered settled "
            "even if time heuristic says it should be")

    def test_settlement_in_progress(self):
        """Test: epoch with no row (settlement hasn't run yet) uses time heuristic"""
        self._create_epoch_state_table(schema='settled')
        
        # No row for epoch 99 - settlement hasn't run yet
        current_slot = 14400  # epoch 100
        
        # Epoch 99 is only 1 epoch in the past, time heuristic says not settled
        result = is_epoch_settled(self.db_path, epoch=99, current_slot=current_slot)
        self.assertFalse(result, "Epoch without row should use time heuristic")


if __name__ == '__main__':
    unittest.main()
