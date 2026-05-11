#!/usr/bin/env python3
"""
RustChain P2P Gossip & CRDT Synchronization Module
===================================================

Implements fully decentralized P2P sync with:
- Gossip protocol (Bitcoin-style INV/GETDATA)
- CRDT state merging (conflict-free eventual consistency)
- Epoch consensus (2-phase commit)

Designed for 3+ nodes with no single point of failure.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, OrderedDict
import logging
import requests

# ---------------------------------------------------------------------------
# P2P HMAC secret — MUST be set via the RC_P2P_SECRET environment variable.
# There is NO safe default: every node in a P2P cluster must share the same
# strong, randomly generated secret (≥ 32 hex chars recommended).
# ---------------------------------------------------------------------------
_P2P_SECRET_RAW = os.environ.get("RC_P2P_SECRET", "").strip()


# =============================================================================
# TTL Cache for message deduplication (Issue #2755: Memory leak fix)
# =============================================================================

class TTLCache:
    """Time-based LRU cache for message deduplication.
    
    Replaces the unbounded set with automatic TTL-based eviction.
    Uses OrderedDict for O(1) operations and LRU eviction.
    """
    
    def __init__(self, ttl: int = 3600, max_size: int = 10000):
        """
        Args:
            ttl: Time-to-live in seconds (default: 1 hour, matching DB cleanup)
            max_size: Maximum number of entries before LRU eviction kicks in
        """
        self._cache = OrderedDict()  # msg_id -> timestamp
        self._ttl = ttl
        self._max_size = max_size
    
    def contains(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        self._cleanup_expired()
        return key in self._cache
    
    def add(self, key: str) -> None:
        """Add key with current timestamp. Evicts LRU if at capacity."""
        self._cleanup_expired()
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = time.time()
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, ts in self._cache.items() if now - ts > self._ttl]
        for k in expired:
            del self._cache[k]
    
    def __len__(self) -> int:
        """Return number of entries (including expired)."""
        return len(self._cache)
    
    def cleanup(self) -> int:
        """Force cleanup of expired entries. Returns count of removed entries."""
        before = len(self._cache)
        self._cleanup_expired()
        return before - len(self._cache)



# Known insecure placeholders that must never be accepted in production.
_INSECURE_DEFAULTS = {
    "rustchain_p2p_secret_2025_decentralized",
    "changeme",
    "secret",
    "default",
    "default-hmac-secret-change-me",
    "",
}

if not _P2P_SECRET_RAW or _P2P_SECRET_RAW.lower() in _INSECURE_DEFAULTS:
    raise SystemExit(
        "[P2P] FATAL: RC_P2P_SECRET environment variable is not set or contains "
        "an insecure placeholder value.  Every node must be configured with the "
        "same strong, randomly generated HMAC secret before startup.\n"
        "  Generate one with:  openssl rand -hex 32\n"
        "  Then export:        export RC_P2P_SECRET=<your-secret>"
    )

P2P_SECRET = _P2P_SECRET_RAW
GOSSIP_TTL = 3
SYNC_INTERVAL = 30
MESSAGE_EXPIRY = 300  # 5 minutes
MAX_INV_BATCH = 1000
DB_PATH = os.environ.get("RUSTCHAIN_DB", "/root/rustchain/rustchain_v2.db")

# TLS verification: defaults to True (secure).
# Set RUSTCHAIN_TLS_VERIFY=false only for local development with self-signed certs.
# Prefer RUSTCHAIN_CA_BUNDLE to point at a pinned CA/cert file instead of disabling.
_tls_verify_env = os.environ.get("RUSTCHAIN_TLS_VERIFY", "true").strip().lower()
_ca_bundle = os.environ.get("RUSTCHAIN_CA_BUNDLE", "").strip()
if _ca_bundle and os.path.isfile(_ca_bundle):
    TLS_VERIFY = _ca_bundle          # Path to pinned cert / CA bundle
elif _tls_verify_env in ("false", "0", "no"):
    TLS_VERIFY = False                # Explicit opt-out (dev only)
else:
    TLS_VERIFY = True                 # Default: full CA verification

logging.basicConfig(level=logging.INFO, format='%(asctime)s [P2P] %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# MESSAGE TYPES
# =============================================================================

class MessageType(Enum):
    # Discovery & Health
    PING = "ping"
    PONG = "pong"
    PEER_ANNOUNCE = "peer_announce"
    PEER_LIST_REQ = "peer_list_req"
    PEER_LIST = "peer_list"

    # Inventory Announcements (INV-style, hash only)
    INV_ATTESTATION = "inv_attest"
    INV_EPOCH = "inv_epoch"
    INV_BALANCE = "inv_balance"

    # Data Requests (GETDATA-style)
    GET_ATTESTATION = "get_attest"
    GET_EPOCH = "get_epoch"
    GET_BALANCES = "get_balances"
    GET_STATE = "get_state"

    # Data Responses
    ATTESTATION = "attestation"
    EPOCH_DATA = "epoch_data"
    BALANCES = "balances"
    STATE = "state"

    # Epoch Consensus
    EPOCH_PROPOSE = "epoch_propose"
    EPOCH_VOTE = "epoch_vote"
    EPOCH_COMMIT = "epoch_commit"


@dataclass
class GossipMessage:
    """Base gossip message structure"""
    msg_type: str
    msg_id: str
    sender_id: str
    timestamp: int
    ttl: int
    signature: str
    payload: Dict

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'GossipMessage':
        return cls(**data)

    def compute_hash(self) -> str:
        """Compute hash of message content for deduplication"""
        content = f"{self.msg_type}:{self.sender_id}:{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]


# =============================================================================
# CRDT IMPLEMENTATIONS
# =============================================================================

class LWWRegister:
    """
    Last-Write-Wins Register for attestations.
    The value with the highest timestamp wins.
    """

    def __init__(self):
        self.data: Dict[str, Tuple[int, Dict]] = {}  # key -> (timestamp, value)

    def set(self, key: str, value: Dict, timestamp: int):
        """Set value if timestamp is newer"""
        if key not in self.data or timestamp > self.data[key][0]:
            self.data[key] = (timestamp, value)
            return True
        return False

    def get(self, key: str) -> Optional[Dict]:
        """Get current value"""
        if key in self.data:
            return self.data[key][1]
        return None

    def merge(self, other: 'LWWRegister'):
        """Merge another LWW register into this one"""
        for key, (ts, value) in other.data.items():
            self.set(key, value, ts)

    def to_dict(self) -> Dict:
        return {k: {"ts": ts, "value": v} for k, (ts, v) in self.data.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'LWWRegister':
        reg = cls()
        for k, v in data.items():
            reg.data[k] = (v["ts"], v["value"])
        return reg


class PNCounter:
    """
    Positive-Negative Counter for balances.
    Tracks increments and decrements per node for conflict-free merging.
    """

    def __init__(self):
        # miner_id -> {node_id: total_amount}
        self.increments: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.decrements: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def credit(self, miner_id: str, node_id: str, amount: int):
        """Record a credit (reward)"""
        self.increments[miner_id][node_id] += amount

    def debit(self, miner_id: str, node_id: str, amount: int):
        """Record a debit (withdrawal)"""
        self.decrements[miner_id][node_id] += amount

    def get_balance(self, miner_id: str) -> int:
        """Compute current balance from CRDT state"""
        incr = sum(self.increments.get(miner_id, {}).values())
        decr = sum(self.decrements.get(miner_id, {}).values())
        return incr - decr

    def get_all_balances(self) -> Dict[str, int]:
        """Get all miner balances"""
        all_miners = set(self.increments.keys()) | set(self.decrements.keys())
        return {m: self.get_balance(m) for m in all_miners}

    def merge(self, other: 'PNCounter'):
        """Merge remote state - take max for each (node_id, miner_id) pair"""
        for miner_id, node_amounts in other.increments.items():
            for node_id, amount in node_amounts.items():
                self.increments[miner_id][node_id] = max(
                    self.increments[miner_id][node_id], amount
                )

        for miner_id, node_amounts in other.decrements.items():
            for node_id, amount in node_amounts.items():
                self.decrements[miner_id][node_id] = max(
                    self.decrements[miner_id][node_id], amount
                )

    def to_dict(self) -> Dict:
        return {
            "increments": {k: dict(v) for k, v in self.increments.items()},
            "decrements": {k: dict(v) for k, v in self.decrements.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PNCounter':
        counter = cls()
        for miner_id, nodes in data.get("increments", {}).items():
            for node_id, amount in nodes.items():
                counter.increments[miner_id][node_id] = amount
        for miner_id, nodes in data.get("decrements", {}).items():
            for node_id, amount in nodes.items():
                counter.decrements[miner_id][node_id] = amount
        return counter


class GSet:
    """
    Grow-only Set for settled epochs.
    Once an epoch is settled, it can never be unsettled.
    """

    def __init__(self):
        self.items: Set[int] = set()
        self.metadata: Dict[int, Dict] = {}  # epoch -> {settled_ts, merkle_root, ...}

    def add(self, epoch: int, metadata: Dict = None):
        """Add epoch to settled set"""
        self.items.add(epoch)
        if metadata:
            self.metadata[epoch] = metadata

    def contains(self, epoch: int) -> bool:
        return epoch in self.items

    def merge(self, other: 'GSet'):
        """Merge another G-Set - union operation"""
        self.items |= other.items
        for epoch, meta in other.metadata.items():
            if epoch not in self.metadata:
                self.metadata[epoch] = meta

    def to_dict(self) -> Dict:
        return {
            "epochs": list(self.items),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GSet':
        gset = cls()
        gset.items = set(data.get("epochs", []))
        gset.metadata = data.get("metadata", {})
        return gset


# =============================================================================
# GOSSIP LAYER
# =============================================================================

class GossipLayer:
    """
    Gossip protocol implementation with INV/GETDATA model.
    """

    def __init__(self, node_id: str, peers: Dict[str, str], db_path: str = DB_PATH):
        self.node_id = node_id
        self.peers = peers  # peer_id -> url
        self.db_path = db_path
        self.seen_messages: TTLCache = TTLCache(ttl=3600, max_size=10000)
        self.message_queue: List[GossipMessage] = []
        self.lock = threading.Lock()

        # CRDT state
        self.attestation_crdt = LWWRegister()
        self.balance_crdt = PNCounter()
        self.epoch_crdt = GSet()

        # Phase F (#2256): per-peer Ed25519 identity, dual-mode signing.
        # Only loaded/generated when needed by the current signing mode;
        # legacy "hmac" mode does not require cryptography to be installed.
        from p2p_identity import (
            SIGNING_MODE,
            LocalKeypair,
            PeerRegistry,
        )
        self._signing_mode = SIGNING_MODE
        self._keypair: Optional[LocalKeypair] = None
        self._peer_registry: Optional[PeerRegistry] = None
        if self._signing_mode != "hmac":
            self._keypair = LocalKeypair()
            self._peer_registry = PeerRegistry()
            # Prime the keypair + registry so startup surfaces any issues.
            _ = self._keypair.pubkey_hex
            self._peer_registry.load()

        # Load initial state from DB
        self._load_state_from_db()

    def _load_state_from_db(self):
        """Load existing state into CRDTs and initialize P2P tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Initialize P2P seen messages table (Issue #2271)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS p2p_seen_messages (
                        msg_id TEXT PRIMARY KEY,
                        ts INTEGER NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_p2p_seen_ts ON p2p_seen_messages(ts)")
                conn.commit()

                # Load attestations
                rows = conn.execute("""
                    SELECT miner, ts_ok, device_family, device_arch, entropy_score
                    FROM miner_attest_recent
                """).fetchall()
                for miner, ts_ok, family, arch, entropy in rows:
                    self.attestation_crdt.set(miner, {
                        "miner": miner,
                        "device_family": family,
                        "device_arch": arch,
                        "entropy_score": entropy or 0
                    }, ts_ok)

                # Load settled epochs
                rows = conn.execute("""
                    SELECT epoch FROM epoch_state WHERE settled = 1
                """).fetchall()
                for (epoch,) in rows:
                    self.epoch_crdt.add(epoch)

                logger.info(f"Loaded {len(self.attestation_crdt.data)} attestations, "
                           f"{len(self.epoch_crdt.items)} settled epochs")
        except Exception as e:
            logger.error(f"Failed to load state from DB: {e}")

    def _sign_message(self, content: str) -> Tuple[str, int]:
        """Generate signature (HMAC, Ed25519, or dual) for message.

        Mode-aware per Phase F:
          - "hmac"     : HMAC only, raw hex (legacy wire format)
          - "dual"     : HMAC + Ed25519, JSON-packed
          - "ed25519"  : Ed25519 only, JSON-packed (HMAC still verified if present)
          - "strict"   : Ed25519 only, JSON-packed (HMAC rejected)
        """
        timestamp = int(time.time())
        message = f"{content}:{timestamp}"
        mode = self._signing_mode

        hmac_sig: Optional[str] = None
        ed25519_sig: Optional[str] = None

        if mode in ("hmac", "dual"):
            hmac_sig = hmac.new(
                P2P_SECRET.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

        if mode in ("dual", "ed25519", "strict") and self._keypair is not None:
            ed25519_sig = self._keypair.sign(message.encode())

        from p2p_identity import pack_signature
        return pack_signature(hmac_sig, ed25519_sig), timestamp

    def _verify_signature(self, content: str, signature: str, timestamp: int) -> bool:
        """Verify a message signature.

        Phase F: accepts HMAC and/or Ed25519 per current signing mode.
        Timestamp freshness is always enforced.
        """
        if abs(time.time() - timestamp) > MESSAGE_EXPIRY:
            return False
        message = f"{content}:{timestamp}"
        mode = self._signing_mode

        from p2p_identity import unpack_signature, verify_ed25519
        hmac_sig, ed25519_sig, _key_version = unpack_signature(signature)

        # "strict" mode: only Ed25519 accepted. HMAC-only sigs are rejected
        # even if valid (flag-day enforcement).
        if mode == "strict":
            if ed25519_sig is None:
                return False
            # Find sender's pubkey via the registry.
            # NOTE: this classmethod-style helper is called with only
            # (content, sig, ts). For Ed25519, we need sender_id. The handler
            # that invokes this has the full msg — we expose a public
            # verify_message() that threads sender_id through. Keep this
            # method's signature stable for HMAC path.
            return False  # strict mode must use verify_message()

        # "hmac" mode: only HMAC accepted. Ed25519-only sigs are rejected.
        if mode == "hmac":
            if hmac_sig is None:
                return False
            expected = hmac.new(
                P2P_SECRET.encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(hmac_sig, expected)

        # "dual" or "ed25519" modes: accept either signature type.
        # HMAC path:
        if hmac_sig is not None:
            expected = hmac.new(
                P2P_SECRET.encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(hmac_sig, expected):
                return True
        # Ed25519 path (cannot run without sender_id; caller should use
        # verify_message()). Fall through to reject if HMAC also absent.
        return False

    # SECURITY (#2256 + #2272): the signed content now includes sender_id, 
    # msg_id, and ttl so the message metadata cannot be flipped post-sign.
    @staticmethod
    def _signed_content(msg_type: str, sender_id: str, msg_id: str, ttl: int, payload: Dict) -> str:
        return f"{msg_type}:{sender_id}:{msg_id}:{ttl}:{json.dumps(payload, sort_keys=True)}"

    def create_message(self, msg_type: MessageType, payload: Dict, ttl: int = GOSSIP_TTL) -> GossipMessage:
        """Create a new gossip message"""
        # Generate msg_id first for signature binding (Issue #2272)
        # Issue #2268: Use cryptographically secure random nonce instead of predictable time.time()
        temp_content = f"{msg_type.value}:{self.node_id}:{json.dumps(payload, sort_keys=True)}"
        secure_nonce = secrets.token_hex(16)  # 128-bit cryptographically secure random value
        msg_id = hashlib.sha256(f"{temp_content}:{secure_nonce}".encode()).hexdigest()[:24]
        
        content = self._signed_content(msg_type.value, self.node_id, msg_id, ttl, payload)
        sig, ts = self._sign_message(content)

        msg = GossipMessage(
            msg_type=msg_type.value,
            msg_id=msg_id,
            sender_id=self.node_id,
            timestamp=ts,
            ttl=ttl,
            signature=sig,
            payload=payload
        )
        return msg

    def verify_message(self, msg: GossipMessage) -> bool:
        """Verify message signature and freshness.

        SECURITY (#2256 + #2272): verifies sender_id, msg_id, and ttl as
        part of the signed content — any post-sign flip of those fields
        fails verification.

        Phase F: if an Ed25519 signature is present AND the sender is a
        registered peer, verify it against their pubkey. HMAC path is a
        fallback per the current signing mode.
        """
        if abs(time.time() - msg.timestamp) > MESSAGE_EXPIRY:
            return False

        content = self._signed_content(msg.msg_type, msg.sender_id, msg.msg_id, msg.ttl, msg.payload)
        message = f"{content}:{msg.timestamp}"
        mode = self._signing_mode

        from p2p_identity import unpack_signature, verify_ed25519
        hmac_sig, ed25519_sig, _key_version = unpack_signature(msg.signature)

        # 1) Try Ed25519 if available AND peer is registered.
        if ed25519_sig and self._peer_registry is not None:
            pubkey = self._peer_registry.get_pubkey(msg.sender_id)
            if pubkey and verify_ed25519(pubkey, ed25519_sig, message.encode()):
                return True
            # In strict mode, Ed25519 must succeed — no fallback.
            if mode == "strict":
                return False

        # 2) HMAC fallback (unless strict).
        if mode == "strict":
            return False
        if hmac_sig is None:
            return False
        expected = hmac.new(
            P2P_SECRET.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(hmac_sig, expected)

    def broadcast(self, msg: GossipMessage, exclude_peer: str = None):
        """Broadcast message to all peers"""
        for peer_id, peer_url in self.peers.items():
            if peer_id == exclude_peer:
                continue
            try:
                self._send_to_peer(peer_url, msg)
            except Exception as e:
                logger.warning(f"Failed to send to {peer_id}: {e}")

    def _send_to_peer(self, peer_url: str, msg: GossipMessage):
        """Send message to a specific peer"""
        try:
            resp = requests.post(
                f"{peer_url}/p2p/gossip",
                json=msg.to_dict(),
                timeout=10,
                verify=TLS_VERIFY
            )
            if resp.status_code != 200:
                logger.warning(f"Peer {peer_url} returned {resp.status_code}")
        except Exception as e:
            logger.debug(f"Send to {peer_url} failed: {e}")

    def handle_message(self, msg: GossipMessage) -> Optional[Dict]:
        """Handle received gossip message"""
        # Deduplication (Issue #2271: DB-backed persistent dedup)
        try:
            with sqlite3.connect(self.db_path) as conn:
                res = conn.execute("SELECT 1 FROM p2p_seen_messages WHERE msg_id = ?", (msg.msg_id,)).fetchone()
                if res:
                    return {"status": "duplicate"}
        except Exception as e:
            logger.error(f"P2P dedup DB error: {e}")
            # Fallback to memory if DB fails
            if self.seen_messages.contains(msg.msg_id):
                return {"status": "duplicate"}

        # Verify signature
        if not self.verify_message(msg):
            logger.warning(f"Invalid signature from {msg.sender_id}")
            return {"status": "invalid_signature"}

        # Record as seen (Issue #2271: Persistent storage)
        try:
            with sqlite3.connect(self.db_path) as conn:
                now = int(time.time())
                conn.execute("INSERT OR IGNORE INTO p2p_seen_messages (msg_id, ts) VALUES (?, ?)",
                             (msg.msg_id, now))
                if conn.execute("SELECT changes()").fetchone()[0] == 0:
                    return {"status": "duplicate"}
                # Prune old messages (> 1 hour)
                conn.execute("DELETE FROM p2p_seen_messages WHERE ts < ?", (now - 3600,))
                conn.commit()
        except Exception as e:
            logger.error(f"P2P save seen DB error: {e}")
            with self.lock:
                if self.seen_messages.contains(msg.msg_id):
                    return {"status": "duplicate"}
                self.seen_messages.add(msg.msg_id)

        # TTLCache handles automatic eviction (TTL + LRU)

        # Handle by type
        msg_type = MessageType(msg.msg_type)

        if msg_type == MessageType.PING:
            return self._handle_ping(msg)
        elif msg_type == MessageType.INV_ATTESTATION:
            return self._handle_inv_attestation(msg)
        elif msg_type == MessageType.INV_EPOCH:
            return self._handle_inv_epoch(msg)
        elif msg_type == MessageType.ATTESTATION:
            return self._handle_attestation(msg)
        elif msg_type == MessageType.EPOCH_PROPOSE:
            return self._handle_epoch_propose(msg)
        elif msg_type == MessageType.EPOCH_VOTE:
            return self._handle_epoch_vote(msg)
        elif msg_type == MessageType.GET_STATE:
            return self._handle_get_state(msg)
        elif msg_type == MessageType.STATE:
            return self._handle_state(msg)

        # Forward if TTL > 0
        if msg.ttl > 0:
            msg.ttl -= 1
            self.broadcast(msg, exclude_peer=msg.sender_id)

        return {"status": "ok"}

    def _handle_ping(self, msg: GossipMessage) -> Dict:
        """Respond to ping with pong"""
        pong = self.create_message(MessageType.PONG, {
            "node_id": self.node_id,
            "attestation_count": len(self.attestation_crdt.data),
            "settled_epochs": len(self.epoch_crdt.items)
        })
        return {"status": "ok", "pong": pong.to_dict()}

    def _handle_inv_attestation(self, msg: GossipMessage) -> Dict:
        """Handle attestation inventory announcement"""
        miner_id = msg.payload.get("miner_id")
        remote_ts = msg.payload.get("ts_ok", 0)

        # Check if we need this attestation
        local = self.attestation_crdt.get(miner_id)
        if local is None or remote_ts > self.attestation_crdt.data.get(miner_id, (0, {}))[0]:
            # Request full data
            return {"status": "need_data", "miner_id": miner_id}

        return {"status": "have_data"}

    def _handle_attestation(self, msg: GossipMessage) -> Dict:
        """Handle full attestation data.

        SECURITY (#2256 Phase E): schema + timestamp sanity. Reject
        attestations with future ts_ok beyond clock-skew tolerance to
        prevent LWW-pinning of poisoned state. Reject malformed miner_id.
        """
        attestation = msg.payload
        if not isinstance(attestation, dict):
            return {"status": "error", "reason": "bad_schema"}

        miner_id = attestation.get("miner")
        if not miner_id or not isinstance(miner_id, str) or len(miner_id) > 256:
            logger.warning(f"Attestation from {msg.sender_id}: invalid miner_id")
            return {"status": "error", "reason": "invalid_miner_id"}

        now = int(time.time())
        MAX_FUTURE_SKEW_S = 300  # 5 minutes
        ts_ok = attestation.get("ts_ok", now)
        if not isinstance(ts_ok, (int, float)):
            return {"status": "error", "reason": "invalid_ts_ok"}
        if ts_ok > now + MAX_FUTURE_SKEW_S:
            logger.warning(
                f"Attestation from {msg.sender_id} for miner {miner_id[:16]}: "
                f"rejecting future-dated ts_ok={ts_ok} (now={now})"
            )
            return {"status": "error", "reason": "future_timestamp"}

        # Update CRDT
        if self.attestation_crdt.set(miner_id, attestation, int(ts_ok)):
            # Also update database
            self._save_attestation_to_db(attestation, int(ts_ok))
            logger.info(f"Merged attestation for {miner_id[:16]}...")

        return {"status": "ok"}

    def _save_attestation_to_db(self, attestation: Dict, ts_ok: int):
        """Save attestation to SQLite database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # FIX: Prevent P2P-synced attestations from downgrading security-
                # relevant fields set by the local node's attestation flow.
                # - fingerprint_passed: MAX() preserves any prior pass (RIP-PoA).
                # - entropy_score: MAX() preserves the highest observed score; a
                #   malicious peer sending entropy_score=0 cannot erase a legitimate
                #   high-entropy measurement (anti-double-mining canonical selection).
                conn.execute("""
                    INSERT INTO miner_attest_recent
                        (miner, ts_ok, device_family, device_arch, entropy_score)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(miner) DO UPDATE SET
                        ts_ok = excluded.ts_ok,
                        device_family = excluded.device_family,
                        device_arch = excluded.device_arch,
                        entropy_score = MAX(
                            COALESCE(miner_attest_recent.entropy_score, 0),
                            excluded.entropy_score),
                        fingerprint_passed = COALESCE(
                            MAX(COALESCE(miner_attest_recent.fingerprint_passed, 0),
                                COALESCE(excluded.fingerprint_passed, miner_attest_recent.fingerprint_passed)),
                            miner_attest_recent.fingerprint_passed)
                """, (
                    attestation.get("miner"),
                    ts_ok,
                    attestation.get("device_family", "unknown"),
                    attestation.get("device_arch", "unknown"),
                    attestation.get("entropy_score", 0)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save attestation: {e}")

    def _handle_inv_epoch(self, msg: GossipMessage) -> Dict:
        """Handle epoch settlement inventory"""
        epoch = msg.payload.get("epoch")
        if not self.epoch_crdt.contains(epoch):
            return {"status": "need_data", "epoch": epoch}
        return {"status": "have_data"}

    def _handle_epoch_propose(self, msg: GossipMessage) -> Dict:
        """Handle epoch settlement proposal.

        SECURITY (#2256 Phase B, RR-delegate gate): proposer identity must
        come from the authenticated sender, not a payload field. Only the
        scheduled round-robin leader for this epoch is accepted. Supplemental
        to Phase A signature coverage — doesn't close the shared-HMAC problem
        (see Phase F Ed25519), but makes out-of-turn proposal acceptance
        impossible via normal protocol paths.
        """
        proposal = msg.payload
        epoch = proposal.get("epoch")
        # Bind proposer to authenticated sender; ignore payload claim entirely.
        proposer = msg.sender_id
        payload_proposer = proposal.get("proposer")

        # Verify proposer is the scheduled RR-delegate for this epoch
        nodes = sorted(list(self.peers.keys()) + [self.node_id])
        expected_leader = nodes[epoch % len(nodes)]

        if proposer != expected_leader:
            logger.warning(f"Epoch {epoch}: rejecting proposal from {proposer}, expected RR-delegate {expected_leader}")
            return {"status": "reject", "reason": "invalid_leader"}

        # If payload carries a contradictory proposer claim, reject — likely tampering
        if payload_proposer is not None and payload_proposer != proposer:
            logger.warning(f"Epoch {epoch}: payload proposer {payload_proposer} != authenticated sender {proposer}")
            return {"status": "reject", "reason": "proposer_identity_mismatch"}

        # Validate Merkle root of distribution
        distribution = proposal.get("distribution", {})
        remote_merkle = proposal.get("merkle_root", "")

        sorted_dist = sorted(distribution.items())
        merkle_data = json.dumps(sorted_dist, sort_keys=True)
        local_merkle = hashlib.sha256(merkle_data.encode()).hexdigest()

        if remote_merkle != local_merkle:
            logger.warning(
                f"Epoch {epoch}: Merkle root mismatch "
                f"(remote={remote_merkle[:16]}..., local={local_merkle[:16]}...)"
            )
            return self._reject_epoch_vote(epoch, proposal, "merkle_root_mismatch")

        # Validate distribution recipients against locally attested miners.
        # The merkle check above only proves internal consistency (the hash
        # matches the provided data); it does NOT verify that the distribution
        # actually corresponds to enrolled miners.  A malicious proposer could
        # send a self-paying distribution with a correctly computed merkle root.
        # Cross-reference each recipient against miner_attest_recent to ensure
        # only legitimately attested miners receive rewards.
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT miner FROM miner_attest_recent"
                )
                attested_miners = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Epoch {epoch}: Failed to query attested miners: {e}")
            return self._reject_epoch_vote(epoch, proposal, "attested_miners_query_error")

        for recipient in distribution:
            if recipient not in attested_miners:
                logger.warning(
                    f"Epoch {epoch}: Distribution recipient {recipient} "
                    f"not found in attested miners"
                )
                return self._reject_epoch_vote(epoch, proposal, "unattested_recipient")

        # Merkle verified AND recipients validated - vote to accept
        vote = self.create_message(MessageType.EPOCH_VOTE, {
            "epoch": epoch,
            "proposal_hash": proposal.get("proposal_hash"),
            "vote": "accept",
            "voter": self.node_id
        })

        self.broadcast(vote)

        return {"status": "voted", "vote": "accept"}

    def _reject_epoch_vote(self, epoch: int, proposal: Dict, reason: str) -> Dict:
        """Helper: broadcast epoch vote rejection with reason."""
        vote = self.create_message(MessageType.EPOCH_VOTE, {
            "epoch": epoch,
            "proposal_hash": proposal.get("proposal_hash"),
            "vote": "reject",
            "voter": self.node_id,
            "reason": reason
        })
        self.broadcast(vote)
        return {"status": "voted", "vote": "reject", "reason": reason}

    def _handle_epoch_vote(self, msg: GossipMessage) -> Dict:
        """Handle epoch vote - collect votes and commit when quorum reached.

        Requires at least 3 of 4 nodes (or majority of known nodes)
        to agree before finalizing an epoch reward distribution.

        SECURITY (#2256 Phase A + C):
        - Voter identity bound to msg.sender_id (not payload["voter"]).
          sender_id itself is now HMAC-covered (see Phase A changes above).
        - Votes indexed by (epoch, proposal_hash), not just epoch. Mixed
          votes for different proposals cannot aggregate into a false quorum;
          only the specific proposal_hash that reached quorum finalizes.
        - Idempotent per (epoch, proposal_hash, voter) — duplicate votes
          silently ignored.
        """
        payload = msg.payload
        epoch = payload.get("epoch")
        # Bind voter to authenticated sender — payload["voter"] is advisory only.
        voter = msg.sender_id
        payload_voter = payload.get("voter")
        vote = payload.get("vote", "reject")
        proposal_hash = payload.get("proposal_hash")

        if epoch is None:
            return {"status": "error", "reason": "missing epoch"}
        if proposal_hash is None:
            return {"status": "error", "reason": "missing proposal_hash"}

        # Reject contradictory payload voter claim (likely tampering).
        if payload_voter is not None and payload_voter != voter:
            logger.warning(
                f"Epoch {epoch}: payload voter {payload_voter} != "
                f"authenticated sender {voter}; rejecting vote"
            )
            return {"status": "error", "reason": "voter_identity_mismatch"}

        # Phase C: index by (epoch, proposal_hash) — not just epoch.
        if not hasattr(self, '_epoch_votes'):
            self._epoch_votes: Dict[Tuple[int, str], Dict[str, str]] = {}
        key = (epoch, proposal_hash)
        if key not in self._epoch_votes:
            self._epoch_votes[key] = {}

        # Idempotent per (epoch, proposal_hash, voter).
        if voter in self._epoch_votes[key]:
            logger.warning(
                f"Epoch {epoch} proposal {proposal_hash[:12]}: "
                f"duplicate vote from {voter} ignored"
            )
            return {"status": "duplicate", "epoch": epoch, "voter": voter}

        self._epoch_votes[key][voter] = vote

        # Count votes for THIS specific proposal_hash only.
        total_nodes = len(self.peers) + 1  # peers + self
        votes_for_proposal = self._epoch_votes[key]
        accept_count = sum(1 for v in votes_for_proposal.values() if v == "accept")
        reject_count = sum(1 for v in votes_for_proposal.values() if v == "reject")

        # Quorum: require at least 3 nodes or strict majority, whichever is larger
        quorum = max(3, (total_nodes // 2) + 1)

        logger.info(
            f"Epoch {epoch} proposal {proposal_hash[:12]} vote from {voter}: {vote} "
            f"(accept={accept_count}, reject={reject_count}, quorum={quorum})"
        )

        # Check if quorum reached for acceptance — bound to this specific proposal_hash.
        if accept_count >= quorum:
            logger.info(
                f"Epoch {epoch}: QUORUM REACHED for proposal {proposal_hash[:12]} "
                f"({accept_count}/{total_nodes} accept)"
            )
            self.epoch_crdt.add(epoch, {"proposal_hash": proposal_hash, "finalized": True})
            # Broadcast commit message
            commit_msg = self.create_message(MessageType.EPOCH_COMMIT, {
                "epoch": epoch,
                "proposal_hash": proposal_hash,
                "accept_count": accept_count,
                "voters": list(votes_for_proposal.keys())
            })
            self.broadcast(commit_msg)
            return {"status": "committed", "epoch": epoch, "accept_count": accept_count}

        # Check if enough rejections to abort
        if reject_count > total_nodes - quorum:
            logger.warning(f"Epoch {epoch}: REJECTED ({reject_count} reject, cannot reach quorum)")
            return {"status": "rejected", "epoch": epoch, "reject_count": reject_count}

        return {"status": "ok", "epoch": epoch, "votes_so_far": len(votes_for_proposal)}

    def _handle_get_state(self, msg: GossipMessage) -> Dict:
        """Handle state request - return full CRDT state with signature"""
        state_data = {
            "attestations": self.attestation_crdt.to_dict(),
            "epochs": self.epoch_crdt.to_dict(),
            "balances": self.balance_crdt.to_dict()
        }
        # Sign the state response so the requester can verify authenticity.
        # Uses the Phase A signed-content shape (msg_type:sender_id:payload)
        # so verify_message() on the requester side accepts it.
        payload = {"state": state_data}
        # Issue #2268: Use cryptographically secure random nonce instead of predictable time.time()
        state_nonce = secrets.token_hex(16)
        state_msg_id = hashlib.sha256(
            f"STATE:{self.node_id}:{json.dumps(payload, sort_keys=True)}:{state_nonce}".encode()
        ).hexdigest()[:24]
        
        content = self._signed_content(MessageType.STATE.value, self.node_id, state_msg_id, 0, payload)
        signature, timestamp = self._sign_message(content)
        return {
            "status": "ok",
            "state": state_data,
            "signature": signature,
            "timestamp": timestamp,
            "sender_id": self.node_id,
            "msg_id": state_msg_id,
            "ttl": 0
        }

    def _handle_state(self, msg: GossipMessage) -> Dict:
        """Handle incoming state - merge with local.

        SECURITY (#2256 Phase D): hardens the blind CRDT merge that was the
        biggest poison sink in the old flow. Validations applied:
          1. Valid signature covering sender_id (Phase A)
          2. Schema validation on each CRDT section
          3. Timestamp sanity: reject attestations with ts_ok > now + skew
          4. Balance PN-counter entries scoped to authenticated sender's
             namespace — the sender can only assert +/- values against its
             own node_id key, not inject counter entries on behalf of others
        """
        # SECURITY: Reject state messages without valid signatures.
        if not msg.signature:
            logger.warning(f"Rejected state merge from {msg.sender_id}: empty signature")
            return {"status": "error", "error": "missing_signature"}
        if not self.verify_message(msg):
            logger.warning(f"Rejected state merge from {msg.sender_id}: invalid signature")
            return {"status": "error", "error": "invalid_signature"}

        state = msg.payload.get("state", {})
        sender = msg.sender_id
        now = int(time.time())
        # Accept attestations up to 5 minutes in the future (clock skew) — anything
        # beyond is rejected as poisoning attempt.
        MAX_FUTURE_SKEW_S = 300

        # Phase D.1: Validate + merge attestations with timestamp sanity
        if "attestations" in state:
            raw = state["attestations"]
            if not isinstance(raw, dict):
                logger.warning(f"State from {sender}: attestations not a dict, skipping")
            else:
                try:
                    remote_attest = LWWRegister.from_dict(raw)
                    # Drop any entries with future-dated ts_ok beyond skew tolerance
                    filtered = LWWRegister()
                    for key, (ts, value) in remote_attest.data.items():
                        if ts > now + MAX_FUTURE_SKEW_S:
                            logger.warning(
                                f"State from {sender}: rejecting future-dated "
                                f"attestation {key[:16]} (ts={ts}, now={now})"
                            )
                            continue
                        filtered.set(key, value, ts)
                    self.attestation_crdt.merge(filtered)
                except Exception as e:
                    logger.warning(f"State from {sender}: attestation merge failed: {e}")

        # Phase D.2: Validate + merge epochs (GSet is additive-only; schema check only)
        if "epochs" in state:
            raw = state["epochs"]
            if not isinstance(raw, dict):
                logger.warning(f"State from {sender}: epochs not a dict, skipping")
            else:
                try:
                    remote_epochs = GSet.from_dict(raw)
                    self.epoch_crdt.merge(remote_epochs)
                except Exception as e:
                    logger.warning(f"State from {sender}: epochs merge failed: {e}")

        # Phase D.3: Scope balance PN-counter entries to sender's own namespace.
        # The sender can only contribute increments/decrements under its own
        # node_id key. Entries under other node_ids are dropped.
        if "balances" in state:
            raw = state["balances"]
            if not isinstance(raw, dict):
                logger.warning(f"State from {sender}: balances not a dict, skipping")
            else:
                try:
                    scoped = {"increments": {}, "decrements": {}}
                    for section in ("increments", "decrements"):
                        entries = raw.get(section, {}) or {}
                        for miner_id, node_map in entries.items():
                            if not isinstance(node_map, dict):
                                continue
                            # Only keep the sender's own contribution key
                            own = node_map.get(sender)
                            if own is not None:
                                scoped[section].setdefault(miner_id, {})[sender] = own
                    remote_balances = PNCounter.from_dict(scoped)
                    self.balance_crdt.merge(remote_balances)
                except Exception as e:
                    logger.warning(f"State from {sender}: balances merge failed: {e}")

        logger.info(f"Merged state from {sender} (scoped)")
        return {"status": "ok"}

    def announce_attestation(self, miner_id: str, ts_ok: int, device_arch: str):
        """Announce new attestation to peers"""
        msg = self.create_message(MessageType.INV_ATTESTATION, {
            "miner_id": miner_id,
            "ts_ok": ts_ok,
            "device_arch": device_arch,
            "attestation_hash": hashlib.sha256(f"{miner_id}:{ts_ok}".encode()).hexdigest()[:16]
        })
        self.broadcast(msg)

    def request_full_sync(self, peer_url: str):
        """Request full state sync from a peer"""
        msg = self.create_message(MessageType.GET_STATE, {
            "requester": self.node_id
        })
        try:
            resp = requests.post(
                f"{peer_url}/p2p/gossip",
                json=msg.to_dict(),
                timeout=30,
                verify=TLS_VERIFY
            )
            if resp.status_code == 200:
                data = resp.json()
                if "state" in data:
                    # SECURITY FIX #2154 & #2288: Verify signature on state response.
                    # The responder signs over {"state": <state_data>} (see
                    # _handle_get_state), including msg_id and ttl for arity.
                    signature = data.get("signature", "")
                    timestamp = data.get("timestamp", int(time.time()))
                    msg_id = data.get("msg_id", f"sync:{self.node_id}:{timestamp}")
                    ttl = data.get("ttl", 0)

                    if not signature:
                        logger.error(f"Full sync from {peer_url}: no signature on state response")
                        return
                    state_payload = {"state": data["state"]}
                    responder_id = data.get("sender_id") or peer_url
                    state_msg = GossipMessage(
                        msg_type=MessageType.STATE.value,
                        msg_id=msg_id,
                        sender_id=responder_id,
                        timestamp=timestamp,
                        ttl=ttl,
                        signature=signature,
                        payload=state_payload
                    )
                    self._handle_state(state_msg)
        except Exception as e:
            logger.error(f"Full sync failed: {e}")


# =============================================================================
# EPOCH CONSENSUS
# =============================================================================

class EpochConsensus:
    """
    Epoch settlement consensus using 2-phase commit.
    Round-robin leader selection based on epoch number.
    """

    def __init__(self, node_id: str, nodes: List[str], gossip: GossipLayer):
        self.node_id = node_id
        self.nodes = sorted(nodes)
        self.gossip = gossip
        self.votes: Dict[int, Dict[str, str]] = defaultdict(dict)  # epoch -> {voter: vote}
        self.proposals: Dict[int, Dict] = {}  # epoch -> proposal

    def get_leader(self, epoch: int) -> str:
        """Deterministic leader selection"""
        return self.nodes[epoch % len(self.nodes)]

    def is_leader(self, epoch: int) -> bool:
        return self.get_leader(epoch) == self.node_id

    def propose_settlement(self, epoch: int, distribution: Dict[str, int]) -> Optional[Dict]:
        """Leader proposes epoch settlement"""
        if not self.is_leader(epoch):
            logger.warning(f"Not leader for epoch {epoch}")
            return None

        # Compute merkle root of distribution
        sorted_dist = sorted(distribution.items())
        merkle_data = json.dumps(sorted_dist, sort_keys=True)
        merkle_root = hashlib.sha256(merkle_data.encode()).hexdigest()

        proposal = {
            "epoch": epoch,
            "proposer": self.node_id,
            "distribution": distribution,
            "merkle_root": merkle_root,
            "proposal_hash": hashlib.sha256(f"{epoch}:{merkle_root}".encode()).hexdigest()[:24],
            "timestamp": int(time.time())
        }

        self.proposals[epoch] = proposal

        # Broadcast proposal
        msg = self.gossip.create_message(MessageType.EPOCH_PROPOSE, proposal)
        self.gossip.broadcast(msg)

        logger.info(f"Proposed settlement for epoch {epoch} with {len(distribution)} miners")
        return proposal

    def vote(self, epoch: int, proposal_hash: str, accept: bool):
        """Vote on epoch proposal"""
        vote = "accept" if accept else "reject"
        self.votes[epoch][self.node_id] = vote

        msg = self.gossip.create_message(MessageType.EPOCH_VOTE, {
            "epoch": epoch,
            "proposal_hash": proposal_hash,
            "vote": vote,
            "voter": self.node_id
        })
        self.gossip.broadcast(msg)

    def check_consensus(self, epoch: int) -> bool:
        """Check if consensus reached for epoch"""
        votes = self.votes.get(epoch, {})
        accept_count = sum(1 for v in votes.values() if v == "accept")
        required = (len(self.nodes) // 2) + 1
        return accept_count >= required

    def receive_vote(self, epoch: int, voter: str, vote: str):
        """Record received vote"""
        self.votes[epoch][voter] = vote

        if self.check_consensus(epoch):
            logger.info(f"Consensus reached for epoch {epoch}!")
            self.gossip.epoch_crdt.add(epoch, self.proposals.get(epoch, {}))


# =============================================================================
# P2P NODE COORDINATOR
# =============================================================================

class RustChainP2PNode:
    """
    Main P2P node coordinator.
    Manages gossip, CRDT state, and epoch consensus.
    """

    def __init__(self, node_id: str, db_path: str, peers: Dict[str, str]):
        self.node_id = node_id
        self.db_path = db_path
        self.peers = peers

        # Initialize components
        self.gossip = GossipLayer(node_id, peers, db_path)
        self.consensus = EpochConsensus(
            node_id,
            list(peers.keys()) + [node_id],
            self.gossip
        )

        self.running = False
        self.sync_thread = None

    def start(self):
        """Start P2P services"""
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info(f"P2P Node {self.node_id} started with {len(self.peers)} peers")

    def stop(self):
        """Stop P2P services"""
        self.running = False

    def _sync_loop(self):
        """Periodic sync with peers"""
        while self.running:
            for peer_id, peer_url in self.peers.items():
                try:
                    self.gossip.request_full_sync(peer_url)
                except Exception as e:
                    logger.debug(f"Sync with {peer_id} failed: {e}")
            time.sleep(SYNC_INTERVAL)

    def handle_gossip(self, data: Dict) -> Dict:
        """Handle incoming gossip message"""
        try:
            msg = GossipMessage.from_dict(data)
            return self.gossip.handle_message(msg)
        except Exception as e:
            logger.error(f"Failed to handle gossip: {e}")
            return {"status": "error", "message": str(e)}

    def get_attestation_state(self) -> Dict:
        """Get attestation state for sync"""
        return {
            "node_id": self.node_id,
            "attestations": {
                k: v[0] for k, v in self.gossip.attestation_crdt.data.items()
            }
        }

    def get_full_state(self) -> Dict:
        """Get full CRDT state"""
        return {
            "node_id": self.node_id,
            "attestations": self.gossip.attestation_crdt.to_dict(),
            "epochs": self.gossip.epoch_crdt.to_dict(),
            "balances": self.gossip.balance_crdt.to_dict()
        }

    def announce_new_attestation(self, miner_id: str, attestation: Dict):
        """Announce new attestation received by this node"""
        ts_ok = attestation.get("ts_ok", int(time.time()))

        # Update local CRDT
        self.gossip.attestation_crdt.set(miner_id, attestation, ts_ok)

        # Broadcast to peers
        self.gossip.announce_attestation(
            miner_id,
            ts_ok,
            attestation.get("device_arch", "unknown")
        )


# =============================================================================
# FLASK ENDPOINTS REGISTRATION
# =============================================================================

def register_p2p_endpoints(app, p2p_node: RustChainP2PNode):
    """Register P2P synchronization endpoints on Flask app"""

    from flask import request, jsonify
    from collections import deque
    from threading import Lock

    # FIX(#2867 M5): Per-IP rate limit on /p2p/gossip POST.
    # The endpoint does signature verification + CRDT merge + SQLite I/O on
    # every request. Without throttling it's a cheap DoS amplifier — one
    # attacker can saturate the node by hammering this with junk messages.
    #
    # Token bucket: 10 requests per IP per 1-second window.
    # That's well above legitimate gossip traffic (peers normally send
    # < 1 msg/sec each) but caps a single misbehaving IP at ~10x the
    # background rate.
    GOSSIP_RATE_WINDOW_S = 1.0
    GOSSIP_RATE_LIMIT = 10
    _gossip_rate: Dict[str, deque] = {}
    _gossip_rate_lock = Lock()

    def _gossip_rate_check(remote_ip: str) -> bool:
        """Returns True if the IP is within rate limit, False if over."""
        now = time.monotonic()
        with _gossip_rate_lock:
            q = _gossip_rate.get(remote_ip)
            if q is None:
                q = deque()
                _gossip_rate[remote_ip] = q
            # Evict timestamps outside the window
            cutoff = now - GOSSIP_RATE_WINDOW_S
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= GOSSIP_RATE_LIMIT:
                return False
            q.append(now)
            # Periodic pruning: if the dict gets large, drop empty queues
            if len(_gossip_rate) > 10_000:
                empties = [ip for ip, dq in _gossip_rate.items() if not dq]
                for ip in empties:
                    del _gossip_rate[ip]
            return True

    @app.route('/p2p/gossip', methods=['POST'])
    def receive_gossip():
        """Receive and process gossip message"""
        # FIX(#2867 M5): per-IP rate limit BEFORE expensive verify+CRDT work.
        remote_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        if not _gossip_rate_check(remote_ip):
            return jsonify({"error": "rate_limited", "limit": f"{GOSSIP_RATE_LIMIT}/{GOSSIP_RATE_WINDOW_S}s"}), 429

        data = request.get_json()
        result = p2p_node.handle_gossip(data)
        return jsonify(result)

    @app.route('/p2p/state', methods=['GET'])
    def get_state():
        """Get full CRDT state for sync"""
        return jsonify(p2p_node.get_full_state())

    @app.route('/p2p/attestation_state', methods=['GET'])
    def get_attestation_state():
        """Get attestation timestamps for efficient sync"""
        return jsonify(p2p_node.get_attestation_state())

    @app.route('/p2p/peers', methods=['GET'])
    def get_peers():
        """Get list of known peers"""
        return jsonify({
            "node_id": p2p_node.node_id,
            "peers": list(p2p_node.peers.keys())
        })

    @app.route('/p2p/health', methods=['GET'])
    def p2p_health():
        """P2P subsystem health check"""
        return jsonify({
            "node_id": p2p_node.node_id,
            "running": p2p_node.running,
            "peer_count": len(p2p_node.peers),
            "attestation_count": len(p2p_node.gossip.attestation_crdt.data),
            "settled_epochs": len(p2p_node.gossip.epoch_crdt.items)
        })

    logger.info("P2P endpoints registered")


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    # Test configuration
    NODE_ID = os.environ.get("RC_NODE_ID", "node1")

    PEERS = {
        "node1": "https://rustchain.org",
        "node2": "http://50.28.86.153:8099",
        "node3": "http://76.8.228.245:8099"
    }

    # Remove self from peers
    if NODE_ID in PEERS:
        del PEERS[NODE_ID]

    # Create and start node
    node = RustChainP2PNode(NODE_ID, DB_PATH, PEERS)
    node.start()

    print(f"P2P Node {NODE_ID} running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()
        print("Stopped.")
