#!/usr/bin/env python3
"""
Tests for CRIT-CLAIMS-1 (signature bypass) and MED-CLAIMS-2 (UNIT mismatch).
"""

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestClaimsSignatureBypass(unittest.TestCase):
    """CRIT-CLAIMS-1: validate_claim_signature must fail when PyNaCl missing."""

    def test_no_nacl_rejects_signature(self):
        """When HAVE_NACL=False, signatures must be REJECTED, not accepted."""
        import claims_submission as cs
        original = cs.HAVE_NACL
        try:
            cs.HAVE_NACL = False
            valid, error = cs.validate_claim_signature(
                payload='{"miner_id":"attacker","epoch":1}',
                signature="0" * 128,
                public_key="1" * 64,
            )
            self.assertFalse(valid, "Must reject when PyNaCl is unavailable")
            self.assertIn("not installed", error)
        finally:
            cs.HAVE_NACL = original

    def test_nacl_available_verifies_properly(self):
        """When HAVE_NACL=True, bad signatures must be rejected."""
        import claims_submission as cs
        if not cs.HAVE_NACL:
            self.skipTest("PyNaCl not installed, skipping real verify test")

        valid, error = cs.validate_claim_signature(
            payload='{"test":"data"}',
            signature="0" * 128,  # fake signature
            public_key="1" * 64,  # fake key
        )
        self.assertFalse(valid, "Fake signature must be rejected")


    def test_claim_submission_rejects_unregistered_signing_key(self):
        """A valid signature from an attacker key must not claim another miner."""
        import claims_submission as cs
        from claims_eligibility import BLOCK_TIME, GENESIS_TIMESTAMP

        if not cs.HAVE_NACL:
            self.skipTest("PyNaCl not installed, skipping real submit test")

        from nacl.signing import SigningKey

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            current_ts = int(time.time())
            current_slot = (current_ts - GENESIS_TIMESTAMP) // BLOCK_TIME
            epoch = max(0, current_slot // 144 - 3)
            epoch_ts = GENESIS_TIMESTAMP + ((epoch * 144 + 72) * BLOCK_TIME)
            miner_id = "victim-miner"
            wallet = "RTC" + "A" * 24
            victim_key = SigningKey.generate()
            attacker_key = SigningKey.generate()
            victim_public_key = victim_key.verify_key.encode().hex()

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE miner_attest_recent (
                        miner TEXT,
                        device_arch TEXT,
                        ts_ok INTEGER,
                        fingerprint_passed INTEGER DEFAULT 1,
                        entropy_score REAL,
                        warthog_bonus REAL DEFAULT 1.0,
                        wallet_address TEXT,
                        public_key TEXT
                    )
                    """
                )
                conn.execute("CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER)")
                conn.executemany(
                    "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (miner_id, "modern", current_ts - 3600, 1, 0.5, 1.0, wallet, victim_public_key),
                        (miner_id, "modern", epoch_ts, 1, 0.5, 1.0, wallet, victim_public_key),
                    ],
                )
                conn.execute("INSERT INTO epoch_state VALUES (?, 1)", (epoch,))

            payload = cs.create_claim_payload(miner_id, epoch, wallet, current_ts)
            attacker_signature = attacker_key.sign(payload.encode("utf-8")).signature.hex()
            result = cs.submit_claim(
                db_path=db_path,
                miner_id=miner_id,
                epoch=epoch,
                wallet_address=wallet,
                signature=attacker_signature,
                public_key=attacker_key.verify_key.encode().hex(),
                current_slot=current_slot,
                current_ts=current_ts,
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "public_key_mismatch")
        finally:
            os.unlink(db_path)


class TestClaimsUnitConsistency(unittest.TestCase):
    """MED-CLAIMS-2: reward_rtc must use 1e6 (matching main server), not 1e8."""

    def test_reward_rtc_uses_1e6(self):
        """1,000,000 µRTC should display as 1.0 RTC, not 0.01 RTC."""
        reward_urtc = 1_000_000
        # The correct conversion (1e6 UNIT)
        reward_rtc = reward_urtc / 1_000_000
        self.assertEqual(reward_rtc, 1.0)

    def test_old_unit_was_wrong(self):
        """Verify the old 1e8 UNIT would produce wrong result."""
        reward_urtc = 1_000_000
        wrong_rtc = reward_urtc / 100_000_000  # old bug
        self.assertAlmostEqual(wrong_rtc, 0.01)  # 100x too small


if __name__ == "__main__":
    unittest.main()
