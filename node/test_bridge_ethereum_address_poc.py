"""
PoC: validate_chain_address_format accepted any non-empty string >= 10 chars
for the 'ethereum' chain because no elif branch existed.

Before fix: validate_chain_address_format("ethereum", "garbage123") -> (True, "")
After fix:  validate_chain_address_format("ethereum", "garbage123") -> (False, "...")
"""
import unittest

try:
    from bridge_api import validate_chain_address_format
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from bridge_api import validate_chain_address_format


class TestBridgeEthereumAddressValidation(unittest.TestCase):

    # --- rejection cases (all were previously accepted) ---

    def test_rejects_garbage_string(self):
        ok, msg = validate_chain_address_format("ethereum", "garbage1234567890")
        self.assertFalse(ok, "Garbage string must be rejected")

    def test_rejects_missing_0x_prefix(self):
        ok, msg = validate_chain_address_format("ethereum", "aabbccddeeff00112233445566778899aabbccdd")
        self.assertFalse(ok)
        self.assertIn("0x", msg)

    def test_rejects_wrong_length(self):
        ok, msg = validate_chain_address_format("ethereum", "0xdeadbeef")
        self.assertFalse(ok)

    def test_rejects_non_hex_chars(self):
        ok, msg = validate_chain_address_format("ethereum", "0x" + "g" * 40)
        self.assertFalse(ok)

    def test_rejects_empty(self):
        ok, msg = validate_chain_address_format("ethereum", "")
        self.assertFalse(ok)

    # --- acceptance cases ---

    def test_accepts_valid_lowercase(self):
        ok, _ = validate_chain_address_format("ethereum", "0x" + "a" * 40)
        self.assertTrue(ok)

    def test_accepts_valid_eip55_checksum(self):
        # EIP-55 checksummed address — mixed-case must match keccak-derived checksum
        ok, _ = validate_chain_address_format("ethereum", "0xabCDEF1234567890ABcDEF1234567890aBCDeF12")
        self.assertTrue(ok)

    def test_rejects_invalid_mixed_case(self):
        # Typo'd mixed-case that does not satisfy EIP-55 checksum
        ok, msg = validate_chain_address_format("ethereum", "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12")
        self.assertFalse(ok)
        self.assertIn("EIP-55", msg)

    def test_accepts_zero_address(self):
        ok, _ = validate_chain_address_format("ethereum", "0x" + "0" * 40)
        self.assertTrue(ok)

    # --- other chains unaffected ---

    def test_base_still_validated(self):
        ok, msg = validate_chain_address_format("base", "not-an-address")
        self.assertFalse(ok)

    def test_rustchain_unaffected(self):
        ok, _ = validate_chain_address_format("rustchain", "RTC" + "a" * 40)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
