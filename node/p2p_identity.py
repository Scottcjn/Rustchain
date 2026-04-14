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
DEFAULT_PRIVKEY_PATH = os.environ.get(
    "RC_P2P_PRIVKEY_PATH",
    "/etc/rustchain/p2p_identity.pem",
)
DEFAULT_REGISTRY_PATH = os.environ.get(
    "RC_P2P_PEER_REGISTRY",
    "/etc/rustchain/peer_registry.json",
)


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

    def __init__(self, path: str = DEFAULT_PRIVKEY_PATH):
        self.path = Path(path)
        self._privkey = None  # lazy
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

        if self.path.exists():
            with open(self.path, "rb") as f:
                self._privkey = load_pem_private_key(f.read(), password=None)
            logger.info(f"[P2P] Loaded Ed25519 identity from {self.path}")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._privkey = Ed25519PrivateKey.generate()
            pem = self._privkey.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            # Write with 0600 perms
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, pem)
            finally:
                os.close(fd)
            logger.info(f"[P2P] Generated new Ed25519 identity at {self.path}")

        from cryptography.hazmat.primitives.serialization import (
            Encoding as _Enc,
            PublicFormat as _Pub,
        )
        pub_bytes = self._privkey.public_key().public_bytes(_Enc.Raw, _Pub.Raw)
        self._pubkey_hex = pub_bytes.hex()

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


class PeerRegistry:
    """Static peer registry loaded from JSON.

    Format (see DESIGN.md):
        {
          "version": 1,
          "peers": [
            {"node_id": "...", "pubkey_hex": "..."},
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
            if not nid or not pk:
                logger.warning(f"[P2P] Skipping malformed peer entry: {p}")
                continue
            entries[nid] = PeerEntry(node_id=nid, pubkey_hex=pk)
        self._by_node_id = entries
        self._loaded = True
        logger.info(f"[P2P] Loaded {len(entries)} peers from registry {self.path}")

    def get_pubkey(self, node_id: str) -> Optional[str]:
        if not self._loaded:
            self.load()
        entry = self._by_node_id.get(node_id)
        return entry.pubkey_hex if entry else None

    def __len__(self) -> int:
        if not self._loaded:
            self.load()
        return len(self._by_node_id)


# ---------------------------------------------------------------------------
# Signature bundle: JSON-encoded dual signature (or legacy hex)
# ---------------------------------------------------------------------------
def pack_signature(hmac_sig: Optional[str], ed25519_sig: Optional[str]) -> str:
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
    return json.dumps(bundle, separators=(",", ":"))


def unpack_signature(sig_field: str) -> Tuple[Optional[str], Optional[str]]:
    """Inverse of pack_signature.

    Returns (hmac_sig, ed25519_sig). Either may be None if not present.
    Treats raw-hex strings as legacy HMAC-only.
    """
    if not sig_field:
        return None, None
    stripped = sig_field.strip()
    if stripped.startswith("{"):
        try:
            bundle = json.loads(stripped)
            return bundle.get("h"), bundle.get("e")
        except json.JSONDecodeError:
            return None, None
    # Legacy hex — assume HMAC
    return stripped, None


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
