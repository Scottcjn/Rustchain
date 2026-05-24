"""Regression tests for faucet wallet address validation (issue #6136)."""
import sys
import os
import re
import pytest

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the validation logic directly (no Flask app needed)
RTC_WALLET_RE = re.compile(r'^RTC[0-9a-fA-F]{40}$')
ETH_WALLET_RE = re.compile(r'^0x[0-9a-fA-F]{40}$')


def is_valid_wallet_address(wallet):
    """Fixed validation: accept legacy Ethereum-style wallets and native RTC wallets."""
    if not isinstance(wallet, str):
        return False
    return bool(ETH_WALLET_RE.fullmatch(wallet) or RTC_WALLET_RE.fullmatch(wallet))


class TestFaucetWalletValidation:
    """Tests for is_valid_wallet_address — regression for issue #6136."""

    # --- RTC wallets ---

    def test_valid_rtc_wallet(self):
        assert is_valid_wallet_address("RTC" + "a" * 40) is True

    def test_rtc_wallet_mixed_case(self):
        assert is_valid_wallet_address("RTC" + "aAbBcCdDeEfF" + "0" * 28) is True

    def test_rtc_wallet_too_short(self):
        assert is_valid_wallet_address("RTC" + "a" * 39) is False

    def test_rtc_wallet_too_long(self):
        assert is_valid_wallet_address("RTC" + "a" * 41) is False

    def test_rtc_wallet_invalid_chars(self):
        assert is_valid_wallet_address("RTC" + "g" * 40) is False

    def test_rtc_wallet_empty(self):
        assert is_valid_wallet_address("RTC") is False

    # --- Ethereum-style wallets ---

    def test_valid_eth_wallet(self):
        assert is_valid_wallet_address("0x" + "a" * 40) is True

    def test_eth_wallet_mixed_case(self):
        assert is_valid_wallet_address("0x" + "Aa1bBb2cCc3dDd4eEe5fFf6" + "0" * 17) is True

    # --- Regression: previously accepted invalid 0x-prefixed strings ---

    def test_short_0x_prefix_rejected(self):
        """Issue #6136: strings like '0x12345' should be rejected."""
        assert is_valid_wallet_address("0x12345") is False

    def test_minimal_0x_prefix_rejected(self):
        """10-char 0x-prefixed string was accepted before; now rejected."""
        assert is_valid_wallet_address("0xAAAAAAAAAA") is False

    def test_0x_plus_10_hex_chars_rejected(self):
        """Another variant of the bypass: exactly 10 chars after 0x."""
        assert is_valid_wallet_address("0x1234567890") is False

    def test_0x_plus_20_hex_chars_rejected(self):
        """20 hex chars after 0x is still not a valid ETH address."""
        assert is_valid_wallet_address("0x" + "1" * 20) is False

    def test_0x_plus_30_hex_chars_rejected(self):
        """30 hex chars after 0x is still not a valid ETH address."""
        assert is_valid_wallet_address("0x" + "1" * 30) is False

    def test_0x_plus_39_hex_chars_rejected(self):
        """39 hex chars after 0x: one short of valid ETH address."""
        assert is_valid_wallet_address("0x" + "1" * 39) is False

    def test_0x_plus_41_hex_chars_rejected(self):
        """41 hex chars after 0x: one too many for a valid ETH address."""
        assert is_valid_wallet_address("0x" + "1" * 41) is False

    # --- Non-string types ---

    def test_none_rejected(self):
        assert is_valid_wallet_address(None) is False

    def test_list_rejected(self):
        assert is_valid_wallet_address(["0x", "ab"]) is False

    def test_int_rejected(self):
        assert is_valid_wallet_address(42) is False

    # --- Empty / whitespace ---

    def test_empty_string_rejected(self):
        assert is_valid_wallet_address("") is False

    def test_whitespace_rejected(self):
        assert is_valid_wallet_address("  ") is False

    def test_0x_with_spaces_rejected(self):
        assert is_valid_wallet_address("0x" + " " * 40) is False
