"""
Tests for P2P Gossip Nonce Security (Issue #2268).

Verifies that message IDs are generated using cryptographically secure 
random nonces instead of predictable timestamps.
"""
import unittest
import os

class TestP2PNonceSecurity(unittest.TestCase):
    def test_create_message_uses_secure_nonce(self):
        """create_message must use secrets.token_hex for nonce generation."""
        gossip_file = os.path.join(os.path.dirname(__file__), '..', 'node', 'rustchain_p2p_gossip.py')
        with open(gossip_file, 'r') as f:
            content = f.read()
        
        # Check that secure_nonce is used in message creation
        self.assertIn("secure_nonce = secrets.token_hex(16)", content, 
            "create_message must use secrets.token_hex(16) for nonce")
        
        # Ensure the vulnerable time.time() pattern in msg_id generation is gone
        self.assertNotIn("f\"{temp_content}:{time.time()}\"", content,
            "msg_id must NOT use predictable time.time()")

    def test_state_message_uses_secure_nonce(self):
        """State messages must also use secure nonces."""
        gossip_file = os.path.join(os.path.dirname(__file__), '..', 'node', 'rustchain_p2p_gossip.py')
        with open(gossip_file, 'r') as f:
            content = f.read()
            
        # Check that state_nonce is used
        self.assertIn("state_nonce = secrets.token_hex(16)", content,
            "State message generation must use secrets.token_hex(16)")
        
        # Ensure the vulnerable pattern in STATE msg_id is gone
        self.assertNotIn("f\"STATE:{self.node_id}:{json.dumps(payload, sort_keys=True)}:{time.time()}\"", content,
            "STATE msg_id must NOT use predictable time.time()")

if __name__ == '__main__':
    unittest.main()
