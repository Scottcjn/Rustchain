// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import sqlite3
import tempfile
import os
import sys

# Add root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from warthog_integration import WarthogMiner, WarthogPoolVerifier, WarthogProcessDetector

class TestWarthogMiner(unittest.TestCase):

    def setUp(self):
        self.miner = WarthogMiner()

    @patch('requests.get')
    def test_get_chain_head_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'height': 123456,
            'hash': '0x1234567890abcdef'
        }
        mock_get.return_value = mock_response

        result = self.miner.get_chain_head()

        self.assertIsNotNone(result)
        self.assertEqual(result['height'], 123456)
        self.assertEqual(result['hash'], '0x1234567890abcdef')
        mock_get.assert_called_with('http://localhost:3000/chain/head', timeout=10)

    @patch('requests.get')
    def test_get_chain_head_fallback_port(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'height': 789012,
            'hash': '0xfedcba0987654321'
        }

        # First call fails, second succeeds
        mock_get.side_effect = [Exception("Connection refused"), mock_response]

        result = self.miner.get_chain_head()

        self.assertIsNotNone(result)
        self.assertEqual(result['height'], 789012)
        self.assertEqual(mock_get.call_count, 2)

    @patch('requests.get')
    def test_get_chain_head_failure(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        result = self.miner.get_chain_head()

        self.assertIsNone(result)

    def test_calculate_difficulty_bonus(self):
        chain_data = {'height': 100000}
        bonus = self.miner.calculate_difficulty_bonus(chain_data)

        self.assertGreaterEqual(bonus, 1.0)
        self.assertLessEqual(bonus, 1.5)

    def test_verify_janushash_algo(self):
        test_hash = "wart_123456789abcdef"
        result = self.miner.verify_janushash_algo(test_hash)

        self.assertTrue(result)

    def test_verify_janushash_algo_invalid(self):
        test_hash = "invalid_hash_format"
        result = self.miner.verify_janushash_algo(test_hash)

        self.assertFalse(result)

class TestWarthogPoolVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = WarthogPoolVerifier()

    @patch('requests.get')
    def test_verify_woolypooly_account(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'address': 'wart1test123',
            'balance': 1.25,
            'workers': [{'name': 'worker1', 'hashrate': 1500}]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_pool_account('wart1test123', 'woolypooly')

        self.assertTrue(result['verified'])
        self.assertEqual(result['balance'], 1.25)
        self.assertEqual(len(result['workers']), 1)

    @patch('requests.get')
    def test_verify_acc_pool_account(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'wallet': 'wart1test456',
            'totalPaid': 0.75,
            'activeWorkers': 2,
            'hashrate': 3000
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_pool_account('wart1test456', 'acc-pool')

        self.assertTrue(result['verified'])
        self.assertEqual(result['totalPaid'], 0.75)
        self.assertEqual(result['activeWorkers'], 2)

    @patch('requests.get')
    def test_verify_pool_account_failure(self, mock_get):
        mock_get.side_effect = Exception("API error")

        result = self.verifier.verify_pool_account('wart1test', 'woolypooly')

        self.assertFalse(result['verified'])
        self.assertIn('error', result)

    def test_calculate_pool_bonus(self):
        pool_data = {
            'verified': True,
            'balance': 2.5,
            'workers': [{'hashrate': 1000}, {'hashrate': 2000}]
        }

        bonus = self.verifier.calculate_pool_bonus(pool_data)

        self.assertGreaterEqual(bonus, 1.0)
        self.assertLessEqual(bonus, 1.3)

class TestWarthogProcessDetector(unittest.TestCase):

    def setUp(self):
        self.detector = WarthogProcessDetector()

    @patch('psutil.process_iter')
    def test_detect_wart_miner_process(self, mock_iter):
        mock_process = MagicMock()
        mock_process.info = {'name': 'wart-miner', 'pid': 12345, 'cmdline': ['./wart-miner', '--pool', 'stratum+tcp://pool.com:4444']}
        mock_iter.return_value = [mock_process]

        processes = self.detector.detect_mining_processes()

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0]['name'], 'wart-miner')
        self.assertEqual(processes[0]['pid'], 12345)

    @patch('psutil.process_iter')
    def test_detect_warthog_miner_process(self, mock_iter):
        mock_process = MagicMock()
        mock_process.info = {'name': 'warthog-miner', 'pid': 67890, 'cmdline': ['warthog-miner', '--cpu-threads', '8']}
        mock_iter.return_value = [mock_process]

        processes = self.detector.detect_mining_processes()

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0]['name'], 'warthog-miner')
        self.assertEqual(processes[0]['pid'], 67890)

    @patch('psutil.process_iter')
    def test_detect_janushash_process(self, mock_iter):
        mock_process = MagicMock()
        mock_process.info = {'name': 'janushash', 'pid': 11111, 'cmdline': ['janushash-cpu-miner']}
        mock_iter.return_value = [mock_process]

        processes = self.detector.detect_mining_processes()

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0]['name'], 'janushash')

    @patch('psutil.process_iter')
    def test_detect_no_processes(self, mock_iter):
        mock_process = MagicMock()
        mock_process.info = {'name': 'chrome', 'pid': 9999, 'cmdline': ['chrome']}
        mock_iter.return_value = [mock_process]

        processes = self.detector.detect_mining_processes()

        self.assertEqual(len(processes), 0)

    @patch('psutil.process_iter')
    def test_process_detection_exception_handling(self, mock_iter):
        mock_process = MagicMock()
        mock_process.info = Exception("Access denied")
        mock_iter.return_value = [mock_process]

        processes = self.detector.detect_mining_processes()

        self.assertEqual(len(processes), 0)

    def test_calculate_process_bonus(self):
        processes = [
            {'name': 'wart-miner', 'pid': 123},
            {'name': 'warthog-miner', 'pid': 456}
        ]

        bonus = self.detector.calculate_process_bonus(processes)

        self.assertGreater(bonus, 1.0)

    def test_is_mining_process(self):
        self.assertTrue(self.detector.is_mining_process('wart-miner'))
        self.assertTrue(self.detector.is_mining_process('warthog-miner'))
        self.assertTrue(self.detector.is_mining_process('janushash'))
        self.assertFalse(self.detector.is_mining_process('chrome'))
        self.assertFalse(self.detector.is_mining_process('firefox'))

class TestWarthogIntegrationDB(unittest.TestCase):

    def setUp(self):
        self.test_db = tempfile.mktemp(suffix='.db')
        self.setup_test_db()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.unlink(self.test_db)

    def setup_test_db(self):
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE warthog_mining_sessions (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    node_height INTEGER,
                    node_hash TEXT,
                    pool_verified INTEGER,
                    pool_balance REAL,
                    processes_detected INTEGER,
                    rtc_bonus REAL
                )
            ''')
            conn.commit()

    def test_store_mining_session(self):
        session_data = {
            'timestamp': '2024-01-15 10:30:00',
            'node_height': 150000,
            'node_hash': '0xabcdef123456',
            'pool_verified': 1,
            'pool_balance': 3.75,
            'processes_detected': 2,
            'rtc_bonus': 1.45
        }

        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO warthog_mining_sessions
                (timestamp, node_height, node_hash, pool_verified, pool_balance, processes_detected, rtc_bonus)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_data['timestamp'],
                session_data['node_height'],
                session_data['node_hash'],
                session_data['pool_verified'],
                session_data['pool_balance'],
                session_data['processes_detected'],
                session_data['rtc_bonus']
            ))
            conn.commit()

            cursor.execute('SELECT COUNT(*) FROM warthog_mining_sessions')
            count = cursor.fetchone()[0]

        self.assertEqual(count, 1)

    def test_retrieve_mining_sessions(self):
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO warthog_mining_sessions
                (timestamp, node_height, node_hash, pool_verified, pool_balance, processes_detected, rtc_bonus)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('2024-01-15 11:00:00', 151000, '0x987654321', 1, 4.25, 1, 1.35))

            cursor.execute('SELECT * FROM warthog_mining_sessions ORDER BY timestamp DESC')
            sessions = cursor.fetchall()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0][2], 151000)  # node_height
        self.assertEqual(sessions[0][5], 4.25)    # pool_balance

class TestWarthogDualMiningFlow(unittest.TestCase):

    @patch('warthog_integration.WarthogMiner.get_chain_head')
    @patch('warthog_integration.WarthogPoolVerifier.verify_pool_account')
    @patch('warthog_integration.WarthogProcessDetector.detect_mining_processes')
    def test_full_dual_mining_verification(self, mock_processes, mock_pool, mock_chain):
        mock_chain.return_value = {
            'height': 175000,
            'hash': '0x1a2b3c4d5e6f',
            'timestamp': 1642248600
        }

        mock_pool.return_value = {
            'verified': True,
            'balance': 2.80,
            'workers': [{'name': 'rig1', 'hashrate': 2500}],
            'pool': 'woolypooly'
        }

        mock_processes.return_value = [
            {'name': 'wart-miner', 'pid': 8888, 'cmdline': ['wart-miner', '--threads', '6']},
            {'name': 'janushash', 'pid': 9999, 'cmdline': ['janushash-miner']}
        ]

        miner = WarthogMiner()
        pool_verifier = WarthogPoolVerifier()
        process_detector = WarthogProcessDetector()

        # Simulate full verification flow
        chain_data = miner.get_chain_head()
        pool_data = pool_verifier.verify_pool_account('wart1test', 'woolypooly')
        processes = process_detector.detect_mining_processes()

        # Calculate bonuses
        node_bonus = miner.calculate_difficulty_bonus(chain_data)
        pool_bonus = pool_verifier.calculate_pool_bonus(pool_data)
        process_bonus = process_detector.calculate_process_bonus(processes)

        total_rtc_bonus = node_bonus * pool_bonus * process_bonus

        self.assertIsNotNone(chain_data)
        self.assertTrue(pool_data['verified'])
        self.assertEqual(len(processes), 2)
        self.assertGreater(total_rtc_bonus, 1.0)
        self.assertLessEqual(total_rtc_bonus, 1.95)  # 1.5 * 1.3 max

    def test_mining_fingerprint_timing(self):
        import time

        start_time = time.time()

        # Simulate RIP-PoA fingerprinting process
        detector = WarthogProcessDetector()
        with patch('psutil.process_iter') as mock_iter:
            mock_process = MagicMock()
            mock_process.info = {'name': 'wart-miner', 'pid': 5555, 'cmdline': ['wart-miner']}
            mock_iter.return_value = [mock_process]

            processes = detector.detect_mining_processes()

        end_time = time.time()
        fingerprint_duration = end_time - start_time

        # Should complete well under 5 seconds
        self.assertLess(fingerprint_duration, 1.0)
        self.assertEqual(len(processes), 1)

if __name__ == '__main__':
    unittest.main()
