"""Wallet utilities for RustChain (address validation, signature helpers)."""

from __future__ import annotations

import hashlib
import base64
import struct
from typing import Tuple

from rustchain.exceptions import WalletError


# Base58 alphabet used by RustChain / Solana-style addresses
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_encode(data: bytes) -> str:
    """Encode bytes to a Base58 string."""
    num = int.from_bytes(data, byteorder="big")
    encoded = ""
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = _BASE58_ALPHABET[rem] + encoded
    # Prepend leading '1's for each leading zero byte
    for byte in data:
        if byte == 0:
            encoded = "1" + encoded
        else:
            break
    return encoded


def _base58_decode(address: str) -> bytes:
    """Decode a Base58 string to bytes."""
    num = 0
    for char in address:
        num *= 58
        try:
            num += _BASE58_ALPHABET.index(char)
        except ValueError:
            raise WalletError(f"Invalid Base58 character: {char!r} in address")
    # Convert to bytes
    result = num.to_bytes((num.bit_length() + 7) // 8 or 1, byteorder="big")
    return result


def validate_address(address: str) -> bool:
    """Validate a RustChain wallet address.

    Accepts Base58-encoded public keys of 32-64 bytes.

    Args:
        address: The wallet address string.

    Returns:
        True if the address is valid, False otherwise.
    """
    if not address or not isinstance(address, str):
        return False
    if len(address) < 32 or len(address) > 88:
        return False
    try:
        decoded = _base58_decode(address)
        # Valid lengths for Ed25519 pubkeys: 32 bytes (raw) or 44 with base58 overhead
        if len(decoded) < 32 or len(decoded) > 64:
            return False
        return True
    except WalletError:
        return False


def validate_signature(signature: bytes | str, expected_length: int = 64) -> bool:
    """Validate a raw Ed25519 signature.

    Args:
        signature: Raw signature bytes or base64-encoded string.
        expected_length: Expected signature length in bytes (default 64 for Ed25519).

    Returns:
        True if the signature is valid format, False otherwise.
    """
    if isinstance(signature, str):
        try:
            sig_bytes = base64.b64decode(signature)
        except Exception:
            return False
    else:
        sig_bytes = signature

    if not isinstance(sig_bytes, bytes):
        return False
    if len(sig_bytes) != expected_length:
        return False
    # Ed25519 signatures are non-zero (check first byte isn't 0)
    if sig_bytes[0] == 0:
        return False
    return True


def encode_signature(signature: bytes) -> str:
    """Encode raw signature bytes to base64 string.

    Args:
        signature: Raw signature bytes.

    Returns:
        Base64-encoded signature string.
    """
    if not isinstance(signature, bytes):
        raise WalletError("signature must be bytes")
    return base64.b64encode(signature).decode("ascii")


def decode_signature(encoded: str) -> bytes:
    """Decode a base64-encoded signature to raw bytes.

    Args:
        encoded: Base64-encoded signature string.

    Returns:
        Raw signature bytes.
    """
    try:
        return base64.b64decode(encoded)
    except Exception as e:
        raise WalletError(f"Invalid base64 signature: {e}") from e


def hash_transaction(
    from_wallet: str,
    to_wallet: str,
    amount: float,
    nonce: int | None = None,
) -> str:
    """Create a deterministic hash of a transfer for signing.

    Args:
        from_wallet: Sender wallet address.
        to_wallet: Recipient wallet address.
        amount: Amount to transfer.
        nonce: Optional transaction nonce.

    Returns:
        SHA-256 hash of the transaction as a hex string.
    """
    msg = f"{from_wallet}:{to_wallet}:{amount}"
    if nonce is not None:
        msg = f"{msg}:{nonce}"
    return hashlib.sha256(msg.encode()).hexdigest()
