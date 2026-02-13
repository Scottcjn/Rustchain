import unittest
from unittest import mock
import hashlib
import sys
from pathlib import Path


# Allow running directly: `python3 x402/tests/test_replay_protection.py`
X402_DIR = Path(__file__).resolve().parents[1]
if str(X402_DIR) not in sys.path:
    sys.path.insert(0, str(X402_DIR))

import rtc_payment_middleware as mw


class TestReplayProtection(unittest.TestCase):
    def setUp(self):
        mw._payment_cache.clear()
        mw._spent_tx_cache.clear()

    def test_tx_hash_is_single_use_across_nonces(self):
        proof = {
            "tx_hash": "abc123",
            "nonce": "n1",
            "signature": "00" * 64,
            "sender": "11" * 32,
        }

        with mock.patch.object(mw, "verify_rtc_signature", return_value=True), mock.patch.object(
            mw, "verify_payment_on_chain", return_value=True
        ):
            self.assertTrue(mw.verify_payment_proof(proof, expected_amount=0.1, recipient="RTCxxxx"))

            # Same tx_hash, different nonce should be rejected (replay).
            proof2 = dict(proof)
            proof2["nonce"] = "n2"
            self.assertFalse(mw.verify_payment_proof(proof2, expected_amount=0.1, recipient="RTCxxxx"))

            # Idempotent retry with original nonce remains allowed.
            self.assertTrue(mw.verify_payment_proof(proof, expected_amount=0.1, recipient="RTCxxxx"))

    def test_sender_wallet_is_bound_to_payment_tx(self):
        pubkey = b"\x01" * 32
        expected_sender = f"RTC{hashlib.sha256(pubkey).hexdigest()[:40]}"

        proof = {
            "tx_hash": "abc123",
            "nonce": "n1",
            "signature": "00" * 64,
            "sender": pubkey.hex(),
        }

        with mock.patch.object(mw, "verify_rtc_signature", return_value=True), mock.patch.object(
            mw, "verify_payment_on_chain", autospec=True, return_value=True
        ) as verify_on_chain:
            self.assertTrue(mw.verify_payment_proof(proof, expected_amount=0.1, recipient="RTCdest"))
            verify_on_chain.assert_called()
            _, args, kwargs = verify_on_chain.mock_calls[0]
            # verify_payment_on_chain(tx_hash, expected_amount, recipient, expected_sender=...)
            self.assertEqual(args[0], proof["tx_hash"])
            self.assertEqual(args[1], 0.1)
            self.assertEqual(args[2], "RTCdest")
            self.assertEqual(kwargs.get("expected_sender"), expected_sender)


if __name__ == "__main__":
    unittest.main()
