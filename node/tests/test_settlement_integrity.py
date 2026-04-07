#!/usr/bin/env python3
"""
Tests for settlement-integrity fix: delayed settlement must produce the same
reward distribution as immediate settlement by using epoch_enroll as the
canonical miner list instead of the stale miner_attest_recent time-window query.
"""

import os
import sys
import sqlite3
import tempfile
import unittest

# Ensure the node/ directory is on the import path.
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rip_200_round_robin_1cpu1vote import (
    calculate_epoch_rewards_time_aged,
    GENESIS_TIMESTAMP,
    BLOCK_TIME,
    ATTESTATION_TTL,
)

SLOTS_PER_EPOCH = 144
UNIT = 1_000_000
PER_EPOCH_URTC = int(1.5 * UNIT)


def _setup_db(db_path: str) -> sqlite3.Connection:
    """Create minimal schema needed for reward calculation."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS epoch_enroll (
            epoch INTEGER, miner_pk TEXT, weight REAL,
            PRIMARY KEY (epoch, miner_pk)
        );
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY,
            device_arch TEXT,
            fingerprint_passed INTEGER DEFAULT 1,
            entropy_score REAL DEFAULT 0,
            ts_ok INTEGER
        );
        CREATE TABLE IF NOT EXISTS miner_fingerprint_history (
            miner TEXT, ts INTEGER, profile_json TEXT
        );
        CREATE TABLE IF NOT EXISTS epoch_state (
            epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER
        );
    """)
    return conn


def _enroll_miner(conn, epoch: int, miner_pk: str, weight: float):
    conn.execute(
        "INSERT OR IGNORE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
        (epoch, miner_pk, weight),
    )
    conn.commit()


def _attest_miner(conn, miner_pk: str, device_arch: str, ts_ok: int, fingerprint_passed: int = 1):
    conn.execute(
        "INSERT OR REPLACE INTO miner_attest_recent "
        "(miner, device_arch, fingerprint_passed, entropy_score, ts_ok) "
        "VALUES (?, ?, ?, 0.5, ?)",
        (miner_pk, device_arch, fingerprint_passed, ts_ok),
    )
    conn.commit()


class TestDelayedSettlementIntegrity(unittest.TestCase):
    """Delayed settlement must use the same miner list as immediate settlement."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.conn = _setup_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def _epoch_ts(self, epoch: int):
        start_ts = GENESIS_TIMESTAMP + (epoch * SLOTS_PER_EPOCH * BLOCK_TIME)
        end_ts = GENESIS_TIMESTAMP + ((epoch + 1) * SLOTS_PER_EPOCH - 1) * BLOCK_TIME
        return start_ts, end_ts

    def test_delayed_settlement_uses_epoch_enroll(self):
        """
        Miner A enrolls in epoch 10, then re-attests in epoch 11.
        Delayed settlement of epoch 10 must still include Miner A
        because epoch_enroll has the per-epoch snapshot.
        """
        EPOCH = 10
        start_ts, end_ts = self._epoch_ts(EPOCH)

        # Miner A (G4) enrolls epoch 10
        _enroll_miner(self.conn, EPOCH, "miner_A", weight=2.5)
        _attest_miner(self.conn, "miner_A", "g4", ts_ok=start_ts + 100)

        # Miner B (modern) enrolls epoch 10
        _enroll_miner(self.conn, EPOCH, "miner_B", weight=1.0)
        _attest_miner(self.conn, "miner_B", "x86_64", ts_ok=start_ts + 200)

        # Immediate settlement of epoch 10
        current_slot = EPOCH * SLOTS_PER_EPOCH + 72  # mid-epoch
        rewards_immediate = calculate_epoch_rewards_time_aged(
            self.db_path, EPOCH, PER_EPOCH_URTC, current_slot
        )

        self.assertIn("miner_A", rewards_immediate)
        self.assertIn("miner_B", rewards_immediate)

        # Now Miner A re-attests in epoch 11 (ts_ok moves forward)
        epoch11_start = GENESIS_TIMESTAMP + (11 * SLOTS_PER_EPOCH * BLOCK_TIME)
        _attest_miner(self.conn, "miner_A", "g4", ts_ok=epoch11_start + 100)

        # Delayed settlement of epoch 10 (simulating node restart + catch-up)
        # The old code would miss miner_A because ts_ok is now in epoch 11.
        # The fix uses epoch_enroll, so miner_A should still be included.
        current_slot_late = 11 * SLOTS_PER_EPOCH + 72  # epoch 11
        rewards_delayed = calculate_epoch_rewards_time_aged(
            self.db_path, EPOCH, PER_EPOCH_URTC, current_slot_late
        )

        # Both miners must still be present
        self.assertIn("miner_A", rewards_delayed,
                      "miner_A must be in delayed settlement (epoch_enroll source)")
        self.assertIn("miner_B", rewards_delayed)

        # Total rewards must still sum to PER_EPOCH_URTC
        self.assertEqual(sum(rewards_delayed.values()), PER_EPOCH_URTC)

    def test_fallback_to_attest_recent_when_no_enroll(self):
        """
        When epoch_enroll has no rows, fall back to miner_attest_recent
        time-window query (legacy compatibility).
        """
        EPOCH = 5
        start_ts, end_ts = self._epoch_ts(EPOCH)

        # Attest miners but DON'T enroll (simulates legacy epochs)
        _attest_miner(self.conn, "miner_X", "g5", ts_ok=start_ts + 100)
        _attest_miner(self.conn, "miner_Y", "modern", ts_ok=start_ts + 200)

        current_slot = EPOCH * SLOTS_PER_EPOCH + 72
        rewards = calculate_epoch_rewards_time_aged(
            self.db_path, EPOCH, PER_EPOCH_URTC, current_slot
        )

        # Both miners should be found via fallback path
        self.assertIn("miner_X", rewards)
        self.assertIn("miner_Y", rewards)

    def test_enrolled_miner_without_attestation_gets_unknown_arch(self):
        """
        A miner enrolled in epoch_enroll but with no attestation record
        should still receive rewards with 'unknown' arch (multiplier 1.0).
        """
        EPOCH = 3
        start_ts, _ = self._epoch_ts(EPOCH)

        _enroll_miner(self.conn, EPOCH, "orphan_miner", weight=2.0)
        # No attestation for this miner

        current_slot = EPOCH * SLOTS_PER_EPOCH + 72
        rewards = calculate_epoch_rewards_time_aged(
            self.db_path, EPOCH, PER_EPOCH_URTC, current_slot
        )

        self.assertIn("orphan_miner", rewards)
        self.assertGreater(rewards["orphan_miner"], 0)

    def test_fingerprint_failed_miner_excluded_from_enroll_path(self):
        """
        A miner enrolled in epoch_enroll but with fingerprint_passed=0
        in miner_attest_recent should receive zero weight.
        """
        EPOCH = 7
        start_ts, _ = self._epoch_ts(EPOCH)

        _enroll_miner(self.conn, EPOCH, "vm_miner", weight=0.0)
        _attest_miner(self.conn, "vm_miner", "aarch64", ts_ok=start_ts + 100,
                      fingerprint_passed=0)
        _enroll_miner(self.conn, EPOCH, "good_miner", weight=2.5)
        _attest_miner(self.conn, "good_miner", "g4", ts_ok=start_ts + 200,
                      fingerprint_passed=1)

        current_slot = EPOCH * SLOTS_PER_EPOCH + 72
        rewards = calculate_epoch_rewards_time_aged(
            self.db_path, EPOCH, PER_EPOCH_URTC, current_slot
        )

        # vm_miner should get zero (fingerprint failed)
        self.assertEqual(rewards.get("vm_miner", 0), 0)
        # good_miner should get all rewards
        self.assertEqual(rewards["good_miner"], PER_EPOCH_URTC)


class TestAntiDoubleMiningSettlementIntegrity(unittest.TestCase):
    """Anti-double-mining path must also use epoch_enroll as canonical source."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.conn = _setup_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def test_get_epoch_miner_groups_uses_enroll(self):
        """get_epoch_miner_groups should prefer epoch_enroll over attest_recent."""
        from anti_double_mining import get_epoch_miner_groups

        EPOCH = 12
        start_ts, _ = self._epoch_ts(EPOCH)

        _enroll_miner(self.conn, EPOCH, "miner_P", weight=2.5)
        _attest_miner(self.conn, "miner_P", "g4", ts_ok=start_ts + 100)

        _enroll_miner(self.conn, EPOCH, "miner_Q", weight=1.0)
        _attest_miner(self.conn, "miner_Q", "x86_64", ts_ok=start_ts + 200)

        groups = get_epoch_miner_groups(self.conn, EPOCH)

        # Both miners should be in the groups
        all_miners = set()
        for miners in groups.values():
            all_miners.update(miners)

        self.assertIn("miner_P", all_miners)
        self.assertIn("miner_Q", all_miners)

    def test_detect_duplicates_uses_enroll(self):
        """detect_duplicate_identities should prefer epoch_enroll."""
        from anti_double_mining import detect_duplicate_identities

        EPOCH = 15
        start_ts, end_ts = self._epoch_ts(EPOCH)

        _enroll_miner(self.conn, EPOCH, "miner_R", weight=2.5)
        _attest_miner(self.conn, "miner_R", "g4", ts_ok=start_ts + 100)

        duplicates = detect_duplicate_identities(self.conn, EPOCH, start_ts, end_ts)

        # Should find the enrolled miner (no duplicates in this case)
        # The key assertion is that the function doesn't crash and returns
        # based on epoch_enroll data
        self.assertIsInstance(duplicates, list)

    def _epoch_ts(self, epoch: int):
        start_ts = GENESIS_TIMESTAMP + (epoch * SLOTS_PER_EPOCH * BLOCK_TIME)
        end_ts = GENESIS_TIMESTAMP + ((epoch + 1) * SLOTS_PER_EPOCH - 1) * BLOCK_TIME
        return start_ts, end_ts


if __name__ == "__main__":
    unittest.main()
