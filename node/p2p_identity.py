#!/usr/bin/env python3
\"\"\"
RustChain P2P Identity — Phase F Hardening (#2273)
=================================================

Per-peer Ed25519 identity with Key Rotation, Registry Expiry, and Flexible Paths.
\"\"\"
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signing mode
# ---------------------------------------------------------------------------
_MODE_RAW = os.environ.get(\"RC_P2P_SIGNING_MODE\", \"hmac\").strip().lower()
_VALID_MODES = {\"hmac\", \"dual\", \"ed25519\", \"strict\"}
if _MODE_RAW not in _VALID_MODES:
    logger.warning(
        f\"[P2P] Unknown RC_P2P_SIGNING_MODE={_MODE_RAW!r}; defaulting to 'hmac'. \"
        f\"Valid: {_VALID_MODES}\"
    )
    _MODE_RAW = \"hmac\"
SIGNING_MODE = _MODE_RAW

# Paths
DEFAULT_PRIVKEY_PATH = os.environ.get(
    \"RC_P2P_PRIVKEY_PATH\",
    \"/etc/rustchain/p2p_identity.pem\",
)
DEFAULT_REGISTRY_PATH = os.environ.get(
    \"RC_P2P_PEER_REGISTRY\",
    \"/etc/rustchain/peer_registry.json\",
)

def _require_crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            NoEncryption,
            load_pem_private_key,
        )
        from cryptography.exceptions import InvalidSignature
        return (
            Ed25519PrivateKey,
            Ed25519PublicKey,
            Encoding,
            PrivateFormat,
            NoEncryption,
            load_pem_private_key,
            InvalidSignature,
        )
    except ImportError as e:
        raise ImportError(
            \"[P2P] cryptography library required for Phase F Ed25519 mode. \"
            \"Install with: pip install cryptography\"
        ) from e

# ---------------------------------------------------------------------------
# Keypair management
# ---------------------------------------------------------------------------
class LocalKeypair:
    \"\"\"Per-node Ed25519 identity with key rotation (Item A) and flexible paths (Item C).\"\"\"

    def __init__(self, path: Optional[str] = None):
        # Item C: Non-root key path fallback
        # Priority: $RC_P2P_PRIVKEY_PATH -> /etc/rustchain/p2p_identity.pem -> $HOME/.rustchain/p2p_identity.pem
        if path:
            self.path = Path(path)
        else:
            env_path = os.environ.get(\"RC_P2P_PRIVKEY_PATH\")
            if env_path:
                self.path = Path(env_path)
            elif os.access(\"/etc/rustchain/p2p_identity.pem\", os.W_OK):
                self.path = Path(\"/etc/rustchain/p2p_identity.pem\")
            else:
                home = Path.home()
                self.path = home / \".rustchain\" / \"p2p_identity.pem\"
        
        logger.info(f\"[P2P] Using identity path: {self.path}\")
        self._privkey = None
        self._pubkey_hex: Optional[str] = None
        self.key_version = 0

    def _load_or_generate(self):
        (
            Ed25519PrivateKey,
            Ed25519PublicKey,
            Encoding,
            PrivateFormat,
            NoEncryption,
            load_pem_private_key,
            _InvalidSignature,
        ) = _require_crypto()

        if self.path.exists():
            with open(self.path, \"rb\") as f:
                # We expect a JSON wrapper for versioning, or raw PEM for legacy
                try:
                    data = json.load(f)
                    if \"pem\" in data and \"version\" in data:
                        self.key_version = data[\"version\"]
                        self._privkey = load_pem_private_key(data[\"pem\"].encode(), password=None)
                    else:
                        # Legacy raw PEM
                        f.seek(0)
                        self._privkey = load_pem_private_key(f.read(), password=None)
                        self.key_version = 0
                except json.JSONDecodeError:
                    f.seek(0)
                    self._privkey = load_pem_private_key(f.read(), password=None)
                    self.key_version = 0
            logger.info(f\"[P2P] Loaded Ed25519 identity v{self.key_version} from {self.path}\")
        else:
            self._generate_new(version=0)

        from cryptography.hazmat.primitives.serialization import (
            Encoding as _Enc,
            PublicFormat as _Pub,
        )
        pub_bytes = self._privkey.public_key().public_bytes(_Enc.Raw, _Pub.Raw)
        self._pubkey_hex = pub_bytes.hex()

    def _generate_new(self, version: int):
        (
            Ed25519PrivateKey,
            Ed25519PublicKey,
            Encoding,
            PrivateFormat,
            NoEncryption,
            load_pem_private_key,
            _InvalidSignature,
        ) = _require_crypto()

        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Item A: Rotation - keep old keypair as rollback grace
        if self.path.exists():
            old_path = self.path.with_name(f\"p2p_identity.v{self.key_version}.pem\")
            self.path.rename(old_path)
            logger.info(f\"[P2P] Rotated old key to {old_path}\")

        self._privkey = Ed25519PrivateKey.generate()
        pem = self._privkey.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption
        )
        
        # Save as JSON to store version
        payload = {
            \"version\": version,
            \"pem\": pem.decode('utf-8')
        }
        
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, json.dumps(payload).encode())
        finally:
            os.close(fd)
        
        self.key_version = version
        logger.info(f\"[P2P] Generated new Ed25519 identity v{version} at {self.path}\")

    def rotate(self):
        \"\"\"Force a fresh keypair generation with incremented version (Item A).\"\"\"
        self._load_or_generate()
        new_version = self.key_version + 1
        self._generate_new(version=new_version)
        # Update pubkey_hex after rotation
        from cryptography.hazmat.primitives.serialization import (
            Encoding as _Enc,
            PublicFormat as _Pub,
        )
        pub_bytes = self._privkey.public_key().public_bytes(_Enc.Raw, _Pub.Raw)
        self._pubkey_hex = pub_bytes.hex()
        logger.info(f\"[P2P] Key rotation complete. New version: {self.key_version}\")

    def sign(self, data: bytes) -> str:
        if self._privkey is None:
            self._load_or_generate()
        return self._privkey.sign(data).hex()

    @property
    def pubkey_hex(self) -> str:
        if self._pubkey_hex is None:
            self._load_or_generate()
        return self._pubkey_hex

# ---------------------------------------------------------------------------
# Peer registry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PeerEntry:
    node_id: str
    pubkey_hex: str
    key_version: int = 0
    not_before: Optional[str] = None
    not_after: Optional[str] = None

class PeerRegistry:
    \"\"\"Static peer registry with Key Versioning (Item A) and Expiry (Item B).\"\"\"

    def __init__(self, path: str = DEFAULT_REGISTRY_PATH):
        self.path = Path(path)
        self._by_node_id: Dict[str, PeerEntry] = {}
        self._loaded = False

    def load(self) -> None:
        if not self.path.exists():
            logger.warning(
                f\"[P2P] Peer registry not found at {self.path}. \"
                f\"Ed25519 verification will reject all peers until provisioned.\"
            )
            self._by_node_id = {}
            self._loaded = True
            return
        with open(self.path) as f:
            data = json.load(f)
        peers = data.get(\"peers\", [])
        entries: Dict[str, PeerEntry] = {}
        for p in peers:
            nid = p.get(\"node_id\")
            pk = p.get(\"pubkey_hex\")
            if not nid or not pk:
                logger.warning(f\"[P2P] Skipping malformed peer entry: {p}\")
                continue
            entries[nid] = PeerEntry(
                node_id=nid, 
                pubkey_hex=pk, 
                key_version=p.get(\"key_version\", 0),
                not_before=p.get(\"not_before\"),
                not_after=p.get(\"not_after\")
            )
        self._by_node_id = entries
        self._loaded = True
        logger.info(f\"[P2P] Loaded {len(entries)} peers from registry {self.path}\")

    def get_pubkey(self, node_id: str) -> Optional[str]:
        if not self._loaded:
            self.load()
        entry = self._by_node_id.get(node_id)
        if not entry:
            return None
            
        # Item B: Registry Expiry check
        if entry.not_before or entry.not_after:
            try:
                now = datetime.now(timezone.utc).isoformat()
                # Basic ISO-8601 comparison
                if entry.not_before and now < entry.not_before:
                    logger.debug(f\"[P2P] Peer {node_id} not yet valid (not_before={entry.not_before})\")
                    return None
                if entry.not_after and now > entry.not_after:
                    logger.debug(f\"[P2P] Peer {node_id} expired (not_after={entry.not_after})\")
                    return None
            except Exception as e:
                logger.warning(f\"[P2P] Expiry check failed for {node_id}: {e}\")
        
        return entry.pubkey_hex

    def __len__(self) -> int:
        if not self._loaded:
            self.load()
        return len(self._by_node_id)

# ---------------------------------------------------------------------------
# Signature bundle
# ---------------------------------------------------------------------------
def pack_signature(hmac_sig: Optional[str], ed25519_sig: Optional[str]) -> str:
    if ed25519_sig is None:
        return hmac_sig or \"\"
    bundle = {}
    if hmac_sig:
        bundle[\"h\"] = hmac_sig
    bundle[\"e\"] = ed25519_sig
    return json.dumps(bundle, separators=\",\", \":\")

def unpack_signature(sig_field: str) -> Tuple[Optional[str], Optional[str]]:
    if not sig_field:
        return None, None
    stripped = sig_field.strip()
    if stripped.startswith(\"{\"):
        try:
            bundle = json.loads(stripped)
            return bundle.get(\"h\"), bundle.get(\"e\")
        except json.JSONDecodeError:
            return None, None
    return stripped, None

def verify_ed25519(pubkey_hex: str, signature_hex: str, data: bytes) -> bool:
    (
        _PrivKey,
        Ed25519PublicKey,
        _Enc,
        _Priv,
        _NoEnc,
        _load_pem,
        InvalidSignature,
    ) = _require_crypto()
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        pub.verify(bytes.fromhex(signature_hex), data)
        return True
    except (InvalidSignature, ValueError):
        return False
