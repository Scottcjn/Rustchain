#!/usr/bin/env python3
"""
RustChain P2P Identity — Phase F (#2256)
=========================================

Per-peer Ed25519 identity replacing the shared-HMAC trust model. Each node
has a unique keypair persisted to disk; peers authenticate each other via
a root-signed peer registry.

Dual-mode signing during migration (RC_P2P_SIGNING_MODE):
  - "hmac"     — legacy only, Phase 2 behavior
  - "dual"     — sign with BOTH HMAC and Ed25519, verify either (Phase F.1)
  - "ed25519"  — sign with Ed25519 only, verify either (Phase F.2)
  - "strict"   — sign + verify Ed25519 only, HMAC removed (Phase F.3)

Default: "dual" on the migration path. Set explicitly via environment.

Wire format for signature field:
  - Legacy HMAC-only:        raw hex (e.g. "abc123...")  — unchanged
  - Dual or Ed25519:         JSON dict: {"h":"<hmac_hex>","e":"<ed25519_hex>"}
    "h" key is optional in strict mode.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signing mode
# ---------------------------------------------------------------------------
# Default is "hmac" so legacy callers (and pre-Phase-F regression tests) keep
# working without needing cryptography/keypair paths to be configured.
# Production nodes on the F.1 migration path MUST explicitly set "dual" in
# their systemd unit or equivalent — see PR #2260 rollout plan.
_MODE_RAW = os.environ.get("RC_P2P_SIGNING_MODE", "hmac").strip().lower()
_VALID_MODES = {"hmac", "dual", "ed25519", "strict"}
if _MODE_RAW not in _VALID_MODES:
    logger.warning(
        f"[P2P] Unknown RC_P2P_SIGNING_MODE={_MODE_RAW!r}; defaulting to 'hmac'. "
        f"Valid: {_VALID_MODES}"
    )
    _MODE_RAW = "hmac"
SIGNING_MODE = _MODE_RAW

# Paths
DEFAULT_PRIVKEY_PATH = "/etc/rustchain/p2p_identity.pem"
DEFAULT_REGISTRY_PATH = os.environ.get(
    "RC_P2P_PEER_REGISTRY",
    "/etc/rustchain/peer_registry.json",
)


def get_default_privkey_path() -> Path:
    """Return the first writable private key path in priority order."""
    env_path = os.environ.get("RC_P2P_PRIVKEY_PATH")
    if env_path:
        return Path(env_path)

    paths = [
        Path("/etc/rustchain/p2p_identity.pem"),
        Path.home() / ".rustchain" / "p2p_identity.pem",
    ]

    # Use the first one that exists
    for p in paths:
        if p.exists():
            return p

    # Otherwise, return the first one we can write to (or the last fallback)
    for p in paths:
        try:
            p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Try to create/append to a dummy file to check writability
            test_file = p.parent / ".write_test"
            test_file.touch()
            test_file.unlink()
            return p
        except (PermissionError, OSError):
            continue

    return paths[-1]


# ---------------------------------------------------------------------------
# Optional dependency: cryptography.
#
# We import lazily so nodes running in "hmac" mode (legacy) don't require
# the cryptography library to be installed. Any node entering dual/ed25519/
# strict must have it.
# ---------------------------------------------------------------------------
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
            "[P2P] cryptography library required for Phase F Ed25519 mode. "
            "Install with: pip install cryptography"
        ) from e


# ---------------------------------------------------------------------------
# Keypair management
# ---------------------------------------------------------------------------
class LocalKeypair:
    """Per-node Ed25519 identity, persisted to disk.

    Generates on first access if none exists. Mode 0600 on the private key
    file. Public key is exposed as hex.
    """

    def __init__(self, path: Optional[str | Path] = None):
        if path is None:
            self.path = get_default_privkey_path()
        else:
            self.path = Path(path)
        self.key_version = 1
        self._privkey = None  # lazy
        self._pubkey_hex: Optional[str] = None
        self._loaded = False

    def sign(self, data: bytes) -> str:
        """Return hex-encoded Ed25519 signature over data."""
        self._ensure_loaded()
        return self._privkey.sign(data).hex()

    @property
    def pubkey_hex(self) -> str:
        self._ensure_loaded()
        return self._pubkey_hex

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_or_generate()
            self._loaded = True

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

        # Item A: Look for versioned key file if forced or if current exists
        force_keygen = os.environ.get("RC_P2P_KEYGEN", "0") == "1"
        version_path = self.path.with_suffix(".version")
        
        if self.path.exists() and not force_keygen:
            with open(self.path, "rb") as f:
                content = f.read()
                self._privkey = load_pem_private_key(content, password=None)
            
            # Item A: Load existing version
            if version_path.exists():
                try:
                    self.key_version = int(version_path.read_text().strip())
                except ValueError:
                    self.key_version = 1
            logger.info(f"[P2P] Loaded Ed25519 identity (v{self.key_version}) from {self.path}")
        else:
            if force_keygen and self.path.exists():
                # Item A: keep old keypair for rollback grace
                current_v = 1
                if version_path.exists():
                    try:
                        current_v = int(version_path.read_text().strip())
                    except ValueError:
                        pass
                
                old_path = self.path.parent / f"{self.path.stem}.v{current_v}.pem"
                self.path.replace(old_path)
                logger.info(f"[P2P] Archived old identity to {old_path}")
                self.key_version = current_v + 1
            
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._privkey = Ed25519PrivateKey.generate()
            pem = self._privkey.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            # Write with 0600 perms
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, pem)
            finally:
                os.close(fd)
            
            # Persist version
            version_path = self.path.with_suffix(".version")
            version_path.write_text(str(self.key_version))
            
            logger.info(f"[P2P] Generated new Ed25519 identity (v{self.key_version}) at {self.path}")

        from cryptography.hazmat.primitives.serialization import (
            Encoding as _Enc,
            PublicFormat as _Pub,
        )
        pub_bytes = self._privkey.public_key().public_bytes(_Enc.Raw, _Pub.Raw)
        self._pubkey_hex = pub_bytes.hex()


# ---------------------------------------------------------------------------
# Peer registry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PeerEntry:
    node_id: str
    pubkey_hex: str
    key_version: int = 1
    not_before: Optional[str] = None  # ISO-8601
    not_after: Optional[str] = None   # ISO-8601


class PeerRegistry:
    """Static peer registry loaded from JSON.

    Format (see DESIGN.md):
        {
          "version": 1,
          "peers": [
            {
              "node_id": "...",
              "pubkey_hex": "...",
              "key_version": 1,
              "not_before": "2026-04-01T00:00:00Z",
              "not_after": "2027-04-01T00:00:00Z"
            },
            ...
          ],
          "cluster_root_sig": "..."    # optional root-signed attestation
        }
    """

    def __init__(self, path: str = DEFAULT_REGISTRY_PATH):
        self.path = Path(path)
        self._by_node_id: Dict[str, PeerEntry] = {}
        self._loaded = False

    def load(self) -> None:
        if not self.path.exists():
            logger.warning(
                f"[P2P] Peer registry not found at {self.path}. "
                f"Ed25519 verification will reject all peers until provisioned."
            )
            self._by_node_id = {}
            self._loaded = True
            return
        with open(self.path) as f:
            data = json.load(f)
        peers = data.get("peers", [])
        entries: Dict[str, PeerEntry] = {}
        for p in peers:
            nid = p.get("node_id")
            pk = p.get("pubkey_hex")
            kv = p.get("key_version", 1)
            nb = p.get("not_before")
            na = p.get("not_after")
            if not nid or not pk:
                logger.warning(f"[P2P] Skipping malformed peer entry: {p}")
                continue
            entries[nid] = PeerEntry(
                node_id=nid,
                pubkey_hex=pk,
                key_version=kv,
                not_before=nb,
                not_after=na
            )
        self._by_node_id = entries
        self._loaded = True
        logger.info(f"[P2P] Loaded {len(entries)} peers from registry {self.path}")

    def get_pubkey(self, node_id: str) -> Optional[str]:
        if not self._loaded:
            self.load()
        entry = self._by_node_id.get(node_id)
        if not entry:
            return None

        # Item B: Registry expiry / not_before / not_after
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Clock skew tolerance: ±5 min (300s)
        SKEW = 300
        
        if entry.not_before:
            try:
                nb = datetime.fromisoformat(entry.not_before.replace("Z", "+00:00"))
                if (nb.timestamp() - now.timestamp()) > SKEW:
                    logger.warning(f"[P2P] Peer {node_id} registry entry not yet valid (not_before={entry.not_before})")
                    return None
            except ValueError:
                logger.warning(f"[P2P] Peer {node_id} has invalid not_before: {entry.not_before}")

        if entry.not_after:
            try:
                na = datetime.fromisoformat(entry.not_after.replace("Z", "+00:00"))
                if (now.timestamp() - na.timestamp()) > SKEW:
                    logger.warning(f"[P2P] Peer {node_id} registry entry expired (not_after={entry.not_after})")
                    return None
            except ValueError:
                logger.warning(f"[P2P] Peer {node_id} has invalid not_after: {entry.not_after}")

        return entry.pubkey_hex

    def get_entry(self, node_id: str) -> Optional[PeerEntry]:
        if not self._loaded:
            self.load()
        # Returns pubkey if valid per get_pubkey, then the entry object
        if self.get_pubkey(node_id) is None:
            return None
        return self._by_node_id.get(node_id)

    def __len__(self) -> int:
        if not self._loaded:
            self.load()
        return len(self._by_node_id)


# ---------------------------------------------------------------------------
# Signature bundle: JSON-encoded dual signature (or legacy hex)
# ---------------------------------------------------------------------------
def pack_signature(hmac_sig: Optional[str], ed25519_sig: Optional[str], key_version: int = 1) -> str:
    """Pack one or two signatures into the wire-format signature field.

    - HMAC only (legacy): return hex string as-is.
    - Ed25519 only OR dual: return JSON dict string.
    """
    if ed25519_sig is None:
        return hmac_sig or ""
    bundle = {}
    if hmac_sig:
        bundle["h"] = hmac_sig
    bundle["e"] = ed25519_sig
    if key_version != 1:
        bundle["v"] = key_version
    return json.dumps(bundle, separators=(",", ":"))


def unpack_signature(sig_field: str) -> Tuple[Optional[str], Optional[str], int]:
    """Inverse of pack_signature.

    Returns (hmac_sig, ed25519_sig, key_version). Either sig may be None if not present.
    Treats raw-hex strings as legacy HMAC-only (version 1).
    """
    if not sig_field:
        return None, None, 1
    stripped = sig_field.strip()
    if stripped.startswith("{"):
        try:
            bundle = json.loads(stripped)
            return bundle.get("h"), bundle.get("e"), bundle.get("v", 1)
        except json.JSONDecodeError:
            return None, None, 1
    # Legacy hex — assume HMAC, version 1
    return stripped, None, 1


def unpack_signature_v2(sig_field: str) -> Tuple[Optional[str], Optional[str], int]:
    """Deprecated alias for unpack_signature."""
    return unpack_signature(sig_field)


# ---------------------------------------------------------------------------
# Verification helper
# ---------------------------------------------------------------------------
def verify_ed25519(pubkey_hex: str, signature_hex: str, data: bytes) -> bool:
    """Verify an Ed25519 signature. Returns False on any error."""
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
