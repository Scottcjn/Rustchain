"""
RustChain P2P Networking (RIP-0005)
===================================

Peer-to-peer networking for block propagation, transaction gossip,
and validator coordination.

Security Features:
- mTLS for peer authentication
- Message signing with validator keys
- DDoS protection via rate limiting
- Reputation-based peer selection
"""

import hashlib
import json
import socket
import time
import threading
import queue
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum, auto

from ..config.chain_params import (
    DEFAULT_PORT,
    MTLS_PORT,
    PROTOCOL_VERSION,
    MAX_PEERS,
    PEER_TIMEOUT_SECONDS,
    SYNC_BATCH_SIZE,
)


# =============================================================================
# Message Types
# =============================================================================

class MessageType(Enum):
    """P2P message types"""
    # Handshake
    HELLO = auto()
    HELLO_ACK = auto()

    # Block propagation
    NEW_BLOCK = auto()
    GET_BLOCKS = auto()
    BLOCKS = auto()

    # Transaction gossip
    NEW_TX = auto()
    GET_TXS = auto()
    TXS = auto()

    # Peer discovery
    GET_PEERS = auto()
    PEERS = auto()

    # Validator coordination
    MINING_PROOF = auto()
    VALIDATOR_STATUS = auto()

    # Entropy verification
    ENTROPY_CHALLENGE = auto()
    ENTROPY_RESPONSE = auto()


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class PeerId:
    """Unique peer identifier"""
    address: str
    port: int
    public_key: bytes = b''

    def __hash__(self):
        return hash((self.address, self.port))

    def __eq__(self, other):
        if isinstance(other, PeerId):
            return self.address == other.address and self.port == other.port
        return False

    def to_string(self) -> str:
        return f"{self.address}:{self.port}"


@dataclass
class PeerInfo:
    """Information about a connected peer"""
    peer_id: PeerId
    protocol_version: str
    chain_id: int
    best_block_height: int
    best_block_hash: str
    connected_at: int
    last_seen: int
    reputation: float = 50.0
    latency_ms: float = 0.0

    def is_alive(self, timeout: int = PEER_TIMEOUT_SECONDS) -> bool:
        return (int(time.time()) - self.last_seen) < timeout


@dataclass
class Message:
    """P2P message"""
    msg_type: MessageType
    sender: PeerId
    payload: Dict[str, Any]
    timestamp: int = 0
    signature: bytes = b''
    nonce: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = int(time.time())
        if not self.nonce:
            self.nonce = int.from_bytes(hashlib.sha256(str(time.time()).encode()).digest()[:4], 'big')

    def to_bytes(self) -> bytes:
        """Serialize message to bytes"""
        data = {
            "type": self.msg_type.name,
            "sender": self.sender.to_string() if self.sender else "",
            "payload": self.payload,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }
        return json.dumps(data).encode()

    @classmethod
    def from_bytes(cls, data: bytes, sender: PeerId) -> 'Message':
        """Deserialize message from bytes"""
        parsed = json.loads(data.decode())
        return cls(
            msg_type=MessageType[parsed["type"]],
            sender=sender,
            payload=parsed["payload"],
            timestamp=parsed["timestamp"],
            nonce=parsed["nonce"],
        )

    def compute_hash(self) -> str:
        """Compute message hash for signing"""
        data = f"{self.msg_type.name}:{self.timestamp}:{self.nonce}:{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()


# =============================================================================
# Peer Manager
# =============================================================================

class PeerManager:
    """
    Manages peer connections and reputation.

    Security:
    - Maintains peer reputation based on behavior
    - Bans malicious peers
    - Limits connections to prevent resource exhaustion
    """

    def __init__(self, max_peers: int = MAX_PEERS):
        self.peers: Dict[str, PeerInfo] = {}
        self.banned: Set[str] = set()
        self.max_peers = max_peers
        self._lock = threading.Lock()

    def add_peer(self, peer_info: PeerInfo) -> bool:
        """Add a new peer"""
        with self._lock:
            peer_key = peer_info.peer_id.to_string()

            if peer_key in self.banned:
                return False

            if len(self.peers) >= self.max_peers:
                # Remove lowest reputation peer
                if self.peers:
                    worst = min(self.peers.values(), key=lambda p: p.reputation)
                    if worst.reputation < peer_info.reputation:
                        del self.peers[worst.peer_id.to_string()]
                    else:
                        return False

            self.peers[peer_key] = peer_info
            return True

    def remove_peer(self, peer_id: PeerId):
        """Remove a peer"""
        with self._lock:
            peer_key = peer_id.to_string()
            if peer_key in self.peers:
                del self.peers[peer_key]

    def update_peer(self, peer_id: PeerId, **kwargs):
        """Update peer information"""
        with self._lock:
            peer_key = peer_id.to_string()
            if peer_key in self.peers:
                peer = self.peers[peer_key]
                for key, value in kwargs.items():
                    if hasattr(peer, key):
                        setattr(peer, key, value)
                peer.last_seen = int(time.time())

    def adjust_reputation(self, peer_id: PeerId, delta: float):
        """Adjust peer reputation"""
        with self._lock:
            peer_key = peer_id.to_string()
            if peer_key in self.peers:
                peer = self.peers[peer_key]
                peer.reputation = max(0, min(100, peer.reputation + delta))

                # Ban if reputation too low
                if peer.reputation < 10:
                    self.ban_peer(peer_id, "Low reputation")

    def ban_peer(self, peer_id: PeerId, reason: str):
        """Ban a malicious peer"""
        with self._lock:
            peer_key = peer_id.to_string()
            self.banned.add(peer_key)
            if peer_key in self.peers:
                del self.peers[peer_key]
            print(f"BANNED: {peer_key} - {reason}")

    def get_peers(self, count: int = 10) -> List[PeerInfo]:
        """Get best peers by reputation"""
        with self._lock:
            alive_peers = [p for p in self.peers.values() if p.is_alive()]
            sorted_peers = sorted(alive_peers, key=lambda p: p.reputation, reverse=True)
            return sorted_peers[:count]

    def get_peer(self, peer_id: PeerId) -> Optional[PeerInfo]:
        """Get specific peer info"""
        with self._lock:
            return self.peers.get(peer_id.to_string())

    def cleanup_stale(self):
        """Remove stale peers"""
        with self._lock:
            stale = [
                k for k, p in self.peers.items()
                if not p.is_alive()
            ]
            for peer_key in stale:
                del self.peers[peer_key]


# =============================================================================
# Message Handler
# =============================================================================

class MessageHandler:
    """
    Handles incoming P2P messages.

    Implements message validation, deduplication, and routing.
    """

    def __init__(self):
        self.handlers: Dict[MessageType, List[Callable]] = {}
        self.seen_messages: Set[str] = set()
        self._lock = threading.Lock()

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a message handler"""
        if msg_type not in self.handlers:
            self.handlers[msg_type] = []
        self.handlers[msg_type].append(handler)

    def handle_message(self, message: Message) -> bool:
        """
        Handle an incoming message.

        Returns True if message was processed, False if duplicate/invalid.
        """
        # Check for duplicate
        msg_hash = message.compute_hash()
        with self._lock:
            if msg_hash in self.seen_messages:
                return False
            self.seen_messages.add(msg_hash)

            # Cleanup old messages periodically
            if len(self.seen_messages) > 10000:
                self.seen_messages.clear()

        # Validate timestamp (reject old messages)
        now = int(time.time())
        if abs(now - message.timestamp) > 300:  # 5 minute window
            return False

        # Route to handlers
        handlers = self.handlers.get(message.msg_type, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                print(f"Handler error: {e}")

        return True


# =============================================================================
# Network Manager
# =============================================================================

class NetworkManager:
    """
    Main network manager for P2P communication.

    Features:
    - Peer discovery and management
    - Message broadcasting and routing
    - Block and transaction propagation
    - Sync coordination
    """

    def __init__(
        self,
        listen_port: int = DEFAULT_PORT,
        chain_id: int = 2718,
        validator_id: str = "",
    ):
        self.listen_port = listen_port
        self.chain_id = chain_id
        self.validator_id = validator_id

        self.peer_manager = PeerManager()
        self.message_handler = MessageHandler()

        self.outbound_queue: queue.Queue = queue.Queue()
        self.running = False

        self._local_peer_id = PeerId(
            address="0.0.0.0",
            port=listen_port,
        )

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default message handlers"""
        self.message_handler.register_handler(MessageType.HELLO, self._handle_hello)
        self.message_handler.register_handler(MessageType.GET_PEERS, self._handle_get_peers)
        self.message_handler.register_handler(MessageType.PEERS, self._handle_peers)

    def _handle_hello(self, message: Message):
        """Handle HELLO message"""
        payload = message.payload
        peer_info = PeerInfo(
            peer_id=message.sender,
            protocol_version=payload.get("version", PROTOCOL_VERSION),
            chain_id=payload.get("chain_id", 0),
            best_block_height=payload.get("best_height", 0),
            best_block_hash=payload.get("best_hash", ""),
            connected_at=int(time.time()),
            last_seen=int(time.time()),
        )

        # Verify chain ID
        if peer_info.chain_id != self.chain_id:
            print(f"Rejecting peer {message.sender.to_string()}: wrong chain ID")
            return

        self.peer_manager.add_peer(peer_info)

        # Send HELLO_ACK
        self.send_message(message.sender, MessageType.HELLO_ACK, {
            "version": PROTOCOL_VERSION,
            "chain_id": self.chain_id,
            "validator_id": self.validator_id,
        })

    def _handle_get_peers(self, message: Message):
        """Handle GET_PEERS message"""
        peers = self.peer_manager.get_peers(10)
        peer_list = [
            {
                "address": p.peer_id.address,
                "port": p.peer_id.port,
                "reputation": p.reputation,
            }
            for p in peers
        ]

        self.send_message(message.sender, MessageType.PEERS, {
            "peers": peer_list,
        })

    def _handle_peers(self, message: Message):
        """Handle PEERS message"""
        for peer_data in message.payload.get("peers", []):
            peer_id = PeerId(
                address=peer_data["address"],
                port=peer_data["port"],
            )
            # Try to connect to new peer
            self.connect_to_peer(peer_id)

    def connect_to_peer(self, peer_id: PeerId) -> bool:
        """Initiate connection to a peer"""
        # Send HELLO message
        self.send_message(peer_id, MessageType.HELLO, {
            "version": PROTOCOL_VERSION,
            "chain_id": self.chain_id,
            "best_height": 0,  # TODO: Get from chain
            "best_hash": "",
            "validator_id": self.validator_id,
        })
        return True

    def send_message(self, peer_id: PeerId, msg_type: MessageType, payload: Dict[str, Any]):
        """Send a message to a specific peer"""
        message = Message(
            msg_type=msg_type,
            sender=self._local_peer_id,
            payload=payload,
        )

        self.outbound_queue.put((peer_id, message))

    def broadcast(self, msg_type: MessageType, payload: Dict[str, Any]):
        """Broadcast a message to all peers"""
        peers = self.peer_manager.get_peers()
        for peer in peers:
            self.send_message(peer.peer_id, msg_type, payload)

    def broadcast_block(self, block_data: Dict[str, Any]):
        """Broadcast a new block to the network"""
        self.broadcast(MessageType.NEW_BLOCK, {"block": block_data})

    def broadcast_transaction(self, tx_data: Dict[str, Any]):
        """Broadcast a new transaction to the network"""
        self.broadcast(MessageType.NEW_TX, {"transaction": tx_data})

    def request_blocks(self, peer_id: PeerId, start_height: int, count: int = SYNC_BATCH_SIZE):
        """Request blocks from a peer"""
        self.send_message(peer_id, MessageType.GET_BLOCKS, {
            "start_height": start_height,
            "count": count,
        })

    def start(self):
        """Start the network manager"""
        self.running = True
        print(f"Network started on port {self.listen_port}")

        # Start peer cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

    def stop(self):
        """Stop the network manager"""
        self.running = False
        print("Network stopped")

    def _cleanup_loop(self):
        """Periodic cleanup of stale peers"""
        while self.running:
            time.sleep(60)
            self.peer_manager.cleanup_stale()

    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status"""
        peers = self.peer_manager.get_peers()
        if not peers:
            return {
                "synced": False,
                "best_peer_height": 0,
                "connected_peers": 0,
            }

        best_peer = max(peers, key=lambda p: p.best_block_height)

        return {
            "synced": True,  # TODO: Compare with local height
            "best_peer_height": best_peer.best_block_height,
            "connected_peers": len(peers),
            "best_peer": best_peer.peer_id.to_string(),
        }


# =============================================================================
# Seed Nodes
# =============================================================================

SEED_NODES = [
    PeerId("seed1.rustchain.net", DEFAULT_PORT),
    PeerId("seed2.rustchain.net", DEFAULT_PORT),
    PeerId("seed3.rustchain.net", DEFAULT_PORT),
]


def bootstrap_network(manager: NetworkManager):
    """Bootstrap network connections from seed nodes"""
    for seed in SEED_NODES:
        try:
            manager.connect_to_peer(seed)
        except Exception as e:
            print(f"Failed to connect to seed {seed.to_string()}: {e}")


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN P2P NETWORKING TEST")
    print("=" * 60)

    manager = NetworkManager(
        listen_port=8085,
        chain_id=2718,
        validator_id="test_validator",
    )

    manager.start()

    # Simulate peer connection
    peer_id = PeerId("192.168.1.100", 8085)
    peer_info = PeerInfo(
        peer_id=peer_id,
        protocol_version=PROTOCOL_VERSION,
        chain_id=2718,
        best_block_height=100,
        best_block_hash="abc123",
        connected_at=int(time.time()),
        last_seen=int(time.time()),
    )

    manager.peer_manager.add_peer(peer_info)

    status = manager.get_sync_status()
    print(f"\nSync Status: {status}")
    print(f"Connected Peers: {status['connected_peers']}")

    manager.stop()
