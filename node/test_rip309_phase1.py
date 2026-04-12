#!/usr/bin/env python3
"""
Unit tests for RIP-309 Phase 1: Fingerprint Check Rotation

Tests the measurement nonce generation, check selection determinism,
and integration with the epoch reward calculation.
"""

import hashlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from rip_200_round_robin_1cpu1vote import (
    get_measurement_nonce,
    get_active_fingerprint_checks,
    get_inactive_fingerprint_checks,
    calculate_epoch_rewards_time_aged,
    FINGERPRINT_CHECKS,
    ACTIVE_CHECKS_PER_EPOCH,
    GENESIS_TIMESTAMP,
    BLOCK_TIME,
)


class TestMeasurementNonce(unittest.TestCase):
    """Tests for RIP-309 measurement nonce generation."""

    def test_nonce_is_32_bytes(self):
        """Nonce should be 32 bytes (SHA-256)."""
        h = hashlib.sha256(b"block123").digest()
        nonce = get_measurement_nonce(h)
        self.assertEqual(len(nonce), 32)

    def test_nonce_deterministic(self):
        """Same block hash → same nonce."""
        h = hashlib.sha256(b"same_block").digest()
        n1 = get_measurement_nonce(h)
        n2 = get_measurement_nonce(h)
        self.assertEqual(n1, n2)

    def test_nonce_differs_for_different_blocks(self):
        """Different block hashes → different nonces."""
        h1 = hashlib.sha256(b"block_a").digest()
        h2 = hashlib.sha256(b"block_b").digest()
        self.assertNotEqual(get_measurement_nonce(h1), get_measurement_nonce(h2))

    def test_nonce_includes_salt(self):
        """Nonce should differ from raw block hash (measurement_nonce salt)."""
        h = hashlib.sha256(b"test").digest()
        nonce = get_measurement_nonce(h)
        self.assertNotEqual(h, nonce)


class TestFingerprintCheckSelection(unittest.TestCase):
    """Tests for 4-of-6 fingerprint check selection."""

    def test_exactly_4_active(self):
        """Exactly 4 checks should be active per epoch."""
        h = hashlib.sha256(b"epoch_1").digest()
        nonce = get_measurement_nonce(h)
        active = get_active_fingerprint_checks(nonce)
        self.assertEqual(len(active), ACTIVE_CHECKS_PER_EPOCH)

    def test_exactly_2_inactive(self):
        """Exactly 2 checks should be inactive per epoch."""
        h = hashlib.sha256(b"epoch_1").digest()
        nonce = get_measurement_nonce(h)
        active = get_active_fingerprint_checks(nonce)
        inactive = get_inactive_fingerprint_checks(active)
        self.assertEqual(len(inactive), 6 - ACTIVE_CHECKS_PER_EPOCH)

    def test_active_and_inactive_partition(self):
        """Active + inactive = all 6 checks."""
        h = hashlib.sha256(b"epoch_1").digest()
        nonce = get_measurement_nonce(h)
        active = get_active_fingerprint_checks(nonce)
        inactive = get_inactive_fingerprint_checks(active)
        combined = sorted(active + inactive)
        self.assertEqual(combined, sorted(FINGERPRINT_CHECKS))

    def test_no_duplicates_in_active(self):
        """Active checks should have no duplicates."""
        h = hashlib.sha256(b"epoch_1").digest()
        nonce = get_measurement_nonce(h)
        active = get_active_fingerprint_checks(nonce)
        self.assertEqual(len(active), len(set(active)))

    def test_selection_deterministic(self):
        """Same nonce → same selection."""
        h = hashlib.sha256(b"deterministic_test").digest()
        nonce = get_measurement_nonce(h)
        a1 = get_active_fingerprint_checks(nonce)
        a2 = get_active_fingerprint_checks(nonce)
        self.assertEqual(a1, a2)

    def test_different_epochs_different_selections(self):
        """Different block hashes should (usually) produce different selections."""
        selections = set()
        for i in range(20):
            h = hashlib.sha256(f"epoch_{i}".encode()).digest()
            nonce = get_measurement_nonce(h)
            active = tuple(get_active_fingerprint_checks(nonce))
            selections.add(active)
        # With 20 epochs and C(6,4)=15 possible combos, we should see >1 unique selection
        self.assertGreater(len(selections), 1, "Expected different selections across epochs")

    def test_all_checks_valid_names(self):
        """All returned checks must be in the known FINGERPRINT_CHECKS list."""
        h = hashlib.sha256(b"validity_test").digest()
        nonce = get_measurement_nonce(h)
        active = get_active_fingerprint_checks(nonce)
        for check in active:
            self.assertIn(check, FINGERPRINT_CHECKS)

    def test_active_checks_sorted(self):
        """Active checks should be returned in sorted order for consistency."""
        h = hashlib.sha256(b"sort_test").digest()
        nonce = get_measurement_nonce(h)
        active = get_active_fingerprint_checks(nonce)
        self.assertEqual(active, sorted(active))


class TestEpochRewardsWithRotation(unittest.TestCase):
    """Tests for calculate_epoch_rewards_time_aged with RIP-309 rotation."""

    def _make_test_db(self):
        """Create an in-memory test database with minimal schema."""
        db = sqlite3.connect(":memory:")
        db.execute("""
            CREATE TABLE IF NOT EXISTS epoch_enroll (
                epoch INTEGER, miner_pk TEXT, PRIMARY KEY (epoch, miner_pk)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS miner_attest_recent (
                miner TEXT, device_arch TEXT, fingerprint_passed INTEGER DEFAULT 1,
                ts_ok INTEGER
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS epoch_state (
                epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0
            )
        """)
        return db

    def test_rewards_without_block_hash(self):
        """Pre-RIP-309: rewards work without prev_block_hash."""
        db = self._make_test_db()
        # Enroll 2 miners
        db.execute("INSERT INTO epoch_enroll VALUES (0, 'miner_a')")
        db.execute("INSERT INTO epoch_enroll VALUES (0, 'miner_b')")
        db.execute("INSERT INTO miner_attest_recent VALUES ('miner_a', 'g4', 1, ?)", (GENESIS_TIMESTAMP + 1000,))
        db.execute("INSERT INTO miner_attest_recent VALUES ('miner_b', 'modern', 1, ?)", (GENESIS_TIMESTAMP + 1000,))
        db.commit()

        # Save to temp file for function that opens its own connection
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
            # Copy in-memory db to file
            con = sqlite3.connect(db_path)
            for line in db.iterdump():
                con.execute(line)
            con.commit()
            con.close()
        db.close()

        rewards = calculate_epoch_rewards_time_aged(
            db_path, epoch=0, total_reward_urtc=1_500_000, current_slot=10,
            prev_block_hash=None,
        )
        self.assertEqual(len(rewards), 2)
        total = sum(rewards.values())
        self.assertEqual(total, 1_500_000)

        import os
        os.unlink(db_path)

    def test_rewards_with_block_hash(self):
        """RIP-309: rewards work with prev_block_hash."""
        db = self._make_test_db()
        db.execute("INSERT INTO epoch_enroll VALUES (0, 'miner_a')")
        db.execute("INSERT INTO miner_attest_recent VALUES ('miner_a', 'g4', 1, ?)", (GENESIS_TIMESTAMP + 1000,))
        db.commit()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
            con = sqlite3.connect(db_path)
            for line in db.iterdump():
                con.execute(line)
            con.commit()
            con.close()
        db.close()

        block_hash = hashlib.sha256(b"genesis_block").digest()
        rewards = calculate_epoch_rewards_time_aged(
            db_path, epoch=0, total_reward_urtc=1_500_000, current_slot=10,
            prev_block_hash=block_hash,
        )
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards['miner_a'], 1_500_000)

        import os
        os.unlink(db_path)

    def test_failed_fingerprint_zero_reward_with_rotation(self):
        """RIP-309: miner with failed fingerprint gets zero reward."""
        db = self._make_test_db()
        db.execute("INSERT INTO epoch_enroll VALUES (0, 'miner_bad')")
        db.execute("INSERT INTO miner_attest_recent VALUES ('miner_bad', 'g4', 0, ?)", (GENESIS_TIMESTAMP + 1000,))
        db.commit()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
            con = sqlite3.connect(db_path)
            for line in db.iterdump():
                con.execute(line)
            con.commit()
            con.close()
        db.close()

        block_hash = hashlib.sha256(b"genesis_block").digest()
        rewards = calculate_epoch_rewards_time_aged(
            db_path, epoch=0, total_reward_urtc=1_500_000, current_slot=10,
            prev_block_hash=block_hash,
        )
        self.assertEqual(len(rewards), 0)

        import os
        os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
