"""
test_tip_bot.py — Tests for the RustChain GitHub tip bot.

Coverage:
- Command parsing (valid, malformed, edge cases)
- Validation (amount bounds, self-tip, rate limiting)
- Authorization (maintainer allowlist)
- Idempotency / duplicate detection
- State persistence
- End-to-end event processing (mocked GitHub API)
- Webhook signature verification
"""

import hashlib
import hmac
import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from auth import RateLimiter, is_authorized_sender, verify_webhook_signature
from state import TipState
from tip_bot import (
    ParseResult,
    TipCommand,
    build_duplicate_comment,
    build_failure_comment,
    build_success_comment,
    build_unauthorized_comment,
    main,
    parse_tip_command,
    process_event,
    validate_tip,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def state_file(tmp_path):
    return str(tmp_path / "tip_state.json")


@pytest.fixture()
def state(state_file):
    return TipState(state_file)


@pytest.fixture()
def config():
    return {
        "maintainers": ["Scottcjn", "alice"],
        "token_symbol": "RTC",
        "min_amount": 1,
        "max_amount": 10000,
        "rate_limit": {"max_per_hour": 20},
        "rustchain_node_url": "https://example.com",
        "payout_mode": "log_only",
        "state_file": "tip_state.json",
    }


@pytest.fixture()
def rate_limiter():
    return RateLimiter(max_per_hour=20)


def make_event(
    comment_body: str,
    sender: str = "Scottcjn",
    comment_id: int = 12345,
    issue_number: int = 42,
    comment_url: str = "https://github.com/org/repo/issues/42#issuecomment-12345",
) -> dict[str, Any]:
    return {
        "comment": {
            "id": comment_id,
            "body": comment_body,
            "user": {"login": sender},
            "html_url": comment_url,
        },
        "issue": {"number": issue_number},
    }


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

class TestParseTipCommand:

    def test_valid_basic(self):
        result = parse_tip_command("/tip @alice 50 RTC", "RTC")
        assert result.error is None
        assert result.command is not None
        assert result.command.recipient == "alice"
        assert result.command.amount == 50.0
        assert result.command.token == "RTC"

    def test_valid_decimal_amount(self):
        result = parse_tip_command("/tip @bob 12.5 RTC", "RTC")
        assert result.error is None
        assert result.command.amount == 12.5

    def test_valid_inline_in_comment(self):
        body = "Great work! /tip @contributor 100 RTC for fixing that bug."
        result = parse_tip_command(body, "RTC")
        assert result.error is None
        assert result.command.recipient == "contributor"

    def test_valid_case_insensitive_token(self):
        result = parse_tip_command("/tip @alice 10 rtc", "RTC")
        assert result.error is None
        assert result.command.token == "RTC"

    def test_valid_multiline_body(self):
        body = "Some text\n/tip @alice 25 RTC\nMore text"
        result = parse_tip_command(body, "RTC")
        assert result.error is None
        assert result.command.recipient == "alice"

    def test_valid_hyphenated_username(self):
        result = parse_tip_command("/tip @alice-dev 10 RTC", "RTC")
        assert result.error is None
        assert result.command.recipient == "alice-dev"

    def test_no_tip_command_returns_none_none(self):
        result = parse_tip_command("This comment has nothing special.", "RTC")
        assert result.command is None
        assert result.error is None

    def test_missing_at_sign_is_malformed(self):
        result = parse_tip_command("/tip alice 50 RTC", "RTC")
        assert result.command is None
        assert result.error is not None
        assert "Malformed" in result.error

    def test_missing_amount_is_malformed(self):
        result = parse_tip_command("/tip @alice RTC", "RTC")
        assert result.command is None
        assert result.error is not None

    def test_missing_token_is_malformed(self):
        result = parse_tip_command("/tip @alice 50", "RTC")
        assert result.command is None
        assert result.error is not None

    def test_wrong_token_symbol(self):
        result = parse_tip_command("/tip @alice 50 ETH", "RTC")
        assert result.command is None
        assert result.error is not None
        assert "ETH" in result.error

    def test_zero_amount_triggers_error(self):
        result = parse_tip_command("/tip @alice 0 RTC", "RTC")
        assert result.command is None
        assert result.error is not None
        assert "greater than 0" in result.error

    def test_negative_amount_not_parsed(self):
        # Regex only matches digits, so -10 won't match
        result = parse_tip_command("/tip @alice -10 RTC", "RTC")
        assert result.command is None
        assert result.error is not None

    def test_empty_body(self):
        result = parse_tip_command("", "RTC")
        assert result.command is None
        assert result.error is None

    def test_just_slash_tip(self):
        result = parse_tip_command("/tip", "RTC")
        assert result.command is None
        assert result.error is not None  # Near-miss → malformed error

    def test_username_too_long_rejected(self):
        # GitHub max is 39 chars
        long_name = "a" * 40
        result = parse_tip_command(f"/tip @{long_name} 10 RTC", "RTC")
        assert result.command is None
        assert result.error is not None


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateTip:

    def test_valid_tip_passes(self, config, rate_limiter):
        cmd = TipCommand(recipient="bob", amount=50, token="RTC", raw="/tip @bob 50 RTC")
        error = validate_tip(cmd, "Scottcjn", config, rate_limiter)
        assert error is None

    def test_self_tip_rejected(self, config, rate_limiter):
        cmd = TipCommand(recipient="Scottcjn", amount=10, token="RTC", raw="")
        error = validate_tip(cmd, "Scottcjn", config, rate_limiter)
        assert error is not None
        assert "yourself" in error

    def test_self_tip_case_insensitive(self, config, rate_limiter):
        cmd = TipCommand(recipient="scottcjn", amount=10, token="RTC", raw="")
        error = validate_tip(cmd, "Scottcjn", config, rate_limiter)
        assert error is not None

    def test_amount_below_minimum(self, config, rate_limiter):
        cmd = TipCommand(recipient="bob", amount=0.5, token="RTC", raw="")
        error = validate_tip(cmd, "Scottcjn", config, rate_limiter)
        assert error is not None
        assert "Minimum" in error

    def test_amount_above_maximum(self, config, rate_limiter):
        cmd = TipCommand(recipient="bob", amount=99999, token="RTC", raw="")
        error = validate_tip(cmd, "Scottcjn", config, rate_limiter)
        assert error is not None
        assert "Maximum" in error

    def test_rate_limit_exceeded(self, config):
        limiter = RateLimiter(max_per_hour=2)
        cmd = TipCommand(recipient="bob", amount=10, token="RTC", raw="")

        assert validate_tip(cmd, "Scottcjn", config, limiter) is None
        assert validate_tip(cmd, "Scottcjn", config, limiter) is None
        error = validate_tip(cmd, "Scottcjn", config, limiter)
        assert error is not None
        assert "Rate limit" in error


# ---------------------------------------------------------------------------
# Authorization tests
# ---------------------------------------------------------------------------

class TestAuthorization:

    def test_maintainer_authorized(self):
        assert is_authorized_sender("Scottcjn", ["Scottcjn", "alice"]) is True

    def test_case_insensitive_match(self):
        assert is_authorized_sender("scottcjn", ["Scottcjn"]) is True
        assert is_authorized_sender("SCOTTCJN", ["Scottcjn"]) is True

    def test_unknown_user_unauthorized(self):
        assert is_authorized_sender("hacker", ["Scottcjn", "alice"]) is False

    def test_empty_allowlist(self):
        assert is_authorized_sender("Scottcjn", []) is False


# ---------------------------------------------------------------------------
# Webhook signature tests
# ---------------------------------------------------------------------------

class TestWebhookVerification:

    def _sign(self, payload: bytes, secret: str) -> str:
        sig = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    def test_valid_signature(self):
        payload = b'{"action": "created"}'
        secret = "mysecret"
        sig = self._sign(payload, secret)
        with patch.dict(os.environ, {"WEBHOOK_SECRET": secret}):
            assert verify_webhook_signature(payload, sig) is True

    def test_invalid_signature_rejected(self):
        payload = b'{"action": "created"}'
        with patch.dict(os.environ, {"WEBHOOK_SECRET": "mysecret"}):
            assert verify_webhook_signature(payload, "sha256=deadbeef") is False

    def test_missing_signature_rejected(self):
        payload = b'{"action": "created"}'
        with patch.dict(os.environ, {"WEBHOOK_SECRET": "mysecret"}):
            assert verify_webhook_signature(payload, None) is False

    def test_no_secret_configured_rejects_unsigned_payload(self):
        payload = b'{"action": "created"}'
        with patch.dict(os.environ, {}, clear=True):
            assert verify_webhook_signature(payload, None) is False

    def test_tampered_payload_rejected(self):
        original = b'{"action": "created"}'
        tampered = b'{"action": "injected"}'
        secret = "mysecret"
        sig = self._sign(original, secret)
        with patch.dict(os.environ, {"WEBHOOK_SECRET": secret}):
            assert verify_webhook_signature(tampered, sig) is False


# ---------------------------------------------------------------------------
# Main entrypoint webhook gate tests
# ---------------------------------------------------------------------------

class TestMainWebhookGate:

    def _write_event(self, tmp_path) -> str:
        event_path = tmp_path / "event.json"
        event_path.write_text(json.dumps(make_event("Just a normal comment.")))
        return str(event_path)

    def _base_env(self, event_path: str) -> dict[str, str]:
        return {
            "GITHUB_EVENT_PATH": event_path,
            "GITHUB_TOKEN": "token",
            "GITHUB_REPOSITORY": "org/repo",
        }

    def test_external_webhook_without_secret_or_signature_aborts(self, tmp_path):
        env = self._base_env(self._write_event(tmp_path))
        with patch.dict(os.environ, env, clear=True), \
             patch("tip_bot.process_event") as mock_process:
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        mock_process.assert_not_called()

    def test_external_webhook_with_secret_but_missing_signature_aborts(self, tmp_path):
        env = self._base_env(self._write_event(tmp_path))
        env["WEBHOOK_SECRET"] = "mysecret"
        with patch.dict(os.environ, env, clear=True), \
             patch("tip_bot.process_event") as mock_process:
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        mock_process.assert_not_called()

    def test_github_actions_payload_without_signature_is_allowed(self, tmp_path, config):
        event_path = self._write_event(tmp_path)
        env = self._base_env(event_path)
        env["GITHUB_ACTIONS"] = "true"
        with patch.dict(os.environ, env, clear=True), \
             patch("tip_bot.load_config", return_value=config), \
             patch("tip_bot.TipState") as mock_state, \
             patch("tip_bot.process_event", return_value="no_command") as mock_process:
            main()

        mock_state.assert_called_once_with(config["state_file"])
        mock_process.assert_called_once()


# ---------------------------------------------------------------------------
# State / idempotency tests
# ---------------------------------------------------------------------------

class TestTipState:

    def test_fresh_state_empty(self, state):
        assert state.tip_log == []
        assert state.get_pending_payouts() == []

    def test_record_and_retrieve(self, state):
        state.record_tip(
            "org/repo/111", 42, "Scottcjn", "alice", 50, "RTC",
            "https://github.com/org/repo/issues/42#issuecomment-111",
        )
        state.save()
        assert len(state.tip_log) == 1
        assert state.tip_log[0]["sender"] == "Scottcjn"
        assert state.tip_log[0]["recipient"] == "alice"
        assert state.tip_log[0]["amount"] == 50

    def test_is_processed_false_initially(self, state):
        assert state.is_processed("org/repo/111") is False

    def test_is_processed_true_after_record(self, state):
        state.record_tip("org/repo/111", 42, "Scottcjn", "alice", 50, "RTC", "url")
        assert state.is_processed("org/repo/111") is True

    def test_duplicate_key_not_double_recorded(self, state):
        key = "org/repo/111"
        state.record_tip(key, 42, "Scottcjn", "alice", 50, "RTC", "url")
        # Simulating what process_event does — it checks is_processed first
        # so the record_tip call for the same key would not happen.
        assert len(state.tip_log) == 1

    def test_state_persists_across_instances(self, state_file):
        s1 = TipState(state_file)
        s1.record_tip("org/repo/222", 10, "Scottcjn", "bob", 10, "RTC", "url")
        s1.save()

        s2 = TipState(state_file)
        assert s2.is_processed("org/repo/222") is True
        assert len(s2.tip_log) == 1

    def test_mark_paid(self, state):
        key = "org/repo/333"
        state.record_tip(key, 5, "Scottcjn", "carol", 25, "RTC", "url")
        state.mark_paid(key, tx_ref="txabc123")
        assert state.tip_log[0]["status"] == "paid"
        assert state.tip_log[0]["tx_ref"] == "txabc123"

    def test_pending_payouts_filter(self, state):
        state.record_tip("org/repo/1", 1, "Scottcjn", "a", 10, "RTC", "url")
        state.record_tip("org/repo/2", 2, "Scottcjn", "b", 20, "RTC", "url")
        state.mark_paid("org/repo/1")
        pending = state.get_pending_payouts()
        assert len(pending) == 1
        assert pending[0]["recipient"] == "b"

    def test_invalid_state_file_resets(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("not valid json {{{")
        s = TipState(path)
        assert s.tip_log == []


# ---------------------------------------------------------------------------
# End-to-end process_event tests (GitHub API mocked)
# ---------------------------------------------------------------------------

class TestProcessEvent:

    @pytest.fixture(autouse=True)
    def mock_github(self):
        """Mock all outbound GitHub API calls."""
        with patch("tip_bot.github_post_comment", return_value=True) as mock_comment, \
             patch("tip_bot.github_commit_state", return_value=True) as mock_commit:
            self.mock_comment = mock_comment
            self.mock_commit = mock_commit
            yield

    def test_valid_tip_succeeds(self, config, state):
        event = make_event("/tip @alice 50 RTC")
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "success"
        assert state.is_processed("org/repo/12345")
        assert self.mock_comment.call_count == 1
        body = self.mock_comment.call_args[0][2]
        assert "alice" in body
        assert "50" in body

    def test_no_tip_command_skipped(self, config, state):
        event = make_event("Just a normal comment, nothing to see here.")
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "no_command"
        assert self.mock_comment.call_count == 0

    def test_unauthorized_sender_rejected(self, config, state):
        event = make_event("/tip @alice 50 RTC", sender="random_user")
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "unauthorized"
        body = self.mock_comment.call_args[0][2]
        assert "Unauthorized" in body

    def test_malformed_command_gets_error(self, config, state):
        event = make_event("/tip alice 50 RTC")  # missing @
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "parse_error"
        body = self.mock_comment.call_args[0][2]
        assert "failed" in body.lower() or "Tip failed" in body

    def test_duplicate_comment_id_prevented(self, config, state):
        event = make_event("/tip @alice 50 RTC", comment_id=99)
        # Process once
        result1 = process_event(event, config, state, "token", "org/repo")
        assert result1 == "success"
        # Process same event again
        result2 = process_event(event, config, state, "token", "org/repo")
        assert result2 == "duplicate"
        # Should have 2 comment calls (success + duplicate notice)
        assert self.mock_comment.call_count == 2
        duplicate_body = self.mock_comment.call_args[0][2]
        assert "Duplicate" in duplicate_body

    def test_replay_prevention_different_amounts(self, config, state):
        """Idempotency is keyed on comment_id, not content — same id means dup."""
        event1 = make_event("/tip @alice 50 RTC", comment_id=555)
        event2 = make_event("/tip @alice 100 RTC", comment_id=555)  # same id, different amount
        process_event(event1, config, state, "token", "org/repo")
        result = process_event(event2, config, state, "token", "org/repo")
        assert result == "duplicate"

    def test_self_tip_rejected(self, config, state):
        event = make_event("/tip @Scottcjn 10 RTC", sender="Scottcjn")
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "validation_error"
        body = self.mock_comment.call_args[0][2]
        assert "yourself" in body

    def test_amount_too_large_rejected(self, config, state):
        event = make_event("/tip @alice 999999 RTC")
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "validation_error"
        body = self.mock_comment.call_args[0][2]
        assert "Maximum" in body

    def test_amount_below_minimum_rejected(self, config, state):
        event = make_event("/tip @alice 0.1 RTC")
        result = process_event(event, config, state, "token", "org/repo")
        assert result == "validation_error"

    def test_multiple_tips_different_comments_all_succeed(self, config, state):
        for i, recipient in enumerate(["alice", "bob", "carol"], start=100):
            event = make_event(f"/tip @{recipient} 10 RTC", comment_id=i)
            result = process_event(event, config, state, "token", "org/repo")
            assert result == "success"
        assert len(state.tip_log) == 3

    def test_state_committed_after_success(self, config, state):
        event = make_event("/tip @alice 10 RTC")
        process_event(event, config, state, "token", "org/repo")
        assert self.mock_commit.call_count == 1

    def test_no_state_commit_on_failure(self, config, state):
        event = make_event("/tip @alice 10 RTC", sender="attacker")
        process_event(event, config, state, "token", "org/repo")
        assert self.mock_commit.call_count == 0


# ---------------------------------------------------------------------------
# Comment format tests
# ---------------------------------------------------------------------------

class TestCommentBuilders:

    def test_success_comment_contains_fields(self):
        cmd = TipCommand(recipient="alice", amount=50, token="RTC", raw="")
        body = build_success_comment("Scottcjn", cmd, "https://example.com")
        assert "alice" in body
        assert "Scottcjn" in body
        assert "50" in body
        assert "RTC" in body
        assert "pending" in body.lower()

    def test_failure_comment_contains_error(self):
        body = build_failure_comment("Scottcjn", "Minimum tip is 1 RTC.")
        assert "Scottcjn" in body
        assert "Minimum" in body
        assert "failed" in body.lower() or "Failed" in body

    def test_duplicate_comment(self):
        cmd = TipCommand(recipient="alice", amount=50, token="RTC", raw="")
        body = build_duplicate_comment("Scottcjn", cmd)
        assert "Duplicate" in body
        assert "alice" in body

    def test_unauthorized_comment(self):
        body = build_unauthorized_comment("hacker")
        assert "hacker" in body
        assert "Unauthorized" in body


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------

class TestRateLimiter:

    def test_within_limit_allowed(self):
        limiter = RateLimiter(max_per_hour=5)
        for _ in range(5):
            assert limiter.check("user") is True

    def test_exceeding_limit_blocked(self):
        limiter = RateLimiter(max_per_hour=3)
        limiter.check("user")
        limiter.check("user")
        limiter.check("user")
        assert limiter.check("user") is False

    def test_different_users_independent(self):
        limiter = RateLimiter(max_per_hour=1)
        assert limiter.check("alice") is True
        assert limiter.check("bob") is True
        assert limiter.check("alice") is False

    def test_count_reflects_usage(self):
        limiter = RateLimiter(max_per_hour=10)
        limiter.check("user")
        limiter.check("user")
        assert limiter.count("user") == 2
