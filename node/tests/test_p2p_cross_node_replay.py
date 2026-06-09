import unittest
import time
import secrets
import json
from node.rustchain_p2p_gossip import GossipMessage, MessageType, validate_gossip_payload, LWWRegister, GossipLayer

class TestCrossNodeReplayDefense(unittest.TestCase):
    def setUp(self):
        self.node_a_id = "node_A_peer_id_123"
        self.node_b_id = "node_B_peer_id_456"
        self.miner_id = "miner_wallet_abc"

    def create_attestation_msg(self, target_node_id, sender_id=None):
        """Helper to create a signed gossip message containing an attestation."""
        if sender_id is None:
            sender_id = self.miner_id
        
        payload = {
            "miner": self.miner_id,
            "node_peer_id": target_node_id,
            "ts_ok": int(time.time()),
            "entropy_score": 0.95,
            "device_family": "x86_64",
            "device_arch": "Intel"
        }
        
        # We mock the signature since we aren't running the full Rust signer here
        # In a real integration test, we would use the actual signer.
        return GossipMessage(
            msg_type=MessageType.ATTESTATION.value,
            msg_id=secrets.token_hex(16),
            sender_id=sender_id,
            timestamp=int(time.time()),
            ttl=3,
            signature="mock_signature_valid",
            payload=payload
        )

    def test_attestation_node_mismatch_rejected(self):
        """
        Case: An attestation generated for Node A is sent to Node B.
        Expected: Node B should reject it as a replay attempt.
        """
        # Attestation is bound to Node A
        msg = self.create_attestation_msg(target_node_id=self.node_a_id)
        
        # Simulate Node B receiving this message
        from node.rustchain_p2p_gossip import RustChainP2PNode
        # Mocking the node object
        class MockGossip(GossipLayer):
            def __init__(self, node_id):
                # Use a simple object to bypass the full GossipLayer.__init__
                # which requires complex environment and networking setup.
                self.node_id = node_id
                self.attestation_crdt = LWWRegister()
                self.db_path = "/tmp/test_rustchain.db"





        node_b = MockGossip(self.node_b_id)
        result = node_b._handle_attestation(msg)
        
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "attestation_node_mismatch")
        self.assertEqual(result["miner_id"], self.miner_id)
        self.assertEqual(result["expected_node"], self.node_b_id)
        self.assertEqual(result["received_node"], self.node_a_id)

    def test_attestation_correct_node_accepted(self):
        """
        Case: An attestation generated for Node B is sent to Node B.
        Expected: Node B should accept it.
        """
        msg = self.create_attestation_msg(target_node_id=self.node_b_id)
        
        from node.rustchain_p2p_gossip import RustChainP2PNode
        # Mocking the node object
        class MockGossip(GossipLayer):
            def __init__(self, node_id):
                self.node_id = node_id
                self.attestation_crdt = LWWRegister()
                self.db_path = "/tmp/test_rustchain.db"


        node_b = MockGossip(self.node_b_id)
        result = node_b._handle_attestation(msg)
        
        self.assertEqual(result["status"], "ok")
if __name__ == "__main__":
    unittest.main()
