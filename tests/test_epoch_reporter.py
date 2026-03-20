# SPDX-License-Identifier: MIT

"""
Tests for the epoch reporter bot.
Tests epoch detection, data fetching, summary formatting, deduplication,
error handling, and multi-platform posting functionality.
"""

import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

from epoch_reporter import (
    EpochReporter,
    get_epoch_data,
    get_active_miners,
    format_epoch_summary,
    setup_database,
    is_epoch_posted,
    mark_epoch_posted
)


def mock_response(data, ok=True, status_code=200):
    """Create mock HTTP response."""
    r = MagicMock()
    r.ok = ok
    r.status_code = status_code
    r.json.return_value = data
    r.text = json.dumps(data) if data else ""
    return r


class TestEpochReporter(unittest.TestCase):

    def setUp(self):
        """Set up test database and reporter instance."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.reporter = EpochReporter(
            db_path=self.db_path,
            discord_webhook="https://discord.com/webhook/test",
            moltbook_api="https://moltbook.com/api/posts",
            twitter_config={
                "api_key": "test_key",
                "api_secret": "test_secret",
                "access_token": "test_token",
                "access_secret": "test_access_secret"
            }
        )
        setup_database(self.db_path)

    def tearDown(self):
        """Clean up test database."""
        import os
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @patch("epoch_reporter.requests.get")
    def test_get_epoch_data_success(self, mock_get):
        """Test successful epoch data retrieval."""
        mock_get.return_value = mock_response({
            "epoch": 95,
            "total_distributed": 1.5,
            "miner_count": 12,
            "block_height": 13680,
            "total_mined": 142.5
        })

        data = get_epoch_data()
        self.assertEqual(data["epoch"], 95)
        self.assertEqual(data["total_distributed"], 1.5)
        self.assertEqual(data["miner_count"], 12)

    @patch("epoch_reporter.requests.get")
    def test_get_epoch_data_failure(self, mock_get):
        """Test epoch data retrieval failure."""
        mock_get.side_effect = Exception("Connection failed")

        data = get_epoch_data()
        self.assertIsNone(data)

    @patch("epoch_reporter.requests.get")
    def test_get_active_miners_success(self, mock_get):
        """Test successful active miners retrieval."""
        mock_get.return_value = mock_response([
            {
                "miner_id": "dual-g4-125",
                "earnings": 0.297,
                "hardware_tier": "G4",
                "multiplier": 2.5
            },
            {
                "miner_id": "modern-cpu-01",
                "earnings": 0.15,
                "hardware_tier": "modern",
                "multiplier": 1.0
            }
        ])

        miners = get_active_miners()
        self.assertEqual(len(miners), 2)
        self.assertEqual(miners[0]["miner_id"], "dual-g4-125")
        self.assertEqual(miners[1]["earnings"], 0.15)

    def test_format_epoch_summary(self):
        """Test epoch summary formatting."""
        epoch_data = {
            "epoch": 95,
            "total_distributed": 1.5,
            "miner_count": 12,
            "block_height": 13680,
            "total_mined": 142.5
        }

        miners = [
            {
                "miner_id": "dual-g4-125",
                "earnings": 0.297,
                "hardware_tier": "G4",
                "multiplier": 2.5
            },
            {
                "miner_id": "power8-node",
                "earnings": 0.201,
                "hardware_tier": "POWER8",
                "multiplier": 1.8
            }
        ]

        summary = format_epoch_summary(epoch_data, miners)

        self.assertIn("📊 Epoch 95 Complete", summary)
        self.assertIn("💰 1.5 RTC distributed to 12 miners", summary)
        self.assertIn("🏆 Top earner: dual-g4-125 (0.297 RTC, G4 2.5x)", summary)
        self.assertIn("📦 Block height: 13,680", summary)
        self.assertIn("💎 Total RTC mined: 142.5", summary)
        self.assertIn("Explorer: https://50.28.86.131/explorer", summary)

    def test_hardware_tier_counting(self):
        """Test hardware tier counting in summary."""
        epoch_data = {
            "epoch": 96,
            "total_distributed": 2.1,
            "miner_count": 8,
            "block_height": 13700,
            "total_mined": 145.3
        }

        miners = [
            {"hardware_tier": "G4", "miner_id": "g4-1", "earnings": 0.3},
            {"hardware_tier": "G4", "miner_id": "g4-2", "earnings": 0.25},
            {"hardware_tier": "G5", "miner_id": "g5-1", "earnings": 0.4},
            {"hardware_tier": "POWER8", "miner_id": "p8-1", "earnings": 0.2},
            {"hardware_tier": "modern", "miner_id": "mod-1", "earnings": 0.15},
            {"hardware_tier": "modern", "miner_id": "mod-2", "earnings": 0.12},
            {"hardware_tier": "modern", "miner_id": "mod-3", "earnings": 0.1}
        ]

        summary = format_epoch_summary(epoch_data, miners)

        self.assertIn("⛏️ Active miners: 8 (2 G4, 1 G5, 1 POWER8, 3 modern)", summary)

    def test_database_setup(self):
        """Test database initialization."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn("posted_epochs", tables)

    def test_epoch_deduplication(self):
        """Test epoch posting deduplication."""
        # First check - epoch not posted
        self.assertFalse(is_epoch_posted(95, self.db_path))

        # Mark as posted
        mark_epoch_posted(95, self.db_path)

        # Second check - epoch already posted
        self.assertTrue(is_epoch_posted(95, self.db_path))

    @patch("epoch_reporter.requests.post")
    def test_discord_posting(self, mock_post):
        """Test Discord webhook posting."""
        mock_post.return_value = mock_response({"success": True})

        summary = "📊 Epoch 95 Complete\n💰 1.5 RTC distributed"
        result = self.reporter.post_to_discord(summary)

        self.assertTrue(result)
        mock_post.assert_called_once()

        # Check webhook URL and payload
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://discord.com/webhook/test")
        payload = call_args[1]["json"]
        self.assertIn("content", payload)
        self.assertIn("📊 Epoch 95 Complete", payload["content"])

    @patch("epoch_reporter.requests.post")
    def test_moltbook_posting(self, mock_post):
        """Test Moltbook API posting."""
        mock_post.return_value = mock_response({"post_id": "12345", "status": "published"})

        summary = "📊 Epoch 95 Complete\n💰 1.5 RTC distributed"
        result = self.reporter.post_to_moltbook(summary)

        self.assertTrue(result)
        mock_post.assert_called_once()

        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://moltbook.com/api/posts")
        payload = call_args[1]["json"]
        self.assertIn("content", payload)
        self.assertEqual(payload["content"], summary)

    @patch("epoch_reporter.tweepy.API")
    def test_twitter_posting(self, mock_twitter):
        """Test Twitter posting via Tweepy."""
        mock_api = MagicMock()
        mock_twitter.return_value = mock_api
        mock_api.update_status.return_value = MagicMock(id=123456789)

        summary = "📊 Epoch 95 Complete\n💰 1.5 RTC distributed"
        result = self.reporter.post_to_twitter(summary)

        self.assertTrue(result)
        mock_api.update_status.assert_called_once_with(summary)

    @patch("epoch_reporter.requests.post")
    def test_posting_error_handling(self, mock_post):
        """Test error handling in platform posting."""
        mock_post.side_effect = Exception("Network timeout")

        summary = "📊 Epoch 95 Complete"
        result = self.reporter.post_to_discord(summary)

        self.assertFalse(result)

    @patch("epoch_reporter.get_epoch_data")
    @patch("epoch_reporter.get_active_miners")
    def test_full_reporter_run(self, mock_miners, mock_epoch):
        """Test complete reporter execution flow."""
        # Mock data
        mock_epoch.return_value = {
            "epoch": 97,
            "total_distributed": 1.8,
            "miner_count": 15,
            "block_height": 13720,
            "total_mined": 148.2
        }

        mock_miners.return_value = [
            {
                "miner_id": "top-miner",
                "earnings": 0.35,
                "hardware_tier": "G5",
                "multiplier": 3.0
            }
        ]

        with patch.object(self.reporter, 'post_to_discord', return_value=True) as mock_discord:
            with patch.object(self.reporter, 'post_to_moltbook', return_value=True) as mock_moltbook:
                with patch.object(self.reporter, 'post_to_twitter', return_value=True) as mock_twitter:

                    # First run should post
                    result = self.reporter.run()
                    self.assertTrue(result)

                    # Verify all platforms were called
                    mock_discord.assert_called_once()
                    mock_moltbook.assert_called_once()
                    mock_twitter.assert_called_once()

                    # Second run should skip (already posted)
                    mock_discord.reset_mock()
                    mock_moltbook.reset_mock()
                    mock_twitter.reset_mock()

                    result = self.reporter.run()
                    self.assertFalse(result)

                    # Verify no platforms were called
                    mock_discord.assert_not_called()
                    mock_moltbook.assert_not_called()
                    mock_twitter.assert_not_called()

    def test_empty_miners_list(self):
        """Test handling of empty miners list."""
        epoch_data = {
            "epoch": 98,
            "total_distributed": 0.0,
            "miner_count": 0,
            "block_height": 13740,
            "total_mined": 150.0
        }

        summary = format_epoch_summary(epoch_data, [])

        self.assertIn("📊 Epoch 98 Complete", summary)
        self.assertIn("💰 0.0 RTC distributed to 0 miners", summary)
        self.assertIn("🏆 Top earner: None", summary)
        self.assertIn("⛏️ Active miners: 0", summary)

    @patch("epoch_reporter.requests.get")
    def test_malformed_api_response(self, mock_get):
        """Test handling of malformed API responses."""
        # Missing required fields
        mock_get.return_value = mock_response({"epoch": 99})

        data = get_epoch_data()
        self.assertIsNone(data)

    @patch("epoch_reporter.requests.get")
    def test_api_http_error(self, mock_get):
        """Test handling of HTTP error responses."""
        mock_get.return_value = mock_response({}, ok=False, status_code=500)

        data = get_epoch_data()
        self.assertIsNone(data)

    def test_database_connection_error(self):
        """Test handling of database connection errors."""
        invalid_path = "/invalid/path/db.sqlite"

        # Should not raise exception
        result = is_epoch_posted(100, invalid_path)
        self.assertFalse(result)

        # Should not raise exception
        mark_epoch_posted(100, invalid_path)

    @patch("epoch_reporter.requests.post")
    def test_partial_posting_failure(self, mock_post):
        """Test handling when some platforms fail."""
        # Discord succeeds, Moltbook fails
        mock_post.side_effect = [
            mock_response({"success": True}),  # Discord
            Exception("Moltbook API down")     # Moltbook
        ]

        summary = "📊 Epoch 100 Complete"

        discord_result = self.reporter.post_to_discord(summary)
        moltbook_result = self.reporter.post_to_moltbook(summary)

        self.assertTrue(discord_result)
        self.assertFalse(moltbook_result)


if __name__ == "__main__":
    unittest.main()
