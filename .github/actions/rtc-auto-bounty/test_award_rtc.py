#!/usr/bin/env python3
"""
Regression tests for the patched RTC auto-bounty helper.

Run with:  python -m pytest test_award_rtc_patched.py -v
       or: python -m unittest test_award_rtc_patched.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ACTION_DIR = Path(__file__).parent
import sys

sys.path.insert(0, str(ACTION_DIR))

from award_rtc_patched import (
    Config,
    _AWARD_MARKER,
    build_transfer_url,
    check_already_awarded,
    is_endpoint_unreachable_error,
    is_valid_wallet,
    resolve_wallet,
    resolve_wallet_details,
    resolve_wallet_from_file,
    resolve_wallet_from_pr_body,
    resolve_wallet_from_pr_body_details,
    set_output,
    transfer_rtc,
)


WALLET_A = "RTC" + ("a1" * 20)
WALLET_B = "0x" + ("b2" * 20)
WALLET_C = "RTC" + ("c3" * 20)
INVALID_SAMPLE_WALLET = "RTC29WwMjwcaFeTTQqKaMNmFUFLYz3f"
SAMPLE_DIR = Path("/tmp/wallet-parser-fix")


class TestWalletValidation(unittest.TestCase):
    def test_accepts_rtc_hex_wallet(self):
        self.assertTrue(is_valid_wallet(WALLET_A))

    def test_accepts_0x_hex_wallet(self):
        self.assertTrue(is_valid_wallet(WALLET_B))

    def test_rejects_github_username(self):
        self.assertFalse(is_valid_wallet("some-contributor"))

    def test_rejects_invalid_rtc_shape(self):
        self.assertFalse(is_valid_wallet(INVALID_SAMPLE_WALLET))

    def test_rejects_lowercase_rtc_prefix(self):
        self.assertFalse(is_valid_wallet("rtc" + ("a1" * 20)))


class TestResolveWalletFromPrBody(unittest.TestCase):
    def test_supported_directive_formats(self):
        cases = [
            ("wallet", f"wallet: {WALLET_A}\n", WALLET_A),
            ("rtc wallet", f"RTC wallet: {WALLET_A}\n", WALLET_A),
            ("rtc payout wallet", f"RTC payout wallet: `{WALLET_A}`\n", WALLET_A),
            ("miner id", f"miner id: {WALLET_A}\n", WALLET_A),
            ("rtc wallet/miner id", f"RTC wallet/miner id: {WALLET_A}\n", WALLET_A),
            ("payment", f"Payment: RTC | {WALLET_A}\n", WALLET_A),
            ("dot rtc wallet", f".rtc-wallet: {WALLET_B}\n", WALLET_B),
        ]
        for name, body, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(resolve_wallet_from_pr_body(body), expected)
                self.assertEqual(resolve_wallet_from_pr_body_details(body), (expected, None))

    def test_fallback_uses_first_wallet_substring_when_unlabeled(self):
        body = f"Thanks for the review.\nDeclared payout is `{WALLET_B}` in prose.\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), WALLET_B)
        self.assertEqual(resolve_wallet_from_pr_body_details(body), (WALLET_B, None))

    def test_duplicate_same_wallet_is_not_ambiguous(self):
        body = f"wallet: {WALLET_A}\nRTC wallet: `{WALLET_A}`\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), WALLET_A)
        self.assertEqual(resolve_wallet_from_pr_body_details(body), (WALLET_A, None))

    def test_same_underlying_wallet_with_rtc_and_0x_forms_is_not_ambiguous(self):
        hex_tail = "d4" * 20
        rtc_wallet = "RTC" + hex_tail
        hex_wallet = "0x" + hex_tail
        body = f"RTC wallet: {rtc_wallet}\nPayment: RTC | {hex_wallet}\n"
        self.assertEqual(resolve_wallet_from_pr_body(body), rtc_wallet)
        self.assertEqual(resolve_wallet_from_pr_body_details(body), (rtc_wallet, None))

    def test_multiple_different_wallets_is_rejected(self):
        body = f"wallet: {WALLET_A}\nPayment: RTC | {WALLET_B}\n"
        self.assertIsNone(resolve_wallet_from_pr_body(body))
        self.assertEqual(
            resolve_wallet_from_pr_body_details(body),
            (None, "ambiguous_pr_wallets"),
        )

    def test_invalid_github_username_only_directive_returns_none(self):
        body = "wallet: some-contributor\n"
        self.assertIsNone(resolve_wallet_from_pr_body(body))
        self.assertEqual(
            resolve_wallet_from_pr_body_details(body),
            (None, "wallet_not_found"),
        )

    def test_garbage_string_returns_none(self):
        body = "Payment: RTC | not-a-wallet\n"
        self.assertIsNone(resolve_wallet_from_pr_body(body))
        self.assertEqual(
            resolve_wallet_from_pr_body_details(body),
            (None, "wallet_not_found"),
        )

    def test_missing_wallet_returns_none(self):
        body = "This PR has no payout information.\n"
        self.assertIsNone(resolve_wallet_from_pr_body(body))
        self.assertEqual(
            resolve_wallet_from_pr_body_details(body),
            (None, "wallet_not_found"),
        )

    def test_real_sample_5692_parses(self):
        body = (SAMPLE_DIR / "sample_pr5692_body.txt").read_text()
        expected = "RTCd1acb2189e9f36df2b5393c3c27a867c3c32b116"
        self.assertEqual(resolve_wallet_from_pr_body(body), expected)

    def test_real_sample_5680_parses(self):
        body = (SAMPLE_DIR / "sample_pr5680_body.txt").read_text()
        expected = "RTC0a1c0ce2204390bc49ecf9780fe894da9dc3d92c"
        self.assertEqual(resolve_wallet_from_pr_body(body), expected)

    def test_real_sample_5666_is_rejected_as_invalid_wallet(self):
        body = (SAMPLE_DIR / "sample_pr5666_body.txt").read_text()
        self.assertIsNone(resolve_wallet_from_pr_body(body))
        self.assertEqual(
            resolve_wallet_from_pr_body_details(body),
            (None, "wallet_not_found"),
        )


class TestResolveWalletFromFile(unittest.TestCase):
    def test_valid_wallet_file(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text(f"# payout\n{WALLET_A}\n")
            self.assertEqual(resolve_wallet_from_file(td), WALLET_A)

    def test_invalid_wallet_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text("alice\n")
            self.assertIsNone(resolve_wallet_from_file(td))

    def test_resolve_wallet_uses_file_when_pr_body_has_no_wallet(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text(f"{WALLET_B}\n")
            self.assertEqual(resolve_wallet("No wallet here.\n", td), WALLET_B)
            self.assertEqual(resolve_wallet_details("No wallet here.\n", td), (WALLET_B, None))

    def test_ambiguous_pr_body_blocks_file_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".rtc-wallet").write_text(f"{WALLET_C}\n")
            body = f"wallet: {WALLET_A}\nPayment: RTC | {WALLET_B}\n"
            self.assertIsNone(resolve_wallet(body, td))
            self.assertEqual(resolve_wallet_details(body, td), (None, "ambiguous_pr_wallets"))


class TestCheckAlreadyAwarded(unittest.TestCase):
    def test_marker_present(self):
        comments = [{"body": f"Some text {_AWARD_MARKER} tx=abc"}]
        self.assertTrue(check_already_awarded(comments))

    def test_dry_run_marker_does_not_block_real_award(self):
        comments = [{"body": f"<!-- {_AWARD_MARKER} (dry-run) -->"}]
        self.assertFalse(check_already_awarded(comments))

    def test_manual_required_marker_blocks_automatic_retry(self):
        comments = [{"body": f"<!-- {_AWARD_MARKER}:MANUAL-REQUIRED -->"}]
        self.assertTrue(check_already_awarded(comments))


class TestConfig(unittest.TestCase):
    def _cfg(self, **overrides):
        env = {
            "INPUT_RTC_AMOUNT": "50",
            "INPUT_RTC_API_URL": "",
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

    def test_validate_ok(self):
        self.assertIsNone(self._cfg().validate())

    def test_validate_rejects_nan_amount(self):
        self.assertEqual(self._cfg(INPUT_RTC_AMOUNT="nan").validate(), "rtc-amount must be finite, got nan")

    def test_validate_allows_api_url_without_legacy_host(self):
        cfg = self._cfg(
            INPUT_RTC_API_URL="https://rustchain.org/wallet/transfer",
            INPUT_RTC_VPS_HOST="",
        )
        self.assertIsNone(cfg.validate())


class TestEndpointUnreachableError(unittest.TestCase):
    def test_matches_common_network_failures(self):
        samples = [
            "Connection failed: [Errno 111] Connection refused",
            "timed out while connecting",
            "Temporary failure in name resolution",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(is_endpoint_unreachable_error(sample))

    def test_does_not_match_business_logic_rejections(self):
        self.assertFalse(is_endpoint_unreachable_error("invalid recipient wallet"))


class TestSetOutput(unittest.TestCase):
    def test_set_output_writes_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name
        try:
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}, clear=True):
                set_output("awarded", "true")
                set_output("amount", "5.0")
            self.assertIn("awarded=true", Path(output_file).read_text())
        finally:
            os.unlink(output_file)


class TestTransferRtc(unittest.TestCase):
    def test_build_transfer_url_preserves_full_path(self):
        self.assertEqual(
            build_transfer_url("https://rustchain.org/wallet/transfer"),
            "https://rustchain.org/wallet/transfer",
        )

    def test_build_transfer_url_appends_transfer_path_to_origin(self):
        self.assertEqual(
            build_transfer_url("https://rustchain.org"),
            "https://rustchain.org/wallet/transfer",
        )

    def test_build_transfer_url_keeps_legacy_host_mode(self):
        self.assertEqual(
            build_transfer_url("1.2.3.4"),
            "http://1.2.3.4:8099/wallet/transfer",
        )

    def test_strips_scalar_request_values(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "tx_hash": "tx_abc"}'

        with patch("award_rtc_patched.urlopen", return_value=mock_resp) as mock_urlopen:
            ok, result = transfer_rtc(
                " https://rustchain.org/wallet/transfer\n",
                " test-admin-key\n",
                " founder_community\n",
                f" {WALLET_A}\n",
                5.0,
                "PR #4559 auto-bounty",
            )

        self.assertTrue(ok)
        self.assertEqual(result["tx_hash"], "tx_abc")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://rustchain.org/wallet/transfer")
        self.assertEqual(req.get_header("X-admin-key"), "test-admin-key")

        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["from_miner"], "founder_community")
        self.assertEqual(payload["to_miner"], WALLET_A)

    def test_rejects_invalid_recipient_before_network_call(self):
        with patch("award_rtc_patched.urlopen") as mock_urlopen:
            ok, result = transfer_rtc(
                "https://rustchain.org/wallet/transfer",
                "admin",
                "founder_community",
                "alice",
                5.0,
                "memo",
            )
        self.assertFalse(ok)
        self.assertIn("Refusing transfer", result["error"])
        mock_urlopen.assert_not_called()


class TestMainFlow(unittest.TestCase):
    def _env(self, **overrides):
        output_file = tempfile.NamedTemporaryFile(delete=False)
        output_file.close()
        env = {
            "INPUT_RTC_AMOUNT": "75",
            "INPUT_RTC_API_URL": "",
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
            "PR_BODY": f"wallet: {WALLET_A}\n",
            "PR_HEAD_SHA": "abc123",
            "PR_TITLE": "Test PR",
            "GITHUB_OUTPUT": output_file.name,
        }
        env.update(overrides)
        return patch.dict(os.environ, env, clear=True)

    def test_skip_when_not_merged(self):
        from award_rtc_patched import main

        with self._env(PR_MERGED="false"):
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                rc = main()
        self.assertEqual(rc, 0)

    def test_skip_already_awarded(self):
        from award_rtc_patched import main

        comments = [{"body": f"<!-- {_AWARD_MARKER} tx=old -->"}]
        with self._env():
            with patch("award_rtc_patched.fetch_pr_comments", return_value=comments):
                rc = main()
        self.assertEqual(rc, 0)

    def test_dry_run_mode(self):
        from award_rtc_patched import main

        with self._env(INPUT_DRY_RUN="true"):
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.post_pr_comment") as mock_post:
                    rc = main()
        self.assertEqual(rc, 0)
        mock_post.assert_called_once()

    def test_successful_transfer(self):
        from award_rtc_patched import main

        transfer_result = {
            "ok": True,
            "phase": "pending",
            "pending_id": 99,
            "tx_hash": "tx_abc123",
            "confirms_in_hours": 24,
        }
        with self._env():
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.transfer_rtc", return_value=(True, transfer_result)):
                    with patch("award_rtc_patched.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)

    def test_connection_failure_posts_manual_notice_without_failing_job(self):
        from award_rtc_patched import main

        transfer_result = {
            "ok": False,
            "error": "Connection failed: [Errno 111] Connection refused",
        }
        with self._env():
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.transfer_rtc", return_value=(False, transfer_result)):
                    with patch("award_rtc_patched.post_pr_comment", return_value=True) as mock_post:
                        rc = main()
        self.assertEqual(rc, 0)
        self.assertIn("Manual Transfer Required", mock_post.call_args[0][2])

    def test_bounty_override_in_pr_body(self):
        from award_rtc_patched import main

        transfer_result = {
            "ok": True,
            "phase": "pending",
            "pending_id": 100,
            "tx_hash": "tx_override",
        }
        body = f"wallet: {WALLET_A}\nbounty: 200 RTC\n"
        with self._env(PR_BODY=body, INPUT_RTC_AMOUNT="50"):
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.transfer_rtc", return_value=(True, transfer_result)) as mock_tx:
                    with patch("award_rtc_patched.post_pr_comment", return_value=True):
                        rc = main()
        self.assertEqual(rc, 0)
        self.assertEqual(mock_tx.call_args[0][4], 200.0)

    def test_missing_wallet_fails_without_transfer(self):
        from award_rtc_patched import main

        with self._env(PR_BODY="Just a regular PR\n", PR_AUTHOR="bob"):
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.transfer_rtc") as mock_tx:
                    rc = main()
        self.assertEqual(rc, 1)
        mock_tx.assert_not_called()

    def test_github_username_only_pr_body_fails_without_transfer(self):
        from award_rtc_patched import main

        with self._env(PR_BODY="wallet: bob\n", PR_AUTHOR="bob"):
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.transfer_rtc") as mock_tx:
                    rc = main()
        self.assertEqual(rc, 1)
        mock_tx.assert_not_called()

    def test_ambiguous_wallets_fail_without_transfer(self):
        from award_rtc_patched import main

        body = f"wallet: {WALLET_A}\nPayment: RTC | {WALLET_B}\n"
        with self._env(PR_BODY=body):
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.transfer_rtc") as mock_tx:
                    rc = main()
        self.assertEqual(rc, 1)
        mock_tx.assert_not_called()

    def test_invalid_wallet_safety_gate_blocks_transfer(self):
        from award_rtc_patched import main

        with self._env():
            with patch("award_rtc_patched.fetch_pr_comments", return_value=[]):
                with patch("award_rtc_patched.resolve_wallet_details", return_value=("alice", None)):
                    with patch("award_rtc_patched.transfer_rtc") as mock_tx:
                        rc = main()
        self.assertEqual(rc, 1)
        mock_tx.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
