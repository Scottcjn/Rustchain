"""
Unit tests for RustChainClient
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rustchain_query_bot import RustChainClient, RateLimiter


class TestRustChainClient:
    """Tests for RustChainClient class."""

    def test_init_default_values(self):
        """Test client initialization with default values."""
        client = RustChainClient()
        assert client.base_url == "https://50.28.86.131"
        assert client.verify_ssl is False

    def test_init_custom_values(self):
        """Test client initialization with custom values."""
        client = RustChainClient(base_url="https://custom.api.com", verify_ssl=True)
        assert client.base_url == "https://custom.api.com"
        assert client.verify_ssl is True

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base URL."""
        client = RustChainClient(base_url="https://api.com/")
        assert client.base_url == "https://api.com"

    @patch('rustchain_query_bot.requests.Session')
    def test_health_success(self, mock_session_class):
        """Test health endpoint success."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "version": "2.2.1"}
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        client = RustChainClient()
        result = client.health()

        assert result == {"ok": True, "version": "2.2.1"}
        mock_session.get.assert_called_once_with(
            "https://50.28.86.131/health",
            params=None,
            timeout=15
        )

    @patch('rustchain_query_bot.requests.Session')
    def test_health_timeout(self, mock_session_class):
        """Test health endpoint timeout."""
        import requests
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.Timeout()

        client = RustChainClient()
        result = client.health()

        assert "error" in result
        assert "timeout" in result["error"].lower()

    @patch('rustchain_query_bot.requests.Session')
    def test_health_connection_error(self, mock_session_class):
        """Test health endpoint connection error."""
        import requests
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        client = RustChainClient()
        result = client.health()

        assert "error" in result
        assert "connection" in result["error"].lower()

    @patch('rustchain_query_bot.requests.Session')
    def test_epoch_success(self, mock_session_class):
        """Test epoch endpoint success."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.json.return_value = {"epoch": 95, "slot": 12345, "height": 67890}
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        client = RustChainClient()
        result = client.epoch()

        assert result == {"epoch": 95, "slot": 12345, "height": 67890}

    @patch('rustchain_query_bot.requests.Session')
    def test_balance_success(self, mock_session_class):
        """Test balance endpoint success."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "amount_i64": 155000000,
            "amount_rtc": 155.0,
            "miner_id": "Ivan-houzhiwen"
        }
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        client = RustChainClient()
        result = client.balance("Ivan-houzhiwen")

        assert result["amount_rtc"] == 155.0
        assert result["miner_id"] == "Ivan-houzhiwen"
        mock_session.get.assert_called_once()

    @patch('rustchain_query_bot.requests.Session')
    def test_miners_success(self, mock_session_class):
        """Test miners endpoint success."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.json.return_value = ["miner1", "miner2", "miner3"]
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        client = RustChainClient()
        result = client.miners()

        assert result == ["miner1", "miner2", "miner3"]


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_default_limit(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        assert limiter.max_requests == 10  # Default from config
        assert limiter.min_interval_seconds == 5

    def test_init_custom_limit(self):
        """Test rate limiter with custom limit."""
        limiter = RateLimiter(max_requests=5)
        assert limiter.max_requests == 5

    def test_first_request_allowed(self):
        """Test that first request is always allowed."""
        limiter = RateLimiter(max_requests=5)
        assert limiter.is_allowed(user_id=123) is True

    def test_requests_within_limit_allowed(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter(max_requests=3, min_interval_seconds=0)
        
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is True

    def test_requests_exceeding_limit_blocked(self):
        """Test that requests exceeding limit are blocked."""
        limiter = RateLimiter(max_requests=2, min_interval_seconds=0)
        
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is False

    def test_different_users_independent(self):
        """Test that rate limits are per-user."""
        limiter = RateLimiter(max_requests=1, min_interval_seconds=0)
        
        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(123) is False
        assert limiter.is_allowed(456) is True  # Different user

    @patch('time.time')
    def test_old_requests_expire(self, mock_time):
        """Test that old requests are cleaned up."""
        mock_time.return_value = 1000.0
        
        limiter = RateLimiter(max_requests=2, min_interval_seconds=0)
        limiter.is_allowed(123)  # Request at t=1000
        limiter.is_allowed(123)  # Request at t=1000
        
        # At this point, user should be rate limited
        assert limiter.is_allowed(123) is False
        
        # Advance time by 61 seconds (past the 60-second window)
        mock_time.return_value = 1061.0
        
        # Now the request should be allowed again
        assert limiter.is_allowed(123) is True

    @patch('time.time')
    def test_minimum_interval_blocks_rapid_repeat(self, mock_time):
        """Test 1-request-per-5-seconds throttle."""
        limiter = RateLimiter(max_requests=10, min_interval_seconds=5)

        mock_time.return_value = 1000.0
        assert limiter.is_allowed(123) is True

        mock_time.return_value = 1004.0
        assert limiter.is_allowed(123) is False

        mock_time.return_value = 1005.0
        assert limiter.is_allowed(123) is True
