# SPDX-License-Identifier: MIT
import os
import sys
import unittest
import tempfile
import json
import time

# Add node directory to path
NODE_DIR = os.path.join(os.path.dirname(__file__), '..', 'node')
sys.path.insert(0, NODE_DIR)

# Mock p2p_identity to avoid environment variable requirements
class MockIdentity:
    SIGNING_MODE = "hmac"
    def pack_signature(h, e): return h
    def unpack_signature(s): return s, None
sys.modules['p2p_identity'] = MockIdentity

from rustchain_p2p_gossip import GossipLayer, MessageType, GossipMessage

class TestHandleGetStateArity(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        # Use a secret that passes the insecurity check (>= 32 hex chars)
        os.environ["RC_P2P_SECRET"] = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        self.layer = GossipLayer("node1", {}, self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_handle_get_state_does_not_raise(self):
        """Test that _handle_get_state returns correctly and includes msg_id/ttl."""
        # Create a dummy GET_STATE message
        msg = self.layer.create_message(MessageType.GET_STATE, {"requester": "node2"})
        
        # Execute handler
        try:
            response = self.layer._handle_get_state(msg)
        except TypeError as e:
            self.fail(f"_handle_get_state raised TypeError: {e}")

        # Check response structure
        self.assertEqual(response["status"], "ok")
        self.assertIn("msg_id", response)
        self.assertEqual(response["ttl"], 0)
        self.assertIn("signature", response)
        self.assertIn("timestamp", response)

    def test_verify_message_accepts_state_response(self):
        """Round-trip: verify that a response from _handle_get_state is valid under verify_message."""
        # 1. Generate response
        get_msg = self.layer.create_message(MessageType.GET_STATE, {"requester": "node2"})
        response = self.layer._handle_get_state(get_msg)
        
        # 2. Reconstruct as GossipMessage
        state_msg = GossipMessage(
            msg_type=MessageType.STATE.value,
            msg_id=response["msg_id"],
            sender_id=response["sender_id"],
            timestamp=response["timestamp"],
            ttl=response["ttl"],
            signature=response["signature"],
            payload={"state": response["state"]}
        )
        
        # 3. Verify
        self.assertTrue(self.layer.verify_message(state_msg), 
                        "verify_message failed to validate the state response (likely signature mismatch)")

if __name__ == '__main__':
    unittest.main()
