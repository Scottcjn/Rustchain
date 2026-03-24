"""
Tests for the Delete Action and Moderation Service.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.audit_logger import AuditLogger
from src.config import BotConfig, ScoringConfig, WhitelistConfig
from src.feature_extractor import CommentFeatures
from src.github_auth import GitHubAuth
from src.moderation_service import (
    ModerationContext,
    ModerationDecision,
    ModerationService,
)
from src.scorer import ScoreBreakdown


@pytest.fixture
def mock_config() -> BotConfig:
    """Create a mock configuration."""
    config = MagicMock(spec=BotConfig)
    config.enabled = True
    config.dry_run = True
    config.log_dir = "./test_logs"
    config.log_level = "DEBUG"
    config.delivery_cache_ttl_seconds = 3600
    config.enable_semantic_classifier = False
    config.semantic_classifier_endpoint = None
    config.scoring = MagicMock(spec=ScoringConfig)
    config.scoring.auto_delete_threshold = 0.85
    config.scoring.flag_threshold = 0.60
    config.scoring.spam_keywords_weight = 0.25
    config.scoring.link_ratio_weight = 0.20
    config.scoring.length_penalty_weight = 0.10
    config.scoring.repetition_weight = 0.20
    config.scoring.mention_spam_weight = 0.15
    config.scoring.semantic_weight = 0.10
    config.whitelist = MagicMock(spec=WhitelistConfig)
    config.whitelist.get_trusted_users.return_value = set()
    config.whitelist.get_trusted_orgs.return_value = set()
    config.whitelist.get_exempt_repos.return_value = set()
    config.whitelist.get_exempt_labels.return_value = set()
    config.github_app = MagicMock()
    config.github_app.api_base_url = "https://api.github.com"
    return config


@pytest.fixture
def mock_auth() -> GitHubAuth:
    """Create a mock GitHub auth."""
    auth = MagicMock(spec=GitHubAuth)
    auth.get_auth_headers = AsyncMock(return_value={"Authorization": "Bearer token"})
    return auth


@pytest.fixture
def mock_audit_logger() -> AuditLogger:
    """Create a mock audit logger."""
    logger = MagicMock(spec=AuditLogger)
    logger.log_action = MagicMock()
    logger.log_error = MagicMock()
    logger.log_webhook_event = MagicMock()
    return logger


@pytest.fixture
def sample_comment_data() -> dict:
    """Sample comment data."""
    return {
        "id": 1234567890,
        "body": "This is a test comment",
        "user": {"login": "testuser"},
        "author_association": "NONE",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
        "issue_url": "https://api.github.com/repos/testorg/testrepo/issues/1",
        "html_url": "https://github.com/testorg/testrepo/issues/1#issuecomment-1234567890",
    }


@pytest.fixture
def sample_issue_data() -> dict:
    """Sample issue data."""
    return {
        "number": 1,
        "title": "Test Issue",
        "state": "open",
        "labels": [],
        "created_at": "2024-01-15T09:00:00Z",
        "comments": 1,
    }


class TestModerationService:
    """Tests for ModerationService."""

    @pytest.mark.asyncio
    async def test_process_comment_allowed(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
        sample_comment_data: dict,
        sample_issue_data: dict,
    ) -> None:
        """Test processing a comment that should be allowed."""
        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        decision = await service.process_comment_event(
            comment_data=sample_comment_data,
            issue_data=sample_issue_data,
            delivery_id="test-delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        assert decision.action == "allow"
        assert decision.dry_run is True

    @pytest.mark.asyncio
    async def test_process_comment_disabled_bot(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
        sample_comment_data: dict,
        sample_issue_data: dict,
    ) -> None:
        """Test processing when bot is disabled."""
        mock_config.enabled = False

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        decision = await service.process_comment_event(
            comment_data=sample_comment_data,
            issue_data=sample_issue_data,
            delivery_id="test-delivery-2",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        assert decision.action == "allow"
        assert decision.exemption_reason == "Bot is disabled"

    @pytest.mark.asyncio
    async def test_process_duplicate_delivery(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
        sample_comment_data: dict,
        sample_issue_data: dict,
    ) -> None:
        """Test processing duplicate delivery (replay protection)."""
        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        # First delivery
        decision1 = await service.process_comment_event(
            comment_data=sample_comment_data,
            issue_data=sample_issue_data,
            delivery_id="test-delivery-3",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        # Second delivery with same ID
        decision2 = await service.process_comment_event(
            comment_data=sample_comment_data,
            issue_data=sample_issue_data,
            delivery_id="test-delivery-3",  # Same delivery ID
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        assert decision2.exemption_reason == "Duplicate delivery (replay)"

    @pytest.mark.asyncio
    async def test_process_whitelisted_user(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
        sample_comment_data: dict,
        sample_issue_data: dict,
    ) -> None:
        """Test processing comment from whitelisted user."""
        # Configure trusted user
        mock_config.whitelist.get_trusted_users.return_value = {"testuser"}

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        decision = await service.process_comment_event(
            comment_data=sample_comment_data,
            issue_data=sample_issue_data,
            delivery_id="test-delivery-4",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        assert decision.is_exempt is True
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_process_high_risk_comment(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
        sample_issue_data: dict,
    ) -> None:
        """Test processing high-risk comment."""
        # Spam comment with multiple risk factors
        comment_data = {
            "id": 9999999999,
            "body": "Check out https://bit.ly/spam @u1 @u2 @u3 @u4 @u5 @u6 @u7 @u8 crypto giveaway! Click here!",
            "user": {"login": "spammer"},
            "author_association": "NONE",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "issue_url": "https://api.github.com/repos/testorg/testrepo/issues/1",
            "html_url": "https://github.com/testorg/testrepo/issues/1#issuecomment-9999999999",
        }

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        decision = await service.process_comment_event(
            comment_data=comment_data,
            issue_data=sample_issue_data,
            delivery_id="test-delivery-5",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        # Should have elevated risk score (but may not exceed 0.5 with default weights)
        assert decision.risk_score > 0.2
        assert decision.dry_run is True

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
    ) -> None:
        """Test getting service statistics."""
        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        stats = service.get_stats()

        assert stats["enabled"] is True
        assert stats["dry_run"] is True
        assert "delivery_cache" in stats
        assert "thresholds" in stats


class TestDeleteAction:
    """Tests for comment deletion action."""

    @pytest.mark.asyncio
    async def test_delete_dry_run(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
    ) -> None:
        """Test delete action in dry-run mode."""
        mock_config.dry_run = True  # Ensure dry run is enabled

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        # Create a decision to delete
        decision = ModerationDecision(
            action="delete",
            risk_score=0.95,
            breakdown=ScoreBreakdown(),
            is_exempt=False,
            dry_run=True,
        )

        # Create context
        from src.github_client import CommentData, IssueData

        comment = CommentData(
            id=12345,
            body="spam",
            author_login="spammer",
            author_association="NONE",
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z",
            issue_url="https://api.github.com/repos/testorg/testrepo/issues/1",
            html_url="https://github.com/testorg/testrepo/issues/1#issuecomment-12345",
        )

        issue = IssueData(
            number=1,
            title="Test",
            state="open",
            labels=[],
            created_at="2024-01-15T09:00:00Z",
            comments_count=1,
        )

        context = ModerationContext(
            comment=comment,
            issue=issue,
            delivery_id="test-delivery",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        # Execute action
        result = await service._execute_action(decision, context)

        # Should not actually delete in dry-run mode
        assert result is False
        mock_audit_logger.log_action.assert_called()

    @pytest.mark.asyncio
    async def test_delete_live_mode(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
    ) -> None:
        """Test delete action in live mode."""
        mock_config.dry_run = False  # Live mode

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        # Mock the GitHub client
        service.github_client.delete_comment = AsyncMock(return_value=True)

        # Create a decision to delete
        decision = ModerationDecision(
            action="delete",
            risk_score=0.95,
            breakdown=ScoreBreakdown(),
            is_exempt=False,
            dry_run=False,
        )

        from src.github_client import CommentData, IssueData

        comment = CommentData(
            id=12345,
            body="spam",
            author_login="spammer",
            author_association="NONE",
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z",
            issue_url="https://api.github.com/repos/testorg/testrepo/issues/1",
            html_url="https://github.com/testorg/testrepo/issues/1#issuecomment-12345",
        )

        issue = IssueData(
            number=1,
            title="Test",
            state="open",
            labels=[],
            created_at="2024-01-15T09:00:00Z",
            comments_count=1,
        )

        context = ModerationContext(
            comment=comment,
            issue=issue,
            delivery_id="test-delivery",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        # Execute action
        result = await service._execute_action(decision, context)

        # Should delete in live mode
        assert result is True
        service.github_client.delete_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_failure(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
    ) -> None:
        """Test delete action failure handling."""
        mock_config.dry_run = False

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        # Mock the GitHub client to fail
        service.github_client.delete_comment = AsyncMock(return_value=False)

        decision = ModerationDecision(
            action="delete",
            risk_score=0.95,
            breakdown=ScoreBreakdown(),
            is_exempt=False,
            dry_run=False,
        )

        from src.github_client import CommentData, IssueData

        comment = CommentData(
            id=12345,
            body="spam",
            author_login="spammer",
            author_association="NONE",
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z",
            issue_url="https://api.github.com/repos/testorg/testrepo/issues/1",
            html_url="https://github.com/testorg/testrepo/issues/1#issuecomment-12345",
        )

        issue = IssueData(
            number=1,
            title="Test",
            state="open",
            labels=[],
            created_at="2024-01-15T09:00:00Z",
            comments_count=1,
        )

        context = ModerationContext(
            comment=comment,
            issue=issue,
            delivery_id="test-delivery",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        result = await service._execute_action(decision, context)

        assert result is False
        mock_audit_logger.log_error.assert_called()

    @pytest.mark.asyncio
    async def test_delete_exception(
        self,
        mock_config: BotConfig,
        mock_auth: GitHubAuth,
        mock_audit_logger: AuditLogger,
    ) -> None:
        """Test delete action exception handling."""
        mock_config.dry_run = False

        service = ModerationService(
            config=mock_config,
            github_auth=mock_auth,
            audit_logger=mock_audit_logger,
        )

        # Mock the GitHub client to raise exception
        service.github_client.delete_comment = AsyncMock(
            side_effect=Exception("API Error")
        )

        decision = ModerationDecision(
            action="delete",
            risk_score=0.95,
            breakdown=ScoreBreakdown(),
            is_exempt=False,
            dry_run=False,
        )

        from src.github_client import CommentData, IssueData

        comment = CommentData(
            id=12345,
            body="spam",
            author_login="spammer",
            author_association="NONE",
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z",
            issue_url="https://api.github.com/repos/testorg/testrepo/issues/1",
            html_url="https://github.com/testorg/testrepo/issues/1#issuecomment-12345",
        )

        issue = IssueData(
            number=1,
            title="Test",
            state="open",
            labels=[],
            created_at="2024-01-15T09:00:00Z",
            comments_count=1,
        )

        context = ModerationContext(
            comment=comment,
            issue=issue,
            delivery_id="test-delivery",
            event_type="issue_comment",
            repo="testorg/testrepo",
            installation_id=98765,
        )

        result = await service._execute_action(decision, context)

        assert result is False
        mock_audit_logger.log_error.assert_called()


class TestModerationDecision:
    """Tests for ModerationDecision dataclass."""

    def test_decision_allow(self) -> None:
        """Test allow decision."""
        decision = ModerationDecision(
            action="allow",
            risk_score=0.1,
            breakdown=ScoreBreakdown(),
            is_exempt=False,
        )

        assert decision.action == "allow"
        assert decision.risk_score == 0.1

    def test_decision_delete(self) -> None:
        """Test delete decision."""
        decision = ModerationDecision(
            action="delete",
            risk_score=0.95,
            breakdown=ScoreBreakdown(factors=["spam", "links"]),
            is_exempt=False,
            dry_run=False,
        )

        assert decision.action == "delete"
        assert decision.dry_run is False
        assert len(decision.breakdown.factors) == 2
