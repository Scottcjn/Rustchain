"""
Pytest configuration and fixtures for BoTTube Telegram Bot tests
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture
def mock_update():
    """Create a mock update object."""
    update = Mock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_message = update.message
    return update


@pytest.fixture
def mock_context():
    """Create a mock context object."""
    context = Mock()
    context.args = []
    return context


@pytest.fixture
def mock_callback_query():
    """Create a mock callback query object."""
    query = Mock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "test_data"
    return query


@pytest.fixture
def mock_video_data():
    """Sample video data for testing."""
    return {
        "video_id": "abc123",
        "title": "Test Video",
        "agent_name": "test-agent",
        "views": 100,
        "likes": 10,
        "duration": 180,
        "created_at": 1711111111,
        "description": "A test video description"
    }


@pytest.fixture
def mock_agent_data():
    """Sample agent data for testing."""
    return {
        "agent_name": "test-agent",
        "display_name": "Test Agent",
        "bio": "A test agent bio",
        "video_count": 5,
        "total_views": 500,
        "comment_count": 20,
        "total_likes": 50,
        "rtc_balance": 0.045
    }


@pytest.fixture
def mock_stats_data():
    """Sample platform statistics for testing."""
    return {
        "videos": 130,
        "agents": 17,
        "humans": 4,
        "total_views": 1415,
        "total_comments": 701,
        "total_likes": 300
    }


@pytest.fixture
def mock_health_data():
    """Sample health check data."""
    return {
        "ok": True,
        "version": "1.3.1"
    }
