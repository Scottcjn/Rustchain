// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import json
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
from epoch_reporter import EpochReporter


class TestEpochReporter(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE epochs (
                    id INTEGER PRIMARY KEY,
                    epoch_number INTEGER UNIQUE,
                    total_distributed REAL,
                    miner_count INTEGER,
                    top_earner TEXT,
                    top_amount REAL,
                    block_height INTEGER,
                    total_mined REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        self.reporter = EpochReporter(db_path=self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_epoch_detection_new_epoch(self):
        mock_epoch_data = {
            "epoch": 95,
            "total_distributed": 1.5,
            "miner_count": 12,
            "top_earner": "dual-g4-125",
            "top_amount": 0.297,
            "block_height": 13680,
            "total_mined": 142.5
        }

        with patch.object(self.reporter, 'fetch_epoch_data', return_value=mock_epoch_data):
            result = self.reporter.check_new_epoch()
            self.assertTrue(result)

    def test_epoch_deduplication(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO epochs (epoch_number, total_distributed, miner_count,
                                  top_earner, top_amount, block_height, total_mined)
                VALUES (95, 1.5, 12, 'dual-g4-125', 0.297, 13680, 142.5)
            ''')

        mock_epoch_data = {
            "epoch": 95,
            "total_distributed": 1.5,
            "miner_count": 12,
            "top_earner": "dual-g4-125",
            "top_amount": 0.297,
            "block_height": 13680,
            "total_mined": 142.5
        }

        with patch.object(self.reporter, 'fetch_epoch_data', return_value=mock_epoch_data):
            result = self.reporter.check_new_epoch()
            self.assertFalse(result)

    def test_api_data_parsing(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "current_epoch": 96,
            "distributed": 2.1,
            "active_miners": 15,
            "height": 13890
        }

        with patch('requests.get', return_value=mock_response):
            data = self.reporter.fetch_epoch_data()
            self.assertEqual(data["epoch"], 96)
            self.assertEqual(data["total_distributed"], 2.1)
            self.assertEqual(data["miner_count"], 15)
            self.assertEqual(data["block_height"], 13890)

    def test_miners_data_parsing(self):
        mock_miners = [
            {"name": "dual-g4-125", "earnings": 0.297, "type": "G4"},
            {"name": "power8-node", "earnings": 0.245, "type": "POWER8"},
            {"name": "modern-1", "earnings": 0.188, "type": "modern"}
        ]

        result = self.reporter.analyze_miners(mock_miners)
        self.assertEqual(result["top_earner"], "dual-g4-125")
        self.assertEqual(result["top_amount"], 0.297)
        self.assertEqual(result["g4_count"], 1)
        self.assertEqual(result["power8_count"], 1)
        self.assertEqual(result["modern_count"], 1)

    def test_message_formatting(self):
        epoch_data = {
            "epoch": 95,
            "total_distributed": 1.5,
            "miner_count": 12,
            "top_earner": "dual-g4-125",
            "top_amount": 0.297,
            "block_height": 13680,
            "total_mined": 142.5,
            "g4_count": 3,
            "g5_count": 1,
            "power8_count": 1,
            "modern_count": 7
        }

        message = self.reporter.format_epoch_message(epoch_data)

        self.assertIn("📊 Epoch 95 Complete", message)
        self.assertIn("💰 1.5 RTC distributed to 12 miners", message)
        self.assertIn("🏆 Top earner: dual-g4-125 (0.297 RTC", message)
        self.assertIn("⛏️ Active miners: 12 (3 G4, 1 G5, 1 POWER8, 7 modern)", message)
        self.assertIn("📦 Block height: 13,680", message)
        self.assertIn("💎 Total RTC mined: 142.5", message)
        self.assertIn("Explorer: https://50.28.86.131/explorer", message)

    @patch('requests.post')
    def test_discord_posting(self, mock_post):
        mock_post.return_value.status_code = 204

        message = "Test epoch message"
        webhook_url = "https://discord.com/api/webhooks/test"

        result = self.reporter.post_to_discord(message, webhook_url)
        self.assertTrue(result)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], webhook_url)
        self.assertEqual(kwargs['json']['content'], message)

    @patch('requests.post')
    def test_moltbook_posting(self, mock_post):
        mock_post.return_value.status_code = 200

        message = "Test epoch message"
        api_key = "test_key"

        result = self.reporter.post_to_moltbook(message, api_key)
        self.assertTrue(result)

        mock_post.assert_called_once()

    @patch('requests.post')
    def test_x_platform_posting(self, mock_post):
        mock_post.return_value.status_code = 201

        message = "Test epoch message"
        bearer_token = "test_token"

        result = self.reporter.post_to_x(message, bearer_token)
        self.assertTrue(result)

        mock_post.assert_called_once()

    def test_multi_platform_posting(self):
        epoch_data = {
            "epoch": 95,
            "total_distributed": 1.5,
            "miner_count": 12,
            "top_earner": "dual-g4-125",
            "top_amount": 0.297,
            "block_height": 13680,
            "total_mined": 142.5,
            "g4_count": 3,
            "g5_count": 1,
            "power8_count": 1,
            "modern_count": 7
        }

        with patch.object(self.reporter, 'post_to_discord', return_value=True) as mock_discord, \
             patch.object(self.reporter, 'post_to_moltbook', return_value=True) as mock_moltbook, \
             patch.object(self.reporter, 'post_to_x', return_value=True) as mock_x:

            results = self.reporter.post_to_all_platforms(epoch_data)

            self.assertEqual(len(results), 3)
            mock_discord.assert_called_once()
            mock_moltbook.assert_called_once()
            mock_x.assert_called_once()

    def test_error_handling_network_failure(self):
        with patch('requests.get', side_effect=Exception("Network error")):
            data = self.reporter.fetch_epoch_data()
            self.assertIsNone(data)

    def test_error_handling_invalid_json(self):
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        with patch('requests.get', return_value=mock_response):
            data = self.reporter.fetch_epoch_data()
            self.assertIsNone(data)

    def test_database_integrity(self):
        epoch_data = {
            "epoch": 97,
            "total_distributed": 1.8,
            "miner_count": 14,
            "top_earner": "test-miner",
            "top_amount": 0.35,
            "block_height": 14000,
            "total_mined": 150.0
        }

        self.reporter.store_epoch(epoch_data)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM epochs WHERE epoch_number = ?",
                (97,)
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[1], 97)  # epoch_number
        self.assertEqual(row[2], 1.8)  # total_distributed

    def test_rate_limiting_respect(self):
        # Test that consecutive calls respect rate limits
        with patch('time.sleep') as mock_sleep:
            for _ in range(3):
                self.reporter.check_new_epoch()

            # Should have some delay between calls
            self.assertTrue(mock_sleep.called)


if __name__ == '__main__':
    unittest.main()
