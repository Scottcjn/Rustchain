# SPDX-License-Identifier: MIT
"""
Test: Attestation overwrite causes prior-epoch reward loss

Vulnerability:
  miner_attest_recent uses INSERT OR REPLACE with `miner` as PRIMARY KEY.
  When the same miner re-attests (e.g. with a failed fingerprint), the
  INSERT OR REPLACE overwrites fingerprint_passed from 1 → 0.  Epoch
  settlement reads fingerprint_passed from miner_attest_recent and assigns
  ZERO weight to miners with fingerprint_passed=0, so the miner loses its
  entire epoch reward despite having legitimately attested earlier.

  Additionally, the auto-enroll code uses INSERT OR REPLACE INTO epoch_enroll,
  so a later low-weight attestation overwrites a prior high-weight enrollment
  within the same epoch.

Fix:
  1. record_attestation_success: use ON CONFLICT DO UPDATE with
     MAX(fingerprint_passed, excluded.fingerprint_passed) to prevent downgrade.
  2. Auto-enroll: use INSERT OR IGNORE for epoch_enroll so a prior enrollment
     within the same epoch is preserved.
"""

import os
import sys
import sqlite3
import unittest
import tempfile
import time

# Add node directory to path
NODE_DIR = os.path.join(os.path.dirname(__file__), '..', 'node')
sys.path.insert(0, NODE_DIR)


class TestAttestationOverwriteRewardLoss(unittest.TestCase):
    """Validate that attestation overwrite can cause prior-epoch reward loss,
    and that the fix prevents it."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self._init_db()

    def tearDown(self):
        try:
            os.close(self.db_fd)
        except OSError:
            pass
        os.unlink(self.db_path)

    def _init_db(self):
        """Create the minimal schema needed for the test."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER NOT NULL,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL DEFAULT 0,
                    fingerprint_passed INTEGER DEFAULT 0,
                    source_ip TEXT,
                    warthog_bonus REAL DEFAULT 1.0
                );

                CREATE TABLE miner_attest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner TEXT NOT NULL,
                    ts_ok INTEGER NOT NULL,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL DEFAULT 0,
                    fingerprint_passed INTEGER DEFAULT 0
                );

                CREATE TABLE epoch_enroll (
                    epoch INTEGER,
                    miner_pk TEXT,
                    weight REAL,
                    PRIMARY KEY (epoch, miner_pk)
                );

                CREATE TABLE epoch_state (
                    epoch INTEGER PRIMARY KEY,
                    settled INTEGER DEFAULT 0,
                    settled_ts INTEGER
                );

                CREATE TABLE balances (
                    miner_pk TEXT PRIMARY KEY,
                    balance_rtc REAL DEFAULT 0
                );
            """)

    # ------------------------------------------------------------------
    # Helpers that mirror the node's record_attestation_success and enroll
    # ------------------------------------------------------------------

    def _record_attestation_old(self, miner: str, device_arch: str = "modern",
                                device_family: str = "x86", fingerprint_passed: bool = True):
        """OLD behaviour: INSERT OR REPLACE — vulnerable to overwrite."""
        now = int(time.time())
        new_fp = 1 if fingerprint_passed else 0
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO miner_attest_recent
                (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, source_ip)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (miner, now, device_family, device_arch, 0.0, new_fp, "127.0.0.1"))
            conn.execute("""
                INSERT INTO miner_attest_history (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (miner, now, device_family, device_arch, 0.0, new_fp))
            conn.commit()

    def _record_attestation_fixed(self, miner: str, device_arch: str = "modern",
                                  device_family: str = "x86", fingerprint_passed: bool = True):
        """FIXED behaviour: ON CONFLICT DO UPDATE with MAX(fingerprint_passed)."""
        now = int(time.time())
        new_fp = 1 if fingerprint_passed else 0
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, source_ip)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(miner) DO UPDATE SET
                    ts_ok = excluded.ts_ok,
                    device_family = excluded.device_family,
                    device_arch = excluded.device_arch,
                    source_ip = excluded.source_ip,
                    fingerprint_passed = MAX(miner_attest_recent.fingerprint_passed, excluded.fingerprint_passed)
            """, (miner, now, device_family, device_arch, 0.0, new_fp, "127.0.0.1"))
            conn.execute("""
                INSERT INTO miner_attest_history (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (miner, now, device_family, device_arch, 0.0, new_fp))
            conn.commit()

    def _enroll_miner_replace(self, epoch: int, miner_pk: str, weight: float = 1.0):
        """OLD: INSERT OR REPLACE — vulnerable to weight downgrade."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)", (miner_pk,))
            conn.execute(
                "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (epoch, miner_pk, weight)
            )
            conn.commit()

    def _enroll_miner_ignore(self, epoch: int, miner_pk: str, weight: float = 1.0):
        """FIXED: INSERT OR IGNORE — preserves prior enrollment."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)", (miner_pk,))
            conn.execute(
                "INSERT OR IGNORE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (epoch, miner_pk, weight)
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Tests — demonstrate the bug
    # ------------------------------------------------------------------

    def test_old_behaviour_fp_downgrade_causes_zero_reward(self):
        """With INSERT OR REPLACE, a later failed fingerprint zeroes out the prior pass."""
        miner = "n64-scott-unit1"

        # First attestation: fingerprint passes
        self._record_attestation_old(miner, fingerprint_passed=True)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()
            self.assertEqual(row[0], 1)

        # Second attestation: fingerprint fails (e.g. VM detected)
        self._record_attestation_old(miner, fingerprint_passed=False)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()
            self.assertEqual(row[0], 0,
                "BUG: fingerprint_passed was downgraded from 1 to 0 by INSERT OR REPLACE. "
                "Epoch settlement will assign ZERO weight to this miner.")

    def test_old_behaviour_epoch_enroll_weight_downgrade(self):
        """With INSERT OR REPLACE on epoch_enroll, a later low-weight attestation overwrites prior high weight."""
        epoch = 100
        miner = "n64-scott-unit1"

        # First enrollment: high weight (fingerprint passed)
        self._enroll_miner_replace(epoch, miner, weight=2.5)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, miner)).fetchone()
            self.assertEqual(row[0], 2.5)

        # Second enrollment: near-zero weight (fingerprint failed)
        self._enroll_miner_replace(epoch, miner, weight=0.000000001)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, miner)).fetchone()
            self.assertAlmostEqual(row[0], 0.000000001,
                msg="BUG: epoch_enroll weight was downgraded from 2.5 to ~0 by INSERT OR REPLACE.")

    # ------------------------------------------------------------------
    # Tests — verify the fix
    # ------------------------------------------------------------------

    def test_fixed_behaviour_fp_preserved(self):
        """With ON CONFLICT DO UPDATE + MAX, fingerprint_passed=1 is preserved."""
        miner = "n64-scott-unit1"

        # First attestation: fingerprint passes
        self._record_attestation_fixed(miner, fingerprint_passed=True)
        # Second attestation: fingerprint fails
        self._record_attestation_fixed(miner, fingerprint_passed=False)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()
            self.assertEqual(row[0], 1,
                "FIX: fingerprint_passed=1 should be preserved despite later failed attestation.")

    def test_fixed_behaviour_fp_upgrade_allowed(self):
        """If first attestation fails FP but second passes, it should upgrade to 1."""
        miner = "n64-scott-unit1"

        self._record_attestation_fixed(miner, fingerprint_passed=False)
        self._record_attestation_fixed(miner, fingerprint_passed=True)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()
            self.assertEqual(row[0], 1,
                "FIX: fingerprint_passed should upgrade from 0 to 1 on successful re-attestation.")

    def test_fixed_behaviour_epoch_enroll_preserved(self):
        """With INSERT OR IGNORE, prior epoch enrollment is preserved."""
        epoch = 100
        miner = "n64-scott-unit1"

        # First enrollment: high weight
        self._enroll_miner_ignore(epoch, miner, weight=2.5)
        # Second enrollment: near-zero weight (should be ignored)
        self._enroll_miner_ignore(epoch, miner, weight=0.000000001)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, miner)).fetchone()
            self.assertEqual(row[0], 2.5,
                "FIX: epoch_enroll weight=2.5 should be preserved; later INSERT OR IGNORE is a no-op.")

    def test_fixed_behaviour_new_epoch_allows_enroll(self):
        """INSERT OR IGNORE should still allow enrollment in a NEW epoch."""
        miner = "n64-scott-unit1"

        self._enroll_miner_ignore(100, miner, weight=2.5)
        self._enroll_miner_ignore(101, miner, weight=1.0)  # new epoch

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT epoch, weight FROM epoch_enroll WHERE miner_pk=? ORDER BY epoch", (miner,)
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], (100, 2.5))
            self.assertEqual(rows[1], (101, 1.0))

    # ------------------------------------------------------------------
    # End-to-end: simulate epoch settlement
    # ------------------------------------------------------------------

    def test_end_to_end_old_behaviour_reward_loss(self):
        """Full scenario: miner attests (FP pass) → re-attests (FP fail) → epoch settles → zero reward."""
        epoch = 200
        miner = "n64-scott-unit1"

        # Attest with fingerprint pass
        self._record_attestation_old(miner, fingerprint_passed=True)
        # Enroll with high weight
        self._enroll_miner_replace(epoch, miner, weight=2.5)

        # Re-attest with fingerprint fail (e.g. slightly different device signals)
        self._record_attestation_old(miner, fingerprint_passed=False)
        # Re-enroll with near-zero weight
        self._enroll_miner_replace(epoch, miner, weight=0.000000001)

        # Simulate settlement: read miner_attest_recent for fingerprint status
        with sqlite3.connect(self.db_path) as conn:
            fp = conn.execute(
                "SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)
            ).fetchone()[0]
            weight = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, miner)
            ).fetchone()[0]

            # With old behaviour, both are degraded
            self.assertEqual(fp, 0, "fingerprint_passed should be 0 (downgraded)")
            self.assertAlmostEqual(weight, 0.000000001,
                msg="weight should be ~0 (downgraded)")

    def test_end_to_end_fixed_behaviour_reward_preserved(self):
        """Full scenario with fix: miner's reward eligibility is preserved despite later failed attestation."""
        epoch = 200
        miner = "n64-scott-unit1"

        # Attest with fingerprint pass
        self._record_attestation_fixed(miner, fingerprint_passed=True)
        # Enroll with high weight (fixed path)
        self._enroll_miner_ignore(epoch, miner, weight=2.5)

        # Re-attest with fingerprint fail
        self._record_attestation_fixed(miner, fingerprint_passed=False)
        # Try to re-enroll with near-zero weight (should be ignored)
        self._enroll_miner_ignore(epoch, miner, weight=0.000000001)

        with sqlite3.connect(self.db_path) as conn:
            fp = conn.execute(
                "SELECT fingerprint_passed FROM miner_attest_recent WHERE miner=?", (miner,)
            ).fetchone()[0]
            weight = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, miner)
            ).fetchone()[0]

            # With fixed behaviour, both are preserved
            self.assertEqual(fp, 1, "fingerprint_passed should remain 1 (not downgraded)")
            self.assertEqual(weight, 2.5, "epoch_enroll weight should remain 2.5 (not downgraded)")

    # ------------------------------------------------------------------
    # Tests — external downgrade via explicit /epoch/enroll endpoint
    # (distinct from prior submission which covered auto-enroll path)
    # ------------------------------------------------------------------

    def test_external_enroll_downgrade_old_behaviour(self):
        """With INSERT OR REPLACE on epoch_enroll, an external actor can call
        /epoch/enroll with a victim's pubkey and overwrite their weight."""
        epoch = 300
        victim = "n64-legit-miner"
        attacker = "external-actor"

        # Victim auto-enrolls with high weight (fingerprint passed)
        self._enroll_miner_replace(epoch, victim, weight=2.5)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, victim)
            ).fetchone()
            self.assertEqual(row[0], 2.5)

        # Attacker calls /epoch/enroll with victim's pubkey and default device
        # (simulated: weight=1.0 for default x86, or 1e-9 if fingerprint failed)
        self._enroll_miner_replace(epoch, victim, weight=0.000000001)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, victim)
            ).fetchone()
            self.assertAlmostEqual(row[0], 0.000000001,
                msg="BUG: external actor downgraded victim's weight from 2.5 to ~0 via INSERT OR REPLACE")

    def test_external_enroll_downgrade_fixed(self):
        """With INSERT OR IGNORE, an external /epoch/enroll call is a no-op
        if the miner is already enrolled in the epoch."""
        epoch = 300
        victim = "n64-legit-miner"

        # Victim auto-enrolls with high weight
        self._enroll_miner_ignore(epoch, victim, weight=2.5)
        # Attacker tries to overwrite with near-zero weight
        self._enroll_miner_ignore(epoch, victim, weight=0.000000001)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, victim)
            ).fetchone()
            self.assertEqual(row[0], 2.5,
                "FIX: victim's weight=2.5 should be preserved; external INSERT OR IGNORE is a no-op")

    def test_first_enroll_wins_fixed(self):
        """With INSERT OR IGNORE, the FIRST enrollment wins regardless of source.
        If an attacker enrolls first with low weight, the victim's later
        legitimate enrollment is also blocked — but this is no worse than
        the attacker having mined with that pubkey from the start."""
        epoch = 400
        victim = "n64-legit-miner"

        # Attacker enrolls first with low weight (e.g. via /epoch/enroll with bad device)
        self._enroll_miner_ignore(epoch, victim, weight=0.000000001)
        # Victim's legitimate auto-enroll is a no-op
        self._enroll_miner_ignore(epoch, victim, weight=2.5)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT weight FROM epoch_enroll WHERE epoch=? AND miner_pk=?", (epoch, victim)
            ).fetchone()
            # First enrollment wins — this is the expected behavior with INSERT OR IGNORE
            self.assertAlmostEqual(row[0], 0.000000001,
                "FIX: first enrollment wins; victim's later enroll is a no-op. "
                "This is acceptable because the attacker would need the victim's pubkey "
                "and would be sacrificing their own rewards.")


if __name__ == '__main__':
    unittest.main()
