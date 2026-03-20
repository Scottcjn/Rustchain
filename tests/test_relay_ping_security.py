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

from beacon_chat import app, get_db_connection, DB_PATH
from identity import generate_keypair, sign_message, verify_signature


class TestRelayPingSecurityTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Create temp database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        # Override DB_PATH for tests
        import beacon_chat
        self.original_db_path = beacon_chat.DB_PATH
        beacon_chat.DB_PATH = self.temp_db.name

        # Initialize test database
        self.init_test_db()

    def tearDown(self):
        # Restore original DB_PATH
        import beacon_chat
        beacon_chat.DB_PATH = self.original_db_path

        # Clean up temp database
        os.unlink(self.temp_db.name)

    def init_test_db(self):
        """Initialize test database with required tables"""
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS atlas_agents (
                    agent_id TEXT PRIMARY KEY,
                    last_seen INTEGER,
                    relay_token TEXT,
                    public_key TEXT,
                    endpoint TEXT,
                    status TEXT DEFAULT 'active',
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')
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
        self.assertIn('Missing required fields', data.get('error', ''))

    def test_relay_ping_invalid_signature_rejected(self):
        """Test that ping with invalid signature is rejected"""
        # Generate test keypair
        private_key, public_key = generate_keypair()
        agent_id = 'test_agent_456'

        # Register agent in database
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute(
                "INSERT INTO atlas_agents (agent_id, public_key) VALUES (?, ?)",
                (agent_id, public_key)
            )
            conn.commit()

        payload = {
            'agent_id': agent_id,
            'timestamp': int(time.time()),
            'signature': 'invalid_signature_hex'
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Invalid signature format', data.get('error', ''))

    def test_relay_ping_valid_signature_accepted(self):
        """Test that ping with valid signature is accepted"""
        # Generate test keypair
        private_key, public_key = generate_keypair()
        agent_id = 'test_agent_789'
        timestamp = int(time.time())

        # Register agent in database
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute(
                "INSERT INTO atlas_agents (agent_id, public_key) VALUES (?, ?)",
                (agent_id, public_key)
            )
            conn.commit()

        # Create message and sign it
        message_data = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'action': 'ping'
        }
        message = json.dumps(message_data, sort_keys=True).encode('utf-8')
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'signature': signature.hex()
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get('status'), 'success')

    def test_relay_ping_expired_timestamp_rejected(self):
        """Test that ping with expired timestamp is rejected"""
        # Generate test keypair
        private_key, public_key = generate_keypair()
        agent_id = 'test_agent_old'
        old_timestamp = int(time.time()) - 600  # 10 minutes ago

        # Register agent in database
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute(
                "INSERT INTO atlas_agents (agent_id, public_key) VALUES (?, ?)",
                (agent_id, public_key)
            )
            conn.commit()

        # Create message and sign it
        message_data = {
            'agent_id': agent_id,
            'timestamp': old_timestamp,
            'action': 'ping'
        }
        message = json.dumps(message_data, sort_keys=True).encode('utf-8')
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': old_timestamp,
            'signature': signature.hex()
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Timestamp too old', data.get('error', ''))

    def test_relay_ping_unregistered_agent_rejected(self):
        """Test that ping from unregistered agent is rejected"""
        payload = {
            'agent_id': 'unregistered_agent',
            'timestamp': int(time.time()),
            'signature': 'abc123'
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('Agent not registered', data.get('error', ''))


if __name__ == '__main__':
    unittest.main()
