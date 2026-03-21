"""Unit tests for wallet utilities."""

import pytest
import base64
from rustchain.wallet import (
    validate_address,
    validate_signature,
    encode_signature,
    decode_signature,
    hash_transaction,
)
from rustchain.exceptions import WalletError


class TestValidateAddress:
    def test_valid_address(self):
        # Valid 44-char Base58-encoded address
        assert validate_address("C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg") is True

    def test_invalid_empty(self):
        assert validate_address("") is False

    def test_invalid_none(self):
        assert validate_address(None) is False  # type: ignore

    def test_invalid_too_short(self):
        assert validate_address("abc") is False

    def test_invalid_too_long(self):
        assert validate_address("a" * 100) is False

    def test_invalid_chars(self):
        assert validate_address("C4c7r9WPsnEe6CUfeg!MU9M7ReHD1pWg8qeSfTBoRcLbg") is False


class TestValidateSignature:
    def test_valid_64byte_signature(self):
        # 64 random non-zero bytes
        sig = bytes([1] * 64)
        assert validate_signature(sig) is True

    def test_valid_base64_signature(self):
        sig = base64.b64encode(bytes([1] * 64)).decode()
        assert validate_signature(sig) is True

    def test_invalid_wrong_length(self):
        sig = bytes([1] * 32)
        assert validate_signature(sig) is False

    def test_invalid_zero_byte(self):
        sig = bytes([0] * 64)
        assert validate_signature(sig) is False

    def test_invalid_string(self):
        assert validate_signature("not-valid-base64!!!") is False


class TestEncodeSignature:
    def test_encode_roundtrip(self):
        raw = bytes([2] * 64)
        encoded = encode_signature(raw)
        assert isinstance(encoded, str)
        decoded = decode_signature(encoded)
        assert decoded == raw

    def test_encode_non_bytes_raises(self):
        with pytest.raises(WalletError):
            encode_signature("not-bytes")  # type: ignore


class TestDecodeSignature:
    def test_decode_invalid_base64(self):
        with pytest.raises(WalletError):
            decode_signature("!!!not-valid-base64")


class TestHashTransaction:
    def test_hash_transaction_deterministic(self):
        h1 = hash_transaction("wallet1", "wallet2", 10.0)
        h2 = hash_transaction("wallet1", "wallet2", 10.0)
        assert h1 == h2

    def test_hash_transaction_different_inputs(self):
        h1 = hash_transaction("wallet1", "wallet2", 10.0)
        h2 = hash_transaction("wallet1", "wallet3", 10.0)
        assert h1 != h2

    def test_hash_transaction_with_nonce(self):
        h1 = hash_transaction("wallet1", "wallet2", 10.0, nonce=1)
        h2 = hash_transaction("wallet1", "wallet2", 10.0, nonce=2)
        assert h1 != h2

    def test_hash_transaction_returns_hex(self):
        h = hash_transaction("w1", "w2", 1.0)
        assert all(c in "0123456789abcdef" for c in h)
