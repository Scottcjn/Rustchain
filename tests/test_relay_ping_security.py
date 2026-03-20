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

# Import from the relay_ping_secure module
from relay_ping_secure import app, get_agent_by_id
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

            # Insert test agent
            conn.execute('''
                INSERT INTO agents (agent_id, public_key, relay_token, last_ping, status)
                VALUES (?, ?, ?, ?, ?)
            ''', ('test_agent_123', 'test_public_key', 'test_token', int(time.time()), 'active'))
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

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Missing signature')

    def test_relay_ping_missing_agent_id_rejected(self):
        """Test that ping without agent_id is rejected"""
        payload = {
            'timestamp': int(time.time()),
            'signature': 'test_signature'
        }

        response = self.client.post('/relay/ping',
                                   data=json.dumps(payload),
                                   content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Missing agent_id')

    def test_relay_ping_unknown_agent_rejected(self):
        """Test that ping from unknown agent is rejected"""
        payload = {
            'agent_id': 'unknown_agent',
            'timestamp': int(time.time()),
            'signature': 'test_signature'
        }

        response = self.client.post('/relay/ping',
                                   data=json.dumps(payload),
                                   content_type='application/json')

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Agent not found')

    def test_relay_ping_valid_request_accepted(self):
        """Test that valid ping request is accepted"""
        payload = {
            'agent_id': 'test_agent_123',
            'timestamp': int(time.time()),
            'signature': 'valid_signature'
        }

        with patch('relay_ping_secure.verify_ping_signature', return_value=True):
            response = self.client.post('/relay/ping',
                                       data=json.dumps(payload),
                                       content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')

    def test_signature_verification_function(self):
        """Test signature verification utility function"""
        test_data = {'test': 'data'}
        test_signature = 'test_sig'
        test_key = 'test_key'

        # Test with mock
        result = verify_ping_signature(test_data, test_signature, test_key)
        self.assertIsInstance(result, bool)

    def test_get_agent_by_id_function(self):
        """Test get_agent_by_id utility function"""
        agent = get_agent_by_id('test_agent_123')
        self.assertIsNotNone(agent)
        self.assertEqual(agent['agent_id'], 'test_agent_123')

        # Test non-existent agent
        agent = get_agent_by_id('non_existent')
        self.assertIsNone(agent)


if __name__ == '__main__':
    unittest.main()
