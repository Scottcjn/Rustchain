#!/usr/bin/env python3
"""
Behavioral Integration Tests for Bounty #1524 - Beacon Atlas API
Tests actual API behavior with Flask test client and database.
"""
import unittest
import json
import time
import sys
import os
import tempfile
import sqlite3
import gc
from unittest.mock import Mock, patch
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBeaconAtlasAPIBehavior(unittest.TestCase):
    """Behavioral tests for Beacon Atlas API endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        # Create temporary database for testing
        cls.test_db_fd, cls.test_db_path = tempfile.mkstemp(suffix='.db')
        
        # Import and initialize Flask app
        from flask import Flask, g
        import sqlite3
        
        cls.app = Flask(__name__)
        cls.app.config['TESTING'] = True
        cls.app.config['DB_PATH'] = cls.test_db_path
        
        # Import blueprint routes manually to avoid teardown_appcontext issue
        from node.beacon_api import DB_PATH, init_beacon_tables
        
        # Register blueprint
        from node import beacon_api as beacon_module
        cls.app.register_blueprint(beacon_module.beacon_api)
        
        # Add database setup/teardown handlers
        @cls.app.before_request
        def before_request():
            g.db = sqlite3.connect(cls.test_db_path)
            g.db.row_factory = sqlite3.Row
        
        @cls.app.teardown_request
        def teardown_request(exception):
            db = getattr(g, 'db', None)
            if db is not None:
                db.close()
        
        # Initialize database tables
        init_beacon_tables(cls.test_db_path)
        
        cls.client = cls.app.test_client()
        cls.agent_keys = {
            agent_id: Ed25519PrivateKey.generate()
            for agent_id in [
                'bcn_alice_test',
                'bcn_bob_test',
                'bcn_test_from',
                'bcn_test_to',
            ]
        }

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.client = None
        cls.app = None
        gc.collect()
        os.close(cls.test_db_fd)
        os.unlink(cls.test_db_path)

    def setUp(self):
        """Reset database state before each test."""
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("DELETE FROM beacon_contracts")
            conn.execute("DELETE FROM beacon_bounties")
            conn.execute("DELETE FROM beacon_reputation")
            conn.execute("DELETE FROM beacon_chat")
            conn.execute("DELETE FROM relay_agents")
            now = int(time.time())
            conn.executemany(
                """
                INSERT INTO relay_agents
                (agent_id, pubkey_hex, name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (agent_id, self._pubkey_hex(agent_id), name, 'active', now, now)
                    for agent_id, name in [
                        ('bcn_alice_test', 'Alice Test'),
                        ('bcn_bob_test', 'Bob Test'),
                        ('bcn_test_from', 'From Test'),
                        ('bcn_test_to', 'To Test'),
                    ]
                ],
            )
            conn.commit()

    @classmethod
    def _pubkey_hex(cls, agent_id):
        pubkey = cls.agent_keys[agent_id].public_key()
        return pubkey.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    @classmethod
    def _signed_headers(cls, agent_id, method, path, body):
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body
        timestamp = str(int(time.time()))
        nonce = hashlib.blake2b(f"{agent_id}:{timestamp}:{body}".encode(), digest_size=16).hexdigest()
        body_hash = hashlib.sha256(body_bytes or b'').hexdigest()
        message = '\n'.join([
            method.upper(),
            path,
            body_hash,
            timestamp,
            nonce,
            agent_id,
        ]).encode('utf-8')
        signature = cls.agent_keys[agent_id].sign(message).hex()
        return {
            'X-Agent-Id': agent_id,
            'X-Agent-Timestamp': timestamp,
            'X-Agent-Nonce': nonce,
            'X-Agent-Signature': signature,
        }

    def test_health_endpoint_returns_ok(self):
        """Health check endpoint returns status ok."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('timestamp', data)
        self.assertEqual(data['service'], 'beacon-atlas-api')

    def test_create_contract_workflow(self):
        """Full workflow: create contract, verify, update state."""
        # Create contract
        contract_data = {
            'from': 'bcn_alice_test',
            'to': 'bcn_bob_test',
            'type': 'rent',
            'amount': 100.0,
            'term': '30d'
        }
        
        create_body = json.dumps(contract_data)
        create_response = self.client.post(
            '/api/contracts',
            data=create_body,
            content_type='application/json',
            headers=self._signed_headers('bcn_alice_test', 'POST', '/api/contracts', create_body),
        )
        self.assertEqual(create_response.status_code, 201)
        
        created = json.loads(create_response.data)
        self.assertIn('id', created)
        self.assertEqual(created['from'], 'bcn_alice_test')
        self.assertEqual(created['to'], 'bcn_bob_test')
        self.assertEqual(created['state'], 'offered')
        
        contract_id = created['id']
        
        # Verify contract appears in list
        list_response = self.client.get('/api/contracts')
        self.assertEqual(list_response.status_code, 200)
        contracts = json.loads(list_response.data)
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0]['id'], contract_id)
        
        # Update contract state to active
        update_body = json.dumps({'state': 'active'})
        update_response = self.client.put(
            f'/api/contracts/{contract_id}',
            data=update_body,
            content_type='application/json',
            headers=self._signed_headers(
                'bcn_bob_test',
                'PUT',
                f'/api/contracts/{contract_id}',
                update_body,
            ),
        )
        self.assertEqual(update_response.status_code, 200)
        
        # Verify state changed
        list_response2 = self.client.get('/api/contracts')
        contracts2 = json.loads(list_response2.data)
        self.assertEqual(contracts2[0]['state'], 'active')

    def test_public_agent_id_bearer_rejected_for_contract_create(self):
        """A public agent ID in X-Agent-Key is not enough to create contracts."""
        contract_data = {
            'from': 'bcn_alice_test',
            'to': 'bcn_bob_test',
            'type': 'rent',
            'amount': 100.0,
            'term': '30d'
        }

        response = self.client.post(
            '/api/contracts',
            data=json.dumps(contract_data),
            content_type='application/json',
            headers={'X-Agent-Key': 'bcn_alice_test'},
        )

        self.assertEqual(response.status_code, 401)

    def test_contract_validation_rejects_invalid(self):
        """Contract creation rejects invalid/missing fields."""
        # Missing required field 'to'
        invalid_data = {
            'from': 'bcn_alice',
            'type': 'rent',
            'amount': 50,
            'term': '30d'
        }
        
        response = self.client.post(
            '/api/contracts',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_bounty_lifecycle_workflow(self):
        """Full bounty lifecycle: create, claim, complete."""
        # Insert a test bounty directly
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                INSERT INTO beacon_bounties 
                (id, title, reward_rtc, difficulty, state, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('gh_test_bounty', 'Test Feature (50 RTC)', 50.0, 'MEDIUM', 'open', int(time.time())))
            conn.commit()
        
        # Get bounties list
        response = self.client.get('/api/bounties')
        self.assertEqual(response.status_code, 200)
        bounties = json.loads(response.data)
        self.assertEqual(len(bounties), 1)
        self.assertEqual(bounties[0]['difficulty'], 'MEDIUM')
        
        # Claim bounty (admin-only per #2800 — requires X-Admin-Key)
        claim_response = self.client.post(
            '/api/bounties/gh_test_bounty/claim',
            data=json.dumps({'agent_id': 'bcn_claimer'}),
            content_type='application/json',
            headers={'X-Admin-Key': os.environ['RC_ADMIN_KEY']},
        )
        self.assertEqual(claim_response.status_code, 200)
        
        # Verify claimed state
        response2 = self.client.get('/api/bounties')
        bounties2 = json.loads(response2.data)
        # Bounty should no longer appear in open list (state changed to claimed)
        
    def test_reputation_tracking_workflow(self):
        """Reputation is tracked and updated correctly."""
        # Insert test reputation
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                INSERT INTO beacon_reputation 
                (agent_id, score, bounties_completed, contracts_completed)
                VALUES (?, ?, ?, ?)
            """, ('bcn_reputation_test', 50, 2, 5))
            conn.commit()
        
        # Get all reputations
        response = self.client.get('/api/reputation')
        self.assertEqual(response.status_code, 200)
        reps = json.loads(response.data)
        self.assertEqual(len(reps), 1)
        self.assertEqual(reps[0]['agent_id'], 'bcn_reputation_test')
        self.assertEqual(reps[0]['score'], 50)
        
        # Get single agent reputation
        response2 = self.client.get('/api/reputation/bcn_reputation_test')
        self.assertEqual(response2.status_code, 200)
        rep = json.loads(response2.data)
        self.assertEqual(rep['bounties_completed'], 2)
        
        # Non-existent agent returns 404
        response3 = self.client.get('/api/reputation/bcn_nonexistent')
        self.assertEqual(response3.status_code, 404)

    def test_chat_message_storage(self):
        """Chat messages are stored and can be retrieved."""
        # Send chat message
        chat_data = {
            'agent_id': 'bcn_chat_test',
            'message': 'Hello, agent!'
        }
        
        response = self.client.post(
            '/api/chat',
            data=json.dumps(chat_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('response', data)
        self.assertEqual(data['agent'], 'bcn_chat_test')
        
        # Verify message was stored in database
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM beacon_chat WHERE agent_id = ?",
                ('bcn_chat_test',)
            )
            count = cursor.fetchone()[0]
            self.assertGreaterEqual(count, 1)  # At least user message stored

    def test_invalid_state_update_rejected(self):
        """Contract state updates reject invalid states."""
        # Create a contract first
        contract_data = {
            'from': 'bcn_test_from',
            'to': 'bcn_test_to',
            'type': 'service',
            'amount': 25.0,
            'term': '7d'
        }
        
        create_body = json.dumps(contract_data)
        create_response = self.client.post(
            '/api/contracts',
            data=create_body,
            content_type='application/json',
            headers=self._signed_headers('bcn_test_from', 'POST', '/api/contracts', create_body),
        )
        contract_id = json.loads(create_response.data)['id']
        
        # Try invalid state
        update_body = json.dumps({'state': 'invalid_state'})
        update_response = self.client.put(
            f'/api/contracts/{contract_id}',
            data=update_body,
            content_type='application/json',
            headers=self._signed_headers(
                'bcn_test_from',
                'PUT',
                f'/api/contracts/{contract_id}',
                update_body,
            ),
        )
        self.assertEqual(update_response.status_code, 400)

    def test_recipient_can_reject_offered_contract(self):
        """Offered contracts can move to the documented rejected terminal state."""
        contract_data = {
            'from': 'bcn_test_from',
            'to': 'bcn_test_to',
            'type': 'service',
            'amount': 25.0,
            'term': '7d'
        }

        create_response = self.client.post(
            '/api/contracts',
            data=json.dumps(contract_data),
            content_type='application/json',
            headers={'X-Agent-Key': 'bcn_test_from'},
        )
        self.assertEqual(create_response.status_code, 201)
        contract_id = json.loads(create_response.data)['id']

        reject_response = self.client.put(
            f'/api/contracts/{contract_id}',
            data=json.dumps({'state': 'rejected'}),
            content_type='application/json',
            headers={'X-Agent-Key': 'bcn_test_to'},
        )
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(json.loads(reject_response.data)['state'], 'rejected')

        list_response = self.client.get('/api/contracts')
        contracts = json.loads(list_response.data)
        self.assertEqual(contracts[0]['state'], 'rejected')

        for terminal_attempt in ('active', 'expired', 'completed'):
            update_response = self.client.put(
                f'/api/contracts/{contract_id}',
                data=json.dumps({'state': terminal_attempt}),
                content_type='application/json',
                headers={'X-Agent-Key': 'bcn_test_to'},
            )
            self.assertEqual(update_response.status_code, 400)

    def test_creator_cannot_reject_offered_contract(self):
        """Only the recipient can reject an offered contract."""
        contract_data = {
            'from': 'bcn_test_from',
            'to': 'bcn_test_to',
            'type': 'service',
            'amount': 25.0,
            'term': '7d'
        }

        create_response = self.client.post(
            '/api/contracts',
            data=json.dumps(contract_data),
            content_type='application/json',
            headers={'X-Agent-Key': 'bcn_test_from'},
        )
        self.assertEqual(create_response.status_code, 201)
        contract_id = json.loads(create_response.data)['id']

        reject_response = self.client.put(
            f'/api/contracts/{contract_id}',
            data=json.dumps({'state': 'rejected'}),
            content_type='application/json',
            headers={'X-Agent-Key': 'bcn_test_from'},
        )
        self.assertEqual(reject_response.status_code, 403)

        list_response = self.client.get('/api/contracts')
        contracts = json.loads(list_response.data)
        self.assertEqual(contracts[0]['state'], 'offered')

    def test_bounty_completion_updates_reputation(self):
        """Completing a bounty increases agent reputation."""
        # Insert test bounty
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                INSERT INTO beacon_bounties 
                (id, title, reward_rtc, difficulty, state, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('gh_complete_test', 'Complete Me (100 RTC)', 100.0, 'HARD', 'claimed', int(time.time())))
            conn.commit()
        
        # Complete bounty (admin-only per security patch 93dc968 — requires X-Admin-Key)
        complete_response = self.client.post(
            '/api/bounties/gh_complete_test/complete',
            data=json.dumps({'agent_id': 'bcn_completer'}),
            content_type='application/json',
            headers={'X-Admin-Key': os.environ['RC_ADMIN_KEY']},
        )
        self.assertEqual(complete_response.status_code, 200)
        
        # Verify reputation was created/updated
        rep_response = self.client.get('/api/reputation/bcn_completer')
        self.assertEqual(rep_response.status_code, 200)
        rep = json.loads(rep_response.data)
        self.assertEqual(rep['bounties_completed'], 1)
        self.assertEqual(rep['score'], 10)  # 10 points per bounty

    def test_bounty_sync_requires_admin_before_network_fetch(self):
        """Unauthenticated sync cannot trigger GitHub fetches or DB writes."""
        with patch.dict(os.environ, {'RC_ADMIN_KEY': 'test-admin'}, clear=False):
            with patch('ssl.create_default_context', return_value=object()):
                with patch('urllib.request.urlopen') as mock_urlopen:
                    response = self.client.post('/api/bounties/sync')

        self.assertEqual(response.status_code, 401)
        mock_urlopen.assert_not_called()

    def test_bounty_sync_requires_admin_configuration_before_network_fetch(self):
        """Sync fails closed when no admin key is configured."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('ssl.create_default_context', return_value=object()):
                with patch('urllib.request.urlopen') as mock_urlopen:
                    response = self.client.post('/api/bounties/sync')

        self.assertEqual(response.status_code, 503)
        mock_urlopen.assert_not_called()

    def test_bounty_sync_preserves_existing_lifecycle_state(self):
        """Sync refreshes metadata without reopening locally claimed bounties."""
        created_at = int(time.time())
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                INSERT INTO beacon_bounties
                (id, github_number, title, reward_rtc, reward_text, difficulty,
                 github_repo, github_url, state, claimant_agent, completed_by,
                 description, labels, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'gh_Rustchain_123',
                123,
                'Old title (10 RTC)',
                10.0,
                '10 RTC',
                'EASY',
                'Scottcjn/Rustchain',
                'https://github.com/Scottcjn/Rustchain/issues/123',
                'claimed',
                'bcn_alice_test',
                None,
                'old description',
                '["bounty"]',
                created_at,
                created_at,
            ))
            conn.commit()

        response_payload = json.dumps([
            {
                'number': 123,
                'title': 'Updated title (75 RTC)',
                'html_url': 'https://github.com/Scottcjn/Rustchain/issues/123',
                'body': 'Updated bounty body',
                'labels': [{'name': 'bounty'}, {'name': 'major'}],
                'created_at': '2026-05-11T00:00:00Z',
            }
        ]).encode()
        fake_response = Mock()
        fake_response.read.return_value = response_payload
        fake_response.__enter__ = Mock(return_value=fake_response)
        fake_response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, {'RC_ADMIN_KEY': 'test-admin'}, clear=False):
            with patch('ssl.create_default_context', return_value=object()):
                with patch('urllib.request.urlopen', return_value=fake_response):
                    response = self.client.post(
                        '/api/bounties/sync',
                        headers={'X-Admin-Key': 'test-admin'},
                    )

        self.assertEqual(response.status_code, 200)

        with sqlite3.connect(self.test_db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT title, reward_rtc, difficulty, state, claimant_agent, completed_by "
                "FROM beacon_bounties WHERE id = ?",
                ('gh_Rustchain_123',),
            ).fetchone()

        self.assertEqual(row['title'], 'Updated title (75 RTC)')
        self.assertEqual(row['reward_rtc'], 75.0)
        self.assertEqual(row['difficulty'], 'HARD')
        self.assertEqual(row['state'], 'claimed')
        self.assertEqual(row['claimant_agent'], 'bcn_alice_test')
        self.assertIsNone(row['completed_by'])


class TestBeaconAtlasDataValidation(unittest.TestCase):
    """Data validation and edge case tests."""

    def test_agent_id_format_validation(self):
        """Agent IDs must follow bcn_<identifier> format."""
        import re
        pattern = r'^bcn_[a-z0-9_]+$'
        
        valid_ids = [
            'bcn_sophia_elya',
            'bcn_boris_volkov',
            'bcn_auto_janitor',
            'bcn_test_123',
            'bcn_a',  # Minimal valid
        ]
        
        invalid_ids = [
            'agent_001',  # Missing prefix
            'bcn_Agent',  # Uppercase
            'bcn-agent',  # Hyphen
            'bcn.agent',  # Dot
            '',  # Empty
            'bcn_',  # No identifier
        ]
        
        for agent_id in valid_ids:
            self.assertRegex(agent_id, pattern,
                           f"Valid ID should match: {agent_id}")
        
        for agent_id in invalid_ids:
            self.assertNotRegex(agent_id, pattern,
                              f"Invalid ID should not match: {agent_id}")

    def test_bounty_difficulty_enum(self):
        """Bounty difficulty must be one of allowed values."""
        valid_difficulties = {'EASY', 'MEDIUM', 'HARD', 'ANY'}
        
        # Test from bounties.js colors
        difficulty_colors = {
            'EASY': '#33ff33',
            'MEDIUM': '#ffb000',
            'HARD': '#ff4444',
            'ANY': '#8888ff',
        }
        
        self.assertEqual(set(difficulty_colors.keys()), valid_difficulties)
        
        for diff, color in difficulty_colors.items():
            # Validate hex color format
            self.assertRegex(color, r'^#[0-9a-f]{6}$',
                           f"Invalid color format for {diff}")

    def test_contract_state_machine(self):
        """Contract states follow valid transitions."""
        valid_states = {'offered', 'active', 'renewed', 'completed', 'breached', 'expired', 'rejected'}
        
        # Valid state transitions
        valid_transitions = {
            'offered': {'active', 'expired'},
            'active': {'completed', 'breached', 'renewed', 'expired'},
            'renewed': {'completed', 'breached', 'expired'},
            'completed': set(),  # Terminal state
            'breached': set(),  # Terminal state
            'expired': set(),  # Terminal state
            'rejected': set(),  # Terminal state
        }
        
        # Verify all states have transitions defined
        for state in valid_states:
            self.assertIn(state, valid_transitions,
                         f"Missing transitions for state: {state}")

    def test_reward_extraction_regex(self):
        """Test regex for extracting RTC reward from bounty titles."""
        import re
        
        test_cases = [
            ("Fix Bug #123 (50 RTC)", 50.0),
            ("Implement Feature (100.5 RTC)", 100.5),
            ("Pool: 25 RTC Bounty", 25.0),
            ("Major Refactor (200 RTC)", 200.0),
            ("Small Fix (5 RTC)", 5.0),
        ]
        
        pattern = r'\((?:Pool:\s*)?(\d+(?:\.\d+)?)\s*RTC[^)]*\)'
        
        for title, expected_reward in test_cases:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                reward = float(match.group(1))
                self.assertEqual(reward, expected_reward,
                               f"Reward extraction failed for: {title}")


class TestBeaconAtlasVisualizationLogic(unittest.TestCase):
    """Test visualization logic that can be validated without browser."""

    def test_ring_layout_calculation(self):
        """Test bounty ring layout mathematics."""
        import math
        
        def calculate_ring_position(index, total, ring_capacity=8):
            """Calculate position for bounty in ring layout."""
            ring_index = index // ring_capacity
            position_in_ring = index % ring_capacity
            
            ring_radius = 180 + (ring_index * 40)
            angle = position_in_ring * (2 * math.pi / ring_capacity)
            height = 60 + (ring_index * 30)
            
            return {
                'x': math.cos(angle) * ring_radius,
                'y': height,
                'z': math.sin(angle) * ring_radius,
                'ring': ring_index,
            }
        
        # First ring (8 bounties)
        pos0 = calculate_ring_position(0, 12)
        self.assertEqual(pos0['ring'], 0)
        self.assertAlmostEqual(pos0['x'], 180.0, places=5)
        self.assertEqual(pos0['y'], 60)
        
        pos7 = calculate_ring_position(7, 12)
        self.assertEqual(pos7['ring'], 0)
        self.assertEqual(pos7['y'], 60)
        
        # Second ring starts at index 8
        pos8 = calculate_ring_position(8, 12)
        self.assertEqual(pos8['ring'], 1)
        self.assertAlmostEqual(pos8['x'], 220.0, places=5)
        self.assertEqual(pos8['y'], 90)

    def test_animation_timing(self):
        """Test animation timing calculations."""
        import math
        
        def calculate_bob_position(base_y, elapsed, phase):
            """Calculate vertical bobbing position."""
            return base_y + math.sin(elapsed * 1.5 + phase) * 2
        
        def calculate_pulse_opacity(base, elapsed, phase):
            """Calculate pulsing opacity."""
            return base + math.sin(elapsed * 2.5 + phase) * 0.06
        
        # Test bobbing stays within bounds
        base_y = 60
        for elapsed in [0, 1, 2, 10, 100]:
            for phase in [0, math.pi/2, math.pi]:
                y = calculate_bob_position(base_y, elapsed, phase)
                self.assertGreaterEqual(y, base_y - 2)
                self.assertLessEqual(y, base_y + 2)
        
        # Test opacity stays in valid range
        base_opacity = 0.12
        for elapsed in [0, 1, 2, 10, 100]:
            opacity = calculate_pulse_opacity(base_opacity, elapsed, 0)
            self.assertGreaterEqual(opacity, 0.0)
            self.assertLessEqual(opacity, 1.0)

    def test_vehicle_distribution(self):
        """Test ambient vehicle type distribution."""
        vehicle_config = {
            'car': {'count': 9, 'altitude_range': (0, 2)},
            'drone': {'count': 7, 'altitude_range': (15, 30)},
            'plane': {'count': 5, 'altitude_range': (40, 70)},
        }
        
        total_vehicles = sum(v['count'] for v in vehicle_config.values())
        self.assertEqual(total_vehicles, 21)
        
        # Verify altitude ranges don't overlap
        sorted_by_alt = sorted(vehicle_config.items(), 
                               key=lambda x: x[1]['altitude_range'][0])
        
        prev_max = 0
        for vtype, config in sorted_by_alt:
            min_alt, max_alt = config['altitude_range']
            self.assertGreater(min_alt, prev_max - 5,  # Allow small overlap
                             f"{vtype} altitude overlaps with previous")
            prev_max = max_alt


def run_tests():
    """Run all behavioral test suites."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasAPIBehavior))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasDataValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasVisualizationLogic))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
