"""
Test suite for TOFU Key Manager
"""

import os
import tempfile
import unittest
from node.security.tofu_key_manager import TOFUKeyManager


class TestTOFUKeyManager(unittest.TestCase):
    """Test cases for TOFU Key Manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.key_store_path = os.path.join(self.temp_dir, "test_keys.json")
        self.key_manager = TOFUKeyManager(self.key_store_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.key_store_path):
            os.remove(self.key_store_path)
        os.rmdir(self.temp_dir)
    
    def test_generate_key(self):
        """Test key generation."""
        node_id = "test_node_1"
        key = self.key_manager.generate_key(node_id)
        
        self.assertIsNotNone(key)
        self.assertTrue(self.key_manager.is_key_valid(node_id))
        self.assertEqual(len(key), 64)  # SHA256 hash length
        
    def test_revoke_key(self):
        """Test key revocation."""
        node_id = "test_node_2"
        self.key_manager.generate_key(node_id)
        
        # Key should be valid initially
        self.assertTrue(self.key_manager.is_key_valid(node_id))
        
        # Revoke the key
        result = self.key_manager.revoke_key(node_id, "test revocation")
        self.assertTrue(result)
        
        # Key should be invalid after revocation
        self.assertFalse(self.key_manager.is_key_valid(node_id))
        
    def test_rotate_key(self):
        """Test key rotation."""
        node_id = "test_node_3"
        original_key = self.key_manager.generate_key(node_id)
        
        # Rotate the key
        new_key = self.key_manager.rotate_key(node_id)
        
        # New key should be different from original
        self.assertNotEqual(original_key, new_key)
        
        # Key should still be valid
        self.assertTrue(self.key_manager.is_key_valid(node_id))
        
        # Check rotation history
        key_info = self.key_manager.get_key_info(node_id)
        self.assertIn("rotation_history", key_info)
        self.assertEqual(len(key_info["rotation_history"]), 1)
        
    def test_key_validation(self):
        """Test key validation for non-existent keys."""
        self.assertFalse(self.key_manager.is_key_valid("non_existent_node"))
        
    def test_duplicate_key_generation(self):
        """Test that duplicate key generation raises an error."""
        node_id = "duplicate_test"
        self.key_manager.generate_key(node_id)
        
        with self.assertRaises(ValueError):
            self.key_manager.generate_key(node_id)


if __name__ == "__main__":
    unittest.main()