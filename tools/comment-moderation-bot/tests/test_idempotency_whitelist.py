"""
Tests for Idempotency and Whitelist modules.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.idempotency import DeliveryCache, IdempotencyHandler
from src.whitelist import WhitelistChecker, WhitelistCheckResult


class TestDeliveryCache:
    """Tests for DeliveryCache."""

    def test_record_and_check(self) -> None:
        """Test recording and checking deliveries."""
        cache = DeliveryCache(ttl_seconds=3600)

        # Record a delivery
        cache.record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
            action_taken="allow",
        )

        # Check if duplicate
        assert cache.is_duplicate(
            "delivery-1", "issue_comment", "testorg/testrepo", 12345
        ) is True

        # Different delivery ID should not be duplicate
        assert cache.is_duplicate(
            "delivery-2", "issue_comment", "testorg/testrepo", 12345
        ) is False

    def test_different_comment_same_delivery(self) -> None:
        """Test different comments with same delivery ID."""
        cache = DeliveryCache(ttl_seconds=3600)

        # Record first comment
        cache.record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
        )

        # Different comment ID should not be duplicate
        assert cache.is_duplicate(
            "delivery-1", "issue_comment", "testorg/testrepo", 67890
        ) is False

    def test_ttl_expiry(self) -> None:
        """Test TTL-based expiry."""
        cache = DeliveryCache(ttl_seconds=1)  # 1 second TTL

        # Record a delivery
        cache.record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
        )

        # Should be duplicate immediately
        assert cache.is_duplicate(
            "delivery-1", "issue_comment", "testorg/testrepo", 12345
        ) is True

        # Wait for expiry
        time.sleep(1.1)

        # Should not be duplicate after expiry
        assert cache.is_duplicate(
            "delivery-1", "issue_comment", "testorg/testrepo", 12345
        ) is False

    def test_max_size_eviction(self) -> None:
        """Test LRU eviction when max size reached."""
        cache = DeliveryCache(ttl_seconds=3600, max_size=3)

        # Fill cache
        for i in range(3):
            cache.record(
                delivery_id=f"delivery-{i}",
                event_type="issue_comment",
                repo="testorg/testrepo",
                comment_id=i,
            )

        # Add one more (should evict oldest)
        cache.record(
            delivery_id="delivery-3",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=3,
        )

        # Oldest should be evicted
        assert cache.is_duplicate(
            "delivery-0", "issue_comment", "testorg/testrepo", 0
        ) is False

        # Newest should still be there
        assert cache.is_duplicate(
            "delivery-3", "issue_comment", "testorg/testrepo", 3
        ) is True

    def test_get_stats(self) -> None:
        """Test cache statistics."""
        cache = DeliveryCache(ttl_seconds=3600, max_size=100)

        # Add some entries
        for i in range(5):
            cache.record(
                delivery_id=f"delivery-{i}",
                event_type="issue_comment",
                repo="testorg/testrepo",
                comment_id=i,
            )

        stats = cache.get_stats()

        assert stats["size"] == 5
        assert stats["max_size"] == 100
        assert stats["ttl_seconds"] == 3600

    def test_clear(self) -> None:
        """Test clearing cache."""
        cache = DeliveryCache(ttl_seconds=3600)

        # Add entries
        cache.record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=1,
        )

        # Clear
        cache.clear()

        # Should be empty
        assert cache.get_stats()["size"] == 0


class TestIdempotencyHandler:
    """Tests for IdempotencyHandler."""

    def test_check_and_record_new(self) -> None:
        """Test checking and recording a new delivery."""
        cache = DeliveryCache(ttl_seconds=3600)
        handler = IdempotencyHandler(cache)

        is_dup, was_recorded = handler.check_and_record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
            action_taken="allow",
        )

        assert is_dup is False
        assert was_recorded is True

    def test_check_and_record_duplicate(self) -> None:
        """Test checking a duplicate delivery."""
        cache = DeliveryCache(ttl_seconds=3600)
        handler = IdempotencyHandler(cache)

        # First call
        handler.check_and_record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
        )

        # Second call with same ID
        is_dup, was_recorded = handler.check_and_record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
        )

        assert is_dup is True
        assert was_recorded is False

    def test_is_replay(self) -> None:
        """Test replay check without recording."""
        cache = DeliveryCache(ttl_seconds=3600)
        handler = IdempotencyHandler(cache)

        # Record first
        cache.record(
            delivery_id="delivery-1",
            event_type="issue_comment",
            repo="testorg/testrepo",
            comment_id=12345,
        )

        # Check replay
        assert handler.is_replay(
            "delivery-1", "issue_comment", "testorg/testrepo", 12345
        ) is True

        # Different delivery should not be replay
        assert handler.is_replay(
            "delivery-2", "issue_comment", "testorg/testrepo", 12345
        ) is False


class TestWhitelistChecker:
    """Tests for WhitelistChecker."""

    @pytest.fixture
    def checker(self) -> WhitelistChecker:
        """Create a WhitelistChecker instance."""
        from src.config import WhitelistConfig

        config = MagicMock(spec=WhitelistConfig)
        config.get_trusted_users.return_value = {"octocat", "dependabot"}
        config.get_trusted_orgs.return_value = {"github", "microsoft"}
        config.get_exempt_repos.return_value = {"testorg/docs"}
        config.get_exempt_labels.return_value = {"bug", "security"}

        return WhitelistChecker(config)

    def test_check_trusted_user(self, checker: WhitelistChecker) -> None:
        """Test checking trusted user."""
        result = checker.check_user("octocat")

        assert result.is_exempt is True
        assert result.matched_rule == "trusted_user"

    def test_check_untrusted_user(self, checker: WhitelistChecker) -> None:
        """Test checking untrusted user."""
        result = checker.check_user("randomuser")

        assert result.is_exempt is False
        assert result.matched_rule is None

    def test_check_trusted_org(self, checker: WhitelistChecker) -> None:
        """Test checking user in trusted org."""
        result = checker.check_user(
            "someuser",
            user_orgs={"github", "other-org"},
        )

        assert result.is_exempt is True
        assert result.matched_rule == "trusted_org"

    def test_check_trusted_association(self, checker: WhitelistChecker) -> None:
        """Test checking trusted author association."""
        result = checker.check_user("someuser", author_association="OWNER")

        assert result.is_exempt is True
        assert result.matched_rule == "trusted_association"

    def test_check_exempt_repo(self, checker: WhitelistChecker) -> None:
        """Test checking exempt repository."""
        result = checker.check_repository("testorg/docs")

        assert result.is_exempt is True
        assert result.matched_rule == "exempt_repo"

    def test_check_non_exempt_repo(self, checker: WhitelistChecker) -> None:
        """Test checking non-exempt repository."""
        result = checker.check_repository("testorg/code")

        assert result.is_exempt is False

    def test_check_exempt_label(self, checker: WhitelistChecker) -> None:
        """Test checking exempt label."""
        result = checker.check_issue_labels(["bug", "enhancement"])

        assert result.is_exempt is True
        assert result.matched_rule == "exempt_label"

    def test_check_non_exempt_label(self, checker: WhitelistChecker) -> None:
        """Test checking non-exempt label."""
        result = checker.check_issue_labels(["enhancement", "question"])

        assert result.is_exempt is False

    def test_is_bot_user(self, checker: WhitelistChecker) -> None:
        """Test bot user detection."""
        assert checker.is_bot_user("dependabot[bot]") is True
        assert checker.is_bot_user("github-actions[bot]") is True
        assert checker.is_bot_user("renovate[bot]") is True
        assert checker.is_bot_user("octocat") is False

    def test_case_insensitive_user(self, checker: WhitelistChecker) -> None:
        """Test case-insensitive user matching."""
        result = checker.check_user("OctoCat")

        assert result.is_exempt is True

    def test_user_with_at_symbol(self, checker: WhitelistChecker) -> None:
        """Test user with @ symbol."""
        result = checker.check_user("@octocat")

        assert result.is_exempt is True


class TestWhitelistCheckResult:
    """Tests for WhitelistCheckResult dataclass."""

    def test_exempt_result(self) -> None:
        """Test exempt result."""
        result = WhitelistCheckResult(
            is_exempt=True,
            reason="User is trusted",
            matched_rule="trusted_user",
        )

        assert result.is_exempt is True
        assert result.matched_rule == "trusted_user"

    def test_non_exempt_result(self) -> None:
        """Test non-exempt result."""
        result = WhitelistCheckResult(
            is_exempt=False,
            reason="User is not whitelisted",
        )

        assert result.is_exempt is False
        assert result.matched_rule is None
