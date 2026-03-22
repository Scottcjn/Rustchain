"""
Unit tests for BoTTube API client
Issue #2299 - BoTTube Telegram Bot
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBoTTubeClientEndpoints:
    """Tests for BoTTubeClient API endpoints."""

    @patch('bottube_bot.requests.Session')
    def test_health_endpoint(self, mock_session_class):
        """Test health check endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "version": "1.3.1"}
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.health()

        assert result == {"ok": True, "version": "1.3.1"}
        mock_session.get.assert_called_once()

    @patch('bottube_bot.requests.Session')
    def test_trending_endpoint(self, mock_session_class):
        """Test trending videos endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "videos": [
                {"video_id": "abc123", "title": "Trending Video"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.trending(limit=10)

        assert "videos" in result
        mock_session.get.assert_called_once()

    @patch('bottube_bot.requests.Session')
    def test_list_videos_endpoint(self, mock_session_class):
        """Test list videos endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "videos": [
                {"video_id": "abc123", "title": "New Video"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.list_videos(page=1, sort="newest", per_page=10)

        assert "videos" in result

    @patch('bottube_bot.requests.Session')
    def test_search_endpoint(self, mock_session_class):
        """Test search endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "videos": [
                {"video_id": "abc123", "title": "AI Video"}
            ],
            "total": 1
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.search(query="AI robots", page=1, per_page=10)

        assert "videos" in result
        assert result["total"] == 1

    @patch('bottube_bot.requests.Session')
    def test_get_video_endpoint(self, mock_session_class):
        """Test get video endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "video_id": "abc123",
            "title": "Test Video",
            "agent_name": "test-agent"
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.get_video("abc123")

        assert result["video_id"] == "abc123"

    @patch('bottube_bot.requests.Session')
    def test_describe_video_endpoint(self, mock_session_class):
        """Test describe video endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "title": "Test Video",
            "description": "Test description",
            "scene_description": "Scene details"
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.describe_video("abc123")

        assert "description" in result

    @patch('bottube_bot.requests.Session')
    def test_get_comments_endpoint(self, mock_session_class):
        """Test get comments endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "comments": [
                {"id": 1, "content": "Great video!", "agent_name": "user1"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.get_comments("abc123")

        assert "comments" in result

    @patch('bottube_bot.requests.Session')
    def test_get_agent_endpoint(self, mock_session_class):
        """Test get agent endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "agent_name": "test-agent",
            "display_name": "Test Agent",
            "video_count": 5
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.get_agent("test-agent")

        assert result["agent_name"] == "test-agent"

    @patch('bottube_bot.requests.Session')
    def test_get_stats_endpoint(self, mock_session_class):
        """Test get stats endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "videos": 130,
            "agents": 17,
            "total_views": 1415
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.get_stats()

        assert result["videos"] == 130

    @patch('bottube_bot.requests.Session')
    def test_get_categories_endpoint(self, mock_session_class):
        """Test get categories endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {
            "categories": ["ai-art", "education", "tech"]
        }
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        client = BoTTubeClient()
        result = client.get_categories()

        assert "categories" in result
        assert len(result["categories"]) == 3

    @patch('bottube_bot.requests.Session')
    def test_like_video_endpoint(self, mock_session_class):
        """Test like video endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response

        client = BoTTubeClient(api_key="test-key")
        result = client.like_video("abc123", vote=1)

        assert result["ok"] is True
        mock_session.post.assert_called_once()

    @patch('bottube_bot.requests.Session')
    def test_comment_on_video_endpoint(self, mock_session_class):
        """Test comment on video endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response

        client = BoTTubeClient(api_key="test-key")
        result = client.comment_on_video("abc123", "Great video!")

        assert result["ok"] is True

    @patch('bottube_bot.requests.Session')
    def test_subscribe_agent_endpoint(self, mock_session_class):
        """Test subscribe agent endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "follower_count": 5}
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response

        client = BoTTubeClient(api_key="test-key")
        result = client.subscribe_agent("test-agent")

        assert result["ok"] is True
        assert result["follower_count"] == 5

    @patch('bottube_bot.requests.Session')
    def test_record_view_endpoint(self, mock_session_class):
        """Test record view endpoint."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response

        client = BoTTubeClient()
        result = client.record_view("abc123")

        assert result["ok"] is True


class TestBoTTubeClientErrors:
    """Tests for error handling in BoTTubeClient."""

    @patch('bottube_bot.requests.Session')
    def test_timeout_error(self, mock_session_class):
        """Test timeout error handling."""
        from bottube_bot import BoTTubeClient
        import requests

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.Timeout()

        client = BoTTubeClient()
        result = client.health()

        assert "error" in result
        assert "timeout" in result["error"].lower()

    @patch('bottube_bot.requests.Session')
    def test_connection_error(self, mock_session_class):
        """Test connection error handling."""
        from bottube_bot import BoTTubeClient
        import requests

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        client = BoTTubeClient()
        result = client.health()

        assert "error" in result

    @patch('bottube_bot.requests.Session')
    def test_http_error(self, mock_session_class):
        """Test HTTP error handling."""
        from bottube_bot import BoTTubeClient
        import requests

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session.get.side_effect = mock_response.raise_for_status

        client = BoTTubeClient()
        result = client.health()

        assert "error" in result

    def test_interactions_require_api_key(self):
        """Test that interactions require API key."""
        from bottube_bot import BoTTubeClient

        client = BoTTubeClient()  # No API key
        result = client.like_video("abc123", vote=1)

        assert "error" in result
        assert "API key" in result["error"]

    @patch('bottube_bot.requests.Session')
    def test_general_exception_handling(self, mock_session_class):
        """Test general exception handling."""
        from bottube_bot import BoTTubeClient

        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = Exception("Unexpected error")

        client = BoTTubeClient()
        result = client.health()

        assert "error" in result
