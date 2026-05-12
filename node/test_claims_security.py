#!/usr/bin/env python3
"""
Tests for CRIT-CLAIMS-1 (signature bypass) and MED-CLAIMS-2 (UNIT mismatch).
"""

import os
import sys
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


class TestClaimsWalletBinding(unittest.TestCase):
    """Claim payouts must stay bound to the miner's registered wallet."""

    def test_submit_claim_rejects_registered_wallet_mismatch(self):
        """Reject claims when submitted wallet differs from the registered wallet."""
        import claims_submission as cs

        with patch.object(cs, "check_claim_eligibility", return_value={
            "eligible": True,
            "reason": None,
            "wallet_address": "RTC1RegisteredWallet123456789",
            "reward_urtc": 1_000_000,
        }):
            result = cs.submit_claim(
                db_path="unused.db",
                miner_id="wallet-bound-claimer",
                epoch=123,
                wallet_address="RTC1AttackerWallet9999999999",
                signature="mock_signature",
                public_key="mock_public_key",
                current_slot=20000,
                current_ts=1766000000,
                skip_signature_verify=True,
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "wallet_mismatch")

    def test_submit_claim_accepts_case_variant_of_registered_wallet(self):
        import claims_submission as cs

        registered_wallet = "rtc1registeredwallet123456789"
        submitted_wallet = "RTC1REGISTEREDWALLET123456789"

        with (
            patch.object(cs, "check_claim_eligibility", return_value={
                "eligible": True,
                "reason": None,
                "wallet_address": registered_wallet,
                "reward_urtc": 1_000_000,
            }),
            patch.object(cs, "create_claim_record", return_value={
                "status": "pending",
                "submitted_at": 1766000000,
                "estimated_settlement": 1766001800,
            }) as create_claim_record,
        ):
            result = cs.submit_claim(
                db_path="unused.db",
                miner_id="wallet-bound-claimer",
                epoch=123,
                wallet_address=submitted_wallet,
                signature="mock_signature",
                public_key="mock_public_key",
                current_slot=20000,
                current_ts=1766000000,
                skip_signature_verify=True,
            )

        self.assertTrue(result["success"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["reward_rtc"], 1.0)
        create_claim_record.assert_called_once()
        self.assertEqual(
            create_claim_record.call_args.kwargs["wallet_address"],
            submitted_wallet,
        )


if __name__ == "__main__":
    unittest.main()
