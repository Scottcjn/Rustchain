"""
Unit tests for Issue #6136: Faucet wallet validation accepts arbitrary
0x-prefixed strings (10+ chars) — allows bypass of RTC wallet format.

Tests import the real is_valid_wallet_address from faucet.py.

Run: python -m pytest test_faucet_wallet_validation_6136.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from faucet import is_valid_wallet_address


class TestRTCWalletValidation:
    """RTC wallet addresses must match RTC[0-9a-fA-F]{40}."""

    def test_valid_rtc_wallet(self):
        assert is_valid_wallet_address("RTC" + "a" * 40) is True

    def test_valid_rtc_uppercase(self):
        assert is_valid_wallet_address("RTC" + "A" * 40) is True

    def test_valid_rtc_mixed_case(self):
        assert is_valid_wallet_address("RTC" + "aAbB" * 10) is True

    def test_rejects_non_hex_chars(self):
        assert is_valid_wallet_address("RTC" + "Z" * 40) is False

    def test_rejects_too_short(self):
        assert is_valid_wallet_address("RTC" + "a" * 39) is False

    def test_rejects_too_long(self):
        assert is_valid_wallet_address("RTC" + "a" * 41) is False

    def test_rejects_no_rtc_prefix(self):
        assert is_valid_wallet_address("a" * 43) is False

    def test_rejects_rtc_only(self):
        assert is_valid_wallet_address("RTC") is False


class TestEthereumStyleWalletValidation:
    """0x-prefixed addresses must be exactly 42 chars (0x + 40 hex)."""

    def test_valid_ethereum_address(self):
        assert is_valid_wallet_address("0x" + "a" * 40) is True

    def test_valid_ethereum_uppercase(self):
        assert is_valid_wallet_address("0x" + "A" * 40) is True

    def test_rejects_short_0x_prefix(self):
        """0x + 8 chars (10 total) must be rejected — issue #6136."""
        assert is_valid_wallet_address("0x" + "1" * 8) is False

    def test_rejects_short_0x_uppercase(self):
        """0xAAAAAAAAAA (10 chars) must be rejected — issue #6136."""
        assert is_valid_wallet_address("0xAAAAAAAAAA") is False

    def test_rejects_0x_non_hex_chars(self):
        """0x + non-hex chars must be rejected."""
        assert is_valid_wallet_address("0x" + "g" * 40) is False

    def test_rejects_short_0x_non_hex(self):
        """Short 0x with non-hex chars must be rejected."""
        assert is_valid_wallet_address("0x" + "g" * 8) is False

    def test_rejects_0x_41_hex(self):
        """0x + 41 hex chars (43 total) must be rejected."""
        assert is_valid_wallet_address("0x" + "a" * 41) is False

    def test_rejects_0x_39_hex(self):
        """0x + 39 hex chars (41 total) must be rejected."""
        assert is_valid_wallet_address("0x" + "a" * 39) is False


class TestInvalidWalletFormats:
    """Other invalid wallet formats."""

    def test_rejects_plain_string(self):
        assert is_valid_wallet_address("not_a_wallet") is False

    def test_rejects_empty_string(self):
        assert is_valid_wallet_address("") is False

    def test_rejects_1x_prefix(self):
        assert is_valid_wallet_address("1x" + "a" * 40) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
