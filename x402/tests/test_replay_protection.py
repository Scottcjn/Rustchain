import unittest
from unittest import mock


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


if __name__ == "__main__":
    unittest.main()

