"""Regression tests for ``faucet_service.FaucetValidator.validate_wallet``.

Mirrors the legacy faucet tightening in commit ``541c784`` so malformed
RTC-prefixed values like ``RTCzzzzzzzzzz`` and ``RTC1234567890`` are rejected
by the faucet_service path as well. Cited by vuln-audit tick
``vuln-tick-2026-05-14T1500Z`` (Tier 2 — High).
"""

import logging
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "faucet_service"))

import faucet_service  # noqa: E402


@pytest.fixture()
def validator():
    return faucet_service.FaucetValidator(
        config={"validation": {}},
        logger=logging.getLogger("test"),
    )


# --- Malformed RTC wallets now rejected ---------------------------------------

def test_validator_rejects_short_rtc_wallet(validator):
    """``RTC1234567890`` is 13 chars: passes legacy length>=10 but is malformed."""
    valid, err = validator.validate_wallet("RTC1234567890")
    assert valid is False
    assert err is not None
    assert "RTC wallet format" in err


def test_validator_rejects_non_hex_rtc_wallet(validator):
    """``RTCzzzzzzzzzz`` has the right prefix and length>=10 but is not hex."""
    valid, err = validator.validate_wallet("RTCzzzzzzzzzz")
    assert valid is False
    assert err is not None
    assert "RTC wallet format" in err


def test_validator_rejects_rtc_with_wrong_hex_length(validator):
    """RTC + 39 hex chars (one short) is rejected."""
    valid, err = validator.validate_wallet("RTC" + "a" * 39)
    assert valid is False
    assert err is not None
    assert "RTC wallet format" in err


def test_validator_rejects_rtc_with_extra_hex_chars(validator):
    """RTC + 41 hex chars (one over) is rejected."""
    valid, err = validator.validate_wallet("RTC" + "a" * 41)
    assert valid is False
    assert err is not None
    assert "RTC wallet format" in err


# --- Well-formed wallets still accepted ---------------------------------------

def test_validator_accepts_canonical_rtc_wallet(validator):
    wallet = "RTC" + "9d7caca3039130d3b26d41f7343d8f4ef4592360"
    valid, err = validator.validate_wallet(wallet)
    assert valid is True
    assert err is None


def test_validator_accepts_uppercase_hex_rtc_wallet(validator):
    wallet = "RTC" + "9D7CACA3039130D3B26D41F7343D8F4EF4592360"
    valid, err = validator.validate_wallet(wallet)
    assert valid is True
    assert err is None


def test_validator_still_accepts_ethereum_style_wallet(validator):
    """Tightening must NOT regress 0x-prefixed wallets."""
    valid, err = validator.validate_wallet("0x9d7caca3039130d3b26d41f7343d8f4ef4592360")
    assert valid is True
    assert err is None
