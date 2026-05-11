#!/usr/bin/env python3
"""
Test suite for Issue #2127 - Beacon Join Routing
Tests POST /beacon/join and GET /beacon/atlas endpoints.
"""
import unittest
import json
import time
import sys
import os
import gc
import tempfile
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBeaconJoinRouting(unittest.TestCase):
    """Behavioral tests for beacon join routing endpoints."""

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

        # Import beacon_api module
        from node.beacon_api import init_beacon_tables

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
            conn.execute("DELETE FROM relay_agents")
            conn.commit()

    # ============================================================
    # POST /beacon/join Tests
    # ============================================================

    def test_join_register_new_agent(self):
        """POST /beacon/join registers a new agent successfully."""
        payload = {
            'agent_id': 'bcn_test_agent_001',
            'pubkey_hex': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'name': 'Test Agent',
        }

        response = self.client.post(
            '/beacon/join',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['agent_id'], 'bcn_test_agent_001')
        self.assertEqual(data['status'], 'active')
        self.assertIn('timestamp', data)

    def test_join_upsert_duplicate_agent(self):
        """POST /beacon/join upserts mutable fields for duplicate agent_id.

        Per security patch 03bf96a, pubkey_hex is immutable after first
        registration (prevents identity takeover). Re-sending the same
        pubkey_hex with a changed name updates the mutable field only.
        """
        pubkey = '0xaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccddddaaaabbbbccccdddd'
        payload1 = {
            'agent_id': 'bcn_upsert_test',
            'pubkey_hex': pubkey,
            'name': 'Original Name',
        }

        # First registration
        response1 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload1),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)

        # Update mutable field only (name). pubkey_hex must stay the same.
        payload2 = {
            'agent_id': 'bcn_upsert_test',
            'pubkey_hex': pubkey,
            'name': 'Updated Name',
        }

        response2 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload2),
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)

        # Verify update occurred (not a duplicate error)
        data2 = json.loads(response2.data)
        self.assertTrue(data2['ok'])
        self.assertEqual(data2['name'], 'Updated Name')

        # Verify only one record exists
        with sqlite3.connect(self.test_db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM relay_agents WHERE agent_id = ?",
                ('bcn_upsert_test',)
            ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_join_pubkey_takeover_rejected(self):
        """POST /beacon/join rejects pubkey_hex change for existing agent (403).

        Security invariant from patch 03bf96a: an attacker sending a join
        request with a victim's agent_id and their own public key must be
        rejected, not silently overwrite the victim's identity.
        """
        payload1 = {
            'agent_id': 'bcn_takeover_target',
            'pubkey_hex': '0x1111' + '00' * 30,
            'name': 'Victim',
        }
        r1 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload1),
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)

        # Attacker attempts takeover with different pubkey_hex
        payload2 = {
            'agent_id': 'bcn_takeover_target',
            'pubkey_hex': '0x2222' + '00' * 30,
            'name': 'Attacker',
        }
        r2 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload2),
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 403)

        # Verify pubkey was NOT overwritten
        with sqlite3.connect(self.test_db_path) as conn:
            row = conn.execute(
                "SELECT pubkey_hex, name FROM relay_agents WHERE agent_id = ?",
                ('bcn_takeover_target',)
            ).fetchone()
            self.assertEqual(row[0], payload1['pubkey_hex'])
            self.assertEqual(row[1], 'Victim')

    def test_join_invalid_pubkey_hex_returns_400(self):
        """POST /beacon/join returns 400 for invalid pubkey_hex."""
        invalid_cases = [
            {'agent_id': 'bcn_test', 'pubkey_hex': 'not-hex-at-all!'},
            {'agent_id': 'bcn_test', 'pubkey_hex': '0xGGGG'},  # Invalid hex chars
            {'agent_id': 'bcn_test', 'pubkey_hex': ''},  # Empty
            {'agent_id': 'bcn_test', 'pubkey_hex': '0x'},  # Just prefix
        ]

        for payload in invalid_cases:
            response = self.client.post(
                '/beacon/join',
                data=json.dumps(payload),
                content_type='application/json'
            )
            self.assertEqual(
                response.status_code, 400,
                f"Expected 400 for invalid pubkey: {payload['pubkey_hex']}"
            )
            data = json.loads(response.data)
            self.assertIn('error', data)

    def test_join_missing_agent_id_returns_400(self):
        """POST /beacon/join returns 400 when agent_id is missing."""
        payload = {
            'pubkey_hex': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        }

        response = self.client.post(
            '/beacon/join',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('agent_id', data['error'])

    def test_join_missing_pubkey_hex_returns_400(self):
        """POST /beacon/join returns 400 when pubkey_hex is missing."""
        payload = {
            'agent_id': 'bcn_test',
        }

        response = self.client.post(
            '/beacon/join',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('pubkey_hex', data['error'])

    def test_join_invalid_json_returns_400(self):
        """POST /beacon/join returns 400 for invalid JSON body."""
        response = self.client.post(
            '/beacon/join',
            data='not valid json',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_join_with_coinbase_address(self):
        """POST /beacon/join accepts valid coinbase_address."""
        payload = {
            'agent_id': 'bcn_wallet_test',
            'pubkey_hex': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'coinbase_address': '0x1234567890123456789012345678901234567890',
        }

        response = self.client.post(
            '/beacon/join',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify coinbase_address was stored
        with sqlite3.connect(self.test_db_path) as conn:
            row = conn.execute(
                "SELECT coinbase_address FROM relay_agents WHERE agent_id = ?",
                ('bcn_wallet_test',)
            ).fetchone()
            self.assertEqual(row[0], '0x1234567890123456789012345678901234567890')

    def test_join_allows_same_coinbase_with_case_and_spacing(self):
        """POST /beacon/join treats the same normalized wallet as unchanged."""
        pubkey = '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        payload1 = {
            'agent_id': 'bcn_wallet_normalized',
            'pubkey_hex': pubkey,
            'name': 'Wallet Owner',
            'coinbase_address': '  0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD  ',
        }
        r1 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload1),
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)

        payload2 = {
            'agent_id': 'bcn_wallet_normalized',
            'pubkey_hex': pubkey,
            'name': 'Renamed Owner',
            'coinbase_address': '0xabcdefabcdefabcdefabcdefabcdefabcdefabcd',
        }
        r2 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload2),
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 200)

        with sqlite3.connect(self.test_db_path) as conn:
            row = conn.execute(
                "SELECT coinbase_address, name FROM relay_agents WHERE agent_id = ?",
                ('bcn_wallet_normalized',),
            ).fetchone()
            self.assertEqual(row[0], '0xabcdefabcdefabcdefabcdefabcdefabcdefabcd')
            self.assertEqual(row[1], 'Renamed Owner')

    def test_join_rejects_coinbase_change_for_existing_agent(self):
        """POST /beacon/join cannot replace an existing agent wallet."""
        pubkey = '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        original_wallet = '0x1111111111111111111111111111111111111111'
        attacker_wallet = '0x2222222222222222222222222222222222222222'
        payload1 = {
            'agent_id': 'bcn_wallet_takeover_target',
            'pubkey_hex': pubkey,
            'name': 'Wallet Owner',
            'coinbase_address': original_wallet,
        }
        r1 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload1),
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)

        payload2 = {
            'agent_id': 'bcn_wallet_takeover_target',
            'pubkey_hex': pubkey,
            'name': 'Renamed Owner',
            'coinbase_address': attacker_wallet,
        }
        r2 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload2),
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 403)
        data = json.loads(r2.data)
        self.assertIn('/api/agents/bcn_wallet_takeover_target/wallet', data['error'])
        self.assertIn('admin key', data['error'])

        with sqlite3.connect(self.test_db_path) as conn:
            row = conn.execute(
                "SELECT coinbase_address, name FROM relay_agents WHERE agent_id = ?",
                ('bcn_wallet_takeover_target',),
            ).fetchone()
            self.assertEqual(row[0], original_wallet)
            self.assertEqual(row[1], 'Wallet Owner')

    def test_join_invalid_coinbase_address_returns_400(self):
        """POST /beacon/join returns 400 for invalid coinbase_address."""
        invalid_cases = [
            {'agent_id': 'bcn_test', 'pubkey_hex': '0x1234', 'coinbase_address': 'not-0x-prefixed'},
            {'agent_id': 'bcn_test', 'pubkey_hex': '0x1234', 'coinbase_address': '0xGGGG'},
            {'agent_id': 'bcn_test', 'pubkey_hex': '0x1234', 'coinbase_address': '0x123'},  # Too short
        ]

        for payload in invalid_cases:
            response = self.client.post(
                '/beacon/join',
                data=json.dumps(payload),
                content_type='application/json'
            )
            self.assertEqual(
                response.status_code, 400,
                f"Expected 400 for invalid coinbase: {payload['coinbase_address']}"
            )

    def test_join_pubkey_without_0x_prefix(self):
        """POST /beacon/join accepts pubkey_hex without 0x prefix."""
        payload = {
            'agent_id': 'bcn_no_prefix',
            'pubkey_hex': 'aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344',
        }

        response = self.client.post(
            '/beacon/join',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

    def test_join_options_returns_cors_headers(self):
        """OPTIONS /beacon/join returns CORS headers."""
        response = self.client.options('/beacon/join')

        self.assertEqual(response.status_code, 200)
        headers = response.headers
        self.assertEqual(headers.get('Access-Control-Allow-Origin'), '*')
        self.assertIn('Content-Type', headers.get('Access-Control-Allow-Headers', ''))
        self.assertIn('POST', headers.get('Access-Control-Allow-Methods', ''))

    # ============================================================
    # GET /beacon/atlas Tests
    # ============================================================

    def test_atlas_empty_list(self):
        """GET /beacon/atlas returns empty list when no agents registered."""
        response = self.client.get('/beacon/atlas')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['agents'], [])
        self.assertEqual(data['total'], 0)
        self.assertIn('timestamp', data)

    def test_atlas_returns_registered_agents(self):
        """GET /beacon/atlas returns list of registered agents."""
        # Register two agents
        agents_data = [
            {'agent_id': 'bcn_alice', 'pubkey_hex': '0xaaaa' + '00' * 30, 'name': 'Alice'},
            {'agent_id': 'bcn_bob', 'pubkey_hex': '0xbbbb' + '00' * 30, 'name': 'Bob'},
        ]

        for agent in agents_data:
            self.client.post(
                '/beacon/join',
                data=json.dumps(agent),
                content_type='application/json'
            )

        response = self.client.get('/beacon/atlas')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['total'], 2)
        self.assertEqual(len(data['agents']), 2)

        agent_ids = {a['agent_id'] for a in data['agents']}
        self.assertIn('bcn_alice', agent_ids)
        self.assertIn('bcn_bob', agent_ids)

    def test_atlas_agent_fields(self):
        """GET /beacon/atlas returns correct agent fields."""
        payload = {
            'agent_id': 'bcn_fields_test',
            'pubkey_hex': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'name': 'Fields Test Agent',
            'coinbase_address': '0x1234567890123456789012345678901234567890',
        }

        self.client.post(
            '/beacon/join',
            data=json.dumps(payload),
            content_type='application/json'
        )

        response = self.client.get('/beacon/atlas')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        agent = data['agents'][0]

        self.assertEqual(agent['agent_id'], 'bcn_fields_test')
        self.assertEqual(agent['pubkey_hex'], payload['pubkey_hex'])
        self.assertEqual(agent['name'], 'Fields Test Agent')
        self.assertEqual(agent['status'], 'active')
        self.assertEqual(agent['coinbase_address'], payload['coinbase_address'])
        self.assertIn('created_at', agent)
        self.assertIn('updated_at', agent)

    def test_atlas_status_filter(self):
        """GET /beacon/atlas supports status query param filter."""
        # Register agents with different statuses
        with sqlite3.connect(self.test_db_path) as conn:
            now = int(time.time())
            conn.execute("""
                INSERT INTO relay_agents (agent_id, pubkey_hex, name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('bcn_active', '0xaaaa' + '00' * 30, 'Active Agent', 'active', now, now))
            conn.execute("""
                INSERT INTO relay_agents (agent_id, pubkey_hex, name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('bcn_inactive', '0xbbbb' + '00' * 30, 'Inactive Agent', 'inactive', now, now))
            conn.commit()

        # Filter by active
        response_active = self.client.get('/beacon/atlas?status=active')
        self.assertEqual(response_active.status_code, 200)
        data_active = json.loads(response_active.data)
        self.assertEqual(data_active['total'], 1)
        self.assertEqual(data_active['agents'][0]['agent_id'], 'bcn_active')

        # Filter by inactive
        response_inactive = self.client.get('/beacon/atlas?status=inactive')
        self.assertEqual(response_inactive.status_code, 200)
        data_inactive = json.loads(response_inactive.data)
        self.assertEqual(data_inactive['total'], 1)
        self.assertEqual(data_inactive['agents'][0]['agent_id'], 'bcn_inactive')

        # No filter - should return both
        response_all = self.client.get('/beacon/atlas')
        self.assertEqual(response_all.status_code, 200)
        data_all = json.loads(response_all.data)
        self.assertEqual(data_all['total'], 2)

    def test_atlas_options_returns_cors_headers(self):
        """OPTIONS /beacon/atlas returns CORS headers."""
        response = self.client.options('/beacon/atlas')

        self.assertEqual(response.status_code, 200)
        headers = response.headers
        self.assertEqual(headers.get('Access-Control-Allow-Origin'), '*')
        self.assertIn('Content-Type', headers.get('Access-Control-Allow-Headers', ''))
        self.assertIn('GET', headers.get('Access-Control-Allow-Methods', ''))

    # ============================================================
    # Integration Tests
    # ============================================================

    def test_full_join_then_atlas_workflow(self):
        """Full workflow: join agent, verify in atlas, update mutable field, verify update.

        pubkey_hex is immutable after first registration (security patch 03bf96a),
        so the "update" step changes the name while keeping the same pubkey_hex.
        """
        pubkey = '0x1111' + '00' * 30

        # Step 1: Register agent
        payload1 = {
            'agent_id': 'bcn_workflow',
            'pubkey_hex': pubkey,
            'name': 'Workflow Agent v1',
        }

        response1 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload1),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)

        # Step 2: Verify in atlas
        response2 = self.client.get('/beacon/atlas')
        self.assertEqual(response2.status_code, 200)
        data2 = json.loads(response2.data)
        self.assertEqual(data2['total'], 1)
        self.assertEqual(data2['agents'][0]['name'], 'Workflow Agent v1')

        # Step 3: Update mutable field (name) — same pubkey_hex
        payload3 = {
            'agent_id': 'bcn_workflow',
            'pubkey_hex': pubkey,
            'name': 'Workflow Agent v2',
        }

        response3 = self.client.post(
            '/beacon/join',
            data=json.dumps(payload3),
            content_type='application/json'
        )
        self.assertEqual(response3.status_code, 200)

        # Step 4: Verify update in atlas
        response4 = self.client.get('/beacon/atlas')
        self.assertEqual(response4.status_code, 200)
        data4 = json.loads(response4.data)
        self.assertEqual(data4['total'], 1)
        self.assertEqual(data4['agents'][0]['name'], 'Workflow Agent v2')
        self.assertEqual(data4['agents'][0]['pubkey_hex'], pubkey)


class TestBeaconJoinValidation(unittest.TestCase):
    """Input validation tests for beacon join endpoint."""

    def test_pubkey_hex_format_validation(self):
        """Test pubkey_hex format validation rules."""
        valid_pubkeys = [
            '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            '0xABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890',
            '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            '00',  # Minimal valid
        ]

        invalid_pubkeys = [
            'not-hex',
            '0xGGGG',  # Invalid hex chars
            '0x',  # Just prefix
            None,  # Null
        ]

        # Valid should pass hex validation
        for pubkey in valid_pubkeys:
            pubkey_clean = pubkey.strip() if pubkey else ''
            if pubkey_clean.startswith('0x') or pubkey_clean.startswith('0X'):
                pubkey_clean = pubkey_clean[2:]
            try:
                bytes.fromhex(pubkey_clean)
                # If we get here, validation passed (as expected)
            except ValueError:
                self.fail(f"Valid pubkey failed validation: {pubkey}")

        # Invalid should fail hex validation (empty string is caught by missing field check)
        for pubkey in invalid_pubkeys:
            if pubkey is None:
                continue  # Skip None, handled by missing field check
            pubkey_clean = pubkey.strip() if pubkey else ''
            if pubkey_clean.startswith('0x') or pubkey_clean.startswith('0X'):
                pubkey_clean = pubkey_clean[2:]
            if not pubkey_clean:
                continue  # Empty after prefix removal, handled separately
            try:
                bytes.fromhex(pubkey_clean)
                self.fail(f"Invalid pubkey passed validation: {pubkey}")
            except ValueError:
                pass  # Expected


def run_tests():
    """Run all test suites."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconJoinRouting))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconJoinValidation))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
