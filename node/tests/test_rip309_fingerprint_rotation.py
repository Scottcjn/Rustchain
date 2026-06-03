"""
RIP-309 Phase 1: Fingerprint Check Rotation Tests
====================================================

Tests for 4-of-6 rotating fingerprint checks per epoch.
"""

import hashlib
import json
import os
import random
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from rip_200_round_robin_1cpu1vote import calculate_epoch_rewards_time_aged, GENESIS_TIMESTAMP
from rip_309_measurement_rotation import (
    ALL_FP_CHECKS,
    evaluate_fingerprint_rotation,
    get_epoch_measurement_config,
    get_reward_active_fingerprint_checks,
)


def _legacy_reward_active_checks(prev_block_hash):
    fp_checks = ['clock_drift', 'cache_timing', 'simd_identity',
                 'thermal_drift', 'instruction_jitter', 'anti_emulation']
    if prev_block_hash:
        nonce = hashlib.sha256(prev_block_hash + b"measurement_nonce").digest()
        seed = int.from_bytes(nonce[:4], 'big')
        return set(random.Random(seed).sample(fp_checks, 4))
    return set(fp_checks)


def _init_db(conn):
    conn.execute("""
        CREATE TABLE epoch_enroll (
            epoch INTEGER,
            miner_pk TEXT,
            weight INTEGER DEFAULT 100
        )
    """)
    conn.execute("""
        CREATE TABLE miner_attest_recent (
            miner TEXT PRIMARY KEY,
            device_arch TEXT,
            ts_ok INTEGER,
            fingerprint_passed INTEGER DEFAULT 1,
            entropy_score REAL,
            fingerprint_checks_json TEXT
        )
    """)
    conn.commit()


def _insert_miner(conn, miner, device_arch="x86_64", passed_all=True, checks=None):
    ts = GENESIS_TIMESTAMP + 1000
    if checks is None:
        checks = {
            "clock_drift": passed_all,
            "cache_timing": passed_all,
            "simd_identity": passed_all,
            "thermal_drift": passed_all,
            "instruction_jitter": passed_all,
            "anti_emulation": passed_all,
        }
    conn.execute(
        "INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, fingerprint_checks_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (miner, device_arch, ts, 1 if passed_all else 0, json.dumps(checks))
    )
    conn.commit()


def _enroll_miner(conn, epoch, miner, weight=100):
    conn.execute(
        "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
        (epoch, miner, weight)
    )
    conn.commit()


class TestRip309Rotation(unittest.TestCase):

    def _fresh_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        _init_db(conn)
        conn.close()
        return path

    def test_determinism_same_hash(self):
        """Same block hash must produce the same active check set."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        _insert_miner(conn, "alice", passed_all=True)
        conn.close()

        prev_hash = b"deadbeef" * 4
        results = []
        for _ in range(5):
            rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, prev_hash)
            results.append(rewards)

        # All identical
        self.assertEqual(len(set(tuple(sorted(r.items())) for r in results)), 1)
        os.unlink(db_path)

    def test_helper_matches_current_inline_reward_algorithm_golden_vectors(self):
        """Canonical helper must preserve current reward-path selection."""
        sample_hashes = [
            b"deadbeef" * 4,
            hashlib.sha256(b"epoch-1").digest(),
            hashlib.sha256(b"epoch-2").digest(),
            hashlib.sha256(b"epoch-309").digest(),
            bytes.fromhex("00" * 32),
            bytes.fromhex("ff" * 32),
        ]

        for prev_hash in sample_hashes:
            expected = _legacy_reward_active_checks(prev_hash)
            actual = set(get_reward_active_fingerprint_checks(prev_hash))
            self.assertEqual(actual, expected, prev_hash.hex())

    def test_helper_preserves_empty_hash_all_checks_fallback(self):
        """Empty prev_block_hash must keep all six checks active."""
        self.assertEqual(
            set(get_reward_active_fingerprint_checks(b"")),
            set(ALL_FP_CHECKS),
        )

    def test_epoch_measurement_config_matches_reward_golden_vectors(self):
        """The public config helper must not drift from reward selection."""
        sample_hashes = [
            hashlib.sha256(b"config-1").digest(),
            hashlib.sha256(b"config-2").digest(),
            bytes.fromhex("11" * 32),
        ]

        for prev_hash in sample_hashes:
            config = get_epoch_measurement_config(prev_hash.hex(), 7)
            self.assertEqual(
                set(config["active_fingerprints"]),
                _legacy_reward_active_checks(prev_hash),
            )

    def test_epoch_measurement_config_empty_hash_uses_all_checks(self):
        """The public config helper must preserve no-prev-hash fallback too."""
        config = get_epoch_measurement_config("", 0)
        self.assertEqual(set(config["active_fingerprints"]), set(ALL_FP_CHECKS))
        self.assertEqual(config["inactive_fingerprints"], [])

    def test_unpredictability_different_hashes(self):
        """Different block hashes should produce different active sets over many trials."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        # 4 passed, 2 failed => possible to select all 4 passed checks
        checks = {
            "clock_drift": True, "cache_timing": True, "simd_identity": True,
            "thermal_drift": True, "instruction_jitter": False, "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        selections = set()
        for i in range(100):
            h = hashlib.sha256(str(i).encode()).digest()
            rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, h)
            selections.add(rewards.get("alice", 0))

        self.assertTrue(0 in selections and max(selections) > 0,
                        f"Expected mixed rewards across hashes, got {selections}")
        os.unlink(db_path)

    def test_only_active_checks_affect_weight(self):
        """A miner failing only inactive checks should still receive rewards."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        checks = {
            "clock_drift": True, "cache_timing": True, "simd_identity": True,
            "thermal_drift": True, "instruction_jitter": True, "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        for i in range(1000):
            h = hashlib.sha256(str(i).encode()).digest()
            fp_checks = ['clock_drift', 'cache_timing', 'simd_identity',
                         'thermal_drift', 'instruction_jitter', 'anti_emulation']
            seed = int.from_bytes(hashlib.sha256(h + b"measurement_nonce").digest()[:4], 'big')
            active = set(random.Random(seed).sample(fp_checks, 4))
            if "anti_emulation" not in active:
                rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, h)
                self.assertGreater(rewards.get("alice", 0), 0,
                                   "Alice should receive rewards when failing check is inactive")
                os.unlink(db_path)
                return

        os.unlink(db_path)
        self.fail("Could not find a hash where anti_emulation was inactive in 1000 attempts")

    def test_active_failure_zeroes_reward(self):
        """A miner failing an active check should get zero rewards."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        checks = {
            "clock_drift": True, "cache_timing": True, "simd_identity": True,
            "thermal_drift": True, "instruction_jitter": True, "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        for i in range(1000):
            h = hashlib.sha256(str(i).encode()).digest()
            fp_checks = ['clock_drift', 'cache_timing', 'simd_identity',
                         'thermal_drift', 'instruction_jitter', 'anti_emulation']
            seed = int.from_bytes(hashlib.sha256(h + b"measurement_nonce").digest()[:4], 'big')
            active = set(random.Random(seed).sample(fp_checks, 4))
            if "anti_emulation" in active:
                rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, h)
                self.assertEqual(rewards.get("alice", 0), 0,
                                 "Alice should get zero rewards when failing check is active")
                os.unlink(db_path)
                return

        os.unlink(db_path)
        self.fail("Could not find a hash where anti_emulation was active in 1000 attempts")

    def test_fallback_all_checks_when_no_prev_hash(self):
        """When prev_block_hash is empty, all checks are active (backward compat)."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        checks = {
            "clock_drift": True, "cache_timing": True, "simd_identity": True,
            "thermal_drift": True, "instruction_jitter": True, "anti_emulation": True,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, b"")
        self.assertGreater(rewards.get("alice", 0), 0)
        os.unlink(db_path)

    def test_fallback_empty_prev_hash_failed_check_zeroes_reward(self):
        """The empty-hash fallback must evaluate every check, not a 4-of-6 subset."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        checks = {
            "clock_drift": True, "cache_timing": True, "simd_identity": True,
            "thermal_drift": True, "instruction_jitter": True, "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, b"")
        self.assertEqual(rewards.get("alice", 0), 0)
        os.unlink(db_path)

    def test_simd_bias_alias_accepts_simd_identity_payloads(self):
        """RIP-309 helpers must bridge issue wording and emitted fingerprint keys."""
        fingerprint = {
            "checks": {
                "simd_identity": {"passed": True},
            },
        }

        passed, active_passed, active_total = evaluate_fingerprint_rotation(
            fingerprint,
            ["simd_bias"],
        )

        self.assertTrue(passed)
        self.assertEqual(active_passed, 1)
        self.assertEqual(active_total, 1)


if __name__ == "__main__":
    unittest.main()
