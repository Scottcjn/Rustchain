import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def blake2b256_hex(data: Any) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def address_from_public_key(pubkey_bytes: bytes) -> str:
    digest = blake2b256_hex(pubkey_bytes)
    return f"RTC{digest[:40]}"


class Ed25519Signer:
    def __init__(self, priv_key_bytes: bytes):
        if len(priv_key_bytes) != 32:
            raise ValueError("Ed25519 private key must be 32 bytes")
        self._sk = Ed25519PrivateKey.from_private_bytes(priv_key_bytes)
        self._vk = self._sk.public_key()

    @property
    def public_key_bytes(self) -> bytes:
        return self._vk.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)

    @property
    def public_key_hex(self) -> str:
        return self.public_key_bytes.hex()

    @property
    def private_key_hex(self) -> str:
        return self._sk.private_bytes(encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw, encryption_algorithm=serialization.NoEncryption()).hex()

    def sign(self, payload: bytes) -> str:
        return self._sk.sign(payload).hex()

    @staticmethod
    def verify(payload: bytes, signature_hex: str, public_key_hex: str) -> bool:
        try:
            vk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            vk.verify(bytes.fromhex(signature_hex), payload)
            return True
        except (InvalidSignature, ValueError):
            return False


def generate_wallet_keypair():
    seed = secrets.token_bytes(32)
    signer = Ed25519Signer(seed)
    pub = signer.public_key_hex
    priv = signer.private_key_hex
    addr = address_from_public_key(bytes.fromhex(pub))
    return addr, pub, priv


@dataclass
class SignedTransaction:
    from_addr: str
    to_addr: str
    amount_urtc: int
    nonce: int
    timestamp: int
    memo: str = ""
    signature: str = ""
    public_key: str = ""
    tx_hash: Optional[str] = None

    def signing_payload(self) -> bytes:
        data = {
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "amount_urtc": int(self.amount_urtc),
            "nonce": int(self.nonce),
            "timestamp": int(self.timestamp),
            "memo": self.memo or "",
        }
        return canonical_json(data).encode()

    def compute_hash(self) -> str:
        return blake2b256_hex(self.signing_payload())

    def sign(self, signer: Ed25519Signer):
        self.public_key = signer.public_key_hex
        self.signature = signer.sign(self.signing_payload())
        self.tx_hash = self.compute_hash()

    def verify(self) -> bool:
        if not self.signature or not self.public_key:
            return False
        if address_from_public_key(bytes.fromhex(self.public_key)) != self.from_addr:
            return False
        if self.tx_hash and self.tx_hash != self.compute_hash():
            return False
        return Ed25519Signer.verify(self.signing_payload(), self.signature, self.public_key)

    def to_dict(self) -> Dict[str, Any]:
        if not self.tx_hash:
            self.tx_hash = self.compute_hash()
        return {
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "amount_urtc": self.amount_urtc,
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "memo": self.memo,
            "signature": self.signature,
            "public_key": self.public_key,
            "tx_hash": self.tx_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SignedTransaction":
        return cls(
            from_addr=d["from_addr"],
            to_addr=d["to_addr"],
            amount_urtc=int(d["amount_urtc"]),
            nonce=int(d["nonce"]),
            timestamp=int(d["timestamp"]),
            memo=d.get("memo", ""),
            signature=d.get("signature", ""),
            public_key=d.get("public_key", ""),
            tx_hash=d.get("tx_hash"),
        )


@dataclass
class CanonicalBlockHeader:
    version: int
    height: int
    timestamp: int
    prev_hash: str
    merkle_root: str
    state_root: str
    attestations_hash: str
    producer: str
    producer_sig: str = ""

    def signing_payload(self) -> bytes:
        data = {
            "version": self.version,
            "height": self.height,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "state_root": self.state_root,
            "attestations_hash": self.attestations_hash,
            "producer": self.producer,
        }
        return canonical_json(data).encode()

    def compute_hash(self) -> str:
        return blake2b256_hex(self.signing_payload())

    def sign(self, signer: Ed25519Signer):
        self.producer_sig = signer.sign(self.signing_payload())

    def verify_signature(self, public_key_hex: str) -> bool:
        return Ed25519Signer.verify(self.signing_payload(), self.producer_sig, public_key_hex)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "height": self.height,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "state_root": self.state_root,
            "attestations_hash": self.attestations_hash,
            "producer": self.producer,
            "producer_sig": self.producer_sig,
            "block_hash": self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalBlockHeader":
        return cls(
            version=int(d["version"]),
            height=int(d["height"]),
            timestamp=int(d["timestamp"]),
            prev_hash=d["prev_hash"],
            merkle_root=d["merkle_root"],
            state_root=d["state_root"],
            attestations_hash=d["attestations_hash"],
            producer=d["producer"],
            producer_sig=d.get("producer_sig", ""),
        )


class MerkleTree:
    def __init__(self):
        self._leaves: List[bytes] = []

    def add_leaf_hash(self, leaf_hash: bytes):
        if not isinstance(leaf_hash, (bytes, bytearray)):
            raise TypeError("leaf_hash must be bytes")
        if len(leaf_hash) != 32:
            raise ValueError("leaf_hash must be 32 bytes")
        self._leaves.append(bytes(leaf_hash))

    @staticmethod
    def _pair_hash(a: bytes, b: bytes) -> bytes:
        return hashlib.blake2b(a + b, digest_size=32).digest()

    @property
    def root(self) -> bytes:
        if not self._leaves:
            return b"\x00" * 32
        level = list(self._leaves)
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else left
                nxt.append(self._pair_hash(left, right))
            level = nxt
        return level[0]

    @property
    def root_hex(self) -> str:
        return self.root.hex()


# Wallet helpers
_WORDS = [
    "apple","badge","canyon","delta","ember","frost","globe","harbor","island","jungle",
    "kernel","lunar","matrix","nectar","orbit","pixel","quantum","radar","signal","thunder",
    "ultra","vector","willow","xenon","yonder","zephyr"
]


def _derive_seed_from_mnemonic(mnemonic: str, passphrase: str = "") -> bytes:
    return hashlib.pbkdf2_hmac('sha512', mnemonic.encode(), (mnemonic + passphrase).encode(), 2048, dklen=32)


def _gen_mnemonic(words: int = 24) -> str:
    return " ".join(secrets.choice(_WORDS) for _ in range(words))


@dataclass
class RustChainWallet:
    private_key_hex: str
    public_key_hex: str
    address: str
    mnemonic: Optional[str] = None

    @classmethod
    def create(cls) -> "RustChainWallet":
        mnemonic = _gen_mnemonic(24)
        seed = _derive_seed_from_mnemonic(mnemonic)
        signer = Ed25519Signer(seed)
        pub = signer.public_key_hex
        priv = signer.private_key_hex
        return cls(private_key_hex=priv, public_key_hex=pub, address=address_from_public_key(bytes.fromhex(pub)), mnemonic=mnemonic)

    @classmethod
    def from_mnemonic(cls, mnemonic: str) -> "RustChainWallet":
        words = [w for w in mnemonic.strip().split() if w]
        if len(words) not in (12, 24):
            raise ValueError("mnemonic must be 12 or 24 words")
        seed = _derive_seed_from_mnemonic(" ".join(words).lower())
        signer = Ed25519Signer(seed)
        pub = signer.public_key_hex
        priv = signer.private_key_hex
        return cls(private_key_hex=priv, public_key_hex=pub, address=address_from_public_key(bytes.fromhex(pub)), mnemonic=" ".join(words).lower())

    def export_encrypted(self, password: str) -> Dict[str, Any]:
        if not password:
            raise ValueError("password required")
        raw = json.dumps({
            "private_key_hex": self.private_key_hex,
            "public_key_hex": self.public_key_hex,
            "address": self.address,
            "mnemonic": self.mnemonic,
        }, sort_keys=True).encode()
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 200_000, dklen=32)
        mac = hmac.new(key, raw, hashlib.sha256).digest()
        ct = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return {
            "version": 1,
            "kdf": "pbkdf2-sha256",
            "iterations": 200000,
            "salt": base64.b64encode(salt).decode(),
            "cipher": "xor-stream",
            "ciphertext": base64.b64encode(ct).decode(),
            "mac": mac.hex(),
        }

    @classmethod
    def from_encrypted(cls, encrypted: Dict[str, Any], password: str) -> "RustChainWallet":
        salt = base64.b64decode(encrypted["salt"])
        ct = base64.b64decode(encrypted["ciphertext"])
        iterations = int(encrypted.get("iterations", 200000))
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations, dklen=32)
        raw = bytes(b ^ key[i % len(key)] for i, b in enumerate(ct))
        mac = hmac.new(key, raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, encrypted["mac"]):
            raise ValueError("invalid password or corrupted keystore")
        payload = json.loads(raw.decode())
        return cls(
            private_key_hex=payload["private_key_hex"],
            public_key_hex=payload["public_key_hex"],
            address=payload["address"],
            mnemonic=payload.get("mnemonic"),
        )

    def sign_transaction(self, to_address: str, amount_rtc: float, memo: str = "") -> Dict[str, Any]:
        amount_urtc = int(round(float(amount_rtc) * 10_000))
        nonce = int.from_bytes(os.urandom(4), "big")
        timestamp = int(__import__("time").time() * 1000)
        tx = SignedTransaction(
            from_addr=self.address,
            to_addr=to_address,
            amount_urtc=amount_urtc,
            nonce=nonce,
            timestamp=timestamp,
            memo=memo,
        )
        signer = Ed25519Signer(bytes.fromhex(self.private_key_hex))
        tx.sign(signer)
        return tx.to_dict()


def verify_transaction(tx_dict: Dict[str, Any]) -> bool:
    tx = SignedTransaction.from_dict(tx_dict)
    return tx.verify()
