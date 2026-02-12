import unittest

from node.payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed


class PayoutPreflightTests(unittest.TestCase):
    def test_admin_rejects_non_dict(self):
        r = validate_wallet_transfer_admin(None)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "invalid_json_body")

    def test_admin_rejects_bad_amount(self):
        r = validate_wallet_transfer_admin({"from_miner": "a", "to_miner": "b", "amount_rtc": "nope"})
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "amount_not_number")

    def test_admin_ok(self):
        r = validate_wallet_transfer_admin({"from_miner": "a", "to_miner": "b", "amount_rtc": 1})
        self.assertTrue(r.ok)

    def test_signed_rejects_missing(self):
        r = validate_wallet_transfer_signed({"from_address": "RTC" + "a" * 40})
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "missing_required_fields")

    def test_signed_rejects_non_finite(self):
        payload = {
            "from_address": "RTC" + "a" * 40,
            "to_address": "RTC" + "b" * 40,
            "amount_rtc": float("nan"),
            "nonce": "1",
            "signature": "00",
            "public_key": "00",
        }
        r = validate_wallet_transfer_signed(payload)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "amount_not_finite")

    def test_signed_ok_shape(self):
        payload = {
            "from_address": "RTC" + "a" * 40,
            "to_address": "RTC" + "b" * 40,
            "amount_rtc": 1.25,
            "nonce": "123",
            "signature": "00",
            "public_key": "00",
        }
        r = validate_wallet_transfer_signed(payload)
        self.assertTrue(r.ok)


if __name__ == "__main__":
    unittest.main()

