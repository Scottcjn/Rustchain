"""
Integration tests for TOFU key management in RustChain attestation flow.
"""

import os
import tempfile
import unittest
import sqlite3
from node.rustchain_v2_integrated_v2.2.1_rip200 import (
    tofu_ensure_tables, tofu_store_first_key, tofu_get_key_info, 
    tofu_validate_key, tofu_revoke_key, tofu_rotate_key
)


class TestTOFUIntegration(unittest.TestCase):
    """Integration tests for TOFU key management."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tofu.db")
        self.conn = sqlite3.connect(self.db_path)
        tofu_ensure_tables(self.conn)
        
    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.remove(self.db_path)
        os.rmdir(self.temp_dir)
        
    def test_first_time_key_storage(self):
        """Test storing first key for a miner."""
        miner_id = "test_miner_1"
        pubkey = "a1b2c3d4e5f6..." * 4  # 64 chars
        
        success = tofu_store_first_key(self.conn, miner_id, pubkey)
        self.assertTrue(success)
        
        key_info = tofu_get_key_info(self.conn, miner_id)
        self.assertIsNotNone(key_info)
        self.assertEqual(key_info["pubkey_hex"], pubkey)
        self.assertFalse(key_info["revoked"])
        
    def test_key_validation_first_time(self):
        """Test key validation for first-time miner."""
        miner_id = "test_miner_2"
        pubkey = "b2c3d4e5f6g7..." * 4
        
        is_valid, reason = tofu_validate_key(self.conn, miner_id, pubkey)
        self.assertTrue(is_valid)
        self.assertEqual(reason, "first_time_key_stored")
        
        # Second validation should pass
        is_valid2, reason2 = tofu_validate_key(self.conn, miner_id, pubkey)
        self.assertTrue(is_valid2)
        self.assertEqual(reason2, "key_valid")
        
    def test_pubkey_mismatch_rejection(self):
        """Test rejection of pubkey mismatch."""
        miner_id = "test_miner_3"
        pubkey1 = "c3d4e5f6g7h8..." * 4
        pubkey2 = "d4e5f6g7h8i9..." * 4
        
        # Store first key
        tofu_store_first_key(self.conn, miner_id, pubkey1)
        
        # Try to validate with different pubkey
        is_valid, reason = tofu_validate_key(self.conn, miner_id, pubkey2)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "pubkey_mismatch")
        
    def test_key_revocation(self):
        """Test key revocation functionality."""
        miner_id = "test_miner_4"
        pubkey = "e5f6g7h8i9j0..." * 4
        
        # Store and validate key
        tofu_store_first_key(self.conn, miner_id, pubkey)
        is_valid, _ = tofu_validate_key(self.conn, miner_id, pubkey)
        self.assertTrue(is_valid)
        
        # Revoke key
        success = tofu_revoke_key(self.conn, miner_id, "security_compromise")
        self.assertTrue(success)
        
        # Validation should fail after revocation
        is_valid2, reason = tofu_validate_key(self.conn, miner_id, pubkey)
        self.assertFalse(is_valid2)
        self.assertIn("key_revoked", reason)
        
    def test_key_rotation(self):
        """Test key rotation functionality."""
        miner_id = "test_miner_5"
        pubkey1 = "f6g7h8i9j0k1..." * 4
        pubkey2 = "g7h8i9j0k1l2..." * 4
        
        # Store initial key
        tofu_store_first_key(self.conn, miner_id, pubkey1)
        
        # Rotate key
        success = tofu_rotate_key(self.conn, miner_id, pubkey2, "regular_rotation")
        self.assertTrue(success)
        
        # Old key should be rejected
        is_valid_old, reason_old = tofu_validate_key(self.conn, miner_id, pubkey1)
        self.assertFalse(is_valid_old)
        self.assertEqual(reason_old, "pubkey_mismatch")
        
        # New key should be accepted
        is_valid_new, reason_new = tofu_validate_key(self.conn, miner_id, pubkey2)
        self.assertTrue(is_valid_new)
        self.assertEqual(reason_new, "key_valid")
        
        # Check rotation history
        key_info = tofu_get_key_info(self.conn, miner_id)
        rotation_history = key_info["rotation_history"]
        self.assertEqual(len(rotation_history), 1)
        self.assertEqual(rotation_history[0]["old_pubkey"], pubkey1)
        self.assertEqual(rotation_history[0]["reason"], "regular_rotation")


if __name__ == "__main__":
    unittest.main()