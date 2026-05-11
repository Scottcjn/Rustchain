"""
Tests for the Webhook Receiver module.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.config import BotConfig, ScoringConfig, WhitelistConfig
from src.webhook import create_app, verify_webhook_signature


@dataclass
class MockGitHubAppConfig:
    """Mock GitHub App config for tests."""
    app_id: int = 12345
    client_id: str = "test_client_id"
    client_secret: SecretStr = SecretStr("test_secret")
    private_key: SecretStr = SecretStr("-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----")
    webhook_secret: SecretStr = SecretStr("test_webhook_secret")
    api_base_url: str = "https://api.github.com"


@dataclass
class MockWhitelistConfig:
    """Mock whitelist config for tests."""
    def get_trusted_users(self) -> set:
        return set()
    
    def get_trusted_orgs(self) -> set:
        return set()
    
    def get_exempt_repos(self) -> set:
        return set()
    
    def get_exempt_labels(self) -> set:
        return set()


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
    config.host = "0.0.0.0"
    config.port = 8000
    
    # Scoring config
    config.scoring = MagicMock(spec=ScoringConfig)
    config.scoring.auto_delete_threshold = 0.85
    config.scoring.flag_threshold = 0.60
    config.scoring.spam_keywords_weight = 0.25
    config.scoring.link_ratio_weight = 0.20
    config.scoring.length_penalty_weight = 0.10
    config.scoring.repetition_weight = 0.20
    config.scoring.mention_spam_weight = 0.15
    config.scoring.semantic_weight = 0.10
    
    # GitHub App config with real SecretStr
    config.github_app = MockGitHubAppConfig()
    
    # Whitelist config
    config.whitelist = MockWhitelistConfig()
    
    return config


@pytest.fixture
def app(mock_config: MagicMock) -> TestClient:
    """Create test client."""
    fastapi_app = create_app(mock_config)
    return TestClient(fastapi_app)


@pytest.fixture
def sample_webhook_payload() -> dict:
    """Sample GitHub webhook payload."""
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
        "repository": {
            "full_name": "testorg/testrepo",
        },
        "installation": {
            "id": 98765,
        },
    }


def generate_signature(body: bytes, secret: str) -> str:
    """Generate a valid GitHub webhook signature."""
    signature = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


class TestWebhookSignature:
    """Tests for webhook signature verification."""

    def test_valid_signature(self) -> None:
        """Test valid signature verification."""
        body = b'{"test": "data"}'
        secret = "test_secret"
        signature = generate_signature(body, secret)

        assert verify_webhook_signature(body, signature, secret) is True

    def test_invalid_signature(self) -> None:
        """Test invalid signature detection."""
        body = b'{"test": "data"}'
        secret = "test_secret"

        assert verify_webhook_signature(body, "sha256=invalid", secret) is False

    def test_missing_signature(self) -> None:
        """Test missing signature handling."""
        body = b'{"test": "data"}'
        secret = "test_secret"

        assert verify_webhook_signature(body, None, secret) is False

    def test_empty_secret(self) -> None:
        """Test empty secret handling."""
        body = b'{"test": "data"}'

        assert verify_webhook_signature(body, "sha256=abc", "") is False

    def test_sha1_signature(self) -> None:
        """Test SHA1 signature verification."""
        body = b'{"test": "data"}'
        secret = "test_secret"
        signature = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha1,
        ).hexdigest()

        assert verify_webhook_signature(body, f"sha1={signature}", secret) is True


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    def test_health_endpoint(self, app: TestClient) -> None:
        """Test health check endpoint."""
        response = app.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "enabled" in data
        assert "dry_run" in data

    def test_ready_endpoint(self, app: TestClient) -> None:
        """Test readiness endpoint."""
        response = app.get("/ready")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ready"

    def test_webhook_missing_event_header(
        self, app: TestClient, sample_webhook_payload: dict
    ) -> None:
        """Test webhook with missing event header."""
        response = app.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={"X-GitHub-Delivery": "test-delivery-id"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_webhook_missing_delivery_header(
        self, app: TestClient, sample_webhook_payload: dict
    ) -> None:
        """Test webhook with missing delivery header."""
        response = app.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={"X-GitHub-Event": "issue_comment"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_webhook_invalid_signature(
        self, app: TestClient, sample_webhook_payload: dict
    ) -> None:
        """Test webhook with invalid signature."""
        body = json.dumps(sample_webhook_payload).encode()

        response = app.post(
            "/webhook",
            json=sample_webhook_payload,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_webhook_non_issue_comment_event(
        self, app: TestClient, sample_webhook_payload: dict, mock_config: MagicMock
    ) -> None:
        """Test webhook with non-issue_comment event."""
        body = json.dumps(sample_webhook_payload).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        response = app.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "issues",  # Not issue_comment
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_comment_not_created(
        self, app: TestClient, sample_webhook_payload: dict, mock_config: MagicMock
    ) -> None:
        """Test webhook with non-created action."""
        sample_webhook_payload["action"] = "deleted"
        body = json.dumps(sample_webhook_payload).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        response = app.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ignored"


class TestWebhookProcessing:
    """Tests for webhook processing flow."""

    @pytest.mark.asyncio
    async def test_webhook_valid_comment(
        self, app: TestClient, sample_webhook_payload: dict, mock_config: MagicMock
    ) -> None:
        """Test processing a valid comment webhook."""
        body = json.dumps(sample_webhook_payload).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        # Mock the moderation service - access via app.app.state for TestClient
        with patch.object(
            app.app.state.moderation_service,
            "process_comment_event",
            new_callable=AsyncMock,
        ) as mock_process:
            from src.moderation_service import ModerationDecision
            from src.scorer import ScoreBreakdown

            mock_process.return_value = ModerationDecision(
                action="allow",
                risk_score=0.15,
                breakdown=ScoreBreakdown(),
                is_exempt=False,
                dry_run=True,
            )

            response = app.post(
                "/webhook",
                content=body,
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-GitHub-Delivery": "test-delivery-id",
                    "X-Hub-Signature-256": signature,
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "processed"
            assert "action" in data
            assert "risk_score" in data

    @pytest.mark.asyncio
    async def test_webhook_spam_comment(
        self, app: TestClient, mock_config: MagicMock
    ) -> None:
        """Test processing a spam comment webhook."""
        payload = {
            "action": "created",
            "comment": {
                "id": 9999999999,
                "body": "Check out https://bit.ly/spam @user1 @user2 @user3 @user4 @user5 @user6",
                "user": {"login": "spammer"},
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

        body = json.dumps(payload).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        with patch.object(
            app.app.state.moderation_service,
            "process_comment_event",
            new_callable=AsyncMock,
        ) as mock_process:
            from src.moderation_service import ModerationDecision
            from src.scorer import ScoreBreakdown

            mock_process.return_value = ModerationDecision(
                action="delete",
                risk_score=0.92,
                breakdown=ScoreBreakdown(
                    spam_keywords_score=0.6,
                    link_ratio_score=0.8,
                    mention_spam_score=0.7,
                    factors=["spam_keywords", "link_ratio", "mention_spam"],
                ),
                is_exempt=False,
                dry_run=True,
            )

            response = app.post(
                "/webhook",
                content=body,
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-GitHub-Delivery": "spam-delivery-id",
                    "X-Hub-Signature-256": signature,
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["action"] == "delete"
            assert data["risk_score"] > 0.8

    def test_webhook_missing_payload_data(
        self, app: TestClient, mock_config: MagicMock
    ) -> None:
        """Test webhook with missing required payload data."""
        payload = {"action": "created"}  # Missing comment and issue

        body = json.dumps(payload).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        response = app.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_webhook_invalid_json(
        self, app: TestClient, mock_config: MagicMock
    ) -> None:
        """Test webhook with invalid JSON."""
        body = b"not valid json"
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())
        
        response = app.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_webhook_rejects_non_object_json(
        self, app: TestClient, mock_config: MagicMock
    ) -> None:
        """Test webhook with valid JSON that is not an object."""
        body = json.dumps(["not", "an", "object"]).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        response = app.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Webhook payload must be a JSON object"

    @pytest.mark.parametrize(
        ("field", "expected_detail"),
        [
            ("repository", "repository must be a JSON object"),
            ("comment", "comment must be a JSON object"),
            ("issue", "issue must be a JSON object"),
            ("installation", "installation must be a JSON object"),
        ],
    )
    def test_webhook_rejects_non_object_nested_payload_fields(
        self,
        app: TestClient,
        sample_webhook_payload: dict,
        mock_config: MagicMock,
        field: str,
        expected_detail: str,
    ) -> None:
        """Test webhook with malformed nested payload objects."""
        sample_webhook_payload[field] = "not-an-object"
        body = json.dumps(sample_webhook_payload).encode()
        signature = generate_signature(body, mock_config.github_app.webhook_secret.get_secret_value())

        response = app.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == expected_detail
