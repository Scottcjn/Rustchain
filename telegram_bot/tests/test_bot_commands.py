"""
Unit tests for Telegram bot commands
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBotCommands:
    """Tests for bot command handlers."""

    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Use a no-delay rate limiter so command tests stay independent."""
        import rustchain_query_bot

        rustchain_query_bot.rate_limiter = rustchain_query_bot.RateLimiter(
            min_interval_seconds=0
        )

    @pytest.fixture
    def mock_update(self):
        """Create a mock update object."""
        update = Mock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock context object."""
        context = Mock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_cmd_start(self, mock_update, mock_context):
        """Test /start command."""
        from rustchain_query_bot import cmd_start

        await cmd_start(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Welcome to RustChain Query Bot" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_help(self, mock_update, mock_context):
        """Test /help command."""
        from rustchain_query_bot import cmd_help

        await cmd_help(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Available Commands" in call_args[0][0] or "Commands:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_balance_no_args(self, mock_update, mock_context):
        """Test /balance command without arguments."""
        from rustchain_query_bot import cmd_balance

        mock_context.args = []
        await cmd_balance(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('rustchain_query_bot.api_client')
    async def test_cmd_balance_success(self, mock_client, mock_update, mock_context):
        """Test /balance command with valid wallet."""
        from rustchain_query_bot import cmd_balance

        mock_context.args = ["test-wallet"]
        mock_client.balance.return_value = {
            "amount_rtc": 100.5,
            "amount_i64": 100500000,
            "miner_id": "test-wallet"
        }

        await cmd_balance(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "100.5" in call_args[0][0]
        assert "test-wallet" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('rustchain_query_bot.api_client')
    async def test_cmd_balance_error(self, mock_client, mock_update, mock_context):
        """Test /balance command with API error."""
        from rustchain_query_bot import cmd_balance

        mock_context.args = ["test-wallet"]
        mock_client.balance.return_value = {"error": "Wallet not found"}

        await cmd_balance(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "error" in call_args[0][0].lower() or "Error" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('rustchain_query_bot.api_client')
    async def test_cmd_health_success(self, mock_client, mock_update, mock_context):
        """Test /health command success."""
        from rustchain_query_bot import cmd_health

        mock_client.health.return_value = {
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 86400
        }

        await cmd_health(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Online" in call_args[0][0] or "online" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('rustchain_query_bot.api_client')
    async def test_cmd_epoch_success(self, mock_client, mock_update, mock_context):
        """Test /epoch command success."""
        from rustchain_query_bot import cmd_epoch

        mock_client.epoch.return_value = {
            "epoch": 100,
            "slot": 5000,
            "height": 10000
        }

        await cmd_epoch(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "100" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('rustchain_query_bot.api_client')
    async def test_cmd_stats_success(self, mock_client, mock_update, mock_context):
        """Test /stats command success."""
        from rustchain_query_bot import cmd_stats

        mock_client.miners.return_value = ["miner1", "miner2"]
        mock_client.epoch.return_value = {"epoch": 100, "height": 5000}

        await cmd_stats(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "2" in call_args[0][0]  # miner count

    @pytest.mark.asyncio
    @patch('rustchain_query_bot.api_client')
    async def test_cmd_miners_success(self, mock_client, mock_update, mock_context):
        """Test /miners command success."""
        from rustchain_query_bot import cmd_miners

        mock_client.miners.return_value = {
            "miners": [
                {
                    "miner_id": "wallet-one",
                    "architecture": "PowerPC G4",
                    "status": "online",
                }
            ]
        }

        await cmd_miners(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "wallet-one" in call_args[0][0]
        assert "PowerPC G4" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_price_success(self, mock_update, mock_context):
        """Test /price command success."""
        from rustchain_query_bot import cmd_price

        await cmd_price(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "$0.10" in call_args[0][0]


class TestConfiguration:
    """Tests for configuration validation."""

    @patch('rustchain_query_bot.TELEGRAM_BOT_TOKEN', '')
    def test_validate_config_missing_token(self):
        """Test validation fails without bot token."""
        from rustchain_query_bot import validate_config

        result = validate_config()
        assert result is False

    @patch('rustchain_query_bot.TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    def test_validate_config_default_token(self):
        """Test validation fails with default token."""
        from rustchain_query_bot import validate_config

        result = validate_config()
        assert result is False

    @patch('rustchain_query_bot.TELEGRAM_BOT_TOKEN', 'test-token-123')
    def test_validate_config_valid_token(self):
        """Test validation passes with valid token."""
        from rustchain_query_bot import validate_config

        result = validate_config()
        assert result is True


class TestBotCommandsSetup:
    """Tests for bot command setup."""

    def test_set_bot_commands(self):
        """Test bot commands are set correctly."""
        from rustchain_query_bot import set_bot_commands
        from telegram import BotCommand

        commands = set_bot_commands(None)

        assert len(commands) == 8
        # BotCommand uses 'command' attribute for the command name
        command_names = [c.command for c in commands]
        assert "start" in command_names
        assert "help" in command_names
        assert "health" in command_names
        assert "epoch" in command_names
        assert "balance" in command_names
        assert "miners" in command_names
        assert "price" in command_names
        assert "stats" in command_names
