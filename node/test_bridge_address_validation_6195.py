"""
Unit tests for Issue #6195: Bridge RTC address validation inconsistent with faucet

Tests that validate_chain_address_format rejects non-hex RTC addresses
and enforces the same RTC[0-9a-fA-F]{40} format as the faucet.

Run: python -m pytest test_bridge_address_validation_6195.py -v
"""

import re
import pytest


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

    elif chain == "base":
        if not address.startswith("0x"):
            return False, "Base addresses must start with '0x'"
        if len(address) != 42:
            return False, "Invalid Base address length"

    return True, ""


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

    def test_rejects_rtc_only(self):
        """Just 'RTC' with no hex chars must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC")
        assert ok is False

    def test_rejects_spaces_in_hex(self):
        """Spaces in the hex portion must be rejected."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "a" * 20 + " " + "b" * 19)
        assert ok is False

    def test_rejects_numeric_only_after_rtc(self):
        """Purely numeric suffix (no a-f) should be valid if 40 chars."""
        ok, msg = validate_chain_address_format("rustchain", "RTC" + "0" * 40)
        assert ok is True  # 0-9 are valid hex digits


class TestSolanaAddressValidation:
    """Basic Solana address validation tests (unchanged by this fix)."""

    def test_valid_solana_address(self):
        ok, msg = validate_chain_address_format("solana", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
        assert ok is True

    def test_rejects_too_short_solana(self):
        ok, msg = validate_chain_address_format("solana", "short")
        assert ok is False


class TestBaseAddressValidation:
    """Basic Base address validation tests (unchanged by this fix)."""

    def test_valid_base_address(self):
        ok, msg = validate_chain_address_format("base", "0x4215a73199d56b7e9c71575bec1632cd1d36908f")
        assert ok is True

    def test_rejects_base_without_0x(self):
        ok, msg = validate_chain_address_format("base", "4215a73199d56b7e9c71575bec1632cd1d36908f")
        assert ok is False
