import unittest
import json
import os
import tempfile
import sqlite3
from node.rustchain_p2p_gossip import GossipLayer, MessageType, GossipMessage

class TestGetStateArity(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.gossip = GossipLayer(node_id="test_node", db_path=self.db_path, peers={})

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_handle_get_state_no_raise(self):
        """Assert _handle_get_state runs without TypeError and returns verifiable signature"""
        # Create a mock GET_STATE message
        msg = GossipMessage(
            msg_type=MessageType.GET_STATE.value,
            msg_id="test_get_state",
            sender_id="peer_node",
            timestamp=1234567890,
            ttl=1,
            signature="mock_sig",
            payload={"requester": "peer_node"}
        )
        
        # This should NOT raise TypeError now
        response = self.gossip._handle_get_state(msg)
        
        self.assertEqual(response["status"], "ok")
        self.assertIn("state", response)
        self.assertIn("signature", response)
        self.assertIn("msg_id", response)
        self.assertIn("ttl", response)
        
        # Verify the signature end-to-end
        # Reconstruction logic used by the requester
        state_msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id=response["msg_id"],
            sender_id=response["sender_id"],
            timestamp=response["timestamp"],
            ttl=response["ttl"],
            signature=response["signature"],
            payload={"state": response["state"]}
        )
        
        self.assertTrue(self.gossip.verify_message(state_msg), "Requester failed to verify state response signature")

if __name__ == "__main__":
    unittest.main()
