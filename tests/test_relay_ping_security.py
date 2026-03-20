# SPDX-License-Identifier: MIT

import sys
import os
import sqlite3
import json
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the relay_ping_secure module instead
from relay_ping_secure import app, get_agent_by_id, DB_PATH
from signature_verifier import verify_ping_signature


class TestRelayPingSecurityTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Create temp database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        # Override DB_PATH for tests
        import relay_ping_secure
        self.original_db_path = relay_ping_secure.DB_PATH
        relay_ping_secure.DB_PATH = self.temp_db.name

        # Initialize test database
        self.init_test_db()
        # Insert test agent
        self.insert_test_agent()

    def tearDown(self):
        # Restore original DB_PATH
        import relay_ping_secure
        relay_ping_secure.DB_PATH = self.original_db_path

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

    def insert_test_agent(self):
        """Insert a test agent with valid public key"""
        # Mock Ed25519 public key (base64 encoded)
        test_public_key = base64.b64encode(b'x' * 32).decode('ascii')  # 32 bytes for Ed25519

        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute(
                "INSERT INTO agents (agent_id, public_key, relay_token, last_ping, status) VALUES (?, ?, ?, ?, ?)",
                ('test_agent_123', test_public_key, 'test_token', int(time.time()), 'active')
            )
            conn.commit()

    def test_relay_ping_missing_signature_rejected(self):
        """Test that ping without signature is rejected"""
        payload = {
            'agent_id': 'test_agent_123',
            'timestamp': int(time.time())
        }

        response = self.client.post('/relay/ping',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_relay_ping_invalid_signature_rejected(self):
        """Test that ping with invalid signature is rejected"""
        payload = {
            'agent_id': 'test_agent_123',
            'timestamp': int(time.time()),
            'signature': 'invalid_signature_hex'
        }

        response = self.client.post('/relay/ping',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('relay_ping_secure.verify_ed25519_signature')
    def test_relay_ping_valid_signature_accepted(self, mock_verify):
        """Test that ping with valid signature is accepted"""
        # Mock signature verification to return True
        mock_verify.return_value = True

        payload = {
            'agent_id': 'test_agent_123',
            'timestamp': int(time.time()),
            'signature': 'deadbeefcafebabe' * 8  # 64 hex chars
        }

        response = self.client.post('/relay/ping',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['agent_id'], 'test_agent_123')

    def test_relay_ping_unknown_agent_rejected(self):
        """Test that ping from unknown agent is rejected"""
        payload = {
            'agent_id': 'unknown_agent',
            'timestamp': int(time.time()),
            'signature': 'deadbeefcafebabe' * 8
        }

        response = self.client.post('/relay/ping',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertIn('error', data)


if __name__ == '__main__':
    unittest.main()
