"""
RustChain Cryptographic Utilities
Ed25519 signing helpers for signed transfers.
"""

import hashlib
import hmac
import struct
import time
from typing import Optional, Tuple

# Try cryptography.io (recommended), fall back to ed25519-blake2b
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    import ed25519
    HAS_ED25519 = True
except ImportError:
    HAS_ED25519 = False


class SigningKey:
    """Ed25519 signing key wrapper compatible with RustChain."""

    def __init__(self, private_key_bytes: bytes) -> None:
        if HAS_CRYPTOGRAPHY:
            self._key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        elif HAS_ED25519:
            self._key = ed25519.SigningKey(private_key_bytes)
        else:
            raise ImportError(
                "Ed25519 support requires either 'cryptography' or 'ed25519' package. "
                "Install with: pip install rustchain[crypto]"
            )

    @classmethod
    def generate(cls) -> "SigningKey":
        """Generate a new Ed25519 signing key."""
        if HAS_CRYPTOGRAPHY:
            key = Ed25519PrivateKey.generate()
            priv_bytes = key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            return cls(priv_bytes)
        elif HAS_ED25519:
            key = ed25519.SigningKey.generate()
            return cls(key.to_bytes())
        else:
            raise ImportError("No Ed25519 library available")

    @classmethod
    def from_seed(cls, seed: bytes) -> "SigningKey":
        """Derive a signing key from a seed (BIP39-style)."""
        if len(seed) < 32:
            seed = hashlib.sha256(seed).digest()
        priv_bytes = hashlib.sha256(b"rustchain-wallet" + seed).digest()
        return cls(priv_bytes)

    def sign(self, message: bytes) -> bytes:
        """Sign a message and return the Ed25519 signature (64 bytes)."""
        if HAS_CRYPTOGRAPHY:
            sig = self._key.sign(message)
            return sig
        elif HAS_ED25519:
            return self._key.sign(message)
        else:
            raise ImportError("No Ed25519 library available")

    def sign_transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: int,
        fee: int = 0,
        timestamp: Optional[int] = None,
    ) -> Tuple[bytes, dict]:
        """
        Sign a transfer payload compatible with POST /wallet/transfer/signed.

        Args:
            from_wallet: Sender wallet ID
            to_wallet: Recipient wallet ID
            amount: Amount in smallest units (1 RTC = 1_000_000 units)
            fee: Transaction fee in smallest units
            timestamp: Unix timestamp (default: now)

        Returns:
            Tuple of (signature_hex, payload_dict)
        """
        if timestamp is None:
            timestamp = int(time.time())

        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "fee": fee,
            "timestamp": timestamp,
        }

        # Canonical JSON bytes for signing (sorted keys, no whitespace)
        import json
        message = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = self.sign(message)

        return signature.hex(), payload


def verify_signature(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an Ed25519 signature."""
    if HAS_CRYPTOGRAPHY:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        pk = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        try:
            pk.verify(signature, message)
            return True
        except InvalidSignature:
            return False
    elif HAS_ED25519:
        try:
            vk = ed25519.VerifyingKey(public_key_bytes)
            vk.verify(signature, message)
            return True
        except Exception:
            return False
    else:
        raise ImportError("No Ed25519 library available")
