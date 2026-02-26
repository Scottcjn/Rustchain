#!/usr/bin/env python3
"""
Test suite for TOFU key management functionality.
"""
import os
import sys
import json
import unittest
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Add parent directory to path to import the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rustchain_v2_integrated_v2.2.1_rip200 import (
    init_tofu_tables,
    store_tofu_pubkey,
    validate_tofu_pubkey,
    revoke_tofu_pubkey,
    rotate_tofu_pubkey,
    get_tofu_pubkey_info
)

class TestTOFUKeyManagement(unittest.TestCase):
    def setUp(self):
        """Set up test database"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db_conn = sqlite3.connect(self.db_path)
        init_tofu_tables(self.db_conn)
        
    def tearDown(self):
        """Clean up test database"""
        self.db_conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_store_and_validate_tofu_pubkey(self):
        """Test storing and validating a TOFU pubkey"""
        miner_id = "test_miner_123"
        pubkey = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
        
        # Store first-time pubkey
        result = store_tofu_pubkey(miner_id, pubkey, self.db_conn)
        self.assertTrue(result)
        
        # Validate the same pubkey
        is_valid, reason = validate_tofu_pubkey(miner_id, pubkey, self.db_conn)
        self.assertTrue(is_valid)
        self.assertEqual(reason, "valid")
        
        # Try to store a different pubkey for the same miner (should fail)
        new_pubkey = "z6y5x4w3v2u1t0s9r8q7p6o5n4m3l2k1j0i9h8g7f6e5d4c3b2a1"
        result = store_tofu_pubkey(miner_id, new_pubkey, self.db_conn)
        self.assertFalse(result)
        
        # Validate the new pubkey (should fail)
        is_valid, reason = validate_tofu_pubkey(miner_id, new_pubkey, self.db_conn)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "pubkey_mismatch")
    
    def test_revoke_tofu_pubkey(self):
        """Test revoking a TOFU pubkey"""
        miner_id = "test_miner_456"
        pubkey = "b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a1"
        admin_key = "admin_signature_123"
        
        # Store pubkey
        store_tofu_pubkey(miner_id, pubkey, self.db_conn)
        
        # Revoke pubkey
        result = revoke_tofu_pubkey(miner_id, admin_key, self.db_conn)
        self.assertTrue(result)
        
        # Validate revoked pubkey (should fail)
        is_valid, reason = validate_tofu_pubkey(miner_id, pubkey, self.db_conn)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "pubkey_revoked")
    
    def test_rotate_tofu_pubkey(self):
        """Test rotating a TOFU pubkey"""
        miner_id = "test_miner_789"
        old_pubkey = "c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a1b2"
        new_pubkey = "d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a1b2c3"
        signature = "valid_signature_for_rotation"
        
        # Store old pubkey
        store_tofu_pubkey(miner_id, old_pubkey, self.db_conn)
        
        # Rotate to new pubkey
        result = rotate_tofu_pubkey(miner_id, old_pubkey, new_pubkey, signature, self.db_conn)
        self.assertTrue(result)
        
        # Validate old pubkey (should fail)
        is_valid, reason = validate_tofu_pubkey(miner_id, old_pubkey, self.db_conn)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "pubkey_rotated")
        
        # Validate new pubkey (should succeed)
        is_valid, reason = validate_tofu_pubkey(miner_id, new_pubkey, self.db_conn)
        self.assertTrue(is_valid)
        self.assertEqual(reason, "valid")
    
    def test_get_tofu_pubkey_info(self):
        """Test getting TOFU pubkey info"""
        miner_id = "test_miner_info"
        pubkey = "e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a1b2c3d4"
        
        # Store pubkey
        store_tofu_pubkey(miner_id, pubkey, self.db_conn)
        
        # Get info
        info = get_tofu_pubkey_info(miner_id, self.db_conn)
        self.assertIsNotNone(info)
        self.assertEqual(info['miner_id'], miner_id)
        self.assertEqual(info['pubkey'], pubkey)
        self.assertIsNone(info['revoked_at'])
        self.assertIsNone(info['rotated_to'])
        self.assertIsNotNone(info['first_seen'])

if __name__ == '__main__':
    unittest.main()