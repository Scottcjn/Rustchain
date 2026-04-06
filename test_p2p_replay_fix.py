"""
Standalone test for the seen_messages.clear() replay vulnerability fix in p2p.py.

This test validates the fix without requiring the full Rustchain package.
It extracts and tests the MessageHandler logic in isolation.
"""
import sys
import os
import time
import threading
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum, auto


# ---- Minimal replicas of p2p.py types (to avoid import issues) ----

class MessageType(Enum):
    HELLO = auto()
    HELLO_ACK = auto()
    NEW_BLOCK = auto()
    GET_BLOCKS = auto()
    BLOCKS = auto()
    NEW_TX = auto()
    GET_TXS = auto()
    TXS = auto()
    GET_PEERS = auto()
    PEERS = auto()
    MINING_PROOF = auto()
    VALIDATOR_STATUS = auto()
    ENTROPY_CHALLENGE = auto()
    ENTROPY_RESPONSE = auto()


@dataclass
class PeerId:
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
class Message:
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

    def compute_hash(self) -> str:
        data = f"{self.msg_type.name}:{self.timestamp}:{self.nonce}:{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()


# ---- Import the actual MessageHandler from p2p.py ----
# We read and exec the relevant parts to test the real code

def _load_message_handler():
    """Load the actual MessageHandler class from p2p.py by parsing the file."""
    import re
    p2p_path = os.path.join(os.path.dirname(__file__), "rips", "rustchain-core", "networking", "p2p.py")
    with open(p2p_path) as f:
        source = f.read()

    # Strip the entire import block (from "from ..config" to the closing paren line)
    source = re.sub(
        r'from \.\.config\.chain_params import \(.*?\)\n',
        '',
        source,
        flags=re.DOTALL,
    )

    # Create a namespace with our mock types
    ns = {
        "MessageType": MessageType,
        "PeerId": PeerId,
        "Message": Message,
        "DEFAULT_PORT": 8085,
        "MTLS_PORT": 4443,
        "PROTOCOL_VERSION": "1.0.0",
        "MAX_PEERS": 50,
        "PEER_TIMEOUT_SECONDS": 30,
        "SYNC_BATCH_SIZE": 100,
        "time": time,
        "hashlib": hashlib,
        "json": json,
        "threading": threading,
        "queue": __import__("queue"),
        "socket": __import__("socket"),
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Set": Set,
        "Any": Any,
        "Callable": Callable,
        "dataclass": dataclass,
        "field": field,
        "Enum": Enum,
        "auto": auto,
        "__name__": "__not_main__",
    }

    # Execute the source to get all the classes
    exec(compile(source, p2p_path, "exec"), ns)
    return ns["MessageHandler"]


MessageHandler = _load_message_handler()


def test_seen_messages_no_replay_on_overflow():
    """
    Regression test: filling the seen_messages cache must NOT clear all entries.

    Before fix: len > 10000 triggered seen_messages.clear(), reopening replay
    window for every previously-seen message.
    After fix: oldest entries are evicted one-by-one (FIFO), so recent messages
    remain deduplicated.
    """
    handler = MessageHandler(max_seen=100)
    peer = PeerId("1.2.3.4", 9999)

    # Insert 100 unique messages (fill the cache to capacity)
    for i in range(100):
        msg = Message(
            msg_type=MessageType.NEW_TX,
            sender=peer,
            payload={"tx_id": f"tx_{i}"},
            timestamp=int(time.time()),
            nonce=i,
        )
        assert handler.handle_message(msg), f"Message {i} should be accepted"

    # The 101st message should be accepted and trigger eviction of oldest
    msg_101 = Message(
        msg_type=MessageType.NEW_TX,
        sender=peer,
        payload={"tx_id": "tx_100"},
        timestamp=int(time.time()),
        nonce=100,
    )
    assert handler.handle_message(msg_101), "Message 101 should be accepted"

    # Recent messages (e.g., tx_99) should still be deduplicated
    # (only the ~1 oldest were evicted, not all)
    msg_99 = Message(
        msg_type=MessageType.NEW_TX,
        sender=peer,
        payload={"tx_id": "tx_99"},
        timestamp=int(time.time()),
        nonce=99,
    )
    assert not handler.handle_message(msg_99), "tx_99 should be rejected as duplicate"

    # The very oldest (tx_0) may have been evicted and is now accepted again —
    # this is expected behavior for a bounded cache.
    msg_0 = Message(
        msg_type=MessageType.NEW_TX,
        sender=peer,
        payload={"tx_id": "tx_0"},
        timestamp=int(time.time()),
        nonce=0,
    )
    assert handler.handle_message(msg_0), "tx_0 was evicted, re-accept is expected"

    print("  [PASS] seen_messages overflow does not reopen replay window")


def test_replay_within_cache():
    """
    Messages within the active cache window are correctly deduplicated.
    """
    handler = MessageHandler(max_seen=1000)
    peer = PeerId("5.6.7.8", 9999)

    msg = Message(
        msg_type=MessageType.NEW_BLOCK,
        sender=peer,
        payload={"block_hash": "deadbeef"},
        timestamp=int(time.time()),
        nonce=42,
    )

    assert handler.handle_message(msg), "First submission should be accepted"
    assert not handler.handle_message(msg), "Replay should be rejected"
    assert not handler.handle_message(msg), "Second replay should also be rejected"

    print("  [PASS] replay within cache window is rejected")


def test_old_bug_clear_all():
    """
    Demonstrate what the OLD bug did: after 10001 messages, ALL previous
    messages become replayable. This test shows the fix prevents mass replay.
    """
    handler = MessageHandler(max_seen=100)
    peer = PeerId("9.9.9.9", 9999)
    now = int(time.time())

    # Fill cache with 100 messages
    for i in range(100):
        msg = Message(
            msg_type=MessageType.NEW_TX,
            sender=peer,
            payload={"tx_id": f"old_{i}"},
            timestamp=now,
            nonce=i,
        )
        handler.handle_message(msg)

    # Add 1 more to trigger eviction (not clear!)
    msg_trigger = Message(
        msg_type=MessageType.NEW_TX,
        sender=peer,
        payload={"tx_id": "trigger"},
        timestamp=now,
        nonce=999,
    )
    handler.handle_message(msg_trigger)

    # With the OLD bug (clear()), ALL 100 old messages would be replayable.
    # With the fix (FIFO eviction), most should still be deduplicated.
    replay_count = 0
    for i in range(50, 100):  # Check the newer half
        msg = Message(
            msg_type=MessageType.NEW_TX,
            sender=peer,
            payload={"tx_id": f"old_{i}"},
            timestamp=now,
            nonce=i,
        )
        if handler.handle_message(msg):
            replay_count += 1

    # With FIFO eviction of ~1 entry, at most 1 of these 50 should replay.
    # With the old clear() bug, all 50 would replay.
    assert replay_count <= 2, f"Too many replays: {replay_count} (expected <= 2 with FIFO)"
    print(f"  [PASS] mass replay prevented (only {replay_count}/50 re-accepted, expected 0-1)")


if __name__ == "__main__":
    print("=" * 60)
    print("P2P seen_messages.clear() REPLAY VULNERABILITY TEST")
    print("=" * 60)
    print()

    test_seen_messages_no_replay_on_overflow()
    test_replay_within_cache()
    test_old_bug_clear_all()

    print()
    print("All tests passed.")
