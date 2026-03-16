#!/usr/bin/env python3
"""
Issue #1449: Anti-Double-Mining Comprehensive Tests
====================================================

Tests for:
1. Same identity multiple miner IDs in same epoch (only one rewarded)
2. Different identities unaffected (each rewarded normally)
3. Idempotent re-runs (same result on repeated settlement)
4. False positive prevention (legitimate distinct machines work correctly)
5. Edge cases (fingerprint failures, missing data, etc.)
"""

import sqlite3
import time
import json
import os
import sys
import unittest
from typing import Dict, List

# Add node directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anti_double_mining import (
    compute_machine_identity_hash,
    normalize_fingerprint,
    detect_duplicate_identities,
    select_representative_miner,
    get_epoch_miner_groups,
    calculate_anti_double_mining_rewards,
    setup_test_scenario
)


class TestMachineIdentity(unittest.TestCase):
    """Test machine identity computation and hashing."""
    
    def test_same_fingerprint_same_identity(self):
        """Same fingerprint profile should produce same identity hash."""
        fingerprint = {
            "checks": {
                "clock_drift": {"data": {"cv": 0.001, "mean_ns": 100.0}},
                "cpu_serial": {"data": {"serial": "SERIAL-12345"}}
            }
        }
        
        hash1 = compute_machine_identity_hash("g4", fingerprint)
        hash2 = compute_machine_identity_hash("g4", fingerprint)
        
        self.assertEqual(hash1, hash2, "Same fingerprint should produce same hash")
    
    def test_different_fingerprint_different_identity(self):
        """Different fingerprint profiles should produce different identity hashes."""
        fingerprint1 = {
            "checks": {
                "clock_drift": {"data": {"cv": 0.001, "mean_ns": 100.0}},
                "cpu_serial": {"data": {"serial": "SERIAL-A"}}
            }
        }
        fingerprint2 = {
            "checks": {
                "clock_drift": {"data": {"cv": 0.002, "mean_ns": 200.0}},
                "cpu_serial": {"data": {"serial": "SERIAL-B"}}
            }
        }
        
        hash1 = compute_machine_identity_hash("g4", fingerprint1)
        hash2 = compute_machine_identity_hash("g4", fingerprint2)
        
        self.assertNotEqual(hash1, hash2, "Different fingerprints should produce different hashes")
    
    def test_different_arch_different_identity(self):
        """Same fingerprint but different arch should produce different identity."""
        fingerprint = {
            "checks": {
                "clock_drift": {"data": {"cv": 0.001, "mean_ns": 100.0}}
            }
        }
        
        hash_g4 = compute_machine_identity_hash("g4", fingerprint)
        hash_g5 = compute_machine_identity_hash("g5", fingerprint)
        
        self.assertNotEqual(hash_g4, hash_g5, "Different arch should produce different hash")
    
    def test_empty_fingerprint_handling(self):
        """Empty fingerprint should be handled gracefully."""
        hash1 = compute_machine_identity_hash("g4", {})
        hash2 = compute_machine_identity_hash("g4", {})
        
        self.assertEqual(hash1, hash2, "Empty fingerprints should produce consistent hash")
    
    def test_normalize_fingerprint_extract_serial(self):
        """Fingerprint normalization should extract CPU serial."""
        fingerprint = {
            "checks": {
                "cpu_serial": {"data": {"serial": "TEST-SERIAL-123"}}
            }
        }
        
        normalized = normalize_fingerprint(fingerprint)
        self.assertIn("cpu_serial", normalized)
        self.assertEqual(normalized["cpu_serial"], "TEST-SERIAL-123")
    
    def test_normalize_fingerprint_extract_clock(self):
        """Fingerprint normalization should extract clock characteristics."""
        fingerprint = {
            "checks": {
                "clock_drift": {"data": {"cv": 0.001234, "mean_ns": 123.456}}
            }
        }
        
        normalized = normalize_fingerprint(fingerprint)
        self.assertIn("clock_cv", normalized)
        self.assertIn("clock_mean", normalized)


class TestDuplicateDetection(unittest.TestCase):
    """Test duplicate identity detection logic."""
    
    def setUp(self):
        """Create test database."""
        self.test_db = "/tmp/test_1449_duplicate_detection.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self._setup_tables()
    
    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def _setup_tables(self):
        """Create required tables."""
        self.conn.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE miner_fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL,
                ts INTEGER NOT NULL,
                profile_json TEXT NOT NULL
            )
        """)
    
    def test_detect_same_machine_multiple_miners(self):
        """Should detect same machine running multiple miner IDs."""
        epoch_start_ts = 1728000000
        current_ts = int(time.time())
        
        # Same fingerprint for 3 miners
        fingerprint = json.dumps({
            "checks": {
                "cpu_serial": {"data": {"serial": "SAME-MACHINE-123"}}
            }
        })
        
        miners = ["miner-a1", "miner-a2", "miner-a3"]
        for miner in miners:
            self.conn.execute("""
                INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
                VALUES (?, ?, ?, ?, ?)
            """, (miner, "g4", epoch_start_ts + 100, 1, 0.05))
            
            self.conn.execute("""
                INSERT INTO miner_fingerprint_history (miner, ts, profile_json)
                VALUES (?, ?, ?)
            """, (miner, current_ts, fingerprint))
        
        self.conn.commit()
        
        duplicates = detect_duplicate_identities(
            self.conn, epoch=0,
            epoch_start_ts=epoch_start_ts,
            epoch_end_ts=epoch_start_ts + 144 * 600
        )
        
        self.assertEqual(len(duplicates), 1, "Should detect 1 duplicate machine")
        self.assertEqual(len(duplicates[0].associated_miner_ids), 3, "Should have 3 miner IDs")
    
    def test_no_duplicates_distinct_machines(self):
        """Should not report duplicates for distinct machines."""
        epoch_start_ts = 1728000000
        current_ts = int(time.time())
        
        # Different fingerprints for 3 miners
        for i in range(3):
            fingerprint = json.dumps({
                "checks": {
                    "cpu_serial": {"data": {"serial": f"UNIQUE-MACHINE-{i}"}}
                }
            })
            
            miner_id = f"miner-{i}"
            self.conn.execute("""
                INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, "g4", epoch_start_ts + 100, 1, 0.05))
            
            self.conn.execute("""
                INSERT INTO miner_fingerprint_history (miner, ts, profile_json)
                VALUES (?, ?, ?)
            """, (miner_id, current_ts, fingerprint))
        
        self.conn.commit()
        
        duplicates = detect_duplicate_identities(
            self.conn, epoch=0,
            epoch_start_ts=epoch_start_ts,
            epoch_end_ts=epoch_start_ts + 144 * 600
        )
        
        self.assertEqual(len(duplicates), 0, "Should not detect duplicates for distinct machines")


class TestRepresentativeSelection(unittest.TestCase):
    """Test representative miner selection logic."""
    
    def setUp(self):
        """Create test database."""
        self.test_db = "/tmp/test_1449_representive.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self._setup_tables()
    
    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def _setup_tables(self):
        """Create required tables."""
        self.conn.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL
            )
        """)
    
    def test_select_highest_entropy(self):
        """Should select miner with highest entropy score."""
        miners = [
            ("miner-low", 0.03),
            ("miner-mid", 0.06),
            ("miner-high", 0.09)
        ]
        
        for miner_id, entropy in miners:
            self.conn.execute("""
                INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, entropy_score)
                VALUES (?, ?, ?, ?)
            """, (miner_id, "g4", 1728000000, entropy))
        
        self.conn.commit()
        
        selected = select_representative_miner(self.conn, [m[0] for m in miners])
        self.assertEqual(selected, "miner-high", "Should select highest entropy miner")
    
    def test_select_most_recent_on_tie(self):
        """Should select most recent attestation on entropy tie."""
        base_ts = 1728000000
        miners = [
            ("miner-old", base_ts),
            ("miner-new", base_ts + 1000)
        ]
        
        for miner_id, ts in miners:
            self.conn.execute("""
                INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, entropy_score)
                VALUES (?, ?, ?, ?)
            """, (miner_id, "g4", ts, 0.05))
        
        self.conn.commit()
        
        selected = select_representative_miner(self.conn, [m[0] for m in miners])
        self.assertEqual(selected, "miner-new", "Should select most recent on tie")
    
    def test_deterministic_alphabetic_tiebreaker(self):
        """Should use alphabetic order as deterministic tiebreaker."""
        miners = ["miner-z", "miner-a", "miner-m"]
        
        for miner_id in miners:
            self.conn.execute("""
                INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, entropy_score)
                VALUES (?, ?, ?, ?)
            """, (miner_id, "g4", 1728000000, 0.05))
        
        self.conn.commit()
        
        selected = select_representative_miner(self.conn, miners)
        self.assertEqual(selected, "miner-a", "Should select alphabetically first on full tie")


class TestAntiDoubleMiningRewards(unittest.TestCase):
    """Test complete anti-double-mining reward calculation."""
    
    def setUp(self):
        """Setup test scenario."""
        self.test_db = "/tmp/test_1449_rewards.db"
        setup_test_scenario(self.test_db)
    
    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_only_one_reward_per_machine(self):
        """Test that only one miner per machine receives reward."""
        current_slot = (int(time.time()) - 1728000000) // 600
        
        rewards, telemetry = calculate_anti_double_mining_rewards(
            self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
        )
        
        # Should have 3 machines (A, B, C) -> 3 rewards
        self.assertEqual(len(rewards), 3, "Should reward exactly 3 machines")
        
        # Machine A has 3 miners, only 1 should be rewarded
        machine_a_miners = ["miner-a1", "miner-a2", "miner-a3"]
        rewarded_from_a = [m for m in machine_a_miners if m in rewards]
        self.assertEqual(len(rewarded_from_a), 1, "Machine A should have exactly 1 rewarded miner")
        
        # Machine B has 1 miner, should be rewarded
        self.assertIn("miner-b1", rewards, "Machine B's single miner should be rewarded")
        
        # Machine C has 2 miners, only 1 should be rewarded
        machine_c_miners = ["miner-c1", "miner-c2"]
        rewarded_from_c = [m for m in machine_c_miners if m in rewards]
        self.assertEqual(len(rewarded_from_c), 1, "Machine C should have exactly 1 rewarded miner")
    
    def test_telemetry_reports_duplicates(self):
        """Test that telemetry correctly reports duplicate detections."""
        current_slot = (int(time.time()) - 1728000000) // 600
        
        _, telemetry = calculate_anti_double_mining_rewards(
            self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
        )
        
        self.assertEqual(telemetry["duplicate_machines_detected"], 2, "Should detect 2 duplicate machines")
        self.assertEqual(telemetry["duplicate_miner_ids_skipped"], 3, "Should skip 3 duplicate miner IDs")
    
    def test_different_identities_unaffected(self):
        """Test that distinct machines are rewarded independently."""
        current_slot = (int(time.time()) - 1728000000) // 600
        
        rewards, telemetry = calculate_anti_double_mining_rewards(
            self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
        )
        
        # Machine B is unique, should be rewarded
        self.assertIn("miner-b1", rewards)
        self.assertGreater(rewards["miner-b1"], 0, "Unique machine should receive positive reward")


class TestIdempotency(unittest.TestCase):
    """Test idempotent re-runs of reward calculation."""
    
    def setUp(self):
        """Setup test scenario."""
        self.test_db = "/tmp/test_1449_idempotent.db"
        setup_test_scenario(self.test_db)
    
    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_idempotent_reward_calculation(self):
        """Running reward calculation multiple times should give same result."""
        current_slot = (int(time.time()) - 1728000000) // 600
        
        # Run calculation 3 times
        results = []
        for _ in range(3):
            rewards, telemetry = calculate_anti_double_mining_rewards(
                self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
            )
            results.append((rewards, telemetry))
        
        # All results should be identical
        first_rewards = results[0][0]
        for i, (rewards, _) in enumerate(results[1:], 1):
            self.assertEqual(
                first_rewards, rewards,
                f"Run {i} should produce same rewards as run 0"
            )
    
    def test_idempotent_representative_selection(self):
        """Representative selection should be deterministic across runs."""
        current_slot = (int(time.time()) - 1728000000) // 600
        
        representatives = []
        for _ in range(5):
            rewards, _ = calculate_anti_double_mining_rewards(
                self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
            )
            representatives.append(set(rewards.keys()))
        
        # All runs should select same representatives
        for i, reps in enumerate(representatives[1:], 1):
            self.assertEqual(
                representatives[0], reps,
                f"Run {i} should select same representatives as run 0"
            )


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def setUp(self):
        """Create test database."""
        self.test_db = "/tmp/test_1449_edge.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self._setup_tables()
    
    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def _setup_tables(self):
        """Create required tables."""
        self.conn.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL,
                warthog_bonus REAL DEFAULT 1.0
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE miner_fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL,
                ts INTEGER NOT NULL,
                profile_json TEXT NOT NULL
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE epoch_state (
                epoch INTEGER PRIMARY KEY,
                settled INTEGER DEFAULT 0,
                settled_ts INTEGER
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER DEFAULT 0
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                epoch INTEGER,
                miner_id TEXT,
                delta_i64 INTEGER,
                reason TEXT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE epoch_rewards (
                epoch INTEGER,
                miner_id TEXT,
                share_i64 INTEGER,
                PRIMARY KEY (epoch, miner_id)
            )
        """)
    
    def test_fingerprint_failure_zero_weight(self):
        """Miners with failed fingerprint should get zero weight."""
        epoch_start_ts = 1728000000
        
        # One miner with fingerprint_passed=0
        self.conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-fail", "g4", epoch_start_ts, 0, 0.05))
        
        self.conn.commit()
        
        current_slot = (int(time.time()) - 1728000000) // 600
        rewards, _ = calculate_anti_double_mining_rewards(
            self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
        )
        
        # Failed fingerprint should not be rewarded
        self.assertNotIn("miner-fail", rewards, "Failed fingerprint should not receive reward")
    
    def test_missing_fingerprint_profile(self):
        """Missing fingerprint profile should be handled gracefully."""
        epoch_start_ts = 1728000000
        
        # Miner with no fingerprint history
        self.conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-no-fp", "g4", epoch_start_ts, 1, 0.05))
        
        self.conn.commit()
        
        current_slot = (int(time.time()) - 1728000000) // 600
        rewards, telemetry = calculate_anti_double_mining_rewards(
            self.test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
        )
        
        # Should still reward the miner (graceful degradation)
        self.assertIn("miner-no-fp", rewards, "Miner without fingerprint history should still be rewarded")
    
    def test_no_miners_in_epoch(self):
        """Empty epoch should return empty rewards."""
        current_slot = (int(time.time()) - 1728000000) // 600
        
        rewards, telemetry = calculate_anti_double_mining_rewards(
            self.test_db, epoch=999, total_reward_urtc=150_000_000, current_slot=current_slot
        )
        
        self.assertEqual(len(rewards), 0, "Empty epoch should have no rewards")


def run_tests():
    """Run all tests and print results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMachineIdentity))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestRepresentativeSelection))
    suite.addTests(loader.loadTestsFromTestCase(TestAntiDoubleMiningRewards))
    suite.addTests(loader.loadTestsFromTestCase(TestIdempotency))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
