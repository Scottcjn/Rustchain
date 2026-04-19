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
        import os, logging
        if path is None:
            env_path = os.getenv("RC_P2P_PRIVKEY_PATH")
            candidates = [Path(env_path)] if env_path else []
            candidates += [Path("/etc/rustchain/p2p_identity.pem"), Path.home() / ".rustchain" / "p2p_identity.pem"]
            
            chosen = None
            for p in candidates:
                if p.exists(): chosen = p; break
            
            if not chosen:
                for p in candidates:
                    try:
                        p.parent.mkdir(parents=True, exist_ok=True)
                        with open(p, 'a'): pass # test write access
                        chosen = p; break
                    except Exception: pass
                    
            if not chosen: raise PermissionError("No writable path found.")
            
            self.path = chosen
            logging.info(f"Chosen P2P path: {self.path}")
        else:
            self.path = Path(path)
            
        self.key_version = 1
        self._privkey = None
        self._pubkey_hex: Optional[str] = None

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

        force_keygen = os.environ.get("RC_P2P_KEYGEN", "0") == "1"
        version_file = self.path.with_suffix(".version")
        
        # Load version or default to 1
        current_version = 1
        if version_file.exists():
            try: current_version = int(version_file.read_text().strip())
            except: pass

        if self.path.exists() and force_keygen:
            # Backup old key: identity.pem -> identity.v1.pem
            backup_path = self.path.parent / f"{self.path.stem}.v{current_version}{self.path.suffix}"
            self.path.rename(backup_path)
            current_version += 1
            version_file.write_text(str(current_version))
            logging.info(f"Rotated P2P key to version {current_version}. Old key saved to {backup_path}")

        if self.path.exists():
            with open(self.path, "rb") as f:
                self._privkey = load_pem_private_key(f.read(), password=None)
        else:
            self._privkey = Ed25519PrivateKey.generate()
            with open(self.path, "wb") as f:
                f.write(self._privkey.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
            version_file.write_text(str(current_version))
            self.path.chmod(0o600)

        self.key_version = current_version
        self._pubkey_hex = self._privkey.public_key().public_bytes(Encoding.X962, PrivateFormat.OpenSSH).hex() # Placeholder for hex logic
    def sign(self, data: bytes) -> str:
        """Return hex-encoded Ed25519 signature over data."""
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

        # Item B: Registry expiry logic
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        tolerance = timedelta(minutes=5)

        if entry.not_before:
            nb = datetime.fromisoformat(entry.not_before.replace('Z', '+00:00'))
            if now + tolerance < nb:
                return None
        
        if entry.not_after:
            na = datetime.fromisoformat(entry.not_after.replace('Z', '+00:00'))
            if now - tolerance > na:
                return None

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
    bundle["v"] = key_version
    return json.dumps(bundle, separators=(",", ":"))


def unpack_signature(sig_field: str) -> Tuple[Optional[str], Optional[str], int]:
    """Inverse of pack_signature.

    Returns (hmac_sig, ed25519_sig, key_version). Either sig may be None if not present.
    Treats raw-hex strings as legacy HMAC-only with version 1.
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
