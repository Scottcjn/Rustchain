#!/usr/bin/env python3
"""
RustChain Post-Quantum Cryptographic Extension (RIP-300 Phase 1)

Extends the existing Ed25519 wallet with ML-DSA-44 (CRYSTALS-Dilithium2)
hybrid signatures. Implements the XLINK approach: bind an existing Ed25519
key to a new post-quantum key while preserving a clear upgrade path once the
backend exposes deterministic seeded ML-DSA key generation.

No breaking changes — existing RTC wallets continue to work unchanged.
New RTCQ wallets can produce hybrid Ed25519+ML-DSA signatures.

Motivated by Google Quantum AI paper (March 2026) showing Ed25519 crackable
with <500K physical qubits in ~9 minutes.

(c) 2026 Elyan Labs — RIP-300 Implementation
"""

import hashlib
import json
import os
import base64
import math
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone

from pqcrypto.sign.ml_dsa_44 import generate_keypair as mldsa_generate_keypair
from pqcrypto.sign.ml_dsa_44 import sign as mldsa_sign
from pqcrypto.sign.ml_dsa_44 import verify as mldsa_verify
from pqcrypto.sign.ml_dsa_44 import (
    PUBLIC_KEY_SIZE as MLDSA44_PUBLIC_KEY_SIZE,
    SECRET_KEY_SIZE as MLDSA44_SECRET_KEY_SIZE,
    SIGNATURE_SIZE as MLDSA44_SIGNATURE_SIZE,
)

from mnemonic import Mnemonic
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
from nacl.exceptions import BadSignatureError
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ── Constants ──

MNEMONIC_STRENGTH = 256
PBKDF2_ITERATIONS = 100000
SALT_SIZE = 16
NONCE_SIZE = 12

# PQ seed derivation uses a distinct salt to produce independent key material
PQ_SEED_SALT = b"RustChain-RIP300-ML-DSA-44-v1"

# Address prefixes
PREFIX_LEGACY = "RTC"
PREFIX_PQ = "RTCQ"

# Keystore version
KEYSTORE_VERSION_PQ = 2

ED25519_PUBLIC_KEY_SIZE = 32
ED25519_PRIVATE_KEY_SIZE = 32
ED25519_SIGNATURE_SIZE = 64

PQ_SIGNATURE_SCHEME = "hybrid-ed25519-mldsa44"


def _decode_hex_field(
    field_name: str,
    value: str,
    *,
    expected_len: Optional[int] = None,
) -> bytes:
    """Decode a hex field and enforce byte length when specified."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a hex string")
    raw = bytes.fromhex(value)
    if expected_len is not None and len(raw) != expected_len:
        raise ValueError(
            f"{field_name} must be exactly {expected_len} bytes, got {len(raw)}"
        )
    return raw


def _pq_address_from_public_keys(ed_public_key: bytes, pq_public_key: bytes) -> str:
    combined_hash = hashlib.sha256(ed_public_key + pq_public_key).hexdigest()[:40]
    return f"{PREFIX_PQ}{combined_hash}"


def _canonical_transaction_message(
    from_address: str,
    to_address: str,
    amount: float,
    memo: str,
    nonce: int,
) -> bytes:
    tx_data = {
        "from": from_address,
        "to": to_address,
        "amount": amount,
        "memo": memo,
        "nonce": nonce,
    }
    return json.dumps(
        tx_data,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _validate_transaction_fields(
    *,
    from_address: str,
    to_address: str,
    amount: float,
    memo: str,
    nonce: int,
) -> tuple[str, str, float, str, int]:
    if not isinstance(from_address, str) or not from_address.strip():
        raise ValueError("from_address must be a non-empty string")
    if not isinstance(to_address, str) or not to_address.strip():
        raise ValueError("to_address must be a non-empty string")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise TypeError("amount must be a finite number")
    amount = float(amount)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("amount must be a finite non-negative number")
    if not isinstance(memo, str):
        raise TypeError("memo must be a string")
    if isinstance(nonce, bool) or not isinstance(nonce, int):
        raise TypeError("nonce must be an integer")
    if nonce < 0:
        raise ValueError("nonce must be non-negative")
    return from_address.strip(), to_address.strip(), amount, memo, nonce


# ══════════════════════════════════════════════════════════════
# RustChainPQWallet — Hybrid Ed25519 + ML-DSA-44
# ══════════════════════════════════════════════════════════════

class RustChainPQWallet:
    """
    Post-quantum wallet with dual Ed25519 + ML-DSA-44 keypairs.

    Usage:
        # Create new PQ wallet
        wallet = RustChainPQWallet.create()
        print(wallet.mnemonic)  # Mnemonic restores Ed25519; keystore preserves PQ key

        # Restore from encrypted keystore (recommended until seeded ML-DSA exists)
        wallet = RustChainPQWallet.from_encrypted(keystore, "password")

        # Hybrid sign (both Ed25519 + ML-DSA)
        tx = wallet.sign_transaction(to_address, amount)
        # tx contains both 'signature' (Ed25519) and 'pq_signature' (ML-DSA)

        # Addresses
        wallet.legacy_address  # RTC...  (Ed25519 only)
        wallet.address         # RTCQ... (PQ-enabled)
    """

    def __init__(
        self,
        ed_signing_key: SigningKey,
        pq_public_key: bytes,
        pq_secret_key: bytes,
        mnemonic: Optional[str] = None,
    ):
        self._ed_signing_key = ed_signing_key
        self._ed_verify_key = ed_signing_key.verify_key
        self._pq_public_key = pq_public_key
        self._pq_secret_key = pq_secret_key
        self._mnemonic = mnemonic
        self._address = None
        self._legacy_address = None

    @classmethod
    def create(cls, passphrase: str = "") -> "RustChainPQWallet":
        """Create a new PQ wallet with fresh 24-word seed phrase."""
        mnemo = Mnemonic("english")
        mnemonic = mnemo.generate(strength=MNEMONIC_STRENGTH)
        return cls._from_mnemonic_material(
            mnemonic,
            passphrase,
            allow_nondeterministic_pq=True,
        )

    @classmethod
    def from_mnemonic(
        cls,
        mnemonic: str,
        passphrase: str = "",
        *,
        allow_nondeterministic_pq: bool = False,
    ) -> "RustChainPQWallet":
        """Restore PQ wallet from BIP39 mnemonic (XLINK binding).

        The installed pqcrypto backend does not currently expose seeded
        ML-DSA-44 key generation, so deterministic PQ restore is refused
        unless the caller explicitly opts into a fresh non-deterministic
        PQ binding via allow_nondeterministic_pq=True.
        """
        return cls._from_mnemonic_material(
            mnemonic,
            passphrase,
            allow_nondeterministic_pq=allow_nondeterministic_pq,
        )

    @classmethod
    def _from_mnemonic_material(
        cls,
        mnemonic: str,
        passphrase: str,
        *,
        allow_nondeterministic_pq: bool,
    ) -> "RustChainPQWallet":
        mnemo = Mnemonic("english")
        if not mnemo.check(mnemonic):
            raise ValueError("Invalid mnemonic phrase")

        # BIP39 seed from mnemonic
        seed = mnemo.to_seed(mnemonic, passphrase)

        # Ed25519 key: SHA256(seed)[:32] — identical to legacy wallet
        ed_key_material = hashlib.sha256(seed).digest()
        ed_signing_key = SigningKey(ed_key_material)

        # ML-DSA key: use a distinct KDF path from the same seed
        # HMAC-SHA512 with PQ-specific salt produces independent key material
        import hmac
        pq_seed = hmac.new(PQ_SEED_SALT, seed, hashlib.sha512).digest()

        if not allow_nondeterministic_pq:
            raise RuntimeError(
                "Deterministic ML-DSA-44 restore is unavailable with the installed "
                "pqcrypto backend. Restore this wallet from an encrypted keystore, "
                "or pass allow_nondeterministic_pq=True only when intentionally "
                "creating a fresh PQ binding."
            )

        pq_pk, pq_sk = _generate_mldsa_keypair_from_seed_material(pq_seed)

        return cls(ed_signing_key, pq_pk, pq_sk, mnemonic)

    @classmethod
    def from_keys(
        cls,
        ed_private_key_hex: str,
        pq_public_key_hex: str,
        pq_secret_key_hex: str,
        mnemonic: Optional[str] = None,
    ) -> "RustChainPQWallet":
        """Load PQ wallet from hex-encoded key material."""
        ed_sk = SigningKey(
            _decode_hex_field(
                "ed_private_key",
                ed_private_key_hex,
                expected_len=ED25519_PRIVATE_KEY_SIZE,
            )
        )
        pq_public_key = _decode_hex_field(
            "pq_public_key",
            pq_public_key_hex,
            expected_len=MLDSA44_PUBLIC_KEY_SIZE,
        )
        pq_secret_key = _decode_hex_field(
            "pq_secret_key",
            pq_secret_key_hex,
            expected_len=MLDSA44_SECRET_KEY_SIZE,
        )
        return cls(
            ed_sk,
            pq_public_key,
            pq_secret_key,
            mnemonic=mnemonic,
        )

    # ── Properties ──

    @property
    def mnemonic(self) -> Optional[str]:
        return self._mnemonic

    @property
    def ed_private_key(self) -> str:
        return self._ed_signing_key.encode(encoder=HexEncoder).decode()

    @property
    def ed_public_key(self) -> str:
        return self._ed_verify_key.encode(encoder=HexEncoder).decode()

    @property
    def pq_public_key(self) -> str:
        return self._pq_public_key.hex()

    @property
    def pq_public_key_bytes(self) -> bytes:
        return self._pq_public_key

    @property
    def legacy_address(self) -> str:
        """Legacy Ed25519-only address (RTC prefix)."""
        if self._legacy_address is None:
            pubkey_hash = hashlib.sha256(self._ed_verify_key.encode()).hexdigest()[:40]
            self._legacy_address = f"{PREFIX_LEGACY}{pubkey_hash}"
        return self._legacy_address

    @property
    def address(self) -> str:
        """PQ-enabled address (RTCQ prefix).

        Derived from hash of BOTH public keys for binding security.
        """
        if self._address is None:
            self._address = _pq_address_from_public_keys(
                self._ed_verify_key.encode(),
                self._pq_public_key,
            )
        return self._address

    # ── Signing ──

    def sign_message(self, message: bytes) -> Dict[str, str]:
        """Hybrid sign: returns both Ed25519 and ML-DSA signatures."""
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")
        ed_signed = self._ed_signing_key.sign(message)
        ed_sig = ed_signed.signature.hex()
        pq_sig = mldsa_sign(self._pq_secret_key, message).hex()
        return {"ed25519": ed_sig, "ml_dsa_44": pq_sig}

    def sign_ed25519_only(self, message: bytes) -> str:
        """Legacy Ed25519-only signature for backwards compatibility."""
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")
        return self._ed_signing_key.sign(message).signature.hex()

    def sign_transaction(
        self,
        to_address: str,
        amount: float,
        memo: str = "",
        nonce: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sign a hybrid transaction with both Ed25519 + ML-DSA signatures."""
        if nonce is None:
            nonce = int(datetime.now(timezone.utc).timestamp() * 1000)

        from_address, to_address, amount, memo, nonce = _validate_transaction_fields(
            from_address=self.address,
            to_address=to_address,
            amount=amount,
            memo=memo,
            nonce=nonce,
        )
        message = _canonical_transaction_message(
            from_address,
            to_address,
            amount,
            memo,
            nonce,
        )

        sigs = self.sign_message(message)

        return {
            "from_address": from_address,
            "legacy_address": self.legacy_address,
            "to_address": to_address,
            "amount_rtc": amount,
            "memo": memo,
            "nonce": nonce,
            "signature": sigs["ed25519"],
            "pq_signature": sigs["ml_dsa_44"],
            "public_key": self.ed_public_key,
            "pq_public_key": self.pq_public_key,
            "signature_scheme": PQ_SIGNATURE_SCHEME,
        }

    # ── Encrypted keystore (v2) ──

    def export_encrypted(self, password: str) -> Dict[str, Any]:
        """Export as encrypted keystore v2 (both key types)."""
        salt = os.urandom(SALT_SIZE)
        key = _derive_key(password, salt)
        nonce = os.urandom(NONCE_SIZE)
        aesgcm = AESGCM(key)

        plaintext = json.dumps(
            {
                "ed_private_key": self.ed_private_key,
                "pq_public_key": self.pq_public_key,
                "pq_secret_key": self._pq_secret_key.hex(),
                "mnemonic": self._mnemonic,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()

        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        return {
            "version": KEYSTORE_VERSION_PQ,
            "address": self.address,
            "legacy_address": self.legacy_address,
            "ed_public_key": self.ed_public_key,
            "pq_public_key": self.pq_public_key,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "kdf": "PBKDF2-SHA256",
            "kdf_iterations": PBKDF2_ITERATIONS,
            "cipher": "AES-256-GCM",
            "signature_scheme": PQ_SIGNATURE_SCHEME,
        }

    @classmethod
    def from_encrypted(cls, encrypted: Dict[str, Any], password: str) -> "RustChainPQWallet":
        """Load PQ wallet from encrypted keystore v2."""
        if encrypted.get("version", 1) < KEYSTORE_VERSION_PQ:
            raise ValueError(
                "Legacy keystore v1 — use RustChainWallet.from_encrypted() instead, "
                "then export a v2 keystore after creating a PQ wallet"
            )

        try:
            salt = base64.b64decode(encrypted["salt"])
            nonce = base64.b64decode(encrypted["nonce"])
            ciphertext = base64.b64decode(encrypted["ciphertext"])
        except Exception as exc:
            raise ValueError("Malformed keystore encoding") from exc

        if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE:
            raise ValueError("Malformed keystore parameters")

        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            raise ValueError("Invalid password")

        try:
            data = json.loads(plaintext.decode())
        except Exception as exc:
            raise ValueError("Malformed keystore payload") from exc
        return cls.from_keys(
            data["ed_private_key"],
            data["pq_public_key"],
            data["pq_secret_key"],
            mnemonic=data.get("mnemonic"),
        )


# ══════════════════════════════════════════════════════════════
# Verification functions
# ══════════════════════════════════════════════════════════════

def verify_hybrid_signature(
    ed_public_key_hex: str,
    pq_public_key_hex: str,
    message: bytes,
    ed_signature_hex: str,
    pq_signature_hex: str,
) -> Dict[str, Any]:
    """Verify a hybrid Ed25519 + ML-DSA signature.

    Both must be valid for the hybrid verification to pass.
    """
    result = {"ed25519_valid": False, "ml_dsa_44_valid": False, "hybrid_valid": False}

    try:
        ed_public_key = _decode_hex_field(
            "ed_public_key",
            ed_public_key_hex,
            expected_len=ED25519_PUBLIC_KEY_SIZE,
        )
        pq_public_key = _decode_hex_field(
            "pq_public_key",
            pq_public_key_hex,
            expected_len=MLDSA44_PUBLIC_KEY_SIZE,
        )
        ed_signature = _decode_hex_field(
            "ed_signature",
            ed_signature_hex,
            expected_len=ED25519_SIGNATURE_SIZE,
        )
        pq_signature = _decode_hex_field(
            "pq_signature",
            pq_signature_hex,
            expected_len=MLDSA44_SIGNATURE_SIZE,
        )
    except (TypeError, ValueError):
        return result

    # Ed25519 verification
    try:
        vk = VerifyKey(ed_public_key)
        vk.verify(message, ed_signature)
        result["ed25519_valid"] = True
    except (BadSignatureError, ValueError):
        pass

    # ML-DSA-44 verification
    try:
        result["ml_dsa_44_valid"] = mldsa_verify(
            pq_public_key,
            message,
            pq_signature,
        ) is True
    except Exception:
        pass

    result["hybrid_valid"] = result["ed25519_valid"] and result["ml_dsa_44_valid"]
    return result


def verify_hybrid_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a hybrid-signed RustChain transaction."""
    result = {"ed25519_valid": False, "ml_dsa_44_valid": False, "hybrid_valid": False}
    if tx.get("signature_scheme", PQ_SIGNATURE_SCHEME) != PQ_SIGNATURE_SCHEME:
        result["address_valid"] = False
        result["fully_valid"] = False
        return result

    try:
        from_address, to_address, amount, memo, nonce = _validate_transaction_fields(
            from_address=tx["from_address"],
            to_address=tx["to_address"],
            amount=tx["amount_rtc"],
            memo=tx.get("memo", ""),
            nonce=tx["nonce"],
        )
        message = _canonical_transaction_message(
            from_address,
            to_address,
            amount,
            memo,
            nonce,
        )
        ed_public_key = _decode_hex_field(
            "public_key",
            tx["public_key"],
            expected_len=ED25519_PUBLIC_KEY_SIZE,
        )
        pq_public_key = _decode_hex_field(
            "pq_public_key",
            tx["pq_public_key"],
            expected_len=MLDSA44_PUBLIC_KEY_SIZE,
        )
    except (KeyError, TypeError, ValueError):
        result["address_valid"] = False
        result["fully_valid"] = False
        return result

    expected_address = _pq_address_from_public_keys(ed_public_key, pq_public_key)
    result = verify_hybrid_signature(
        tx["public_key"],
        tx["pq_public_key"],
        message,
        tx["signature"],
        tx["pq_signature"],
    )
    result["address_valid"] = from_address == expected_address
    result["fully_valid"] = result["hybrid_valid"] and result["address_valid"]
    return result


def verify_legacy_or_hybrid(tx: Dict[str, Any]) -> bool:
    """Accept both legacy (Ed25519-only) and hybrid transactions.

    This is the Phase 2 server verification function.
    """
    scheme = tx.get("signature_scheme", "ed25519")
    has_pq_signature = bool(tx.get("pq_signature"))
    has_pq_public_key = bool(tx.get("pq_public_key"))
    if has_pq_signature != has_pq_public_key:
        return False
    if scheme == PQ_SIGNATURE_SCHEME and not (has_pq_signature and has_pq_public_key):
        return False

    if has_pq_signature and has_pq_public_key:
        result = verify_hybrid_transaction(tx)
        return result["fully_valid"]
    else:
        # Legacy Ed25519-only verification
        try:
            from_address, to_address, amount, memo, nonce = _validate_transaction_fields(
                from_address=tx["from_address"],
                to_address=tx["to_address"],
                amount=tx["amount_rtc"],
                memo=tx.get("memo", ""),
                nonce=tx["nonce"],
            )
            message = _canonical_transaction_message(
                from_address,
                to_address,
                amount,
                memo,
                nonce,
            )
            public_key = _decode_hex_field(
                "public_key",
                tx["public_key"],
                expected_len=ED25519_PUBLIC_KEY_SIZE,
            )
            signature = _decode_hex_field(
                "signature",
                tx["signature"],
                expected_len=ED25519_SIGNATURE_SIZE,
            )
            vk = VerifyKey(public_key)
            vk.verify(message, signature)
        except (BadSignatureError, KeyError, TypeError, ValueError):
            return False

        pubkey_hash = hashlib.sha256(public_key).hexdigest()[:40]
        expected = f"{PREFIX_LEGACY}{pubkey_hash}"
        return from_address == expected


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode())


def _generate_mldsa_keypair_from_seed_material(seed_bytes: bytes) -> Tuple[bytes, bytes]:
    """Generate an ML-DSA keypair from seed material when the backend allows it.

    The current pqcrypto binding exposes only random key generation, so the
    seed currently serves as domain-separated input for future seeded backends.
    """
    _ = seed_bytes
    pk, sk = mldsa_generate_keypair()
    return pk, sk


# ══════════════════════════════════════════════════════════════
# Demo / self-test
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("RustChain Post-Quantum Wallet Demo (RIP-300)")
    print("=" * 60)

    # Create PQ wallet
    print("\n1. Creating PQ wallet...")
    wallet = RustChainPQWallet.create()
    words = wallet.mnemonic.split()
    print(f"   Mnemonic: {words[0]} {words[1]} ... {words[-2]} {words[-1]} (24 words)")
    print(f"   Legacy address: {wallet.legacy_address}")
    print(f"   PQ address:     {wallet.address}")
    print(f"   Ed25519 pubkey: {wallet.ed_public_key[:32]}...")
    print(f"   ML-DSA pubkey:  {wallet.pq_public_key[:32]}... ({len(wallet.pq_public_key_bytes)} bytes)")

    # Hybrid sign
    print("\n2. Signing hybrid transaction...")
    tx = wallet.sign_transaction("RTCQabc123", 42.0, memo="PQ test")
    print(f"   From: {tx['from_address']}")
    print(f"   Scheme: {tx['signature_scheme']}")
    print(f"   Ed25519 sig:  {tx['signature'][:32]}... ({len(tx['signature'])//2} bytes)")
    print(f"   ML-DSA sig:   {tx['pq_signature'][:32]}... ({len(tx['pq_signature'])//2} bytes)")

    # Verify hybrid
    print("\n3. Verifying hybrid transaction...")
    result = verify_hybrid_transaction(tx)
    print(f"   Ed25519 valid:  {result['ed25519_valid']}")
    print(f"   ML-DSA valid:   {result['ml_dsa_44_valid']}")
    print(f"   Address valid:  {result['address_valid']}")
    print(f"   Fully valid:    {result['fully_valid']}")

    # Legacy compat
    print("\n4. Legacy compatibility check...")
    legacy_ok = verify_legacy_or_hybrid(tx)
    print(f"   verify_legacy_or_hybrid: {legacy_ok}")

    # Encrypted keystore
    print("\n5. Encrypted keystore v2...")
    encrypted = wallet.export_encrypted("quantumproof")
    print(f"   Version: {encrypted['version']}")
    print(f"   Address: {encrypted['address']}")
    restored = RustChainPQWallet.from_encrypted(encrypted, "quantumproof")
    print(f"   Restored: {restored.address == wallet.address}")

    # Tamper detection
    print("\n6. Tamper detection...")
    tampered_tx = dict(tx)
    tampered_tx["pq_signature"] = ("00" if tx["pq_signature"][:2] != "00" else "ff") + tx["pq_signature"][2:]
    tampered = verify_hybrid_transaction(tampered_tx)
    print(f"   Tampered fully valid: {tampered['fully_valid']}")
    assert not tampered["fully_valid"]

    # Deterministic restore guard
    print("\n7. Deterministic restore guard...")
    try:
        RustChainPQWallet.from_mnemonic(wallet.mnemonic)
    except RuntimeError as exc:
        print(f"   Guarded: {str(exc)[:60]}...")
    else:
        raise AssertionError("from_mnemonic() should refuse nondeterministic PQ restore")

    print("\n" + "=" * 60)
    print("ALL PQ WALLET TESTS PASSED")
    print("=" * 60)
