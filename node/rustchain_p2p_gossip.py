#!/usr/bin/env python3
\"\"\"
RustChain P2P Gossip & CRDT Synchronization Module
===================================================

Implements fully decentralized P2P sync with:
- Gossip protocol (Bitcoin-style INV/GETDATA)
- CRDT state merging (conflict-free eventual consistency)
- Epoch consensus (2-phase commit)

Designed for 3+ nodes with no single point of failure.
\"\"\"

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
from collections import defaultdict
import logging
import requests

_P2P_SECRET_RAW = os.environ.get(\"RC_P2P_SECRET\", \"\").strip()
_INSECURE_DEFAULTS = {
    \"rustchain_p2p_secret_2025_decentralized\",
    \"changeme\",
    \"secret\",
    \"default\",
    \"default-hmac-secret-change-me\",
    \"\",
}

if not _P2P_SECRET_RAW or _P2P_SECRET_RAW.lower() in _INSECURE_DEFAULTS:
    raise SystemExit(\"[P2P] FATAL: RC_P2P_SECRET environment variable is not set or contains an insecure placeholder value.\")

P2P_SECRET = _P2P_SECRET_RAW
GOSSIP_TTL = 3
SYNC_INTERVAL = 30
MESSAGE_EXPIRY = 300
MAX_INV_BATCH = 1000
DB_PATH = os.environ.get(\"RUSTCHAIN_DB\", \"/root/rustchain/rustchain_v2.db\")

_tls_verify_env = os.environ.get(\"RUSTCHAIN_TLS_VERIFY\", \"true\").strip().lower()
_ca_bundle = os.environ.get(\"RUSTCHAIN_CA_BUNDLE\", \"\").strip()
if _ca_bundle and os.path.isfile(_ca_bundle):
    TLS_VERIFY = _ca_bundle
elif _tls_verify_env in (\"false\", \"0\", \"no\"):
    TLS_VERIFY = False
else:
    TLS_VERIFY = True

logging.basicConfig(level=logging.INFO, format='%(asctime)s [P2P] %(message)s')
logger = logging.getLogger(__name__)

class MessageType(Enum):
    PING = \"ping\"
    PONG = \"pong\"
    PEER_ANNOUNCE = \"peer_announce\"
    PEER_LIST_REQ = \"peer_list_req\"
    PEER_LIST = \"peer_list\"
    INV_ATTESTATION = \"inv_attest\"
    INV_EPOCH = \"inv_epoch\"
    INV_BALANCE = \"inv_balance\"
    GET_ATTESTATION = \"get_attest\"
    GET_EPOCH = \"get_epoch\"
    GET_BALANCES = \"get_balances\"
    GET_STATE = \"get_state\"
    ATTESTATION = \"attestation\"
    EPOCH_DATA = \"epoch_data\"
    BALANCES = \"balances\"
    STATE = \"state\"
    EPOCH_PROPOSE = \"epoch_propose\"
    EPOCH_VOTE = \"epoch_vote\"
    EPOCH_COMMIT = \"epoch_commit\"

@dataclass
class GossipMessage:
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
        content = f\"{self.msg_type}:{self.sender_id}:{json.dumps(self.payload, sort_keys=True)}\"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

class LWWRegister:
    def __init__(self):
        self.data: Dict[str, Tuple[int, Dict]] = {}
    def set(self, key: str, value: Dict, timestamp: int):
        if key not in self.data or timestamp > self.data[key][0]:
            self.data[key] = (timestamp, value)
            return True
        return False
    def get(self, key: str) -> Optional[Dict]:
        if key in self.data:
            return self.data[key][1]
        return None
    def merge(self, other: 'LWWRegister'):
        for key, (ts, value) in other.data.items():
            self.set(key, value, ts)
    def to_dict(self) -> Dict:
        return {k: {\"ts\": ts, \"value\": v} for k, (ts, v) in self.data.items()}
    @classmethod
    def from_dict(cls, data: Dict) -> 'LWWRegister':
        reg = cls()
        for k, v in data.items():
            reg.data[k] = (v[\"ts\"], v[\"value\"])
        return reg

class PNCounter:
    def __init__(self):
        self.increments: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.decrements: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    def credit(self, miner_id: str, node_id: str, amount: int):
        self.increments[miner_id][node_id] += amount
    def debit(self, miner_id: str, node_id: str, amount: int):
        self.decrements[miner_id][node_id] += amount
    def get_balance(self, miner_id: str) -> int:
        incr = sum(self.increments.get(miner_id, {}).values())
        decr = sum(self.decrements.get(miner_id, {}).values())
        return incr - decr
    def get_all_balances(self) -> Dict[str, int]:
        all_miners = set(self.increments.keys()) | set(self.decrements.keys())
        return {m: self.get_balance(m) for m in all_miners}
    def merge(self, other: 'PNCounter'):
        for miner_id, node_amounts in other.increments.items():
            for node_id, amount in node_amounts.items():
                self.increments[miner_id][node_id] = max(self.increments[miner_id].get(node_id, 0), amount)
        for miner_id, node_amounts in other.decrements.items():
            for node_id, amount in node_amounts.items():
                self.decrements[miner_id][node_id] = max(self.decrements[miner_id].get(node_id, 0), amount)
    def to_dict(self) -> Dict:
        return {\"increments\": {k: dict(v) for k, v in self.increments.items()}, \"decrements\": {k: dict(v) for k, v in self.decrements.items()}}
    @classmethod
    def from_dict(cls, data: Dict) -> 'PNCounter':
        counter = cls()
        for miner_id, nodes in data.get(\"increments\", {}).items():
            for node_id, amount in nodes.items():
                counter.increments[miner_id][node_id] = amount
        for miner_id, nodes in data.get(\"decrements\", {}).items():
            for node_id, amount in nodes.items():
                counter.decrements[miner_id][node_id] = amount
        return counter

class GSet:
    def __init__(self):
        self.items: Set[int] = set()
        self.metadata: Dict[int, Dict] = {}
    def add(self, epoch: int, metadata: Dict = None):
        self.items.add(epoch)
        if metadata:
            self.metadata[epoch] = metadata
    def contains(self, epoch: int) -> bool:
        return epoch in self.items
    def merge(self, other: 'GSet'):
        self.items |= other.items
        for epoch, meta in other.metadata.items():
            if epoch not in self.metadata:
                self.metadata[epoch] = meta
    def to_dict(self) -> Dict:
        return {\"epochs\": list(self.items), \"metadata\": self.metadata}
    @classmethod
    def from_dict(cls, data: Dict) -> 'GSet':
        gset = cls()
        gset.items = set(data.get(\"epochs\", []))
        gset.metadata = data.get(\"metadata\", {})
        return gset

class GossipLayer:
    def __init__(self, node_id: str, peers: Dict[str, str], db_path: str = DB_PATH):
        self.node_id = node_id
        self.peers = peers
        self.db_path = db_path
        self.seen_messages: Set[str] = set()
        self.message_queue: List[GossipMessage] = []
        self.lock = threading.Lock()
        self.attestation_crdt = LWWRegister()
        self.balance_crdt = PNCounter()
        self.epoch_crdt = GSet()
        from p2p_identity import SIGNING_MODE, LocalKeypair, PeerRegistry
        self._signing_mode = SIGNING_MODE
        self._keypair: Optional[LocalKeypair] = None
        self._peer_registry: Optional[PeerRegistry] = None
        if self._signing_mode != \"hmac\":
            self._keypair = LocalKeypair()
            self._peer_registry = PeerRegistry()
            _ = self._keypair.pubkey_hex
            self._peer_registry.load()
        self._load_state_from_db()

    def _load_state_from_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(\"CREATE TABLE IF NOT EXISTS p2p_seen_messages (msg_id TEXT PRIMARY KEY, ts INTEGER NOT NULL)\")
                conn.execute(\"CREATE INDEX IF NOT EXISTS idx_p2p_seen_ts ON p2p_seen_messages(ts)\")
                conn.commit()
                rows = conn.execute(\"SELECT miner, ts_ok, device_family, device_arch, entropy_score FROM miner_attest_recent\").fetchall()
                for miner, ts_ok, family, arch, entropy in rows:
                    self.attestation_crdt.set(miner, {\"miner\": miner, \"device_family\": family, \"device_arch\": arch, \"entropy_score\": entropy or 0}, ts_ok)
                rows = conn.execute(\"SELECT epoch FROM epoch_state WHERE settled = 1\").fetchall()
                for (epoch,) in rows:
                    self.epoch_crdt.add(epoch)
        except Exception as e:
            logger.error(f\"Failed to load state from DB: {e}\")

    def _sign_message(self, content: str) -> Tuple[str, int]:
        timestamp = int(time.time())
        message = f\"{content}:{timestamp}\"
        mode = self._signing_mode
        hmac_sig, ed25519_sig = None, None
        if mode in (\"hmac\", \"dual\"):
            hmac_sig = hmac.new(P2P_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
        if mode in (\"dual\", \"ed25519\", \"strict\") and self._keypair is not None:
            ed25519_sig = self._keypair.sign(message.encode())
        from p2p_identity import pack_signature
        return pack_signature(hmac_sig, ed25519_sig), timestamp

    def _verify_signature(self, content: str, signature: str, timestamp: int) -> bool:
        if abs(time.time() - timestamp) > MESSAGE_EXPIRY:
            return False
        message = f\"{content}:{timestamp}\"
        mode = self._signing_mode
        from p2p_identity import unpack_signature, verify_ed25519
        hmac_sig, ed25519_sig = unpack_signature(signature)
        if mode == \"strict\":
            if ed25519_sig is None: return False
            return False
        if mode == \"hmac\":
            if hmac_sig is None: return False
            expected = hmac.new(P2P_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(hmac_sig, expected)
        if hmac_sig is not None:
            expected = hmac.new(P2P_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(hmac_sig, expected): return True
        return False

    @staticmethod
    def _signed_content(msg_type: str, sender_id: str, msg_id: str, ttl: int, payload: Dict) -> str:
        return f\"{msg_type}:{sender_id}:{msg_id}:{ttl}:{json.dumps(payload, sort_keys=True)}\"

    def create_message(self, msg_type: MessageType, payload: Dict, ttl: int = GOSSIP_TTL) -> GossipMessage:
        temp_content = f\"{msg_type.value}:{self.node_id}:{json.dumps(payload, sort_keys=True)}\"
        msg_id = hashlib.sha256(f\"{temp_content}:{time.time()}\".encode()).hexdigest()[:24]
        content = self._signed_content(msg_type.value, self.node_id, msg_id, ttl, payload)
        sig, ts = self._sign_message(content)
        return GossipMessage(msg_type=msg_//C... (truncated)
