"""
Tests for Audit Logger and GitHub Auth modules.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audit_logger import AuditLogger, JSONLFormatter
from src.scorer import ScoreBreakdown


class TestAuditLogger:
    """Tests for AuditLogger."""

    @pytest.fixture
    def temp_log_dir(self) -> Path:
        """Create a temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_init_creates_directory(self, temp_log_dir: Path) -> None:
        """Test that logger creates log directory."""
        log_path = temp_log_dir / "subdir"
        logger = AuditLogger(log_dir=str(log_path))

        assert log_path.exists()
        assert log_path.is_dir()

    def test_log_action(self, temp_log_dir: Path) -> None:
        """Test logging an action."""
        logger = AuditLogger(log_dir=str(temp_log_dir))

        logger.log_action(
            action="deleted",
            comment_id=12345,
            repo="testorg/testrepo",
            issue_number=1,
            risk_score=0.95,
            author="spammer",
            decision="auto",
            dry_run=False,
            delivery_id="test-delivery",
        )

        # Check log file exists
        log_file = logger.get_log_path()
        assert log_file.exists()

        # Check log content
        content = log_file.read_text()
        assert "deleted" in content
        assert "12345" in content
        assert "testorg/testrepo" in content

    def test_log_action_with_breakdown(self, temp_log_dir: Path) -> None:
        """Test logging with score breakdown."""
        logger = AuditLogger(log_dir=str(temp_log_dir))

        breakdown = ScoreBreakdown(
            spam_keywords_score=0.8,
            link_ratio_score=0.6,
            factors=["spam_keywords", "link_ratio"],
        )

        logger.log_action(
            action="flagged",
            comment_id=12345,
            repo="testorg/testrepo",
            issue_number=1,
            risk_score=0.72,
            breakdown=breakdown,
            author="spammer",
            decision="auto",
            dry_run=True,
            delivery_id="test-delivery",
        )

        log_file = logger.get_log_path()
        content = log_file.read_text()

        assert "score_breakdown" in content
        assert "spam_keywords" in content

    def test_log_webhook_event(self, temp_log_dir: Path) -> None:
        """Test logging webhook event."""
        logger = AuditLogger(log_dir=str(temp_log_dir))

        logger.log_webhook_event(
            event_type="issue_comment",
            delivery_id="test-delivery",
            repo="testorg/testrepo",
            action="created",
            payload_summary={"comment_id": 12345},
        )

        log_file = logger.get_log_path()
        content = log_file.read_text()

        assert "webhook_received" in content
        assert "issue_comment" in content

    def test_log_error(self, temp_log_dir: Path) -> None:
        """Test logging error."""
        logger = AuditLogger(log_dir=str(temp_log_dir))

        logger.log_error(
            error_type="delete_error",
            message="Failed to delete comment",
            comment_id=12345,
            repo="testorg/testrepo",
            delivery_id="test-delivery",
            traceback="Traceback...",
        )

        log_file = logger.get_log_path()
        content = log_file.read_text()

        assert "error" in content
        assert "delete_error" in content

    def test_jsonl_format(self, temp_log_dir: Path) -> None:
        """Test that logs are in JSONL format."""
        logger = AuditLogger(log_dir=str(temp_log_dir))

        logger.log_action(
            action="deleted",
            comment_id=12345,
            repo="testorg/testrepo",
            issue_number=1,
            risk_score=0.95,
        )

        log_file = logger.get_log_path()
        lines = log_file.read_text().strip().split("\n")

        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "action" in data

    def test_multiple_actions(self, temp_log_dir: Path) -> None:
        """Test logging multiple actions."""
        logger = AuditLogger(log_dir=str(temp_log_dir))

        for i in range(5):
            logger.log_action(
                action="allow",
                comment_id=i,
                repo="testorg/testrepo",
                issue_number=1,
                risk_score=0.1,
            )

        log_file = logger.get_log_path()
        lines = log_file.read_text().strip().split("\n")

        assert len(lines) == 5


class TestJSONLFormatter:
    """Tests for JSONLFormatter."""

    def test_format_json_message(self) -> None:
        """Test formatting JSON message."""
        formatter = JSONLFormatter()

        # Create a log record with JSON message
        import logging

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg='{"key": "value"}',
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["key"] == "value"

    def test_format_standard_message(self) -> None:
        """Test formatting standard message."""
        formatter = JSONLFormatter()

        import logging

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Standard message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "level" in data
        assert "message" in data


class TestGitHubAuth:
    """Tests for GitHubAuth."""

    @pytest.fixture
    def auth(self) -> "GitHubAuth":
        """Create GitHubAuth instance."""
        from src.github_auth import GitHubAuth

        return GitHubAuth(
            app_id=12345,
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            client_id="test_client",
            client_secret="test_secret",
            api_base_url="https://api.github.com",
        )

    def test_init(self, auth: "GitHubAuth") -> None:
        """Test initialization."""
        assert auth.app_id == 12345
        assert auth.client_id == "test_client"
        assert auth.api_base_url == "https://api.github.com"

    @pytest.mark.asyncio
    async def test_get_app_token(self, auth: "GitHubAuth") -> None:
        """Test getting app token."""
        # This will fail with invalid key, but tests the flow
        with patch("jwt.encode") as mock_encode:
            mock_encode.return_value = "fake_jwt_token"

            token = await auth.get_app_token()

            assert token == "fake_jwt_token"
            mock_encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_installation_token_cached(self, auth: "GitHubAuth") -> None:
        """Test installation token caching."""
        # Pre-populate cache
        from datetime import datetime, timedelta

        future = datetime.now() + timedelta(hours=1)
        auth._installation_tokens[98765] = {
            "token": "cached_token",
            "expires_at": future,
        }

        token = await auth.get_installation_token(98765)

        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_get_installation_token_refresh(self, auth: "GitHubAuth") -> None:
        """Test installation token refresh."""
        # Pre-populate cache with expired token
        from datetime import datetime, timedelta

        past = datetime.now() - timedelta(hours=1)
        auth._installation_tokens[98765] = {
            "token": "expired_token",
            "expires_at": past,
        }

        with patch.object(auth, "get_app_token", return_value="fake_jwt"):
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "token": "new_token",
                    "expires_at": "2024-12-31T23:59:59Z",
                }
                mock_post.return_value = mock_response

                token = await auth.get_installation_token(98765, refresh=True)

                assert token == "new_token"

    def test_invalidate_token(self, auth: "GitHubAuth") -> None:
        """Test token invalidation."""
        # Add tokens
        auth._installation_tokens[98765] = {"token": "token1", "expires_at": None}
        auth._installation_tokens[98766] = {"token": "token2", "expires_at": None}
        auth._app_token = {"token": "app_token", "expires_at": None}

        # Invalidate specific installation
        auth.invalidate_token(98765)

        assert 98765 not in auth._installation_tokens
        assert 98766 in auth._installation_tokens

        # Invalidate all
        auth.invalidate_token()

        assert len(auth._installation_tokens) == 0
        assert auth._app_token is None

    def test_generate_jwt(self, auth: "GitHubAuth") -> None:
        """Test JWT generation."""
        with patch("jwt.encode") as mock_encode:
            mock_encode.return_value = "fake_jwt"

            token = auth.generate_jwt()

            assert token == "fake_jwt"
            mock_encode.assert_called_once()

    def test_generate_jwt_max_expiration(self, auth: "GitHubAuth") -> None:
        """Test JWT max expiration clamping."""
        with patch("jwt.encode") as mock_encode:
            mock_encode.return_value = "fake_jwt"

            # Try to generate with 1 hour expiration (should be clamped to 10 min)
            auth.generate_jwt(expiration_seconds=3600)

            # Check the payload passed to jwt.encode
            call_args = mock_encode.call_args
            payload = call_args[0][0]

            # Expiration should be at most 600 seconds from issued at
            assert payload["exp"] - payload["iat"] <= 600
