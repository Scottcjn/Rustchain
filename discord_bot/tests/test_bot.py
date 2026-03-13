"""
Tests for RustChain Discord Bot command handlers.

Run with: python -m pytest tests/test_bot.py -v
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRustChainAPI(unittest.TestCase):
    """Tests for the RustChainAPI client."""

    def setUp(self):
        """Set up test fixtures."""
        import sys
        sys.path.insert(0, '..')
        from bot import RustChainAPI
        self.api = RustChainAPI(
            base_url="https://test.node.example",
            timeout=5.0
        )

    def tearDown(self):
        """Clean up after tests."""
        asyncio.run(self.api.close())

    @patch('httpx.AsyncClient.get')
    async def test_get_health_success(self, mock_get):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 3600,
            "db_rw": True,
            "tip_age_slots": 0
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await self.api.get_health()

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("version"), "2.2.1")
        mock_get.assert_called_once()

    @patch('httpx.AsyncClient.get')
    async def test_get_health_failure(self, mock_get):
        """Test health check with API failure."""
        mock_get.side_effect = Exception("Connection error")

        result = await self.api.get_health()

        self.assertEqual(result, {})

    @patch('httpx.AsyncClient.get')
    async def test_get_epoch_success(self, mock_get):
        """Test successful epoch fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "epoch": 100,
            "slot": 5000,
            "blocks_per_epoch": 144,
            "epoch_pot": 1.5,
            "enrolled_miners": 25
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await self.api.get_epoch()

        self.assertEqual(result.get("epoch"), 100)
        self.assertEqual(result.get("enrolled_miners"), 25)

    @patch('httpx.AsyncClient.get')
    async def test_get_balance_success(self, mock_get):
        """Test successful balance lookup."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "miner_id": "test_miner",
            "amount_rtc": 42.5
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await self.api.get_balance("test_miner")

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("amount_rtc"), 42.5)

    @patch('httpx.AsyncClient.get')
    async def test_get_balance_not_found(self, mock_get):
        """Test balance lookup for non-existent miner."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "WALLET_NOT_FOUND"
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await self.api.get_balance("unknown_miner")

        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "WALLET_NOT_FOUND")


class TestBotConfig(unittest.TestCase):
    """Tests for BotConfig."""

    def setUp(self):
        """Set up test fixtures."""
        import sys
        sys.path.insert(0, '..')
        from config import BotConfig
        self.BotConfig = BotConfig

    def test_default_values(self):
        """Test default configuration values."""
        config = self.BotConfig()

        self.assertEqual(config.prefix, "!")
        self.assertEqual(config.rustchain_node_url, "https://rustchain.org")
        self.assertEqual(config.api_timeout, 10.0)
        self.assertEqual(config.log_level, "INFO")

    @patch.dict('os.environ', {
        'DISCORD_TOKEN': 'test_token',
        'RUSTCHAIN_NODE_URL': 'https://custom.node',
        'BOT_PREFIX': '$',
        'LOG_LEVEL': 'DEBUG'
    })
    def test_from_env(self):
        """Test loading config from environment."""
        config = self.BotConfig.from_env()

        self.assertEqual(config.discord_token, 'test_token')
        self.assertEqual(config.rustchain_node_url, 'https://custom.node')
        self.assertEqual(config.prefix, '$')
        self.assertEqual(config.log_level, 'DEBUG')

    def test_validate_missing_token(self):
        """Test validation catches missing token."""
        config = self.BotConfig(discord_token="")
        errors = config.validate()

        self.assertIn("DISCORD_TOKEN is required", errors)

    def test_validate_valid_config(self):
        """Test validation passes with valid config."""
        config = self.BotConfig(discord_token="test_token")
        errors = config.validate()

        self.assertEqual(len(errors), 0)


class TestRustChainBot(unittest.TestCase):
    """Tests for RustChainBot helper methods."""

    def setUp(self):
        """Set up test fixtures."""
        import sys
        sys.path.insert(0, '..')
        from config import BotConfig
        from bot import RustChainBot

        config = BotConfig(discord_token="test_token")
        self.bot = RustChainBot(config)

    def test_format_rtc(self):
        """Test RTC formatting."""
        self.assertEqual(self.bot.format_rtc(42.5), "42.500000")
        self.assertEqual(self.bot.format_rtc(0.000001), "0.000001")
        self.assertEqual(self.bot.format_rtc(1000000), "1000000.000000")

    def test_short_id_truncates(self):
        """Test ID truncation for long IDs."""
        long_id = "very_long_miner_id_that_exceeds_limit"
        result = self.bot.short_id(long_id, keep=12)

        self.assertEqual(len(result), 15)  # 12 + "..."
        self.assertTrue(result.endswith("..."))

    def test_short_id_no_truncate(self):
        """Test ID not truncated when short enough."""
        short_id = "short_id"
        result = self.bot.short_id(short_id, keep=12)

        self.assertEqual(result, "short_id")


class TestSlashCommands(unittest.TestCase):
    """Tests for slash command handlers."""

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'DISCORD_TOKEN': 'test_token'})
    async def test_health_command_embed(self):
        """Test health command creates proper embed."""
        import sys
        sys.path.insert(0, '..')
        from config import BotConfig
        from bot import RustChainBot, RustChainAPI

        config = BotConfig.from_env()
        bot = RustChainBot(config)
        bot.api = RustChainAPI("https://test.node", 5.0)

        # Mock the API response
        bot.api.get_health = AsyncMock(return_value={
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 7200,
            "db_rw": True,
            "tip_age_slots": 0
        })

        # Mock interaction
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Call the command
        await bot.tree.get_command("health").callback(interaction)

        # Verify embed was sent
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        self.assertIn("embed", call_args.kwargs)

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'DISCORD_TOKEN': 'test_token'})
    async def test_epoch_command_embed(self):
        """Test epoch command creates proper embed."""
        import sys
        sys.path.insert(0, '..')
        from config import BotConfig
        from bot import RustChainBot, RustChainAPI

        config = BotConfig.from_env()
        bot = RustChainBot(config)
        bot.api = RustChainAPI("https://test.node", 5.0)

        bot.api.get_epoch = AsyncMock(return_value={
            "epoch": 150,
            "slot": 10000,
            "blocks_per_epoch": 144,
            "epoch_pot": 2.0,
            "enrolled_miners": 50
        })

        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await bot.tree.get_command("epoch").callback(interaction)

        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'DISCORD_TOKEN': 'test_token'})
    async def test_balance_command_embed(self):
        """Test balance command creates proper embed."""
        import sys
        sys.path.insert(0, '..')
        from config import BotConfig
        from bot import RustChainBot, RustChainAPI

        config = BotConfig.from_env()
        bot = RustChainBot(config)
        bot.api = RustChainAPI("https://test.node", 5.0)

        bot.api.get_balance = AsyncMock(return_value={
            "ok": True,
            "miner_id": "test_miner",
            "amount_rtc": 100.5
        })

        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await bot.tree.get_command("balance").callback(
            interaction,
            miner_id="test_miner"
        )

        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'DISCORD_TOKEN': 'test_token'})
    async def test_balance_command_invalid_id(self):
        """Test balance command rejects invalid miner ID."""
        import sys
        sys.path.insert(0, '..')
        from config import BotConfig
        from bot import RustChainBot

        config = BotConfig.from_env()
        bot = RustChainBot(config)

        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await bot.tree.get_command("balance").callback(
            interaction,
            miner_id="ab"  # Too short
        )

        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        self.assertTrue(call_args.kwargs.get("ephemeral", False))


if __name__ == "__main__":
    unittest.main()
