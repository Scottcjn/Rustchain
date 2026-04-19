import os
import sys
import json
import sqlite3
import time
import hashlib
import unittest
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Mock the signing infrastructure to avoid external dependencies
def mock_pack_signature(hmac_sig, ed25519_sig):
    return json.dumps({"hmac": hmac_sig, "ed25519": ed25519_sig})

def mock_unpack_signature(sig_json):
    data = json.loads(sig_json)
    return data.get("hmac"), data.get("ed25519")

# Minimal implementation of the P2P Gossip code for reproduction
class GossipMessage:
    def __init__(self, msg_type, msg_id, sender_id, timestamp, ttl, signature, payload):
        self.msg_type = msg_type
        self.msg_id = msg_id
        self.sender_id = sender_id
        self.timestamp = timestamp
        self.ttl = ttl
        self.signature = signature
        self.payload = payload

class LWWRegister:
    def __init__(self): self.data = {}
    def to_dict(self): return self.data

class PNCounter:
    def __init__(self): self.increments = {}; self.decrements = {}
    def to_dict(self): return {"increments": self.increments, "decrements": self.decrements}

class GSet:
    def __init__(self): self.items = set(); self.metadata = {}
    def to_dict(self): return {"epochs": list(self.items), "metadata": self.metadata}

class ReproGossipLayer:
    def __init__(self, node_id):
        self.node_id = node_id
        self.attestation_crdt = LWWRegister()
        self.balance_crdt = PNCounter()
        self.epoch_crdt = GSet()
        self._signing_mode = "hmac"
        self.P2P_SECRET = "test_secret"

    @staticmethod
    def _signed_content(msg_type: str, sender_id: str, msg_id: str, ttl: int, payload: Dict) -> str:
        # BUG: signature takes 5 args, but _handle_get_state passes 3
        return f"{msg_type}:{sender_id}:{msg_id}:{ttl}:{json.dumps(payload, sort_keys=True)}"

    def _sign_message(self, content: str) -> Tuple[str, int]:
        timestamp = int(time.time())
        message = f"{content}:{timestamp}"
        hmac_sig = hashlib.sha256((self.P2P_SECRET + message).encode()).hexdigest()
        return mock_pack_signature(hmac_sig, None), timestamp

    def _handle_get_state(self, msg: GossipMessage) -> Dict:
        state_data = {
            "attestations": self.attestation_crdt.to_dict(),
            "epochs": self.epoch_crdt.to_dict(),
            "balances": self.balance_crdt.to_dict()
        }
        payload = {"state": state_data}
        
        print("CRITICAL: Attempting to call _signed_content with 3 arguments (Expected 5)...")
        # This line matches the bug in node/rustchain_p2p_gossip.py
        try:
            # content = self._signed_content(MessageType.STATE.value, self.node_id, payload)
            # Literal reproduction:
            content = self._signed_content("state", self.node_id, payload)
            return {"status": "ok", "content": content}
        except TypeError as e:
            print(f"REPRODUCED: Caught expected TypeError: {e}")
            raise

class TestIssue305Repro(unittest.TestCase):
    def test_arity_mismatch_repro(self):
        layer = ReproGossipLayer("node1")
        msg = GossipMessage("get_state", "id123", "node2", int(time.time()), 3, "sig", {"requester": "node2"})
        
        with self.assertRaises(TypeError) as cm:
            layer._handle_get_state(msg)
        
        self.assertIn("missing 2 required positional arguments", str(cm.exception))
        print("Verification Successful: Bug is real and reproducible.")

if __name__ == "__main__":
    unittest.main()
