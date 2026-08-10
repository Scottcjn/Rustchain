#!/usr/bin/env python3
"""
Regression tests for airdrop_v2.claim_airdrop GitHub ownership verification (PR #8180).

Covers:
  - Valid GitHub token + matching username → claim succeeds.
  - Mismatched GitHub username → claim rejected.
  - GitHub API failure / network exception → claim rejected.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

# Ensure the node package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "node"))

from airdrop_v2 import (
    AirdropV2,
    EligibilityTier,
    EligibilityResult,
    ClaimRecord,
)


class TestGitHubOwnershipVerification(unittest.TestCase):
    """Regression tests for the GitHub token ownership check in claim_airdrop (PR #8180)."""

    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.airdrop = AirdropV2(db_path=self.temp_db.name)

    def tearDown(self):
        """Remove temporary database."""
        os.unlink(self.temp_db.name)

    # ------------------------------------------------------------------
    # 1. Valid token + matching GitHub username → claim succeeds
    # ------------------------------------------------------------------
    @patch("airdrop_v2.requests.get")
    def test_valid_token_matching_username_succeeds(self, mock_get):
        """A valid GitHub PAT whose /user endpoint returns the same login
        as the claim request must result in a successful claim."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "validuser"}
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="validuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_validtoken123",
            skip_antisybil=True,
        )

        self.assertTrue(success, f"Expected claim to succeed, got: {message}")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.github_username, "validuser")
        self.assertEqual(claim.tier, "contributor")
        self.assertEqual(claim.amount_uwrtc, EligibilityTier.CONTRIBUTOR.reward_uwrtc)

        # Verify the requests.get call was made with correct args
        mock_get.assert_called_once_with(
            "https://api.github.com/user",
            headers={
                "Authorization": "token ghp_validtoken123",
                "User-Agent": "RustChain-Airdrop",
            },
            timeout=10,
        )

    @patch("airdrop_v2.requests.get")
    def test_valid_token_case_insensitive_username_succeeds(self, mock_get):
        """GitHub username comparison should be case-insensitive (casefolded)."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "ValidUser"}
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="VALIDUSER",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_validtoken456",
            skip_antisybil=True,
        )

        self.assertTrue(success, f"Expected claim to succeed, got: {message}")
        self.assertIsNotNone(claim)
        # Username should be normalized (casefolded)
        self.assertEqual(claim.github_username, "validuser")

    # ------------------------------------------------------------------
    # 2. Mismatched GitHub username → claim rejected
    # ------------------------------------------------------------------
    @patch("airdrop_v2.requests.get")
    def test_mismatched_username_rejected(self, mock_get):
        """When the GitHub /user endpoint returns a different login than
        the one supplied in the claim, the claim must be rejected."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "realowner"}
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="impersonator",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_stolentoken789",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("does not match", message)

    @patch("airdrop_v2.requests.get")
    def test_mismatched_username_case_aware_rejected(self, mock_get):
        """Even if usernames differ only by case in a non-matching way,
        a mismatch is a mismatch (tokens owned by different people)."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        # API returns "alice", claimant says "bob"
        mock_resp.json.return_value = {"login": "alice"}
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="bob",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_alicetoken",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("does not match", message)

    # ------------------------------------------------------------------
    # 3. GitHub API failure / network exception → claim rejected
    # ------------------------------------------------------------------
    @patch("airdrop_v2.requests.get")
    def test_github_api_non_200_rejected(self, mock_get):
        """If the GitHub API returns a non-200 status (e.g. 401 Unauthorized),
        the claim must be rejected with an appropriate message."""
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"message": "Bad credentials"}
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_expiredtoken",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("Failed to verify", message)

    @patch("airdrop_v2.requests.get")
    def test_github_api_500_rejected(self, mock_get):
        """A 500 server error from GitHub must also result in rejection."""
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_anytoken",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("Failed to verify", message)

    @patch("airdrop_v2.requests.get")
    def test_network_exception_rejected(self, mock_get):
        """A network-level exception (ConnectionError, Timeout, etc.)
        must be caught and result in claim rejection."""
        import requests as req_lib

        mock_get.side_effect = req_lib.ConnectionError("DNS resolution failed")

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_anytoken",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("verification failed", message)

    @patch("airdrop_v2.requests.get")
    def test_timeout_exception_rejected(self, mock_get):
        """A Timeout exception must also be handled gracefully."""
        import requests as req_lib

        mock_get.side_effect = req_lib.Timeout("Connection timed out")

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_anytoken",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("verification failed", message)

    # ------------------------------------------------------------------
    # Baseline: no token provided → ownership check is skipped
    # ------------------------------------------------------------------
    def test_no_token_skips_ownership_check(self):
        """When no github_token is provided, the ownership verification
        should be skipped entirely and the claim should proceed normally."""
        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token=None,
            skip_antisybil=True,
        )

        self.assertTrue(success, f"Expected claim to succeed, got: {message}")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.github_username, "testuser")

    @patch("airdrop_v2.requests.get")
    def test_empty_login_field_rejected(self, mock_get):
        """If the GitHub API returns an empty login field, the claim
        must be rejected (login doesn't match any username)."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": ""}
        mock_get.return_value = mock_resp

        success, message, claim = self.airdrop.claim_airdrop(
            github_username="testuser",
            wallet_address="RTC1234567890123456789012345678901234567890",
            chain="base",
            tier="contributor",
            github_token="ghp_anytoken",
            skip_antisybil=True,
        )

        self.assertFalse(success)
        self.assertIsNone(claim)
        self.assertIn("does not match", message)


if __name__ == "__main__":
    unittest.main()
