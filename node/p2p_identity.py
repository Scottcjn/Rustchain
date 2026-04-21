import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

RC_P2P_PRIVKEY_PATH = "p2p_identity.pem"
RC_P2P_VERSION_FILE = "p2p_identity.version"

@dataclass
class PeerEntry:
    pubkey: bytes
    not_before: int
    not_after: int

class LocalKeypair:
    def __init__(self, path: str = RC_P2P_PRIVKEY_PATH, force_keygen: bool = False):
        self.path = path
        self.key_version = 1
        self._load_version()
        
        if force_keygen or not os.path.exists(self.path):
            self.generate_keypair()
        else:
            self._load_keypair()

    def _load_version(self):
        if os.path.exists(RC_P2P_VERSION_FILE):
            with open(RC_P2P_VERSION_FILE, "r") as f:
                self.key_version = int(f.read().strip())

    def _save_version(self):
        with open(RC_P2P_VERSION_FILE, "w") as f:
            f.write(str(self.key_version))

    def generate_keypair(self):
        # Item A: Key Rotation - Archive old key before generating new one
        if os.path.exists(self.path):
            archive_path = f"{self.path}.v{self.key_version}"
            os.rename(self.path, archive_path)
            self.key_version += 1
            self._save_version()

        privkey = ed25519.Ed25519PrivateKey.generate()
        with open(self.path, "wb") as f:
            f.write(privkey.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        self.privkey = privkey
        self.pubkey = privkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def _load_keypair(self):
        with open(self.path, "rb") as f:
            self.privkey = serialization.load_pem_private_key(f.read(), password=None)
        self.pubkey = self.privkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

def get_default_privkey_path():
    # Item C: Non-root key path fallback
    paths = [
        RC_P2P_PRIVKEY_PATH,
        "/etc/rustchain/p2p_identity.pem",
        os.path.expanduser("~/.rustchain/p2p_identity.pem")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return RC_P2P_PRIVKEY_PATH

def verify_peer_expiry(entry: PeerEntry):
    # Item B: Registry expiry check with 5 min skew
    now = int(time.time())
    skew = 300
    if now < (entry.not_before - skew) or now > (entry.not_after + skew):
        return False
    return True
