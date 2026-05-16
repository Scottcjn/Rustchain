#!/usr/bin/env python3
"""
Tests for the rtc-auto-bounty GitHub Action helper script.

Run with:  python -m pytest test_award_rtc.py -v
       or: python test_award_rtc.py
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the action directory is importable
ACTION_DIR = Path(__file__).parent
import sys
sys.path.insert(0, str(ACTION_DIR))

from award_rtc import (
    Config,
    resolve_wallet,
    resolve_wallet_from_pr_body,
    resolve_wallet_from_file,
    check_already_awarded,
    set_output,
    transfer_rtc,
    _AWARD_MARKER,
)


# ---------------------------------------------------------------------------
# Wallet resolution tests
# ---------------------------------------------------------------------------


class TestResolveWalletFromPrBody(unittest.TestCase):
    """Test extracting wallet from PR body text."""

    def test_lowercase_wallet_directive(self):
        body = "This is a PR\n\nwallet: RTCabc123def456\n\nSome more text"
        self.assertEqual(resolve_wallet_from_pr_body(body), "RTCabc123def456")

    def test_capitalized_wallet_directive(self):
        body = "Wallet: RTCxyz789\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), "RTCxyz789")

    def test_dot_rtc_wallet_directive(self):
        body = ".rtc-wallet: RTCdotfile123\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), "RTCdotfile123")

    def test_wallet_with_trailingling_comma(self):
        body = "wallet: RTCwithcomma,\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), "RTCwithcomma")

    def test_no_wallet_directive(self):
        body = "This PR has no wallet directive.\n"
        self.assertIsNone(resolve_wallet_from_pr_body(body))

    def test_wallet_in_middle_of_text(self):
        body = "Fixes #123\n\nwallet: RTCmid123\n\nTests added."
        self.assertEqual(resolve_wallet_from_pr_body(body), "RTCmid123")

    def test_github_username_as_wallet(self):
        body = "wallet: some-contributor\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), "some-contributor")


class TestResolveWalletFromFile(unittest.TestCase):
    """Test reading wallet from .rtc-wallet file."""

    def test_simple_wallet_file(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text("RTCfile123\n")
            self.assertEqual(resolve_wallet_from_file(td), "RTCfile123")

    def test_file_with_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text(
                "# My wallet\n\nRTCcommented456\n"
            )
            self.assertEqual(resolve_wallet_from_file(td), "RTCcommented456")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(resolve_wallet_from_file(td))

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text("")
            self.assertIsNone(resolve_wallet_from_file(td))


class TestResolveWalletPriority(unittest.TestCase):
    """Test wallet resolution priority order."""

    def test_pr_body_takes_priority_over_file(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text("RTCfromfile\n")
            body = "wallet: RTCfrombody\n"
            result = resolve_wallet(body, td)
            self.assertEqual(result, "RTCfrombody")

    def test_file_used_when_no_pr_body_directive(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text("RTCfromfile\n")
            body = "No wallet here.\n"
            result = resolve_wallet(body, td)
            self.assertEqual(result, "RTCfromfile")

    def test_returns_none_when_nothing_found(self):
        with tempfile.TemporaryDirectory() as td:
            body = "Nothing.\n"
            result = resolve_wallet(body, td)
            self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Duplicate detection tests
# ---------------------------------------------------------------------------


class TestCheckAlreadyAwarded(unittest.TestCase):
    """Test duplicate award detection."""

    def test_marker_present(self):
        comments = [{"body": f"Some text {_AWARD_MARKER} tx=abc"}]
        self.assertTrue(check_already_awarded(comments))

    def test_marker_absent(self):
        comments = [{"body": "LGTM!"}, {"body": "Merged."}]
        self.assertFalse(check_already_awarded(comments))

    def test_empty_comments(self):
        self.assertFalse(check_already_awarded([]))

    def test_marker_in_last_comment(self):
        comments = [
            {"body": "Looks good"},
            {"body": f"<!-- {_AWARD_MARKER} tx=xyz -->"},
        ]
        self.assertTrue(check_already_awarded(comments))

    def test_dry_run_marker_does_not_block_real_award(self):
        comments = [{"body": f"<!-- {_AWARD_MARKER} (dry-run) -->"}]
        self.assertFalse(check_already_awarded(comments))

    def test_failed_marker_does_not_block_retry(self):
        comments = [{"body": f"<!-- {_AWARD_MARKER}:FAILED -->"}]
        self.assertFalse(check_already_awarded(comments))

    def test_failed_text_outside_marker_does_not_hide_success_marker(self):
        comments = [{"body": f"failed before marker\n<!-- {_AWARD_MARKER} tx=xyz -->"}]
        self.assertTrue(check_already_awarded(comments))


class TestTransferRtc(unittest.TestCase):
    """Test the RustChain transfer helper's retry behavior."""

    def test_retries_after_connection_refused(self):
        from urllib.error import URLError

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"ok": True, "pending_id": 7}).encode()

        with patch("award_rtc.urlopen", side_effect=[URLError(ConnectionRefusedError(111, "Connection refused")), fake_response]) as mock_urlopen:
            with patch("award_rtc.time.sleep") as mock_sleep:
                ok, result = transfer_rtc("1.2.3.4", "secret", "from_wallet", "to_wallet", 12.5, "memo")

        self.assertTrue(ok)
        self.assertEqual(result.get("pending_id"), 7)
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1)




class TestConfig(unittest.TestCase):
    """Test configuration parsing and validation."""

    def _cfg(self, **overrides):
        """Create a Config with the given environment variable overrides."""
        env = {
            "INPUT_RTC_AMOUNT": "50",
            "INPUT_RTC_VPS_HOST": "1.2.3.4",
            "INPUT_RTC_ADMIN_KEY": "test-key-32-chars-long!!",
            "INPUT_FROM_WALLET": "founder_community",
            "INPUT_DRY_RUN": "false",
            "INPUT_POST_COMMENT": "true",
            "INPUT_GITHUB_TOKEN": "ghp_test",
            "INPUT_REPO_PATH": ".",
            "INPUT_MAX_AMOUNT": "10000",
            "GITHUB_REPOSITORY": "test/repo",
            "PR_NUMBER": "42",
            "PR_AUTHOR": "alice",
            "PR_MERGED": "true",
            "PR_BODY": "",
            "PR_HEAD_SHA": "abc123",
            "PR_TITLE": "Test PR",
        }
        env.update(overrides)
        with patch.dict(os.environ, env, clear=True):
            return Config()

    def test_defaults(self):
        cfg = self._cfg()
        self.assertEqual(cfg.rtc_amount, 50.0)
        self.assertEqual(cfg.from_wallet, "founder_community")
        self.assertFalse(cfg.dry_run)
        self.assertTrue(cfg.post_comment)

    def test_dry_run_mode(self):
        cfg = self._cfg(INPUT_DRY_RUN="true")
        self.assertTrue(cfg.dry_run)

    def test_validate_ok(self):
        cfg = self._cfg()
        self.assertIsNone(cfg.validate())

    def test_validate_missing_token(self):
        cfg = self._cfg(INPUT_GITHUB_TOKEN="", GITHUB_TOKEN="")
        self.assertIsNotNone(cfg.validate())

    def test_validate_missing_vps_host_in_live_mode(self):
        cfg = self._cfg(INPUT_RTC_VPS_HOST="", INPUT_DRY_RUN="false")
        self.assertIsNotNone(cfg.validate())

    def test_validate_missing_admin_key_in_live_mode(self):
        cfg = self._cfg(INPUT_RTC_ADMIN_KEY="", INPUT_DRY_RUN="false")
        self.assertIsNotNone(cfg.validate())

    def test_validate_passes_in_dry_run_without_vps(self):
        cfg = self._cfg(INPUT_DRY_RUN="true", INPUT_RTC_VPS_HOST="", INPUT_RTC_ADMIN_KEY="")
        self.assertIsNone(cfg.validate())

    def test_validate_negative_amount(self):
        cfg = self._cfg(INPUT_RTC_AMOUNT="-5")
        self.assertIsNotNone(cfg.validate())


# ---------------------------------------------------------------------------
# set_output tests
# ---------------------------------------------------------------------------


class TestSetOutput(unittest.TestCase):
    """Test GitHub Actions output parameter setting."""

    def test_set_output_writes_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}, clear=True):
                set_output("awarded", "true")
                set_output("amount", "50.0")

            with open(output_file) as f:
                content = f.read()

            self.assertIn("awarded=true", content)
            self.assertIn("amount=50.0", content)
        finally:
            os.unlink(output_file)


# ---------------------------------------------------------------------------
# Integration-style main() tests
# ---------------------------------------------------------------------------


class TestMainFlow(unittest.TestCase):
    """Test the main() flow with mocked external calls."""

    def _env(self, **overrides):
        """Set up environment for main()."""
        output_file = tempfile.NamedTemporaryFile(delete=False)
        output_file.close()
        env = {
            "INPUT_RTC_AMOUNT": "75",
            "INPUT_RTC_VPS_HOST": "1.2.3.4",
            "INPUT_RTC_ADMIN_KEY": "test-admin-key-32chars!!",
            "INPUT_FROM_WALLET": "founder_community",
            "INPUT_DRY_RUN": "false",
            "INPUT_POST_COMMENT": "true",
            "INPUT_GITHUB_TOKEN": "ghp_test",
            "INPUT_REPO_PATH": ".",
            "INPUT_MAX_AMOUNT": "10000",
            "GITHUB_REPOSITORY": "test/repo",
            "PR_NUMBER": "42",
            "PR_AUTHOR": "alice",
            "PR_MERGED": "true",
            "PR_BODY": "wallet: RTCcontributor123\n",
            "PR_HEAD_SHA": "abc123",
            "PR_TITLE": "Test PR",
            "GITHUB_OUTPUT": output_file.name,
        }
        env.update(overrides)
        return patch.dict(os.environ, env, clear=True)

    def test_skip_when_not_merged(self):
        from award_rtc import main
        with self._env(PR_MERGED="false"):
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                rc = main()
        self.assertEqual(rc, 0)

    def test_skip_already_awarded(self):
        from award_rtc import main
        comments = [{"body": f"<!-- {_AWARD_MARKER} tx=old -->"}]
        with self._env():
            with patch("award_rtc.fetch_pr_comments", return_value=comments):
                rc = main()
        self.assertEqual(rc, 0)

    def test_retry_after_dry_run_marker(self):
        from award_rtc import main
        comments = [{"body": f"<!-- {_AWARD_MARKER} (dry-run) -->"}]
        transfer_result = {
            "ok": True,
            "pending_id": 102,
            "tx_hash": "tx_after_dry_run",
        }
        with self._env():
            with patch("award_rtc.fetch_pr_comments", return_value=comments):
                with patch(
                    "award_rtc.transfer_rtc",
                    return_value=(True, transfer_result),
                ) as mock_tx:
                    with patch("award_rtc.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)
        mock_tx.assert_called_once()

    def test_retry_after_failed_marker(self):
        from award_rtc import main
        comments = [{"body": f"<!-- {_AWARD_MARKER}:FAILED -->"}]
        transfer_result = {
            "ok": True,
            "pending_id": 103,
            "tx_hash": "tx_after_failed",
        }
        with self._env():
            with patch("award_rtc.fetch_pr_comments", return_value=comments):
                with patch(
                    "award_rtc.transfer_rtc",
                    return_value=(True, transfer_result),
                ) as mock_tx:
                    with patch("award_rtc.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)
        mock_tx.assert_called_once()

    def test_dry_run_mode(self):
        from award_rtc import main
        with self._env(INPUT_DRY_RUN="true"):
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                with patch("award_rtc.post_pr_comment") as mock_post:
                    rc = main()
        self.assertEqual(rc, 0)
        # Should have posted a dry-run comment
        mock_post.assert_called_once()

    def test_successful_transfer(self):
        from award_rtc import main
        transfer_result = {
            "ok": True,
            "phase": "pending",
            "pending_id": 99,
            "tx_hash": "tx_abc123",
            "confirms_in_hours": 24,
        }
        with self._env():
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                with patch("award_rtc.transfer_rtc", return_value=(True, transfer_result)):
                    with patch("award_rtc.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)

    def test_failed_transfer(self):
        from award_rtc import main
        transfer_result = {"ok": False, "error": "Insufficient balance"}
        with self._env():
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                with patch("award_rtc.transfer_rtc", return_value=(False, transfer_result)):
                    with patch("award_rtc.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 1)

    def test_amount_exceeds_cap(self):
        from award_rtc import main
        with self._env(INPUT_RTC_AMOUNT="50000", INPUT_MAX_AMOUNT="10000"):
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                rc = main()
        self.assertEqual(rc, 1)

    def test_bounty_override_in_pr_body(self):
        from award_rtc import main
        transfer_result = {
            "ok": True,
            "phase": "pending",
            "pending_id": 100,
            "tx_hash": "tx_override",
        }
        body = "wallet: RTCcontributor123\nbounty: 200 RTC\n"
        with self._env(PR_BODY=body, INPUT_RTC_AMOUNT="50"):
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                with patch("award_rtc.transfer_rtc", return_value=(True, transfer_result)) as mock_tx:
                    with patch("award_rtc.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)
        # Verify the bounty override amount was used
        call_args = mock_tx.call_args
        self.assertEqual(call_args[0][4], 200.0)  # amount parameter

    def test_fallback_to_pr_author_when_no_wallet(self):
        from award_rtc import main
        transfer_result = {
            "ok": True,
            "phase": "pending",
            "pending_id": 101,
            "tx_hash": "tx_fallback",
        }
        # No wallet directive in PR body
        with self._env(PR_BODY="Just a regular PR\n", PR_AUTHOR="bob"):
            with patch("award_rtc.fetch_pr_comments", return_value=[]):
                with patch("award_rtc.transfer_rtc", return_value=(True, transfer_result)) as mock_tx:
                    with patch("award_rtc.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)
        # Should use PR author as wallet
        call_args = mock_tx.call_args
        self.assertEqual(call_args[0][3], "bob")  # to_wallet parameter


if __name__ == "__main__":
    unittest.main(verbosity=2)
