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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rip_200_round_robin_1cpu1vote import GENESIS_TIMESTAMP, calculate_epoch_rewards_time_aged


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
        (miner, device_arch, ts, 1 if passed_all else 0, json.dumps(checks)),
    )
    conn.commit()


def _enroll_miner(conn, epoch, miner, weight=100):
    conn.execute("INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)", (epoch, miner, weight))
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

    def test_unpredictability_different_hashes(self):
        """Different block hashes should produce different active sets over many trials."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        # 4 passed, 2 failed => possible to select all 4 passed checks
        checks = {
            "clock_drift": True,
            "cache_timing": True,
            "simd_identity": True,
            "thermal_drift": True,
            "instruction_jitter": False,
            "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        selections = set()
        for i in range(100):
            h = hashlib.sha256(str(i).encode()).digest()
            rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, h)
            selections.add(rewards.get("alice", 0))

        self.assertTrue(
            0 in selections and max(selections) > 0, f"Expected mixed rewards across hashes, got {selections}"
        )
        os.unlink(db_path)

    def test_only_active_checks_affect_weight(self):
        """A miner failing only inactive checks should still receive rewards."""
        db_path = self._fresh_db()
        conn = sqlite3.connect(db_path)
        _enroll_miner(conn, 1, "alice", 100)
        checks = {
            "clock_drift": True,
            "cache_timing": True,
            "simd_identity": True,
            "thermal_drift": True,
            "instruction_jitter": True,
            "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        for i in range(1000):
            h = hashlib.sha256(str(i).encode()).digest()
            fp_checks = [
                "clock_drift",
                "cache_timing",
                "simd_identity",
                "thermal_drift",
                "instruction_jitter",
                "anti_emulation",
            ]
            seed = int.from_bytes(hashlib.sha256(h + b"measurement_nonce").digest()[:4], "big")
            active = set(random.Random(seed).sample(fp_checks, 4))
            if "anti_emulation" not in active:
                rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, h)
                self.assertGreater(
                    rewards.get("alice", 0), 0, "Alice should receive rewards when failing check is inactive"
                )
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
            "clock_drift": True,
            "cache_timing": True,
            "simd_identity": True,
            "thermal_drift": True,
            "instruction_jitter": True,
            "anti_emulation": False,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        for i in range(1000):
            h = hashlib.sha256(str(i).encode()).digest()
            fp_checks = [
                "clock_drift",
                "cache_timing",
                "simd_identity",
                "thermal_drift",
                "instruction_jitter",
                "anti_emulation",
            ]
            seed = int.from_bytes(hashlib.sha256(h + b"measurement_nonce").digest()[:4], "big")
            active = set(random.Random(seed).sample(fp_checks, 4))
            if "anti_emulation" in active:
                rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, h)
                self.assertEqual(
                    rewards.get("alice", 0), 0, "Alice should get zero rewards when failing check is active"
                )
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
            "clock_drift": True,
            "cache_timing": True,
            "simd_identity": True,
            "thermal_drift": True,
            "instruction_jitter": True,
            "anti_emulation": True,
        }
        _insert_miner(conn, "alice", checks=checks)
        conn.close()

        rewards = calculate_epoch_rewards_time_aged(db_path, 1, 1_000_000, 200, b"")
        self.assertGreater(rewards.get("alice", 0), 0)
        os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
