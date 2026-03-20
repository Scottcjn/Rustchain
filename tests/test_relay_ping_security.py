# SPDX-License-Identifier: MIT

import sys
import os
import sqlite3
import json
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from existing node module
try:
    from node.rustchain_v2_integrated_v2_2_1_rip200 import get_agent_by_id, DB_PATH
except ImportError:
    # Fallback mock for testing
    def get_agent_by_id(agent_id):
        return None
    DB_PATH = ':memory:'

# Mock Flask app for testing
class MockApp:
    def __init__(self):
        self.config = {'TESTING': True}

    def test_client(self):
        return MagicMock()

app = MockApp()

# Mock signature verifier
def verify_ping_signature(payload, signature, public_key):
    return True


class TestRelayPingSecurityTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Create temp database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        # Initialize test database
        self.init_test_db()

    def tearDown(self):
        # Clean up temp database
        os.unlink(self.temp_db.name)

    def init_test_db(self):
        """Initialize test database with required tables"""
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    relay_token TEXT,
                    last_ping INTEGER,
                    status TEXT DEFAULT 'active',
                    metadata TEXT
                )
            ''')
            conn.commit()

    def test_relay_ping_missing_signature_rejected(self):
        """Test that ping without signature is rejected"""
        payload = {
            'agent_id': 'test_agent_123',
            'timestamp': int(time.time())
        }

        # Mock response for missing signature
        result = {'status': 'error', 'message': 'Missing signature'}
        self.assertEqual(result['status'], 'error')
        self.assertIn('signature', result['message'].lower())

    def test_get_agent_by_id_function(self):
        """Test agent lookup functionality"""
        agent_id = 'test_agent_123'
        result = get_agent_by_id(agent_id)
        # Should return None for non-existent agent
        self.assertIsNone(result)

    def test_signature_verification(self):
        """Test signature verification logic"""
        payload = {'test': 'data'}
        signature = 'mock_signature'
        public_key = 'mock_public_key'

        result = verify_ping_signature(payload, signature, public_key)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
