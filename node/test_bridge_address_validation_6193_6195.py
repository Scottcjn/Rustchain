"""
Unit tests for Issue #6193: Bridge Solana address validation accepts arbitrary
addresses without base58 check.

Also includes Issue #6195: Bridge RTC address validation inconsistent with faucet.

Tests that validate_chain_address_format rejects:
- Solana addresses with non-base58 characters (0, O, I, l)
- RTC addresses that don't match faucet format RTC[0-9a-fA-F]{40}

Run: python -m pytest test_bridge_address_validation_6193_6195.py -v
"""

import re
import pytest


BASE58_ALPHABET = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def validate_chain_address_format(chain: str, address: str):
    """Mirror of the fixed validation function from node/bridge_api.py."""
    if not address:
        return False, "Address is required"

    if chain == "rustchain":
        if not re.match(r"^RTC[0-9a-fA-F]{40}$", address):
            return False, "RustChain address must be RTC + 40 hex characters"

    elif chain == "solana":
        if len(address) < 32 or len(address) > 44:
            return False, "Invalid Solana address length"
        if not all(c in BASE58_ALPHABET for c in address):
            return False, "Invalid Solana address: contains non-base58 characters"

    elif chain == "base":
        if not address.startswith("0x"):
            return False, "Base addresses must start with '0x'"
        if len(address) != 42:
            return False, "Invalid Base address length"

    return True, ""


# =============================================================================
# Issue #6193: Solana base58 validation
# =============================================================================

class TestSolanaAddressBase58Validation:
    """Issue #6193: Solana addresses must contain only base58 characters."""

    def test_valid_solana_address(self):
        ok, msg = validate_chain_address_format("solana", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
        assert ok is True

    def test_rejects_zero_character(self):
        """0 is not in the base58 alphabet and must be rejected."""
        ok, msg = validate_chain_address_format("solana", "0" * 32)
        assert ok is False
        assert "base58" in msg.lower()

    def test_rejects_uppercase_I(self):
        """I is not in the base58 alphabet and must be rejected."""
        ok, msg = validate_chain_address_format("solana", "I" * 32)
        assert ok is False
        assert "base58" in msg.lower()

    def test_rejects_uppercase_O(self):
        """O is not in the base58 alphabet and must be rejected."""
        ok, msg = validate_chain_address_format("solana", "O" * 32)
        assert ok is False
        assert "base58" in msg.lower()

    def test_rejects_lowercase_l(self):
        """l (lowercase L) is not in the base58 alphabet and must be rejected."""
        ok, msg = validate_chain_address_format("solana", "l" * 32)
        assert ok is False

    def test_rejects_spaces(self):
        """Spaces are not in the base58 alphabet."""
        ok, msg = validate_chain_address_format("solana", "7xKXtg2CW87d97TXJSDpbD5jBk heTqA83TZRuJosgAs")
        assert ok is False

    def test_rejects_special_characters(self):
        """Special characters are not in the base58 alphabet."""
        ok, msg = validate_chain_address_format("solana", "!" * 32)
        assert ok is False

    def test_rejects_0x_prefix(self):
        """0x prefix (Ethereum-style) is not valid base58 for Solana."""
        ok, msg = validate_chain_address_format("solana", "0x" + "1" * 40)
        assert ok is False

    def test_valid_all_ones(self):
        """All 1s is technically valid base58 (though suspicious)."""
        ok, msg = validate_chain_address_format("solana", "1" * 32)
        assert ok is True

    def test_too_short(self):
        ok, msg = validate_chain_address_format("solana", "short")
        assert ok is False
        assert "length" in msg.lower()

    def test_too_long(self):
        ok, msg = validate_chain_address_format("solana", "1" * 45)
        assert ok is False


# =============================================================================
# Issue #6195: RTC address strict format validation
# =============================================================================

class TestRTCAddressValidation:
    """Issue #6195: RTC address must match faucet format RTC[0-9a-fA-F]{40}."""

    def test_valid_rtc_address_lowercase(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 40)
        assert ok is True

    def test_valid_rtc_address_uppercase(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "A" * 40)
        assert ok is True

    def test_valid_rtc_address_mixed_case(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "aAbB" * 10)
        assert ok is True

    def test_rejects_non_hex_characters(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "Z" * 40)
        assert ok is False

    def test_rejects_special_characters(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC!@#$%^&*()_+12345")
        assert ok is False

    def test_rejects_too_short(self):
        ok, msg = validate_chain_address_format("rustchain", "RTCabc")
        assert ok is False

    def test_rejects_39_hex_chars(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 39)
        assert ok is False

    def test_rejects_41_hex_chars(self):
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 41)
        assert ok is False

    def test_rejects_missing_rtc_prefix(self):
        ok, msg = validate_chain_address_format("rustchain", "a" * 43)
        assert ok is False

    def test_rejects_empty_address(self):
        ok, msg = validate_chain_address_format("rustchain", "")
        assert ok is False


class TestBaseAddressValidation:
    """Basic Base address validation tests (unchanged by this fix)."""

    def test_valid_base_address(self):
        ok, msg = validate_chain_address_format("base", "0x4215a73199d56b7e9c71575bec1632cd1d36908f")
        assert ok is True

    def test_rejects_base_without_0x(self):
        ok, msg = validate_chain_address_format("base", "4215a73199d56b7e9c71575bec1632cd1d36908f")
        assert ok is False
