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
from collections import defaultdict
import logging
import requests

# Configuration
P2P_SECRET = os.environ.get("RC_P2P_SECRET", "rustchain_p2p_secret_2025_decentralized")
GOSSIP_TTL = 3
SYNC_INTERVAL = 30
MESSAGE_EXPIRY = 300  # 5 minutes
MAX_INV_BATCH = 1000
DB_PATH = os.environ.get("RUSTCHAIN_DB", "/root/rustchain/rustchain_v2.db")

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
        self.seen_messages: Set[str] = set()
        self.message_queue: List[GossipMessage] = []
        self.lock = threading.Lock()

        # CRDT state
        self.attestation_crdt = LWWRegister()
        self.balance_crdt = PNCounter()
        self.epoch_crdt = GSet()

        # Load initial state from DB
        self._load_state_from_db()

    def _load_state_from_db(self):
        """Load existing state into CRDTs"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
        """Generate HMAC signature for message"""
        timestamp = int(time.time())
        message = f"{content}:{timestamp}"
        sig = hmac.new(P2P_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
        return sig, timestamp

    def _verify_signature(self, content: str, signature: str, timestamp: int) -> bool:
        """Verify HMAC signature"""
        # Check timestamp freshness
        if abs(time.time() - timestamp) > MESSAGE_EXPIRY:
            return False
        message = f"{content}:{timestamp}"
        expected = hmac.new(P2P_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def create_message(self, msg_type: MessageType, payload: Dict, ttl: int = GOSSIP_TTL) -> GossipMessage:
        """Create a new gossip message"""
        content = f"{msg_type.value}:{json.dumps(payload, sort_keys=True)}"
        sig, ts = self._sign_message(content)

        msg = GossipMessage(
            msg_type=msg_type.value,
            msg_id=hashlib.sha256(f"{content}:{ts}".encode()).hexdigest()[:24],
            sender_id=self.node_id,
            timestamp=ts,
            ttl=ttl,
            signature=sig,
            payload=payload
        )
        return msg

    def verify_message(self, msg: GossipMessage) -> bool:
        """Verify message signature and freshness"""
        content = f"{msg.msg_type}:{json.dumps(msg.payload, sort_keys=True)}"
        return self._verify_signature(content, msg.signature, msg.timestamp)

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
                verify=False
            )
            if resp.status_code != 200:
                logger.warning(f"Peer {peer_url} returned {resp.status_code}")
        except Exception as e:
            logger.debug(f"Send to {peer_url} failed: {e}")

    def handle_message(self, msg: GossipMessage) -> Optional[Dict]:
        """Handle received gossip message"""
        # Deduplication
        if msg.msg_id in self.seen_messages:
            return {"status": "duplicate"}

        # Verify signature
        if not self.verify_message(msg):
            logger.warning(f"Invalid signature from {msg.sender_id}")
            return {"status": "invalid_signature"}

        self.seen_messages.add(msg.msg_id)

        # Limit seen_messages size
        if len(self.seen_messages) > 10000:
            self.seen_messages = set(list(self.seen_messages)[-5000:])

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
        """Handle full attestation data"""
        attestation = msg.payload
        miner_id = attestation.get("miner")
        ts_ok = attestation.get("ts_ok", int(time.time()))

        # Update CRDT
        if self.attestation_crdt.set(miner_id, attestation, ts_ok):
            # Also update database
            self._save_attestation_to_db(attestation, ts_ok)
            logger.info(f"Merged attestation for {miner_id[:16]}...")

        return {"status": "ok"}

    def _save_attestation_to_db(self, attestation: Dict, ts_ok: int):
        """Save attestation to SQLite database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score)
                    VALUES (?, ?, ?, ?, ?)
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
        """Handle epoch settlement proposal"""
        proposal = msg.payload
        epoch = proposal.get("epoch")
        proposer = proposal.get("proposer")

        # Verify proposer is legitimate leader
        nodes = sorted(list(self.peers.keys()) + [self.node_id])
        expected_leader = nodes[epoch % len(nodes)]

        if proposer != expected_leader:
            logger.warning(f"Invalid proposer {proposer} for epoch {epoch}, expected {expected_leader}")
            return {"status": "reject", "reason": "invalid_leader"}

        # Validate distribution
        # TODO: Verify merkle root matches our local calculation

        # Vote to accept
        vote = self.create_message(MessageType.EPOCH_VOTE, {
            "epoch": epoch,
            "proposal_hash": proposal.get("proposal_hash"),
            "vote": "accept",
            "voter": self.node_id
        })

        self.broadcast(vote)

        return {"status": "voted", "vote": "accept"}

    def _handle_epoch_vote(self, msg: GossipMessage) -> Dict:
        """Handle epoch vote"""
        # TODO: Collect votes and commit when majority reached
        return {"status": "ok"}

    def _handle_get_state(self, msg: GossipMessage) -> Dict:
        """Handle state request - return full CRDT state"""
        return {
            "status": "ok",
            "state": {
                "attestations": self.attestation_crdt.to_dict(),
                "epochs": self.epoch_crdt.to_dict(),
                "balances": self.balance_crdt.to_dict()
            }
        }

    def _handle_state(self, msg: GossipMessage) -> Dict:
        """Handle incoming state - merge with local"""
        state = msg.payload.get("state", {})

        # Merge attestations
        if "attestations" in state:
            remote_attest = LWWRegister.from_dict(state["attestations"])
            self.attestation_crdt.merge(remote_attest)

        # Merge epochs
        if "epochs" in state:
            remote_epochs = GSet.from_dict(state["epochs"])
            self.epoch_crdt.merge(remote_epochs)

        # Merge balances
        if "balances" in state:
            remote_balances = PNCounter.from_dict(state["balances"])
            self.balance_crdt.merge(remote_balances)

        logger.info(f"Merged state from {msg.sender_id}")
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
                verify=False
            )
            if resp.status_code == 200:
                data = resp.json()
                if "state" in data:
                    state_msg = GossipMessage(
                        msg_type=MessageType.STATE.value,
                        msg_id="sync",
                        sender_id="peer",
                        timestamp=int(time.time()),
                        ttl=0,
                        signature="",
                        payload=data
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

    @app.route('/p2p/gossip', methods=['POST'])
    def receive_gossip():
        """Receive and process gossip message"""
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
        "node1": "http://50.28.86.131:8099",
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
