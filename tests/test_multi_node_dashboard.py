# SPDX-License-Identifier: MIT

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sqlite3
import json
import tempfile
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from multi_node_dashboard import app, init_db, get_node_status, get_all_nodes_status, record_health_check

class TestMultiNodeDashboard(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Create temporary database
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_path = self.test_db.name

        # Initialize test database
        with patch('multi_node_dashboard.DB_PATH', self.db_path):
            init_db()

    def tearDown(self):
        # Clean up temporary database
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @patch('multi_node_dashboard.DB_PATH')
    def test_init_db(self, mock_db_path):
        mock_db_path = self.db_path
        init_db()

        # Verify tables exist
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

        self.assertIn('node_health', tables)
        self.assertIn('attestations', tables)

    def test_dashboard_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Multi-Node Health Dashboard', response.data)
        self.assertIn(b'Node Status Overview', response.data)

    @patch('requests.get')
    @patch('multi_node_dashboard.DB_PATH')
    def test_health_check_route_success(self, mock_db_path, mock_get):
        mock_db_path = self.db_path

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'healthy',
            'attestations': 150,
            'uptime': '99.5%',
            'last_block': 12345
        }
        mock_response.elapsed.total_seconds.return_value = 0.25
        mock_get.return_value = mock_response

        response = self.client.get('/health/node1')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['attestations'], 150)
        self.assertEqual(data['response_time'], 0.25)

    @patch('requests.get')
    @patch('multi_node_dashboard.DB_PATH')
    def test_health_check_route_failure(self, mock_db_path, mock_get):
        mock_db_path = self.db_path

        # Mock failed response
        mock_get.side_effect = Exception('Connection refused')

        response = self.client.get('/health/node2')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Connection refused', data['error'])

    @patch('requests.get')
    @patch('multi_node_dashboard.DB_PATH')
    def test_api_status_all_nodes(self, mock_db_path, mock_get):
        mock_db_path = self.db_path

        # Mock responses for all nodes
        def mock_response_side_effect(url, **kwargs):
            mock_resp = MagicMock()
            if 'node1' in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {'status': 'healthy', 'attestations': 100}
                mock_resp.elapsed.total_seconds.return_value = 0.2
            elif 'node2' in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {'status': 'healthy', 'attestations': 95}
                mock_resp.elapsed.total_seconds.return_value = 0.3
            else:  # node3
                mock_resp.status_code = 500
                mock_resp.json.return_value = {'error': 'Internal error'}
                mock_resp.elapsed.total_seconds.return_value = 1.0
            return mock_resp

        mock_get.side_effect = mock_response_side_effect

        response = self.client.get('/api/status/all')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn('nodes', data)
        self.assertEqual(len(data['nodes']), 3)

    @patch('requests.get')
    def test_get_node_status_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'healthy',
            'attestations': 75,
            'uptime': '98.2%'
        }
        mock_response.elapsed.total_seconds.return_value = 0.15
        mock_get.return_value = mock_response

        status = get_node_status('node1')

        self.assertEqual(status['status'], 'healthy')
        self.assertEqual(status['attestations'], 75)
        self.assertEqual(status['response_time'], 0.15)

    @patch('requests.get')
    def test_get_node_status_timeout(self, mock_get):
        mock_get.side_effect = Exception('Timeout')

        status = get_node_status('node2')

        self.assertEqual(status['status'], 'error')
        self.assertIn('Timeout', status['error'])

    @patch('multi_node_dashboard.get_node_status')
    def test_get_all_nodes_status(self, mock_get_status):
        # Mock different statuses for each node
        mock_responses = [
            {'status': 'healthy', 'attestations': 120, 'response_time': 0.2},
            {'status': 'warning', 'attestations': 80, 'response_time': 0.8},
            {'status': 'error', 'error': 'Connection failed', 'response_time': None}
        ]

        mock_get_status.side_effect = mock_responses

        all_status = get_all_nodes_status()

        self.assertEqual(len(all_status), 3)
        self.assertEqual(all_status[0]['node_id'], 'node1')
        self.assertEqual(all_status[1]['status'], 'warning')
        self.assertEqual(all_status[2]['status'], 'error')

    @patch('multi_node_dashboard.DB_PATH')
    def test_record_health_check(self, mock_db_path):
        mock_db_path = self.db_path

        # Record health check
        record_health_check('node1', 'healthy', 0.25, {'attestations': 100})

        # Verify record was inserted
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT node_id, status, response_time FROM node_health WHERE node_id = ?",
                ('node1',)
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'node1')
        self.assertEqual(result[1], 'healthy')
        self.assertEqual(result[2], 0.25)

    @patch('multi_node_dashboard.DB_PATH')
    def test_historical_data_route(self, mock_db_path):
        mock_db_path = self.db_path

        # Insert test data
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO node_health (node_id, status, response_time, metadata)
                VALUES (?, ?, ?, ?)
            """, ('node1', 'healthy', 0.3, '{"attestations": 85}'))
            conn.commit()

        response = self.client.get('/api/history/node1')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn('history', data)
        self.assertEqual(len(data['history']), 1)
        self.assertEqual(data['history'][0]['status'], 'healthy')

    def test_metrics_route(self):
        response = self.client.get('/api/metrics')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn('total_nodes', data)
        self.assertIn('healthy_nodes', data)
        self.assertIn('avg_response_time', data)

    @patch('multi_node_dashboard.DB_PATH')
    def test_database_operations_with_context_manager(self, mock_db_path):
        mock_db_path = self.db_path

        # Test proper database connection handling
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO node_health (node_id, status, response_time)
                    VALUES (?, ?, ?)
                """, ('test_node', 'healthy', 0.5))
                conn.commit()
        except Exception as e:
            self.fail(f"Database operation failed: {e}")

        # Verify data was inserted
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM node_health WHERE node_id = ?", ('test_node',))
            count = cursor.fetchone()[0]

        self.assertEqual(count, 1)

    def test_error_handling_invalid_node_id(self):
        response = self.client.get('/health/invalid_node')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('error', data)

    @patch('multi_node_dashboard.get_all_nodes_status')
    def test_dashboard_with_mixed_node_states(self, mock_get_all):
        mock_get_all.return_value = [
            {'node_id': 'node1', 'status': 'healthy', 'attestations': 120},
            {'node_id': 'node2', 'status': 'warning', 'attestations': 60},
            {'node_id': 'node3', 'status': 'error', 'error': 'Offline'}
        ]

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'healthy', response.data)
        self.assertIn(b'warning', response.data)
        self.assertIn(b'error', response.data)

if __name__ == '__main__':
    unittest.main()
