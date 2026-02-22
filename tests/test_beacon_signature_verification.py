"""
Test suite for beacon_signature_verification module.
"""

import unittest
import tempfile
import os
import sqlite3
import json
import base64
from unittest.mock import patch, MagicMock

# Add the node directory to Python path
import sys
sys.path.insert(0, 'node')

from beacon_signature_verification import (
    verify_relay_ping_signature, 
    agent_has_stored_pubkey,
    tofu_get_key_info,
    verify_ed25519_fallback
)


class TestBeaconSignatureVerification(unittest.TestCase):
    """Test cases for beacon signature verification."""
    
    def setUp(self):
        """Set up test database and temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_beacon_atlas.db")
        
        # Create test database with relay_agents table
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relay_agents (
                agent_id TEXT PRIMARY KEY,
                pubkey_hex TEXT,
                revoked INTEGER DEFAULT 0,
                last_seen REAL,
                created_at REAL
            )
        """)
        conn.commit()
        conn.close()
        
        # Mock the get_db function to use our test database
        self.original_get_db = None
        
    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
        
    def mock_get_db(self):
        """Mock database connection function."""
        return sqlite3.connect(self.db_path)
        
    def test_tofu_get_key_info_found(self):
        """Test retrieving key info for existing agent."""
        # Insert test data
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO relay_agents (agent_id, pubkey_hex, revoked, created_at) VALUES (?, ?, ?, ?)",
            ("test_agent_1", "a1b2c3d4e5f6..." * 4, 0, 1234567890)
        )
        conn.commit()
        conn.close()
        
        # Test retrieval
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            key_info = tofu_get_key_info(None, "test_agent_1")
            self.assertIsNotNone(key_info)
            self.assertEqual(key_info["pubkey_hex"], "a1b2c3d4e5f6..." * 4)
            self.assertFalse(key_info["revoked"])
            
    def test_tofu_get_key_info_not_found(self):
        """Test retrieving key info for non-existent agent."""
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            key_info = tofu_get_key_info(None, "nonexistent_agent")
            self.assertIsNone(key_info)
            
    def test_tofu_get_key_info_revoked(self):
        """Test retrieving key info for revoked agent."""
        # Insert test data
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO relay_agents (agent_id, pubkey_hex, revoked, created_at) VALUES (?, ?, ?, ?)",
            ("revoked_agent", "b2c3d4e5f6g7..." * 4, 1, 1234567890)
        )
        conn.commit()
        conn.close()
        
        # Test retrieval
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            key_info = tofu_get_key_info(None, "revoked_agent")
            self.assertIsNotNone(key_info)
            self.assertTrue(key_info["revoked"])
            
    def test_agent_has_stored_pubkey_true(self):
        """Test agent has stored pubkey returns True."""
        # Insert test data
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO relay_agents (agent_id, pubkey_hex, created_at) VALUES (?, ?, ?)",
            ("test_agent_2", "c3d4e5f6g7h8..." * 4, 1234567890)
        )
        conn.commit()
        conn.close()
        
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            result = agent_has_stored_pubkey("test_agent_2")
            self.assertTrue(result)
            
    def test_agent_has_stored_pubkey_false(self):
        """Test agent has stored pubkey returns False for non-existent agent."""
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            result = agent_has_stored_pubkey("nonexistent_agent")
            self.assertFalse(result)
            
    def test_verify_ed25519_fallback_no_nacl(self):
        """Test fallback verification when pynacl is not available."""
        with patch('beacon_signature_verification.HAVE_NACL', False):
            result = verify_ed25519_fallback("a1b2c3d4e5f6...", b"test message", "signature")
            self.assertFalse(result)
            
    @patch('beacon_signature_verification.HAVE_NACL', True)
    @patch('beacon_signature_verification.VerifyKey')
    def test_verify_ed25519_fallback_valid_signature(self, mock_verify_key):
        """Test fallback verification with valid signature."""
        mock_verify_instance = MagicMock()
        mock_verify_key.return_value = mock_verify_instance
        mock_verify_instance.verify.return_value = None  # No exception means valid
        
        result = verify_ed25519_fallback("a1b2c3d4e5f6..." * 8, b"test message", "dGVzdCBzaWduYXR1cmU=")
        self.assertTrue(result)
        mock_verify_instance.verify.assert_called_once()
        
    @patch('beacon_signature_verification.HAVE_NACL', True)
    @patch('beacon_signature_verification.VerifyKey')
    def test_verify_ed25519_fallback_invalid_signature(self, mock_verify_key):
        """Test fallback verification with invalid signature."""
        from nacl.exceptions import BadSignatureError
        mock_verify_instance = MagicMock()
        mock_verify_key.return_value = mock_verify_instance
        mock_verify_instance.verify.side_effect = BadSignatureException()
        
        result = verify_ed25519_fallback("a1b2c3d4e5f6..." * 8, b"test message", "invalid_signature")
        self.assertFalse(result)
        
    def test_verify_relay_ping_signature_no_db_connection(self):
        """Test verification fails when database connection fails."""
        with patch('beacon_signature_verification.get_db', side_effect=Exception("DB error")):
            result = verify_relay_ping_signature("test_agent", {}, "signature")
            self.assertFalse(result)
            
    def test_verify_relay_ping_signature_no_key_info(self):
        """Test verification fails when no key info exists."""
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            result = verify_relay_ping_signature("nonexistent_agent", {}, "signature")
            self.assertFalse(result)
            
    def test_verify_relay_ping_signature_revoked_key(self):
        """Test verification fails when key is revoked."""
        # Insert revoked key
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO relay_agents (agent_id, pubkey_hex, revoked, created_at) VALUES (?, ?, ?, ?)",
            ("revoked_test", "d4e5f6g7h8i9..." * 4, 1, 1234567890)
        )
        conn.commit()
        conn.close()
        
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            result = verify_relay_ping_signature("revoked_test", {}, "signature")
            self.assertFalse(result)
            
    @patch('beacon_signature_verification.HAVE_BEACON_SKILL', False)
    @patch('beacon_signature_verification.HAVE_NACL', True)
    @patch('beacon_signature_verification.VerifyKey')
    def test_verify_relay_ping_signature_fallback_success(self, mock_verify_key):
        """Test full verification flow using fallback crypto."""
        # Insert test key
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO relay_agents (agent_id, pubkey_hex, created_at) VALUES (?, ?, ?)",
            ("test_agent_3", "e5f6g7h8i9j0..." * 4, 1234567890)
        )
        conn.commit()
        conn.close()
        
        # Mock successful verification
        mock_verify_instance = MagicMock()
        mock_verify_key.return_value = mock_verify_instance
        mock_verify_instance.verify.return_value = None
        
        # Test payload
        test_payload = {
            "agent_id": "test_agent_3",
            "timestamp": 1234567890,
            "status": "alive"
        }
        
        with patch('beacon_signature_verification.get_db', self.mock_get_db):
            result = verify_relay_ping_signature("test_agent_3", test_payload, "valid_signature")
            self.assertTrue(result)
            
    def test_verify_relay_ping_signature_payload_serialization(self):
        """Test that payload serialization is consistent."""
        # This test ensures that the JSON serialization produces consistent results
        # which is crucial for signature verification
        
        payload1 = {"a": 1, "b": 2, "c": 3}
        payload2 = {"c": 3, "b": 2, "a": 1}  # Same content, different order
        
        # Both should produce the same JSON string due to sort_keys=True
        json1 = json.dumps(payload1, sort_keys=True, separators=(',', ':'))
        json2 = json.dumps(payload2, sort_keys=True, separators=(',', ':'))
        
        self.assertEqual(json1, json2)
        self.assertEqual(json1, '{"a":1,"b":2,"c":3}')


if __name__ == '__main__':
    unittest.main()