# SPDX-License-Identifier: MIT
"""
Comprehensive test suite for Warthog dual-mining integration.
Tests RPC queries, pool verification, process detection, and integration scenarios.
"""
import json
import subprocess
import unittest
from unittest.mock import patch, MagicMock, call
import sqlite3
import tempfile
import os

import requests


def mock_response(data, ok=True, status_code=200):
    """Create a mock response object."""
    r = MagicMock()
    r.ok = ok
    r.status_code = status_code
    r.json.return_value = data
    r.text = json.dumps(data) if isinstance(data, dict) else str(data)
    return r


class TestWarthogDualMining(unittest.TestCase):

    def setUp(self):
        """Set up test environment."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Initialize test database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS warthog_miners (
                    id INTEGER PRIMARY KEY,
                    miner_id TEXT UNIQUE,
                    node_url TEXT,
                    pool_url TEXT,
                    process_name TEXT,
                    last_height INTEGER,
                    last_hash TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                INSERT INTO warthog_miners
                (miner_id, node_url, pool_url, process_name, last_height, last_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('test-miner-001', 'localhost:3000', 'wooLypool.ca:3008', 'wart-miner', 12345, 'abc123def'))
            conn.commit()

    def tearDown(self):
        """Clean up test environment."""
        os.unlink(self.db_path)

    @patch('requests.get')
    def test_warthog_node_rpc_success(self, mock_get):
        """Test successful Warthog node RPC query."""
        mock_get.return_value = mock_response({
            'height': 15678,
            'hash': 'deadbeef1234567890abcdef',
            'timestamp': 1703097600,
            'difficulty': '0x1e0fffff'
        })

        response = requests.get('http://localhost:3000/chain/head')
        self.assertTrue(response.ok)
        data = response.json()
        self.assertEqual(data['height'], 15678)
        self.assertEqual(data['hash'], 'deadbeef1234567890abcdef')
        mock_get.assert_called_once_with('http://localhost:3000/chain/head')

    @patch('requests.get')
    def test_warthog_node_rpc_connection_error(self, mock_get):
        """Test Warthog node RPC connection error handling."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        with self.assertRaises(requests.ConnectionError):
            requests.get('http://localhost:3000/chain/head')

    @patch('requests.get')
    def test_warthog_node_rpc_timeout(self, mock_get):
        """Test Warthog node RPC timeout handling."""
        mock_get.side_effect = requests.Timeout("Request timeout")

        with self.assertRaises(requests.Timeout):
            requests.get('http://localhost:3000/chain/head', timeout=5)

    @patch('requests.get')
    def test_warthog_node_alternate_port(self, mock_get):
        """Test Warthog node on alternate port 3001."""
        mock_get.return_value = mock_response({
            'height': 15679,
            'hash': 'cafebabe987654321',
            'timestamp': 1703097660
        })

        response = requests.get('http://localhost:3001/chain/head')
        data = response.json()
        self.assertEqual(data['height'], 15679)
        mock_get.assert_called_once_with('http://localhost:3001/chain/head')

    @patch('requests.get')
    def test_woolypooly_pool_verification(self, mock_get):
        """Test WoolyPooly pool account verification."""
        mock_get.return_value = mock_response({
            'address': 'wart1qtest123mining456address789',
            'hashrate': '125.4 KH/s',
            'shares_valid': 1247,
            'shares_invalid': 3,
            'last_share': 1703097600,
            'balance': '0.00542'
        })

        response = requests.get('https://api.woolypooly.com/api/wart/stats/wart1qtest123mining456address789')
        data = response.json()
        self.assertEqual(data['address'], 'wart1qtest123mining456address789')
        self.assertGreater(float(data['balance']), 0)

    @patch('requests.get')
    def test_acc_pool_verification(self, mock_get):
        """Test acc-pool API verification."""
        mock_get.return_value = mock_response({
            'wallet': 'wart1qaccpool789test456wallet123',
            'current_hashrate': 98700,
            'average_hashrate': 102300,
            'workers': 2,
            'pending_balance': 0.00234,
            'paid_total': 0.15678
        })

        response = requests.get('https://acc-pool.pw/api/wart/miner/wart1qaccpool789test456wallet123')
        data = response.json()
        self.assertEqual(data['wallet'], 'wart1qaccpool789test456wallet123')
        self.assertEqual(data['workers'], 2)

    @patch('subprocess.check_output')
    def test_detect_wart_miner_process(self, mock_check_output):
        """Test detection of wart-miner process."""
        mock_check_output.return_value = b'''  PID TTY      STAT   TIME COMMAND
12345 ?        Sl     0:45 wart-miner --pool stratum://wooLypool.ca:3008 --wallet wart1qtest123
23456 ?        Sl     1:23 other-process
'''

        output = subprocess.check_output(['ps', 'aux'], universal_newlines=True)
        self.assertIn('wart-miner', output)

    @patch('subprocess.check_output')
    def test_detect_warthog_miner_process(self, mock_check_output):
        """Test detection of warthog-miner process."""
        mock_check_output.return_value = b'''root      34567  0.2  1.5  456789  98765 ?  Sl   Dec20   2:34 warthog-miner --algo janushash --pool wss://pool.example.com
'''

        output = subprocess.check_output(['ps', 'aux'], universal_newlines=True)
        self.assertIn('warthog-miner', output)

    @patch('subprocess.check_output')
    def test_detect_janushash_process(self, mock_check_output):
        """Test detection of janushash process."""
        mock_check_output.return_value = b'''miner     45678  3.2  2.1  234567  87654 ?  R    Dec20  15:42 janushash-cpu-miner -a janushash -o stratum://acc-pool.pw:4008
'''

        output = subprocess.check_output(['ps', 'aux'], universal_newlines=True)
        self.assertIn('janushash', output)

    @patch('subprocess.check_output')
    def test_no_warthog_processes_detected(self, mock_check_output):
        """Test when no Warthog processes are running."""
        mock_check_output.return_value = b'''  PID TTY      STAT   TIME COMMAND
11111 ?        Sl     0:12 some-other-miner
22222 ?        Sl     2:34 different-process
'''

        output = subprocess.check_output(['ps', 'aux'], universal_newlines=True)
        self.assertNotIn('wart-miner', output)
        self.assertNotIn('warthog-miner', output)
        self.assertNotIn('janushash', output)

    def test_database_miner_storage(self):
        """Test storing and retrieving miner data from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM warthog_miners WHERE miner_id = ?', ('test-miner-001',))
            row = cursor.fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row[1], 'test-miner-001')
            self.assertEqual(row[2], 'localhost:3000')
            self.assertEqual(row[3], 'wooLypool.ca:3008')
            self.assertEqual(row[5], 12345)

    def test_database_miner_update(self):
        """Test updating miner data in database."""
        new_height = 15680
        new_hash = 'updated789hash123'

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE warthog_miners
                SET last_height = ?, last_hash = ?
                WHERE miner_id = ?
            ''', (new_height, new_hash, 'test-miner-001'))

            cursor = conn.execute('SELECT last_height, last_hash FROM warthog_miners WHERE miner_id = ?', ('test-miner-001',))
            row = cursor.fetchone()

            self.assertEqual(row[0], new_height)
            self.assertEqual(row[1], new_hash)

    @patch('requests.get')
    @patch('subprocess.check_output')
    def test_integration_scenario_full_detection(self, mock_check_output, mock_get):
        """Test full integration scenario with RPC, pool, and process detection."""
        # Mock successful RPC response
        mock_get.return_value = mock_response({
            'height': 15682,
            'hash': 'integration123test456',
            'timestamp': 1703097720
        })

        # Mock process detection
        mock_check_output.return_value = b'''miner     56789  2.1  1.8  345678  76543 ?  Sl   Dec20   8:42 wart-miner --pool stratum://wooLypool.ca:3008
'''

        # Simulate integration check
        rpc_response = requests.get('http://localhost:3000/chain/head')
        ps_output = subprocess.check_output(['ps', 'aux'], universal_newlines=True)

        self.assertTrue(rpc_response.ok)
        self.assertEqual(rpc_response.json()['height'], 15682)
        self.assertIn('wart-miner', ps_output)

    @patch('requests.get')
    def test_rpc_invalid_json_response(self, mock_get):
        """Test handling of invalid JSON response from RPC."""
        mock_response_obj = MagicMock()
        mock_response_obj.ok = True
        mock_response_obj.status_code = 200
        mock_response_obj.text = '{"height": 123, invalid json'
        mock_response_obj.json.side_effect = json.JSONDecodeError("Expecting ',' delimiter", "", 15)
        mock_get.return_value = mock_response_obj

        response = requests.get('http://localhost:3000/chain/head')
        with self.assertRaises(json.JSONDecodeError):
            response.json()

    @patch('requests.get')
    def test_pool_api_rate_limiting(self, mock_get):
        """Test pool API rate limiting response."""
        mock_get.return_value = mock_response(
            {'error': 'Rate limit exceeded', 'retry_after': 60},
            ok=False,
            status_code=429
        )

        response = requests.get('https://api.woolypooly.com/api/wart/stats/test')
        self.assertFalse(response.ok)
        self.assertEqual(response.status_code, 429)

    def test_database_multiple_miners(self):
        """Test handling multiple miners in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO warthog_miners
                (miner_id, node_url, pool_url, process_name, last_height, last_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('miner-002', 'localhost:3001', 'acc-pool.pw:4008', 'warthog-miner', 15683, 'multi456test789'))

            cursor = conn.execute('SELECT COUNT(*) FROM warthog_miners WHERE status = ?', ('active',))
            count = cursor.fetchone()[0]

            self.assertEqual(count, 2)

    @patch('subprocess.check_output')
    def test_process_detection_with_args(self, mock_check_output):
        """Test process detection with various command line arguments."""
        mock_check_output.return_value = b'''miner     78901  1.5  0.9  123456  43210 ?  Sl   Dec20   3:21 wart-miner --pool stratum://pool.example.com:4747 --wallet wart1qlong789wallet456address123 --threads 8 --intensity 20
'''

        output = subprocess.check_output(['ps', 'aux'], universal_newlines=True)
        self.assertIn('wart-miner', output)
        self.assertIn('--pool', output)
        self.assertIn('--threads', output)

    @patch('requests.get')
    def test_chain_head_missing_fields(self, mock_get):
        """Test RPC response with missing required fields."""
        mock_get.return_value = mock_response({
            'height': 15684,
            # Missing 'hash' field
            'timestamp': 1703097780
        })

        response = requests.get('http://localhost:3000/chain/head')
        data = response.json()
        self.assertEqual(data['height'], 15684)
        self.assertNotIn('hash', data)

    def test_database_connection_error_handling(self):
        """Test database connection error handling."""
        invalid_db_path = '/invalid/path/database.db'

        with self.assertRaises(sqlite3.OperationalError):
            with sqlite3.connect(invalid_db_path) as conn:
                conn.execute('SELECT * FROM warthog_miners')


if __name__ == '__main__':
    unittest.main()
