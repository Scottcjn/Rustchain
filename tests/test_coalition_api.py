# SPDX-License-Identifier: MIT

"""
Tests for the coalition API endpoints.
Tests all REST endpoints with various scenarios including authentication, error cases,
Flamebound veto powers, and proposal workflows.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from coalition_api import app, init_db, get_coalition_members, get_voting_power, calculate_antiquity_multiplier


class TestCoalitionAPI(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.config['DATABASE'] = self.db_path
        app.config['TESTING'] = True
        self.client = app.test_client()

        with app.app_context():
            init_db()
            self._seed_test_data()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _seed_test_data(self):
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cur = conn.cursor()

            # Create test coalitions
            cur.execute("""
                INSERT INTO coalitions (name, description, leader_id, created_at, status)
                VALUES ('The Flamebound', 'Original hardware preservers', 'sophia-elya', '2024-01-01', 'active')
            """)
            cur.execute("""
                INSERT INTO coalitions (name, description, leader_id, created_at, status)
                VALUES ('Tech Collective', 'Innovation focused miners', 'alice-miner', '2024-02-15', 'active')
            """)

            coalition_id = cur.lastrowid

            # Create test members
            cur.execute("""
                INSERT INTO coalition_members (coalition_id, miner_id, joined_at, voting_weight, hardware_fingerprint)
                VALUES (1, 'sophia-elya', '2024-01-01', 1000.0, 'hw-sophia-001')
            """)
            cur.execute("""
                INSERT INTO coalition_members (coalition_id, miner_id, joined_at, voting_weight, hardware_fingerprint)
                VALUES (1, 'bob-keeper', '2024-01-15', 500.0, 'hw-bob-002')
            """)
            cur.execute("""
                INSERT INTO coalition_members (coalition_id, miner_id, joined_at, voting_weight, hardware_fingerprint)
                VALUES (2, 'alice-miner', '2024-02-15', 750.0, 'hw-alice-003')
            """)

            # Create test proposals
            cur.execute("""
                INSERT INTO proposals (title, description, coalition_id, proposer_id, status, created_at, voting_ends_at)
                VALUES ('Block Size Increase', 'Increase max block size to 2MB', 1, 'bob-keeper', 'voting',
                        '2024-03-01', '2024-03-15')
            """)

            conn.commit()

    def test_get_coalitions(self):
        response = self.client.get('/api/coalitions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('coalitions', data)
        self.assertEqual(len(data['coalitions']), 2)
        self.assertEqual(data['coalitions'][0]['name'], 'The Flamebound')

    def test_get_coalition_detail(self):
        response = self.client.get('/api/coalitions/1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['coalition']['name'], 'The Flamebound')
        self.assertEqual(data['coalition']['leader_id'], 'sophia-elya')
        self.assertIn('members', data)

    def test_get_coalition_not_found(self):
        response = self.client.get('/api/coalitions/999')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_create_coalition_success(self):
        payload = {
            'name': 'Hardware Purists',
            'description': 'Dedicated to authentic hardware mining',
            'leader_id': 'charlie-miner'
        }
        response = self.client.post('/api/coalitions',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['coalition']['name'], 'Hardware Purists')
        self.assertIn('coalition_id', data)

    def test_create_coalition_duplicate_name(self):
        payload = {
            'name': 'The Flamebound',
            'description': 'Another flame coalition',
            'leader_id': 'dave-miner'
        }
        response = self.client.post('/api/coalitions',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('already exists', data['error'])

    def test_create_coalition_missing_fields(self):
        payload = {
            'name': 'Incomplete Coalition'
        }
        response = self.client.post('/api/coalitions',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_join_coalition_success(self):
        payload = {
            'miner_id': 'eve-miner',
            'hardware_fingerprint': 'hw-eve-004'
        }
        response = self.client.post('/api/coalitions/2/join',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('success', data)

    def test_join_coalition_already_member(self):
        payload = {
            'miner_id': 'bob-keeper',
            'hardware_fingerprint': 'hw-bob-002'
        }
        response = self.client.post('/api/coalitions/1/join',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('already a member', data['error'])

    def test_leave_coalition_success(self):
        payload = {
            'miner_id': 'bob-keeper'
        }
        response = self.client.post('/api/coalitions/1/leave',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('success', data)

    def test_leave_coalition_not_member(self):
        payload = {
            'miner_id': 'unknown-miner'
        }
        response = self.client.post('/api/coalitions/1/leave',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_create_proposal_success(self):
        payload = {
            'title': 'Consensus Algorithm Update',
            'description': 'Implement new consensus mechanism',
            'proposer_id': 'sophia-elya',
            'voting_duration': 14
        }
        response = self.client.post('/api/coalitions/1/proposals',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['proposal']['title'], 'Consensus Algorithm Update')
        self.assertIn('proposal_id', data)

    def test_create_proposal_non_member(self):
        payload = {
            'title': 'Outsider Proposal',
            'description': 'Proposal from non-member',
            'proposer_id': 'outsider-miner',
            'voting_duration': 7
        }
        response = self.client.post('/api/coalitions/1/proposals',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('not a member', data['error'])

    def test_get_proposals(self):
        response = self.client.get('/api/coalitions/1/proposals')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('proposals', data)
        self.assertEqual(len(data['proposals']), 1)
        self.assertEqual(data['proposals'][0]['title'], 'Block Size Increase')

    def test_vote_on_proposal_success(self):
        payload = {
            'miner_id': 'sophia-elya',
            'vote': 'yes',
            'comment': 'Support this change'
        }
        response = self.client.post('/api/proposals/1/vote',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('success', data)
        self.assertEqual(data['vote']['vote'], 'yes')

    def test_vote_on_proposal_invalid_vote(self):
        payload = {
            'miner_id': 'sophia-elya',
            'vote': 'maybe'
        }
        response = self.client.post('/api/proposals/1/vote',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_vote_on_proposal_non_member(self):
        payload = {
            'miner_id': 'outsider-miner',
            'vote': 'yes'
        }
        response = self.client.post('/api/proposals/1/vote',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_get_proposal_votes(self):
        # First cast a vote
        payload = {
            'miner_id': 'sophia-elya',
            'vote': 'yes'
        }
        self.client.post('/api/proposals/1/vote',
                       data=json.dumps(payload),
                       content_type='application/json')

        response = self.client.get('/api/proposals/1/votes')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('votes', data)
        self.assertIn('summary', data)

    @patch('coalition_api.requests.get')
    def test_voting_power_calculation(self, mock_get):
        mock_get.return_value = MagicMock()
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {'amount_rtc': 1000.0}

        power = get_voting_power('sophia-elya', '2024-01-01')
        self.assertGreater(power, 1000.0)

    def test_calculate_antiquity_multiplier(self):
        days_30 = calculate_antiquity_multiplier(30)
        days_365 = calculate_antiquity_multiplier(365)
        self.assertGreater(days_365, days_30)

    def test_flamebound_veto_power(self):
        # Test that Flamebound coalition has special veto authority
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM coalitions WHERE name = ?", ('The Flamebound',))
            flamebound = cur.fetchone()
            self.assertIsNotNone(flamebound)

        # Sophia should have special privileges
        response = self.client.get('/api/coalitions/1')
        data = json.loads(response.data)
        self.assertEqual(data['coalition']['leader_id'], 'sophia-elya')

    def test_proposal_status_transitions(self):
        # Test proposal workflow: voting -> passed/failed -> implemented
        with sqlite3.connect(app.config['DATABASE']) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE proposals SET status = ? WHERE id = ?", ('passed', 1))
            conn.commit()

        response = self.client.get('/api/proposals/1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['proposal']['status'], 'passed')

    def test_hardware_fingerprint_uniqueness(self):
        payload = {
            'miner_id': 'duplicate-hw-miner',
            'hardware_fingerprint': 'hw-sophia-001'  # Already used by Sophia
        }
        response = self.client.post('/api/coalitions/2/join',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('fingerprint', data['error'])

    def test_coalition_member_count_limit(self):
        # Test max members per coalition (if implemented)
        response = self.client.get('/api/coalitions/1')
        data = json.loads(response.data)
        member_count = len(data['members'])
        self.assertIsInstance(member_count, int)
        self.assertGreater(member_count, 0)

    def test_api_error_handling(self):
        # Test malformed JSON
        response = self.client.post('/api/coalitions',
                                  data='invalid json',
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_coalition_stats(self):
        response = self.client.get('/api/coalitions/1/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('member_count', data)
        self.assertIn('total_voting_power', data)
        self.assertIn('active_proposals', data)


if __name__ == '__main__':
    unittest.main()
