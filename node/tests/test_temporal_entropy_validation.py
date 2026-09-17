#!/usr/bin/env python3
"""
Unit tests for Temporal Validation of Entropy Profiles (Issue #19 / Bounty 40 RTC).
Verifies:
1. Storage of snapshot history in miner_fingerprint_history table (up to 10 records).
2. Scoring and detection of 'FROZEN' deterministic emulator profiles (zero variance).
3. Scoring and detection of 'NOISY' randomized spoofed profiles (variance too high).
4. Validation and passing score for 'REAL' physical silicon with natural gentle drift.
"""

import os
import sys
import tempfile
import sqlite3
import unittest

NODE_DIR = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(NODE_DIR))

import hardware_fingerprint_replay as hfr


class TestTemporalEntropyValidation(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        os.environ['RUSTCHAIN_DB_PATH'] = self.db_path
        hfr.init_replay_defense_schema()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _make_sample_fingerprint(self, clock_cv=0.012, l2_l1=1.45, thermal_ratio=1.08, int_avg=1000, fp_avg=1250):
        return {
            'checks': {
                'clock_drift': {'passed': True, 'data': {'cv': clock_cv, 'drift_stdev': 15}},
                'cache_timing': {'passed': True, 'data': {'l2_l1_ratio': l2_l1, 'l3_l2_ratio': 1.8}},
                'thermal_drift': {'passed': True, 'data': {'drift_ratio': thermal_ratio}},
                'instruction_jitter': {'passed': True, 'data': {'int_avg_ns': int_avg, 'fp_avg_ns': fp_avg}},
                'simd_identity': {'passed': True, 'data': {'arch': 'x86_64', 'has_avx': True}}
            }
        }

    def test_snapshot_storage_and_pruning(self):
        miner_id = "test_miner_storage"
        wallet = "RTC_storage_wallet"
        
        # Store 15 snapshots
        for i in range(15):
            fp = self._make_sample_fingerprint(clock_cv=0.010 + i * 0.0001)
            hfr.store_fingerprint_snapshot(miner_id, wallet, fp, recorded_at=1000 + i)

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM miner_fingerprint_history WHERE miner_id = ?", (miner_id,))
            count = c.fetchone()[0]
            self.assertEqual(count, 10, "History must be pruned to max 10 snapshots per miner")

    def test_frozen_profile_detection(self):
        miner_id = "emulator_frozen_miner"
        wallet = "RTC_emulator_wallet"

        # Deterministic VM/emulator submitting identical float measurements across 8 attestations
        for i in range(8):
            fp = self._make_sample_fingerprint(clock_cv=0.015000, l2_l1=1.500, thermal_ratio=1.0000, int_avg=1000, fp_avg=1200)
            hfr.store_fingerprint_snapshot(miner_id, wallet, fp, recorded_at=2000 + i * 60)

        result = hfr.validate_temporal_consistency(miner_id, min_snapshots=5)
        self.assertEqual(result['status'], 'FROZEN')
        self.assertTrue(result['anomaly_detected'])
        self.assertTrue(result['flagged_for_review'])
        self.assertEqual(result['score'], 0.0)
        self.assertEqual(result['reason'], 'zero_variance_deterministic_emulation')

    def test_noisy_profile_detection(self):
        miner_id = "spoofed_noisy_miner"
        wallet = "RTC_spoofed_wallet"

        # Naive randomizer generating wild fluctuations to evade replay
        clock_cvs = [0.005, 0.085, 0.001, 0.095, 0.020, 0.090, 0.002]
        thermal_ratios = [0.5, 2.5, 0.8, 2.9, 0.6, 2.8, 0.7]

        for i in range(len(clock_cvs)):
            fp = self._make_sample_fingerprint(
                clock_cv=clock_cvs[i],
                thermal_ratio=thermal_ratios[i]
            )
            hfr.store_fingerprint_snapshot(miner_id, wallet, fp, recorded_at=3000 + i * 60)

        result = hfr.validate_temporal_consistency(miner_id, min_snapshots=5)
        self.assertEqual(result['status'], 'NOISY')
        self.assertTrue(result['anomaly_detected'])
        self.assertTrue(result['flagged_for_review'])
        self.assertEqual(result['score'], 0.2)

    def test_natural_silicon_drift_passes(self):
        miner_id = "real_physical_miner"
        wallet = "RTC_real_wallet"

        # Natural physical hardware: tight distribution with subtle thermal & load drift
        natural_cvs = [0.0121, 0.0124, 0.0122, 0.0125, 0.0123, 0.0126, 0.0124]
        natural_thermals = [1.082, 1.085, 1.081, 1.088, 1.084, 1.087, 1.083]

        for i in range(len(natural_cvs)):
            fp = self._make_sample_fingerprint(
                clock_cv=natural_cvs[i],
                thermal_ratio=natural_thermals[i]
            )
            hfr.store_fingerprint_snapshot(miner_id, wallet, fp, recorded_at=4000 + i * 60)

        result = hfr.validate_temporal_consistency(miner_id, min_snapshots=5)
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['anomaly_detected'])
        self.assertFalse(result['flagged_for_review'])
        self.assertGreaterEqual(result['score'], 0.8)
        self.assertEqual(result['reason'], 'natural_physical_silicon_drift')


if __name__ == '__main__':
    unittest.main()
