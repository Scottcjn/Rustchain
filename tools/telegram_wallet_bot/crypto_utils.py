"""
RustChain Wallet Cryptographic Utilities

Ed25519 key generation, address derivation, transaction signing,
and encrypted keystore management for the Telegram Wallet Bot.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random
from nacl.pwhash import argon2id


# === Key Generation ===

def generate_keypair() -> Tuple[str, str]:
    """
    Generate a new Ed25519 keypair.

    Returns:
        (private_key_hex, public_key_hex)
    """
    signing_key = SigningKey.generate()
    private_hex = signing_key.encode(encoder=HexEncoder).decode()
    public_hex = signing_key.verify_key.encode(encoder=HexEncoder).decode()
    return private_hex, public_hex


def pubkey_to_address(public_key_hex: str) -> str:
    """
    Derive RTC address from Ed25519 public key.

    Format: 'RTC' + first 40 chars of SHA256(pubkey_bytes)
    Matches the node's address_from_pubkey() function.
    """
    pubkey_bytes = bytes.fromhex(public_key_hex)
    pubkey_hash = hashlib.sha256(pubkey_bytes).hexdigest()[:40]
    return f"RTC{pubkey_hash}"


# === Transaction Signing ===

def sign_transaction(
    private_key_hex: str,
    from_addr: str,
    to_addr: str,
    amount_urtc: int,
    nonce: int,
    memo: str = "",
) -> str:
    """
    Sign a RustChain transaction with Ed25519.

    Message format: "{from}:{to}:{amount_urtc}:{nonce}:{memo}"
    Matches the node's verify_rtc_signature() expectations.

    Returns:
        Hex-encoded signature string.
    """
    message = f"{from_addr}:{to_addr}:{amount_urtc}:{nonce}:{memo}"
    message_bytes = message.encode("utf-8")

    signing_key = SigningKey(bytes.fromhex(private_key_hex))
    signed = signing_key.sign(message_bytes)
    # signed.signature is the 64-byte detached signature
    return signed.signature.hex()


def verify_signature(
    public_key_hex: str,
    message: str,
    signature_hex: str,
) -> bool:
    """Verify an Ed25519 signature."""
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(
            message.encode("utf-8"),
            bytes.fromhex(signature_hex),
        )
        return True
    except Exception:
        return False


# === Encrypted Keystore ===

def _derive_encryption_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte encryption key from password using Argon2id."""
    return argon2id.kdf(
        SecretBox.KEY_SIZE,
        password.encode("utf-8"),
        salt,
        opslimit=argon2id.OPSLIMIT_MODERATE,
        memlimit=argon2id.MEMLIMIT_MODERATE,
    )


def encrypt_keystore(
    private_key_hex: str,
    public_key_hex: str,
    password: str,
) -> dict:
    """
    Encrypt a private key with a password (Argon2id + XSalsa20-Poly1305).

    Returns a JSON-serialisable keystore dict.
    """
    salt = nacl_random(argon2id.SALTBYTES)
    key = _derive_encryption_key(password, salt)
    box = SecretBox(key)

    plaintext = json.dumps({
        "private_key": private_key_hex,
        "public_key": public_key_hex,
    }).encode("utf-8")

    encrypted = box.encrypt(plaintext)

    address = pubkey_to_address(public_key_hex)

    return {
        "version": 1,
        "address": address,
        "public_key": public_key_hex,
        "crypto": {
            "cipher": "xsalsa20-poly1305",
            "kdf": "argon2id",
            "salt": salt.hex(),
            "ciphertext": encrypted.hex(),
        },
        "created_at": int(time.time()),
    }


def decrypt_keystore(keystore: dict, password: str) -> Tuple[str, str]:
    """
    Decrypt a keystore and return (private_key_hex, public_key_hex).

    Raises ValueError if password is incorrect.
    """
    crypto = keystore["crypto"]
    salt = bytes.fromhex(crypto["salt"])
    ciphertext = bytes.fromhex(crypto["ciphertext"])

    key = _derive_encryption_key(password, salt)
    box = SecretBox(key)

    try:
        plaintext = box.decrypt(ciphertext)
    except Exception:
        raise ValueError("Incorrect password")

    data = json.loads(plaintext.decode("utf-8"))
    return data["private_key"], data["public_key"]


# === Keystore File Management ===

class KeystoreManager:
    """Manage per-user encrypted keystores on disk."""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(str(Path.home()), ".rustchain", "telegram_wallets")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_file(self, telegram_user_id: int) -> Path:
        return self.base_dir / f"user_{telegram_user_id}.json"

    def has_wallet(self, telegram_user_id: int) -> bool:
        return self._user_file(telegram_user_id).exists()

    def create_wallet(self, telegram_user_id: int, password: str) -> str:
        """
        Create a new wallet for a Telegram user.

        Returns the RTC address.
        Raises FileExistsError if wallet already exists.
        """
        path = self._user_file(telegram_user_id)
        if path.exists():
            raise FileExistsError("Wallet already exists for this user")

        priv, pub = generate_keypair()
        keystore = encrypt_keystore(priv, pub, password)
        keystore["telegram_user_id"] = telegram_user_id

        path.write_text(json.dumps(keystore, indent=2))
        return keystore["address"]

    def load_wallet(self, telegram_user_id: int) -> Optional[dict]:
        """Load the keystore metadata (no decryption)."""
        path = self._user_file(telegram_user_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def get_address(self, telegram_user_id: int) -> Optional[str]:
        """Get the RTC address for a user (no password needed)."""
        ks = self.load_wallet(telegram_user_id)
        return ks["address"] if ks else None

    def get_public_key(self, telegram_user_id: int) -> Optional[str]:
        """Get the public key for a user."""
        ks = self.load_wallet(telegram_user_id)
        return ks["public_key"] if ks else None

    def unlock(self, telegram_user_id: int, password: str) -> Tuple[str, str]:
        """
        Decrypt the keystore and return (private_key_hex, public_key_hex).

        Raises ValueError on wrong password, FileNotFoundError if no wallet.
        """
        ks = self.load_wallet(telegram_user_id)
        if ks is None:
            raise FileNotFoundError("No wallet found for this user")
        return decrypt_keystore(ks, password)

    def delete_wallet(self, telegram_user_id: int) -> bool:
        """Delete a user's wallet keystore."""
        path = self._user_file(telegram_user_id)
        if path.exists():
            path.unlink()
            return True
        return False
