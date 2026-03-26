"""
Unit tests for BoTTube Telegram Bot commands
Issue #2299 - BoTTube Telegram Bot
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBotCommands:
    """Tests for bot command handlers."""

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
        from bottube_bot import cmd_start

        await cmd_start(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Welcome to BoTTube" in call_args[0][0] or "BoTTube Telegram Bot" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_help(self, mock_update, mock_context):
        """Test /help command."""
        from bottube_bot import cmd_help

        await cmd_help(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Help" in call_args[0][0] or "Commands" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_trending_success(self, mock_client, mock_update, mock_context):
        """Test /trending command success."""
        from bottube_bot import cmd_trending

        mock_client.trending.return_value = {
            "videos": [
                {"video_id": "abc123", "title": "Test Video", "agent_name": "test", 
                 "views": 100, "likes": 10, "duration": 180, "created_at": 1711111111}
            ]
        }

        await cmd_trending(mock_update, mock_context)

        assert mock_update.message.reply_text.called

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_trending_error(self, mock_client, mock_update, mock_context):
        """Test /trending command with API error."""
        from bottube_bot import cmd_trending

        mock_client.trending.return_value = {"error": "API error"}

        await cmd_trending(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Error" in call_args[0][0] or "error" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_new_success(self, mock_client, mock_update, mock_context):
        """Test /new command success."""
        from bottube_bot import cmd_new

        mock_client.list_videos.return_value = {
            "videos": [
                {"video_id": "abc123", "title": "New Video", "agent_name": "test",
                 "views": 50, "likes": 5, "duration": 120, "created_at": 1711111111}
            ]
        }

        await cmd_new(mock_update, mock_context)

        assert mock_update.message.reply_text.called

    @pytest.mark.asyncio
    async def test_cmd_search_no_args(self, mock_update, mock_context):
        """Test /search command without arguments."""
        from bottube_bot import cmd_search

        mock_context.args = []
        await cmd_search(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_search_success(self, mock_client, mock_update, mock_context):
        """Test /search command with query."""
        from bottube_bot import cmd_search

        mock_context.args = ["AI", "robots"]
        mock_client.search.return_value = {
            "videos": [
                {"video_id": "abc123", "title": "AI Robots", "agent_name": "test",
                 "views": 200, "likes": 20, "duration": 240, "created_at": 1711111111}
            ],
            "total": 1
        }

        await cmd_search(mock_update, mock_context)

        assert mock_update.message.reply_text.called

    @pytest.mark.asyncio
    async def test_cmd_video_no_args(self, mock_update, mock_context):
        """Test /video command without arguments."""
        from bottube_bot import cmd_video

        mock_context.args = []
        await cmd_video(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_video_success(self, mock_client, mock_update, mock_context):
        """Test /video command with video ID."""
        from bottube_bot import cmd_video

        mock_context.args = ["abc123"]
        mock_client.get_video.return_value = {
            "video_id": "abc123", "title": "Test Video", "agent_name": "test",
            "views": 100, "likes": 10, "duration": 180, "created_at": 1711111111
        }
        mock_client.describe_video.return_value = {"description": "Test description"}

        await cmd_video(mock_update, mock_context)

        assert mock_update.message.reply_text.called

    @pytest.mark.asyncio
    async def test_cmd_agent_no_args(self, mock_update, mock_context):
        """Test /agent command without arguments."""
        from bottube_bot import cmd_agent

        mock_context.args = []
        await cmd_agent(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_agent_success(self, mock_client, mock_update, mock_context):
        """Test /agent command with agent name."""
        from bottube_bot import cmd_agent

        mock_context.args = ["test-agent"]
        mock_client.get_agent.return_value = {
            "agent_name": "test-agent", "display_name": "Test Agent",
            "bio": "Test bio", "video_count": 5, "total_views": 500,
            "comment_count": 20, "total_likes": 50, "rtc_balance": 0.045
        }

        await cmd_agent(mock_update, mock_context)

        assert mock_update.message.reply_text.called

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    async def test_cmd_stats_success(self, mock_client, mock_update, mock_context):
        """Test /stats command success."""
        from bottube_bot import cmd_stats

        mock_client.get_stats.return_value = {
            "videos": 130, "agents": 17, "humans": 4,
            "total_views": 1415, "total_comments": 701, "total_likes": 300
        }

        await cmd_stats(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "130" in call_args[0][0] or "Statistics" in call_args[0][0]

    @pytest.mark.asyncio
    @patch('bottube_bot.api_client')
    @patch('bottube_bot.rate_limiter')
    async def test_cmd_health_success(self, mock_limiter, mock_client, mock_update, mock_context):
        """Test /health command success."""
        from bottube_bot import cmd_health

        mock_limiter.is_allowed.return_value = True
        mock_client.health.return_value = {"ok": True, "version": "1.3.1"}

        await cmd_health(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Online" in call_args[0][0] or "ok" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.rate_limiter')
    async def test_cmd_like_no_args(self, mock_limiter, mock_update, mock_context):
        """Test /like command without arguments."""
        from bottube_bot import cmd_like

        mock_limiter.is_allowed.return_value = True
        mock_context.args = []
        await cmd_like(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.rate_limiter')
    async def test_cmd_like_no_api_key(self, mock_limiter, mock_update, mock_context):
        """Test /like command without API key."""
        from bottube_bot import cmd_like, BOTTUBE_API_KEY

        mock_limiter.is_allowed.return_value = True
        mock_context.args = ["abc123"]
        
        with patch('bottube_bot.BOTTUBE_API_KEY', ''):
            await cmd_like(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "API key" in call_args[0][0] or "api key" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.rate_limiter')
    async def test_cmd_comment_no_args(self, mock_limiter, mock_update, mock_context):
        """Test /comment command without arguments."""
        from bottube_bot import cmd_comment

        mock_limiter.is_allowed.return_value = True
        mock_context.args = []
        await cmd_comment(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @patch('bottube_bot.rate_limiter')
    async def test_cmd_subscribe_no_args(self, mock_limiter, mock_update, mock_context):
        """Test /subscribe command without arguments."""
        from bottube_bot import cmd_subscribe

        mock_limiter.is_allowed.return_value = True
        mock_context.args = []
        await cmd_subscribe(mock_update, mock_context)

        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Usage:" in call_args[0][0] or "usage" in call_args[0][0].lower()


class TestConfiguration:
    """Tests for configuration validation."""

    @patch('bottube_bot.TELEGRAM_BOT_TOKEN', '')
    def test_validate_config_missing_token(self):
        """Test validation fails without bot token."""
        from bottube_bot import validate_config

        result = validate_config()
        assert result is False

    @patch('bottube_bot.TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    def test_validate_config_default_token(self):
        """Test validation fails with default token."""
        from bottube_bot import validate_config

        result = validate_config()
        assert result is False

    @patch('bottube_bot.TELEGRAM_BOT_TOKEN', 'test-token-123')
    def test_validate_config_valid_token(self):
        """Test validation passes with valid token."""
        from bottube_bot import validate_config

        result = validate_config()
        assert result is True


class TestBotCommandsSetup:
    """Tests for bot command setup."""

    def test_set_bot_commands(self):
        """Test bot commands are set correctly."""
        from bottube_bot import set_bot_commands
        from telegram import BotCommand

        commands = set_bot_commands(None)

        assert len(commands) >= 10
        command_names = [c.command for c in commands]
        assert "start" in command_names
        assert "help" in command_names
        assert "trending" in command_names
        assert "search" in command_names
        assert "video" in command_names
        assert "agent" in command_names
        assert "stats" in command_names


class TestHelperFunctions:
    """Tests for helper formatting functions."""

    def test_format_video_card(self):
        """Test video card formatting."""
        from bottube_bot import format_video_card

        video = {
            "video_id": "abc123",
            "title": "Test Video",
            "agent_name": "test-agent",
            "views": 1234,
            "likes": 56,
            "duration": 180,
            "created_at": 1711111111
        }

        message = format_video_card(video)

        assert "Test Video" in message
        assert "test-agent" in message
        assert "1,234" in message
        assert "56" in message

    def test_format_agent_card(self):
        """Test agent card formatting."""
        from bottube_bot import format_agent_card

        agent = {
            "agent_name": "test-agent",
            "display_name": "Test Agent",
            "bio": "Test bio",
            "video_count": 5,
            "total_views": 500,
            "comment_count": 20,
            "total_likes": 50,
            "rtc_balance": 0.045
        }

        message = format_agent_card(agent)

        assert "Test Agent" in message
        assert "test-agent" in message
        assert "5" in message  # video count
        assert "500" in message  # total views

    def test_format_stats_card(self):
        """Test stats card formatting."""
        from bottube_bot import format_stats_card

        stats = {
            "videos": 130,
            "agents": 17,
            "humans": 4,
            "total_views": 1415,
            "total_comments": 701,
            "total_likes": 300
        }

        message = format_stats_card(stats)

        assert "130" in message
        assert "17" in message
        assert "Statistics" in message or "Platform" in message


class TestRateLimiter:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_allows_first_request(self):
        """Test that rate limiter allows first request."""
        from bottube_bot import RateLimiter

        limiter = RateLimiter(max_requests=10)
        assert limiter.is_allowed(12345) is True

    def test_rate_limiter_blocks_after_limit(self):
        """Test that rate limiter blocks after reaching limit."""
        from bottube_bot import RateLimiter

        limiter = RateLimiter(max_requests=2)
        
        # First two requests should be allowed
        assert limiter.is_allowed(12345) is True
        assert limiter.is_allowed(12345) is True
        
        # Third request should be blocked
        assert limiter.is_allowed(12345) is False

    def test_rate_limiter_per_user(self):
        """Test that rate limiting is per-user."""
        from bottube_bot import RateLimiter

        limiter = RateLimiter(max_requests=1)
        
        # User 1 reaches limit
        assert limiter.is_allowed(11111) is True
        assert limiter.is_allowed(11111) is False
        
        # User 2 should still be allowed
        assert limiter.is_allowed(22222) is True


class TestBoTTubeClient:
    """Tests for BoTTube API client."""

    def test_client_initialization(self):
        """Test client initialization."""
        from bottube_bot import BoTTubeClient

        client = BoTTubeClient()
        assert client.base_url.endswith("/ai") or "bottube.ai" in client.base_url

    def test_client_with_api_key(self):
        """Test client initialization with API key."""
        from bottube_bot import BoTTubeClient

        client = BoTTubeClient(api_key="test-key")
        assert client.api_key == "test-key"

    @patch('bottube_bot.requests.Session')
    def test_client_get_request(self, mock_session_class):
        """Test GET request handling."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client._get("/health")

        assert result == {"ok": True}
        mock_session.get.assert_called_once()

    @patch('bottube_bot.requests.Session')
    def test_client_timeout(self, mock_session_class):
        """Test timeout handling."""
        from bottube_bot import BoTTubeClient
        import requests

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.Timeout()

        client = BoTTubeClient()
        result = client._get("/health")

        assert "error" in result
        assert "timeout" in result["error"].lower()
