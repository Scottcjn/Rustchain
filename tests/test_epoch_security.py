// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import sqlite3
import tempfile
import os
import time
import threading
from unittest.mock import patch, MagicMock
import sys

# Import the modules we're testing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from node.rustchain_v2_integrated_v2_2_1_rip200 import RustChain
from rewards_implementation_rip200 import EpochManager

class TestEpochSecurity(unittest.TestCase):

    def setUp(self):
        """Set up test environment with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        # Initialize blockchain and epoch manager
        self.blockchain = RustChain(db_path=self.db_path)
        self.epoch_manager = EpochManager(db_path=self.db_path)

        # Set up test miners
        self.test_miners = [
            {'id': 'miner_001', 'hardware': 'GPU', 'multiplier': 2.0},
            {'id': 'miner_002', 'hardware': 'CPU', 'multiplier': 1.0},
            {'id': 'miner_003', 'hardware': 'ASIC', 'multiplier': 3.0}
        ]

        self._setup_test_data()

    def tearDown(self):
        """Clean up temporary database"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def _setup_test_data(self):
        """Initialize test database with realistic data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create miners table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS miners (
                    id TEXT PRIMARY KEY,
                    hardware_type TEXT,
                    multiplier REAL,
                    registered_at INTEGER
                )
            ''')

            # Create epoch_enrollments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS epoch_enrollments (
                    epoch_id INTEGER,
                    miner_id TEXT,
                    enrolled_at INTEGER,
                    PRIMARY KEY (epoch_id, miner_id)
                )
            ''')

            # Create attestations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attestations (
                    id INTEGER PRIMARY KEY,
                    epoch_id INTEGER,
                    miner_id TEXT,
                    attestation_data TEXT,
                    timestamp INTEGER,
                    verified BOOLEAN
                )
            ''')

            # Create settlements table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settlements (
                    epoch_id INTEGER PRIMARY KEY,
                    total_rewards REAL,
                    settled_at INTEGER,
                    status TEXT
                )
            ''')

            # Insert test miners
            for miner in self.test_miners:
                cursor.execute('''
                    INSERT OR REPLACE INTO miners (id, hardware_type, multiplier, registered_at)
                    VALUES (?, ?, ?, ?)
                ''', (miner['id'], miner['hardware'], miner['multiplier'], int(time.time())))

            conn.commit()

    def test_double_enrollment_prevention(self):
        """Test that miners cannot enroll in the same epoch twice"""
        epoch_id = 1001
        miner_id = 'miner_001'

        # First enrollment should succeed
        result1 = self.epoch_manager.enroll_miner(epoch_id, miner_id)
        self.assertTrue(result1)

        # Second enrollment should fail
        result2 = self.epoch_manager.enroll_miner(epoch_id, miner_id)
        self.assertFalse(result2)

        # Verify only one enrollment exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM epoch_enrollments
                WHERE epoch_id = ? AND miner_id = ?
            ''', (epoch_id, miner_id))
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_late_attestation_injection(self):
        """Test prevention of backdated attestations"""
        epoch_id = 1002
        miner_id = 'miner_002'
        current_time = int(time.time())

        # Enroll miner first
        self.epoch_manager.enroll_miner(epoch_id, miner_id)

        # Try to submit attestation with past timestamp
        backdated_time = current_time - 3600  # 1 hour ago
        result = self.epoch_manager.submit_attestation(
            epoch_id, miner_id, "test_attestation", backdated_time
        )

        # Should reject backdated attestation
        self.assertFalse(result)

        # Valid current attestation should work
        valid_result = self.epoch_manager.submit_attestation(
            epoch_id, miner_id, "valid_attestation", current_time
        )
        self.assertTrue(valid_result)

    def test_multiplier_manipulation_detection(self):
        """Test detection of multiplier manipulation attempts"""
        epoch_id = 1003
        miner_id = 'miner_003'

        # Get original multiplier
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT multiplier FROM miners WHERE id = ?', (miner_id,))
            original_multiplier = cursor.fetchone()[0]

        # Enroll with valid multiplier
        self.epoch_manager.enroll_miner(epoch_id, miner_id)

        # Attempt to modify multiplier mid-epoch
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE miners SET multiplier = ? WHERE id = ?
            ''', (original_multiplier * 2, miner_id))
            conn.commit()

        # Settlement should use enrollment-time multiplier, not current
        rewards = self.epoch_manager.calculate_epoch_rewards(epoch_id)

        # Verify multiplier wasn't inflated in rewards calculation
        expected_base_reward = 10.0  # Base reward per attestation
        expected_reward = expected_base_reward * original_multiplier

        self.assertAlmostEqual(rewards.get(miner_id, 0), expected_reward, places=2)

    def test_settlement_race_condition(self):
        """Test prevention of multiple reward claims during settlement"""
        epoch_id = 1004
        miner_id = 'miner_001'

        # Set up epoch with attestation
        self.epoch_manager.enroll_miner(epoch_id, miner_id)
        self.epoch_manager.submit_attestation(epoch_id, miner_id, "test_attestation")

        settlement_results = []

        def attempt_settlement():
            try:
                result = self.epoch_manager.settle_epoch(epoch_id)
                settlement_results.append(result)
            except Exception as e:
                settlement_results.append(str(e))

        # Launch multiple settlement attempts simultaneously
        threads = []
        for i in range(5):
            thread = threading.Thread(target=attempt_settlement)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Only one settlement should succeed
        successful_settlements = [r for r in settlement_results if r is not False and "already settled" not in str(r)]
        self.assertEqual(len(successful_settlements), 1)

        # Verify settlement status in database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM settlements WHERE epoch_id = ?', (epoch_id,))
            status = cursor.fetchone()
            self.assertIsNotNone(status)
            self.assertEqual(status[0], 'completed')

    def test_epoch_boundary_exploitation(self):
        """Test security during epoch transitions"""
        epoch_1 = 1005
        epoch_2 = 1006
        miner_id = 'miner_002'

        # Enroll in first epoch
        self.epoch_manager.enroll_miner(epoch_1, miner_id)

        # Simulate epoch transition timing attack
        transition_time = int(time.time())

        # Try to submit attestation for closed epoch
        late_attestation = self.epoch_manager.submit_attestation(
            epoch_1, miner_id, "late_attestation", transition_time + 100
        )

        # Should reject attestation for closed epoch
        self.assertFalse(late_attestation)

        # Try to enroll in next epoch before current is settled
        early_enrollment = self.epoch_manager.enroll_miner(epoch_2, miner_id)

        # Should allow enrollment in new epoch
        self.assertTrue(early_enrollment)

        # But shouldn't allow claiming rewards from unsettled epoch
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status FROM settlements WHERE epoch_id = ?
            ''', (epoch_1,))
            result = cursor.fetchone()
            # Epoch should not be auto-settled
            self.assertIsNone(result)

    def test_attestation_integrity_validation(self):
        """Test validation of attestation data integrity"""
        epoch_id = 1007
        miner_id = 'miner_003'

        self.epoch_manager.enroll_miner(epoch_id, miner_id)

        # Test various malformed attestations
        malformed_attestations = [
            "",  # Empty attestation
            "x" * 10000,  # Oversized attestation
            "invalid_json",  # Invalid format
            None,  # Null attestation
        ]

        for bad_attestation in malformed_attestations:
            result = self.epoch_manager.submit_attestation(
                epoch_id, miner_id, bad_attestation
            )
            self.assertFalse(result, f"Should reject attestation: {bad_attestation}")

    def test_miner_registration_validation(self):
        """Test validation during miner registration"""
        # Test registration with invalid hardware types
        invalid_miners = [
            {'id': 'fake_001', 'hardware': 'QUANTUM', 'multiplier': 100.0},
            {'id': 'fake_002', 'hardware': '', 'multiplier': 1.0},
            {'id': '', 'hardware': 'CPU', 'multiplier': 1.0},
        ]

        for invalid_miner in invalid_miners:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        INSERT INTO miners (id, hardware_type, multiplier, registered_at)
                        VALUES (?, ?, ?, ?)
                    ''', (invalid_miner['id'], invalid_miner['hardware'],
                          invalid_miner['multiplier'], int(time.time())))
                    conn.commit()
                    # If we get here, the insert succeeded when it shouldn't have
                    self.fail(f"Should reject invalid miner: {invalid_miner}")
                except sqlite3.IntegrityError:
                    # Expected behavior
                    pass

    def test_reward_calculation_bounds(self):
        """Test reward calculation doesn't exceed bounds"""
        epoch_id = 1008

        # Enroll all test miners
        for miner in self.test_miners:
            self.epoch_manager.enroll_miner(epoch_id, miner['id'])
            self.epoch_manager.submit_attestation(epoch_id, miner['id'], "valid_attestation")

        # Calculate rewards
        rewards = self.epoch_manager.calculate_epoch_rewards(epoch_id)

        # Verify total rewards don't exceed epoch budget
        total_distributed = sum(rewards.values())
        max_epoch_budget = 1000.0  # Assuming max budget

        self.assertLessEqual(total_distributed, max_epoch_budget)

        # Verify individual rewards are reasonable
        for miner_id, reward in rewards.items():
            self.assertGreater(reward, 0)
            self.assertLess(reward, max_epoch_budget / 2)  # No single miner gets >50%

    def test_sql_injection_protection(self):
        """Test protection against SQL injection attacks"""
        malicious_inputs = [
            "'; DROP TABLE miners; --",
            "1' OR '1'='1",
            "miner_001'; UPDATE miners SET multiplier = 999; --",
        ]

        epoch_id = 1009

        for malicious_input in malicious_inputs:
            # These operations should not cause SQL injection
            result1 = self.epoch_manager.enroll_miner(epoch_id, malicious_input)
            result2 = self.epoch_manager.submit_attestation(epoch_id, malicious_input, "test")

            # Operations might fail, but should not cause SQL injection
            # Verify miners table still exists and has expected data
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM miners')
                count = cursor.fetchone()[0]
                self.assertEqual(count, 3)  # Original test miners should still exist

if __name__ == '__main__':
    unittest.main()
