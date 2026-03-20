# SPDX-License-Identifier: MIT

"""
Cryptographic utilities for RustChain wallet operations.
Provides key generation, mnemonic handling, encryption, and keystore management.
"""

import os
import json
import hashlib
import hmac
import secrets
import base64
from typing import Optional, Tuple, Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


# BIP39 wordlist subset for mnemonic generation
BIP39_WORDS = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd", "abuse",
    "access", "accident", "account", "accuse", "achieve", "acid", "acoustic", "acquire", "across", "act",
    "action", "actor", "actress", "actual", "adapt", "add", "addict", "address", "adjust", "admit",
    "adult", "advance", "advice", "aerobic", "affair", "afford", "afraid", "again", "agent", "agree",
    "ahead", "aim", "air", "airport", "aisle", "alarm", "album", "alcohol", "alert", "alien",
    "all", "alley", "allow", "almost", "alone", "alpha", "already", "also", "alter", "always",
    "amateur", "amazing", "among", "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle",
    "angry", "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique", "anxiety",
    "any", "apart", "apology", "appear", "apple", "approve", "april", "arch", "arctic", "area",
    "arena", "argue", "arm", "armed", "armor", "army", "around", "arrange", "arrest", "arrive",
    "arrow", "art", "artefact", "artist", "artwork", "ask", "aspect", "assault", "asset", "assist",
    "assume", "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction", "audit",
    "august", "aunt", "author", "auto", "autumn", "average", "avocado", "avoid", "awake", "aware",
    "away", "awesome", "awful", "awkward", "axis", "baby", "bachelor", "bacon", "badge", "bag",
    "balance", "balcony", "ball", "bamboo", "banana", "banner", "bar", "barely", "bargain", "barrel",
    "base", "basic", "basket", "battle", "beach", "bean", "beauty", "because", "become", "beef",
    "before", "begin", "behave", "behind", "believe", "below", "belt", "bench", "benefit", "best",
    "betray", "better", "between", "beyond", "bicycle", "bid", "bike", "bind", "biology", "bird",
    "birth", "bitter", "black", "blade", "blame", "blanket", "blast", "bleak", "bless", "blind",
    "blood", "blossom", "blow", "blue", "blur", "blush", "board", "boat", "body", "boil",
    "bomb", "bone", "bonus", "book", "boost", "border", "boring", "borrow", "boss", "bottom",
    "bounce", "box", "boy", "bracket", "brain", "brand", "brass", "brave", "bread", "breeze",
    "brick", "bridge", "brief", "bright", "bring", "brisk", "broccoli", "broken", "bronze", "broom",
    "brother", "brown", "brush", "bubble", "buddy", "budget", "buffalo", "build", "bulb", "bulk",
    "bullet", "bundle", "bunker", "burden", "burger", "burst", "bus", "business", "busy", "butter",
    "buyer", "buzz", "cabbage", "cabin", "cable", "cactus", "cage", "cake", "call", "calm",
    "camera", "camp", "can", "canal", "cancel", "candy", "cannon", "canoe", "canvas", "canyon"
]


class WalletCrypto:
    """Handles cryptographic operations for RustChain wallet."""

    def __init__(self):
        self.key_length = 32  # 256-bit keys

    def generate_mnemonic(self, word_count: int = 12) -> str:
        """Generate BIP39-compatible mnemonic phrase."""
        if word_count not in [12, 15, 18, 21, 24]:
            word_count = 12

        entropy_bits = (word_count * 11) - (word_count // 3)
        entropy_bytes = entropy_bits // 8

        entropy = secrets.token_bytes(entropy_bytes)
        checksum_bits = entropy_bytes * 8 // 32

        # Create checksum
        checksum = hashlib.sha256(entropy).digest()
        checksum_int = int.from_bytes(checksum, 'big') >> (256 - checksum_bits)

        # Combine entropy and checksum
        combined = (int.from_bytes(entropy, 'big') << checksum_bits) | checksum_int

        # Convert to word indices
        words = []
        for i in range(word_count):
            word_idx = combined & 0x7FF  # 11 bits
            combined >>= 11
            words.append(BIP39_WORDS[word_idx % len(BIP39_WORDS)])

        words.reverse()
        return ' '.join(words)

    def mnemonic_to_seed(self, mnemonic: str, passphrase: str = "") -> bytes:
        """Convert mnemonic to 64-byte seed using PBKDF2."""
        mnemonic_bytes = mnemonic.encode('utf-8')
        salt = ('mnemonic' + passphrase).encode('utf-8')

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA512(),
            length=64,
            salt=salt,
            iterations=2048
        )
        return kdf.derive(mnemonic_bytes)

    def derive_keypair(self, seed: bytes, path: str = "m/44'/0'/0'/0/0") -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Derive Ed25519 keypair from seed using simplified derivation."""
        # Simplified path derivation - hash seed with path
        path_bytes = path.encode('utf-8')
        derived_key = hmac.new(seed[:32], path_bytes, hashlib.sha256).digest()

        private_key = Ed25519PrivateKey.from_private_bytes(derived_key)
        public_key = private_key.public_key()

        return private_key, public_key

    def sign_transaction(self, private_key: Ed25519PrivateKey, message: bytes) -> bytes:
        """Sign message with Ed25519 private key."""
        return private_key.sign(message)

    def verify_signature(self, public_key: Ed25519PublicKey, signature: bytes, message: bytes) -> bool:
        """Verify Ed25519 signature."""
        try:
            public_key.verify(signature, message)
            return True
        except Exception:
            return False

    def derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        return kdf.derive(password.encode('utf-8'))

    def encrypt_data(self, data: bytes, password: str) -> Dict[str, str]:
        """Encrypt data with AES-256-GCM."""
        salt = secrets.token_bytes(16)
        key = self.derive_key_from_password(password, salt)

        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, data, None)

        return {
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'salt': base64.b64encode(salt).decode('utf-8'),
            'algorithm': 'AES-256-GCM'
        }

    def decrypt_data(self, encrypted_data: Dict[str, str], password: str) -> bytes:
        """Decrypt AES-256-GCM encrypted data."""
        ciphertext = base64.b64decode(encrypted_data['ciphertext'])
        nonce = base64.b64decode(encrypted_data['nonce'])
        salt = base64.b64decode(encrypted_data['salt'])

        key = self.derive_key_from_password(password, salt)
        aesgcm = AESGCM(key)

        return aesgcm.decrypt(nonce, ciphertext, None)

    def create_keystore(self, private_key: Ed25519PrivateKey, password: str, address: str) -> Dict[str, Any]:
        """Create encrypted keystore file format."""
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        encrypted = self.encrypt_data(private_bytes, password)

        keystore = {
            'version': 1,
            'id': secrets.token_hex(16),
            'address': address,
            'crypto': encrypted,
            'timestamp': int(os.path.getmtime(__file__) if os.path.exists(__file__) else 1704067200)
        }

        return keystore

    def load_keystore(self, keystore_data: Dict[str, Any], password: str) -> Ed25519PrivateKey:
        """Load private key from encrypted keystore."""
        crypto_data = keystore_data['crypto']
        private_bytes = self.decrypt_data(crypto_data, password)

        return Ed25519PrivateKey.from_private_bytes(private_bytes)

    def generate_address(self, public_key: Ed25519PublicKey) -> str:
        """Generate RustChain address from public key."""
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        # Hash public key and take first 20 bytes
        hash_obj = hashlib.sha256(public_bytes).digest()
        address_bytes = hash_obj[:20]

        # Add prefix and encode as hex
        return 'rtc1' + address_bytes.hex()

    def validate_mnemonic(self, mnemonic: str) -> bool:
        """Validate mnemonic phrase format."""
        words = mnemonic.strip().split()
        if len(words) not in [12, 15, 18, 21, 24]:
            return False

        # Check all words exist in wordlist
        for word in words:
            if word not in BIP39_WORDS:
                return False

        return True

    def create_wallet(self, password: str, mnemonic: Optional[str] = None) -> Dict[str, Any]:
        """Create new wallet with optional mnemonic."""
        if mnemonic is None:
            mnemonic = self.generate_mnemonic()
        elif not self.validate_mnemonic(mnemonic):
            raise ValueError("Invalid mnemonic phrase")

        seed = self.mnemonic_to_seed(mnemonic)
        private_key, public_key = self.derive_keypair(seed)
        address = self.generate_address(public_key)

        keystore = self.create_keystore(private_key, password, address)

        return {
            'address': address,
            'mnemonic': mnemonic,
            'keystore': keystore,
            'public_key': public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            ).hex()
        }
