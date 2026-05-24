"""Regression tests for bridge Solana address base58 validation (issue #6193)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from bridge_api import validate_chain_address_format

# --- Valid Solana addresses (base58 only) ---

def test_valid_base58_solana_address_32_chars():
    addr = "1" * 32  # All 1s, valid base58
    ok, msg = validate_chain_address_format("solana", addr)
    assert ok, f"Expected valid for 32-char base58 address, got: {msg}"

def test_valid_base58_solana_address_44_chars():
    addr = "A" * 44  # All As, valid base58
    ok, msg = validate_chain_address_format("solana", addr)
    assert ok, f"Expected valid for 44-char base58 address, got: {msg}"

def test_valid_base58_solana_realistic_address():
    addr = "7nYBF3k2GLFnCqQ7QhBjH5jdvJ6XZAL3NLxKwchQvBBp"  # 44 chars, all base58
    ok, msg = validate_chain_address_format("solana", addr)
    assert ok, f"Expected valid for realistic Solana address, got: {msg}"

# --- Invalid: non-base58 characters ---

def test_reject_solana_with_zero():
    """Zero (0) is not in the base58 alphabet."""
    addr = "1" * 31 + "0"
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address containing '0', but was accepted"
    assert "base58" in msg.lower() or "non-base58" in msg.lower(), f"Expected base58 error message, got: {msg}"

def test_reject_solana_with_uppercase_O():
    """Uppercase O is not in the base58 alphabet."""
    addr = "1" * 31 + "O"
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address containing 'O'"

def test_reject_solana_with_uppercase_I():
    """Uppercase I is not in the base58 alphabet."""
    addr = "1" * 31 + "I"
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address containing 'I'"

def test_reject_solana_with_lowercase_l():
    """Lowercase l is not in the base58 alphabet."""
    addr = "1" * 31 + "l"
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address containing 'l'"

def test_reject_solana_with_hex_prefix():
    """0x-prefixed address should not be valid Solana."""
    addr = "0x" + "A" * 42
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for 0x-prefixed Solana address"

def test_reject_solana_with_spaces():
    """Address with spaces should be rejected."""
    addr = "1" * 16 + "  " + "A" * 16
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address with spaces"

def test_reject_solana_with_special_chars():
    """Address with special characters should be rejected."""
    addr = "1" * 31 + "!"
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address with special chars"

def test_reject_solana_with_unicode():
    """Address with unicode characters should be rejected."""
    addr = "1" * 31 + "Ñ"
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for Solana address with unicode"

# --- Invalid: length ---

def test_reject_solana_too_short():
    addr = "A" * 31
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for 31-char Solana address"

def test_reject_solana_too_long():
    addr = "A" * 45
    ok, msg = validate_chain_address_format("solana", addr)
    assert not ok, f"Expected rejection for 45-char Solana address"

def test_reject_solana_empty():
    ok, msg = validate_chain_address_format("solana", "")
    assert not ok

# --- Other chains unaffected ---

def test_base_chain_still_works():
    addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18"
    ok, msg = validate_chain_address_format("base", addr)
    assert ok, f"Expected valid Base address, got: {msg}"

def test_rustchain_chain_still_works():
    addr = "RTC" + "a" * 40  # Proper RTC format: RTC + 40 hex chars
    ok, msg = validate_chain_address_format("rustchain", addr)
    assert ok, f"Expected valid RustChain address, got: {msg}"
