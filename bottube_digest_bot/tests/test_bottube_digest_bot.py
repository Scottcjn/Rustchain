#!/usr/bin/env python3
"""
Tests for BoTTube Weekly Digest Bot

Run with:
    python -m pytest tests/test_bottube_digest_bot.py -v
"""

import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bottube_digest_bot import (
    BoTTubeClient,
    DigestContent,
    DigestFormatter,
    DigestGenerator,
    DigestSender,
    RustChainClient,
)
from config import BotConfig


class TestBotConfig(unittest.TestCase):
    """Test configuration loading and validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BotConfig()
        self.assertEqual(config.rustchain_node_url, "https://50.28.86.131")
        self.assertEqual(config.api_timeout, 15.0)
        self.assertEqual(config.digest_top_n, 10)
        self.assertEqual(config.schedule_mode, "weekly")
        self.assertEqual(config.schedule_day, "monday")
        self.assertEqual(config.schedule_hour, 9)
        self.assertFalse(config.dry_run)

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "RUSTCHAIN_NODE_URL": "https://test.node.com",
                "DIGEST_TOP_N": "5",
                "SCHEDULE_DAY": "friday",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            config = BotConfig.from_env()
            self.assertEqual(config.rustchain_node_url, "https://test.node.com")
            self.assertEqual(config.digest_top_n, 5)
            self.assertEqual(config.schedule_day, "friday")
            self.assertEqual(config.log_level, "DEBUG")

    def test_config_validation_valid(self):
        """Test validation with valid configuration."""
        config = BotConfig(dry_run=True)  # Dry run skips delivery validation
        errors = config.validate()
        self.assertEqual(len(errors), 0)

    def test_config_validation_invalid_timeout(self):
        """Test validation catches invalid timeout."""
        config = BotConfig(api_timeout=-1, dry_run=True)
        errors = config.validate()
        self.assertTrue(any("timeout" in e.lower() for e in errors))

    def test_config_validation_invalid_schedule_day(self):
        """Test validation catches invalid schedule day."""
        config = BotConfig(schedule_day="invalid", dry_run=True)
        errors = config.validate()
        self.assertTrue(any("schedule_day" in e.lower() for e in errors))

    def test_config_validation_invalid_hour(self):
        """Test validation catches invalid hour."""
        config = BotConfig(schedule_hour=25, dry_run=True)
        errors = config.validate()
        self.assertTrue(any("hour" in e.lower() for e in errors))

    def test_config_has_delivery_methods(self):
        """Test delivery method detection."""
        config = BotConfig()
        self.assertFalse(config.has_discord())
        self.assertFalse(config.has_telegram())
        self.assertFalse(config.has_email())

        config.discord_webhook_url = "https://discord.com/webhook/xxx"
        self.assertTrue(config.has_discord())

        config.telegram_bot_token = "123:ABC"
        config.telegram_chat_id = "-100123"
        self.assertTrue(config.has_telegram())

        config.smtp_host = "smtp.example.com"
        config.smtp_user = "user@example.com"
        config.digest_recipients = ["recipient@example.com"]
        self.assertTrue(config.has_email())


class TestDigestContent(unittest.TestCase):
    """Test digest content data structure."""

    def test_default_content(self):
        """Test default digest content."""
        content = DigestContent()
        self.assertEqual(content.current_epoch, 0)
        self.assertEqual(content.top_miners, [])
        self.assertEqual(content.top_videos, [])
        self.assertEqual(content.raw_data, {})

    def test_content_with_data(self):
        """Test digest content with data."""
        content = DigestContent(
            generated_at="2026-03-22T10:00:00Z",
            current_epoch=95,
            current_slot=12345,
            active_miners=42,
            top_miners=[
                {"miner_id": "miner1", "balance_rtc": 1000.0, "architecture": "x86_64"}
            ],
        )
        self.assertEqual(content.current_epoch, 95)
        self.assertEqual(len(content.top_miners), 1)
        self.assertEqual(content.top_miners[0]["balance_rtc"], 1000.0)


class TestDigestFormatter(unittest.TestCase):
    """Test digest formatting for different channels."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BotConfig(dry_run=True)
        self.content = DigestContent(
            generated_at="2026-03-22T10:00:00Z",
            period_start="2026-03-15T10:00:00Z",
            period_end="2026-03-22T10:00:00Z",
            current_epoch=95,
            current_slot=12345,
            block_height=67890,
            active_miners=42,
            node_version="2.2.1",
            node_uptime="5d 3h 42m",
            top_miners=[
                {
                    "miner_id": "scott-miner-001",
                    "balance_rtc": 1500.50,
                    "architecture": "x86_64",
                },
                {
                    "miner_id": "ivan-miner-002",
                    "balance_rtc": 1200.25,
                    "architecture": "arm64",
                },
            ],
            top_videos=[
                {
                    "title": "RustChain Tutorial #1",
                    "author": {"name": "Scott"},
                },
                {
                    "title": "Mining Setup Guide",
                    "author": {"name": "Ivan"},
                },
            ],
        )

    def test_format_discord(self):
        """Test Discord formatting."""
        message = DigestFormatter.format_discord(self.content, self.config)

        # Check key elements
        self.assertIn("📊 **BoTTube Weekly Digest**", message)
        self.assertIn("**Period:**", message)
        self.assertIn("━━━ NETWORK STATUS ━━━", message)
        self.assertIn("🔗 **Epoch:** 95", message)
        self.assertIn("👥 **Active Miners:** 42", message)
        self.assertIn("━━━ TOP MINERS ━━━", message)
        self.assertIn("scott-miner-001", message)
        self.assertIn("1,500.50 RTC", message)
        self.assertIn("━━━ TOP VIDEOS ━━━", message)
        self.assertIn("RustChain Tutorial #1", message)

    def test_format_telegram(self):
        """Test Telegram formatting."""
        message = DigestFormatter.format_telegram(self.content, self.config)

        # Check key elements (Telegram uses different markdown)
        self.assertIn("📊 *BoTTube Weekly Digest*", message)
        self.assertIn("*Period:*", message)
        self.assertIn("*━━━ NETWORK STATUS ━━━*", message)
        self.assertIn("🔗 *Epoch:* `95`", message)
        self.assertIn("━━━ TOP MINERS ━━━", message)

    def test_format_email_html(self):
        """Test email HTML formatting."""
        html = DigestFormatter.format_email_html(self.content, self.config)

        # Check HTML structure
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("📊 BoTTube Weekly Digest", html)
        self.assertIn("95", html)  # Epoch
        self.assertIn("42", html)  # Active miners
        self.assertIn("scott-miner-001", html)
        self.assertIn("1,500.50 RTC", html)
        self.assertIn("RustChain Tutorial #1", html)

        # Check styling
        self.assertIn("<style>", html)
        self.assertIn("font-family", html)

    def test_format_email_subject(self):
        """Test email subject generation."""
        subject = DigestFormatter.format_email_subject(self.content)
        self.assertIn("📊 BoTTube Weekly Digest", subject)
        self.assertIn("2026-03-22", subject)

    def test_format_empty_content(self):
        """Test formatting with empty content."""
        empty_content = DigestContent()
        message = DigestFormatter.format_discord(empty_content, self.config)
        self.assertIn("📊 **BoTTube Weekly Digest**", message)
        # Should not crash with empty data


class TestRustChainClient(unittest.TestCase):
    """Test RustChain API client."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BotConfig(dry_run=True)
        self.client = RustChainClient(self.config)

    def test_client_initialization(self):
        """Test client initializes with correct config."""
        self.assertEqual(
            self.client.config.rustchain_node_url, "https://50.28.86.131"
        )

    def test_api_endpoints(self):
        """Test API endpoint methods exist."""
        self.assertTrue(hasattr(self.client, "health"))
        self.assertTrue(hasattr(self.client, "epoch"))
        self.assertTrue(hasattr(self.client, "miners"))
        self.assertTrue(hasattr(self.client, "wallet_balance"))
        self.assertTrue(hasattr(self.client, "rewards_epoch"))

    def tearDown(self):
        """Clean up."""
        asyncio.run(self.client.close())


class TestBoTTubeClient(unittest.TestCase):
    """Test BoTTube API client."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BotConfig(dry_run=True)
        self.client = BoTTubeClient(self.config)

    def test_client_initialization(self):
        """Test client initializes with correct config."""
        self.assertEqual(self.client.config.bottube_url, "https://bottube.ai")

    def test_videos_method(self):
        """Test videos method exists."""
        self.assertTrue(hasattr(self.client, "videos"))

    def tearDown(self):
        """Clean up."""
        asyncio.run(self.client.close())


class TestDigestSender(unittest.TestCase):
    """Test digest sender."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BotConfig(dry_run=True)
        self.sender = DigestSender(self.config)
        self.content = DigestContent(
            current_epoch=95,
            active_miners=42,
            top_miners=[
                {"miner_id": "test-miner", "balance_rtc": 100.0, "architecture": "x86"}
            ],
        )

    def test_sender_initialization(self):
        """Test sender initializes correctly."""
        self.assertEqual(self.sender.config, self.config)

    def test_send_all_dry_run(self):
        """Test send_all in dry run mode."""
        results = asyncio.run(self.sender.send_all(self.content))
        # In dry run mode with no configured channels, should return empty dict
        self.assertIsInstance(results, dict)


class TestIntegration(unittest.TestCase):
    """Integration tests for the digest bot."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BotConfig(dry_run=True)
        self.config.digest_top_n = 3
        self.config.digest_top_videos = 2

    def test_generator_initialization(self):
        """Test digest generator initialization."""
        generator = DigestGenerator(self.config)
        self.assertEqual(generator.config, self.config)
        self.assertIsNotNone(generator.rustchain_client)
        self.assertIsNotNone(generator.bottube_client)

    def test_top_miners_uses_async_rate_limit_delay(self):
        """Top-miner balance lookup should not crash on the async delay."""
        generator = DigestGenerator(self.config)
        generator.rustchain_client.wallet_balance = AsyncMock(
            return_value={"ok": True, "amount_rtc": 42.5}
        )

        top_miners = asyncio.run(
            generator._get_top_miners(
                [{"miner_id": "miner-1", "architecture": "powerpc"}]
            )
        )

        self.assertEqual(
            top_miners,
            [
                {
                    "miner_id": "miner-1",
                    "balance_rtc": 42.5,
                    "architecture": "powerpc",
                }
            ],
        )

    def test_formatter_chain(self):
        """Test formatting chain for all channels."""
        content = DigestContent(
            current_epoch=95,
            active_miners=10,
            top_miners=[
                {"miner_id": "m1", "balance_rtc": 100.0, "architecture": "x86"}
            ],
            top_videos=[{"title": "Test Video", "author": {"name": "Test"}}],
        )

        # Test all formatters
        discord_msg = DigestFormatter.format_discord(content, self.config)
        telegram_msg = DigestFormatter.format_telegram(content, self.config)
        email_html = DigestFormatter.format_email_html(content, self.config)
        email_subject = DigestFormatter.format_email_subject(content)

        # Verify outputs
        self.assertIsInstance(discord_msg, str)
        self.assertTrue(len(discord_msg) > 0)

        self.assertIsInstance(telegram_msg, str)
        self.assertTrue(len(telegram_msg) > 0)

        self.assertIsInstance(email_html, str)
        self.assertTrue(len(email_html) > 0)
        self.assertIn("<html>", email_html)

        self.assertIsInstance(email_subject, str)
        self.assertTrue(len(email_subject) > 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_miners_list(self):
        """Test handling empty miners list."""
        content = DigestContent(top_miners=[])
        config = BotConfig(dry_run=True)
        message = DigestFormatter.format_discord(content, config)
        self.assertIn("📊 **BoTTube Weekly Digest**", message)

    def test_empty_videos_list(self):
        """Test handling empty videos list."""
        content = DigestContent(top_videos=[])
        config = BotConfig(dry_run=True)
        message = DigestFormatter.format_discord(content, config)
        self.assertIn("📊 **BoTTube Weekly Digest**", message)

    def test_very_long_miner_id(self):
        """Test truncation of very long miner IDs."""
        content = DigestContent(
            top_miners=[
                {
                    "miner_id": "very-long-miner-id-that-should-be-truncated",
                    "balance_rtc": 100.0,
                    "architecture": "x86",
                }
            ]
        )
        config = BotConfig(dry_run=True)
        message = DigestFormatter.format_discord(content, config)
        # Should contain truncated version
        self.assertIn("...", message)

    def test_zero_uptime(self):
        """Test handling zero uptime."""
        content = DigestContent(node_uptime="N/A")
        config = BotConfig(dry_run=True)
        message = DigestFormatter.format_discord(content, config)
        self.assertIn("⏱️", message)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBotConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestDigestContent))
    suite.addTests(loader.loadTestsFromTestCase(TestDigestFormatter))
    suite.addTests(loader.loadTestsFromTestCase(TestRustChainClient))
    suite.addTests(loader.loadTestsFromTestCase(TestBoTTubeClient))
    suite.addTests(loader.loadTestsFromTestCase(TestDigestSender))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
