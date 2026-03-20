// SPDX-License-Identifier: MIT
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

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertIn('signature', response_data['error'].lower())

    def test_relay_ping_invalid_signature_rejected(self):
        """Test that ping with invalid signature is rejected"""
        payload = {
            'agent_id': 'test_agent_456',
            'timestamp': int(time.time()),
            'signature': 'invalid_signature_data'
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)

    def test_relay_ping_valid_signature_accepted_new_agent(self):
        """Test that ping with valid signature is accepted for new agent"""
        # Generate keypair for test
        private_key, public_key = generate_keypair()
        agent_id = f"agent_{public_key[:16]}"

        timestamp = int(time.time())
        message = f"{agent_id}:{timestamp}"
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'signature': signature,
            'public_key': public_key
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'registered')

        # Verify agent was added to database
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute('SELECT * FROM atlas_agents WHERE agent_id = ?', (agent_id,))
            agent = cursor.fetchone()
            self.assertIsNotNone(agent)

    def test_relay_ping_existing_agent_with_relay_token(self):
        """Test heartbeat update for existing agent with valid relay token"""
        # Generate keypair and register agent
        private_key, public_key = generate_keypair()
        agent_id = f"agent_{public_key[:16]}"
        relay_token = f"relay_token_{agent_id}"

        # Insert existing agent
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute('''
                INSERT INTO atlas_agents (agent_id, public_key, relay_token, last_seen)
                VALUES (?, ?, ?, ?)
            ''', (agent_id, public_key, relay_token, int(time.time()) - 300))
            conn.commit()

        timestamp = int(time.time())
        message = f"{agent_id}:{timestamp}"
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'signature': signature,
            'relay_token': relay_token
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'heartbeat')

    def test_relay_ping_existing_agent_wrong_relay_token(self):
        """Test that existing agent with wrong relay token is rejected"""
        private_key, public_key = generate_keypair()
        agent_id = f"agent_{public_key[:16]}"
        correct_token = f"relay_token_{agent_id}"
        wrong_token = "wrong_token_123"

        # Insert existing agent
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute('''
                INSERT INTO atlas_agents (agent_id, public_key, relay_token, last_seen)
                VALUES (?, ?, ?, ?)
            ''', (agent_id, public_key, correct_token, int(time.time()) - 300))
            conn.commit()

        timestamp = int(time.time())
        message = f"{agent_id}:{timestamp}"
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'signature': signature,
            'relay_token': wrong_token
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertIn('token', response_data['error'].lower())

    def test_relay_ping_existing_agent_missing_relay_token(self):
        """Test that existing agent without relay token is rejected"""
        private_key, public_key = generate_keypair()
        agent_id = f"agent_{public_key[:16]}"
        relay_token = f"relay_token_{agent_id}"

        # Insert existing agent
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute('''
                INSERT INTO atlas_agents (agent_id, public_key, relay_token, last_seen)
                VALUES (?, ?, ?, ?)
            ''', (agent_id, public_key, relay_token, int(time.time()) - 300))
            conn.commit()

        timestamp = int(time.time())
        message = f"{agent_id}:{timestamp}"
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'signature': signature
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)

    def test_relay_ping_timestamp_validation(self):
        """Test that old timestamps are rejected"""
        private_key, public_key = generate_keypair()
        agent_id = f"agent_{public_key[:16]}"

        # Use timestamp from 10 minutes ago
        old_timestamp = int(time.time()) - 600
        message = f"{agent_id}:{old_timestamp}"
        signature = sign_message(private_key, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': old_timestamp,
            'signature': signature,
            'public_key': public_key
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertIn('timestamp', response_data['error'].lower())

    def test_relay_ping_malformed_request(self):
        """Test that malformed requests are handled gracefully"""
        # Missing required fields
        payload = {'agent_id': 'test_agent'}

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 400)

        # Invalid JSON
        response = self.client.post('/relay/ping',
                                  data='invalid json',
                                  content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_signature_verification_with_different_keypairs(self):
        """Test that signature from wrong keypair is rejected"""
        # Generate two different keypairs
        private_key1, public_key1 = generate_keypair()
        private_key2, public_key2 = generate_keypair()

        agent_id = f"agent_{public_key1[:16]}"
        timestamp = int(time.time())
        message = f"{agent_id}:{timestamp}"

        # Sign with private_key2 but claim public_key1
        signature = sign_message(private_key2, message)

        payload = {
            'agent_id': agent_id,
            'timestamp': timestamp,
            'signature': signature,
            'public_key': public_key1
        }

        response = self.client.post('/relay/ping',
                                  data=json.dumps(payload),
                                  content_type='application/json')

        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)


if __name__ == '__main__':
    unittest.main()
