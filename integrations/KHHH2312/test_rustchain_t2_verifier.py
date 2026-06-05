# SPDX-License-Identifier: MIT

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rustchain_t2_verifier as verifier


class RustChainT2VerifierTests(unittest.TestCase):
    def test_epoch_slot_relationship(self):
        self.assertTrue(
            verifier.verify_epoch_slot(
                {"epoch": 182, "slot": 26347, "blocks_per_epoch": 144}
            )
        )
        self.assertFalse(
            verifier.verify_epoch_slot(
                {"epoch": 183, "slot": 26347, "blocks_per_epoch": 144}
            )
        )

    def test_balance_unit_consistency(self):
        balance = {
            "miner_id": "power8-s824-sophia",
            "amount_i64": 89958498,
            "amount_rtc": 89.958498,
        }
        self.assertTrue(verifier.verify_balance_units(balance, "power8-s824-sophia"))
        self.assertFalse(verifier.verify_balance_units(balance, "other-miner"))

    def test_base_url_validation_rejects_remote_http(self):
        with self.assertRaises(ValueError):
            verifier.validate_base_url("http://rustchain.org")

    def test_base_url_validation_accepts_default_endpoint(self):
        self.assertEqual(
            verifier.validate_base_url("https://rustchain.org/"),
            "https://rustchain.org",
        )


if __name__ == "__main__":
    unittest.main()
