"""
Pytest configuration and shared fixtures.
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def test_config() -> dict:
    """Shared test configuration."""
    return {
        "app_id": 12345,
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "webhook_secret": "test_webhook_secret",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest_key\n-----END RSA PRIVATE KEY-----",
        "api_base_url": "https://api.github.com",
    }


@pytest.fixture
def sample_comment_payload() -> dict:
    """Sample GitHub comment webhook payload."""
    return {
        "action": "created",
        "comment": {
            "id": 1234567890,
            "body": "This is a test comment",
            "user": {"login": "testuser"},
            "author_association": "NONE",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "issue_url": "https://api.github.com/repos/testorg/testrepo/issues/1",
            "html_url": "https://github.com/testorg/testrepo/issues/1#issuecomment-1234567890",
        },
        "issue": {
            "number": 1,
            "title": "Test Issue",
            "state": "open",
            "labels": [],
            "created_at": "2024-01-15T09:00:00Z",
            "comments": 1,
        },
        "repository": {"full_name": "testorg/testrepo"},
        "installation": {"id": 98765},
    }


@pytest.fixture
def spam_comment_payload() -> dict:
    """Sample spam comment payload."""
    return {
        "action": "created",
        "comment": {
            "id": 9999999999,
            "body": "Check out bit.ly/spam @u1 @u2 @u3 @u4 @u5 @u6 crypto giveaway! Click here!",
            "user": {"login": "spammer123"},
            "author_association": "NONE",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "issue_url": "https://api.github.com/repos/testorg/testrepo/issues/1",
            "html_url": "https://github.com/testorg/testrepo/issues/1#issuecomment-9999999999",
        },
        "issue": {
            "number": 1,
            "title": "Test Issue",
            "state": "open",
            "labels": [],
            "created_at": "2024-01-15T09:00:00Z",
            "comments": 1,
        },
        "repository": {"full_name": "testorg/testrepo"},
        "installation": {"id": 98765},
    }
