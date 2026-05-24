"""Regression tests for bridge RustChain address validation (issue #6195)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from bridge_api import validate_chain_address_format

# --- Valid RTC addresses ---

def test_valid_rtc_address():
    addr = "RTC" + "a" * 40
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert ok, f"Expected valid RTC address, got: {msg}"

def test_valid_rtc_address_uppercase_hex():
    addr = "RTC" + "A" * 40
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert ok, f"Expected valid RTC address, got: {msg}"

def test_valid_rtc_address_mixed_hex():
    addr = "RTC1a2B3c4D5e6F7a8b1a2B3c4D5e6F7a8b1a2B3c4D"
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert ok, f"Expected valid RTC address, got: {msg}"

# --- Invalid RTC addresses ---

def test_reject_rtc_no_hex():
    addr = "RTC" + "Z" * 40  # Z is not hex
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for RTC address with non-hex chars"

def test_reject_rtc_too_short():
    addr = "RTC" + "a" * 10  # Only 10 hex chars instead of 40
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for short RTC address"

def test_reject_rtc_too_long():
    addr = "RTC" + "a" * 41  # 41 hex chars instead of 40
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for long RTC address"

def test_reject_rtc_special_chars():
    addr = "RTC" + "a" * 38 + "!@"  # Special characters
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for RTC address with special chars"

def test_reject_rtc_no_prefix():
    addr = "a" * 43  # No RTC prefix
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for address without RTC prefix"

def test_reject_rtc_wrong_prefix():
    addr = "RTX" + "a" * 40  # Wrong prefix
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for address with wrong prefix"

def test_reject_rtc_lowercase_prefix():
    addr = "rtc" + "a" * 40  # Lowercase prefix
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok, f"Expected rejection for lowercase RTC prefix"

def test_reject_rtc_empty():
    ok, msg = validate_chain_address_format("rustchain", "")
    assert not ok

def test_reject_rtc_only_prefix():
    addr = "RTC"  # Just the prefix
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert not ok

# --- Consistency with faucet ---

def test_faucet_canonical_format_accepted():
    """The bridge should accept the same format as the faucet."""
    addr = "RTC742d35Cc6634C0532925a3b844bc9e7595f2bD12"  # 40 hex after RTC
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert ok, f"Bridge should accept faucet-compatible RTC address, got: {msg}"
