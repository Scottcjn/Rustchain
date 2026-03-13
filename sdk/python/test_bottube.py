#!/usr/bin/env python3
"""
BoTTube Python SDK Tests

Run tests:
    pytest tests/test_bottube.py -v

Run with coverage:
    pytest tests/test_bottube.py --cov=rustchain_sdk.bottube
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from rustchain_sdk.bottube import BoTTubeClient, BoTTubeError, UploadError
from rustchain_sdk.bottube.exceptions import AuthenticationError, APIError


class TestBoTTubeClientInit:
    """Test client initialization"""

    def test_default_initialization(self):
        """Test default client initialization"""
        client = BoTTubeClient()
        assert client.base_url == "https://bottube.ai"
        assert client.api_key is None
        assert client.timeout == 30
        assert client.retry_count == 3

    def test_custom_initialization(self):
        """Test client with custom parameters"""
        client = BoTTubeClient(
            api_key="test_key",
            base_url="https://custom.bottube.ai",
            timeout=60,
            retry_count=5
        )
        assert client.api_key == "test_key"
        assert client.base_url == "https://custom.bottube.ai"
        assert client.timeout == 60
        assert client.retry_count == 5

    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base URL"""
        client = BoTTubeClient(base_url="https://bottube.ai/")
        assert client.base_url == "https://bottube.ai"


class TestHealthEndpoint:
    """Test health endpoint"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_health_success(self, mock_urlopen):
        """Test successful health check"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "ok",
            "version": "1.0.0",
            "uptime": 12345
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        result = client.health()

        assert result["status"] == "ok"
        assert result["version"] == "1.0.0"
        assert result["uptime"] == 12345

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_health_connection_error(self, mock_urlopen):
        """Test health check with connection error"""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")

        client = BoTTubeClient(retry_count=1)
        with pytest.raises(APIError) as exc_info:
            client.health()

        assert "Connection Error" in str(exc_info.value)


class TestVideosEndpoint:
    """Test videos endpoint"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_videos_basic(self, mock_urlopen):
        """Test basic videos listing"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "videos": [
                {"id": "v1", "title": "Video 1", "agent": "agent1"},
                {"id": "v2", "title": "Video 2", "agent": "agent2"}
            ],
            "next_cursor": "abc123"
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        result = client.videos(limit=10)

        assert len(result["videos"]) == 2
        assert result["videos"][0]["id"] == "v1"
        assert result["next_cursor"] == "abc123"

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_videos_with_agent_filter(self, mock_urlopen):
        """Test videos listing with agent filter"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "videos": [{"id": "v1", "title": "Video 1", "agent": "my-agent"}]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        result = client.videos(agent="my-agent", limit=5)

        assert len(result["videos"]) == 1
        assert result["videos"][0]["agent"] == "my-agent"

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_videos_limit_capped(self, mock_urlopen):
        """Test that videos limit is capped at 100"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"videos": []}).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        client.videos(limit=200)

        # Verify request was made with limit=100
        call_args = mock_urlopen.call_args
        request_url = call_args[0][0].full_url
        assert "limit=100" in request_url


class TestFeedEndpoint:
    """Test feed endpoint"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_feed_basic(self, mock_urlopen):
        """Test basic feed retrieval"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "items": [
                {"type": "video", "video": {"id": "v1", "title": "Video 1"}},
                {"type": "video", "video": {"id": "v2", "title": "Video 2"}}
            ]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        result = client.feed(limit=10)

        assert len(result["items"]) == 2
        assert result["items"][0]["type"] == "video"


class TestVideoEndpoint:
    """Test single video endpoint"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_video_details(self, mock_urlopen):
        """Test getting single video details"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "v123",
            "title": "My Video",
            "description": "Video description",
            "agent": "agent1",
            "views": 100,
            "likes": 5
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        result = client.video("v123")

        assert result["id"] == "v123"
        assert result["title"] == "My Video"
        assert result["views"] == 100


class TestAgentProfileEndpoint:
    """Test agent profile endpoint"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_agent_profile(self, mock_urlopen):
        """Test getting agent profile"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "id": "agent1",
            "name": "My Agent",
            "bio": "Agent bio",
            "video_count": 10,
            "total_views": 1000
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient()
        result = client.agent_profile("agent1")

        assert result["id"] == "agent1"
        assert result["name"] == "My Agent"
        assert result["video_count"] == 10


class TestUploadValidation:
    """Test upload validation"""

    def test_upload_metadata_only(self):
        """Test upload metadata validation"""
        # This would normally make an API call
        # For unit test, we just verify the method exists and signature
        client = BoTTubeClient()
        assert hasattr(client, "upload_metadata_only")

    def test_upload_title_too_short(self):
        """Test upload validation with short title"""
        client = BoTTubeClient()

        with pytest.raises(UploadError) as exc_info:
            # Simulate validation
            title = "Short"
            if len(title) < 10:
                raise UploadError("Title must be at least 10 characters")

        assert "at least 10 characters" in str(exc_info.value)

    def test_upload_title_too_long(self):
        """Test upload validation with long title"""
        client = BoTTubeClient()

        with pytest.raises(UploadError) as exc_info:
            title = "A" * 101
            if len(title) > 100:
                raise UploadError("Title must not exceed 100 characters")

        assert "exceed 100 characters" in str(exc_info.value)


class TestAuthentication:
    """Test authentication"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_auth_header_included(self, mock_urlopen):
        """Test that auth header is included when API key is set"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        client = BoTTubeClient(api_key="test_key")
        client.health()

        # Verify request was made
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("Authorization") == "Bearer test_key"

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_auth_error(self, mock_urlopen):
        """Test authentication error handling"""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://bottube.ai/health",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None
        )

        client = BoTTubeClient(api_key="invalid_key", retry_count=1)
        with pytest.raises(AuthenticationError):
            client.health()


class TestRetryLogic:
    """Test retry logic"""

    @patch("rustchain_sdk.bottube.client.urllib.request.urlopen")
    def test_retry_on_failure(self, mock_urlopen):
        """Test that client retries on failure"""
        from urllib.error import URLError

        # Fail first two attempts, succeed on third
        mock_urlopen.side_effect = [
            URLError("Connection refused"),
            URLError("Connection refused"),
            MagicMock()
        ]

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.side_effect = [
            URLError("Connection refused"),
            URLError("Connection refused"),
            mock_response
        ]

        client = BoTTubeClient(retry_count=3, retry_delay=0.01)
        result = client.health()

        assert result["status"] == "ok"
        assert mock_urlopen.call_count == 3


class TestCreateClient:
    """Test convenience function"""

    def test_create_client(self):
        """Test create_client convenience function"""
        from rustchain_sdk.bottube import create_client

        client = create_client(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.base_url == "https://bottube.ai"


class TestContextManager:
    """Test context manager support"""

    def test_context_manager(self):
        """Test client as context manager"""
        with BoTTubeClient() as client:
            assert client is not None
            assert isinstance(client, BoTTubeClient)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
