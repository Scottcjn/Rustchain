"""
Unit tests for Issue #6193: Bridge Solana address validation accepts arbitrary
addresses without base58 check.

Also covers Issue #6195: Bridge RTC address validation inconsistent with faucet.

Tests import and exercise the REAL validate_chain_address_format from
node/bridge_api.py — no local mirrors.

Run: python -m pytest node/test_bridge_address_validation_6193_6195.py -v
"""

import pytest
import sys
import os

# Ensure the node directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from bridge_api import validate_chain_address_format


# =============================================================================
# Issue #6195: RTC address validation (must match faucet format RTC + 40 hex)
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

    def test_valid_rtc_all_digits(self):
        """0-9 are valid hex digits."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "0" * 40)
        assert ok is True

    def test_rejects_non_hex_characters(self):
        """RTC addresses with non-hex characters like 'Z' must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "Z" * 40)
        assert ok is False
        assert "40 hex" in msg

    def test_rejects_special_characters(self):
        """RTC addresses with special characters must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC!@#$%^&*()_+12345")
        assert ok is False

    def test_rejects_too_short(self):
        """RTC addresses with fewer than 40 hex chars after prefix must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTCabc")
        assert ok is False

    def test_rejects_39_hex_chars(self):
        """One character short of 40 hex chars must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 39)
        assert ok is False

    def test_rejects_41_hex_chars(self):
        """One character over 40 hex chars must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 41)
        assert ok is False

    def test_rejects_missing_rtc_prefix(self):
        """Addresses without RTC prefix must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "a" * 43)
        assert ok is False

    def test_rejects_empty_address(self):
        """Empty address must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "")
        assert ok is False
        assert "required" in msg.lower()

    def test_rejects_rtc_only(self):
        """Just 'RTC' with no hex chars must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC")
        assert ok is False

    def test_rejects_spaces_in_hex(self):
        """Spaces in the hex portion must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 20 + " " + "b" * 19)
        assert ok is False

    def test_rejects_lowercase_rtc_prefix(self):
        """Lowercase 'rtc' prefix must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "rtc" + "a" * 40)
        assert ok is False


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

    def test_rejects_plus_sign(self):
        """+ is not in base58."""
        ok, msg = validate_chain_address_format("solana", "+" + "1" * 31)
        assert ok is False

    def test_rejects_slash(self):
        """/ is not in base58."""
        ok, msg = validate_chain_address_format("solana", "/" + "1" * 31)
        assert ok is False


# =============================================================================
# Other chains (regression check)
# =============================================================================

class TestBaseAddressValidation:
    """Regression: Base address validation still works."""

    def test_valid_base_address(self):
        ok, msg = validate_chain_address_format("base", "0x" + "a" * 40)
        assert ok is True

    def test_rejects_no_0x_prefix(self):
        ok, msg = validate_chain_address_format("base", "a" * 40)
        assert ok is False


class TestErgoAddressValidation:
    """Regression: Ergo address validation still works."""

    def test_valid_ergo_9_prefix(self):
        ok, msg = validate_chain_address_format("ergo", "9" + "a" * 40)
        assert ok is True

    def test_rejects_wrong_prefix(self):
        ok, msg = validate_chain_address_format("ergo", "4" + "a" * 40)
        assert ok is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
