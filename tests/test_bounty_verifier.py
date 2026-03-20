# SPDX-License-Identifier: MIT
"""
Tests for the bounty verification system.
Tests verification logic, GitHub API integration, and error scenarios.
"""
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os

from tools.bounty_verifier.verifier import BountyVerifier, UserClaim
from tools.bounty_verifier.github_client import GitHubClient


def mock_response(data, status_code=200, ok=True):
    r = MagicMock()
    r.status_code = status_code
    r.ok = ok
    r.json.return_value = data
    r.text = json.dumps(data) if isinstance(data, dict) else str(data)
    return r


class TestBountyVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = BountyVerifier("test-token", "test-owner", "test-repo", dry_run=True)
        self.sample_issue = {
            "number": 123,
            "title": "BOUNTY: 50-75 RTC] Bounty Verification Bot",
            "body": """### What to Build
            A bot that verifies bounty claims.

            ### Requirements
            - Star the repository
            - Follow @scottcjn
            - Have a RustChain wallet
            - Write article on dev.to

            ### Payout
            Total: 75 RTC""",
            "labels": [{"name": "bounty"}, {"name": "BCOS-L2"}]
        }

    @patch('requests.get')
    def test_check_star_verified(self, mock_get):
        mock_get.return_value = mock_response({"starred": True})
        result = self.verifier.check_star("testuser")
        self.assertTrue(result)
        mock_get.assert_called_with(
            "https://api.github.com/user/starred/test-owner/test-repo",
            headers={"Authorization": "token test-token", "X-GitHub-Api-Version": "2022-11-28"}
        )

    @patch('requests.get')
    def test_check_star_not_verified(self, mock_get):
        mock_get.return_value = mock_response({}, status_code=404, ok=False)
        result = self.verifier.check_star("testuser")
        self.assertFalse(result)

    @patch('requests.get')
    def test_check_follow_verified(self, mock_get):
        mock_get.return_value = mock_response([{"login": "scottcjn"}])
        result = self.verifier.check_follow("testuser", "scottcjn")
        self.assertTrue(result)

    @patch('requests.get')
    def test_check_follow_not_verified(self, mock_get):
        mock_get.return_value = mock_response([{"login": "someoneelse"}])
        result = self.verifier.check_follow("testuser", "scottcjn")
        self.assertFalse(result)

    @patch('requests.get')
    def test_wallet_exists(self, mock_get):
        mock_get.return_value = mock_response({
            "miner_id": "test-wallet-123",
            "amount_rtc": 25.5
        })
        result = self.verifier.check_wallet("test-wallet-123")
        self.assertTrue(result)

    @patch('requests.get')
    def test_wallet_not_exists(self, mock_get):
        mock_get.return_value = mock_response({}, status_code=404, ok=False)
        result = self.verifier.check_wallet("invalid-wallet")
        self.assertFalse(result)

    @patch('requests.get')
    def test_article_url_valid(self, mock_get):
        mock_get.return_value = mock_response("<html><body>Test article content</body></html>")
        result = self.verifier.check_article_url("https://dev.to/user/article")
        self.assertTrue(result)

    @patch('requests.get')
    def test_article_url_invalid(self, mock_get):
        mock_get.return_value = mock_response("", status_code=404, ok=False)
        result = self.verifier.check_article_url("https://dev.to/user/nonexistent")
        self.assertFalse(result)

    def test_parse_claim_comment_valid(self):
        comment_body = """I want to claim this bounty!

        GitHub: @testuser
        Wallet: test-wallet-123
        Article: https://dev.to/testuser/bounty-verification-bot

        Please verify my claim."""

        claim = self.verifier.parse_claim_comment(comment_body, "testuser")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.username, "testuser")
        self.assertEqual(claim.wallet, "test-wallet-123")
        self.assertEqual(claim.article_url, "https://dev.to/testuser/bounty-verification-bot")

    def test_parse_claim_comment_minimal(self):
        comment_body = "claim bounty wallet: my-wallet-456"
        claim = self.verifier.parse_claim_comment(comment_body, "user2")
        self.assertIsNotNone(claim)
        self.assertEqual(claim.username, "user2")
        self.assertEqual(claim.wallet, "my-wallet-456")

    def test_parse_claim_comment_invalid(self):
        comment_body = "Just a regular comment about the issue"
        claim = self.verifier.parse_claim_comment(comment_body, "user3")
        self.assertIsNone(claim)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_duplicate_detection(self, mock_file, mock_exists):
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps({
            "123": {
                "verified_users": ["previoususer"],
                "pending_claims": []
            }
        })

        result = self.verifier.is_duplicate_claim("previoususer", 123)
        self.assertTrue(result)

        result = self.verifier.is_duplicate_claim("newuser", 123)
        self.assertFalse(result)

    @patch('requests.get')
    def test_dev_to_word_count(self, mock_get):
        article_html = """<html><body>
        <div class="crayons-article__main">
            <p>This is a test article with multiple paragraphs.</p>
            <p>It contains enough words to meet quality requirements.</p>
            <p>The bot should count all these words properly.</p>
        </div>
        </body></html>"""

        mock_get.return_value = mock_response(article_html)
        word_count = self.verifier.check_article_word_count("https://dev.to/user/article")
        self.assertGreater(word_count, 15)

    @patch('tools.bounty_verifier.verifier.BountyVerifier.check_star')
    @patch('tools.bounty_verifier.verifier.BountyVerifier.check_follow')
    @patch('tools.bounty_verifier.verifier.BountyVerifier.check_wallet')
    @patch('tools.bounty_verifier.verifier.BountyVerifier.check_article_url')
    def test_verify_claim_success(self, mock_article, mock_wallet, mock_follow, mock_star):
        mock_star.return_value = True
        mock_follow.return_value = True
        mock_wallet.return_value = True
        mock_article.return_value = True

        claim = UserClaim(
            username="testuser",
            wallet="test-wallet-123",
            article_url="https://dev.to/testuser/article"
        )

        result = self.verifier.verify_claim(claim, self.sample_issue)
        self.assertTrue(result.star_verified)
        self.assertTrue(result.follow_verified)
        self.assertTrue(result.wallet_verified)
        self.assertTrue(result.article_verified)

    @patch('tools.bounty_verifier.verifier.BountyVerifier.check_star')
    def test_verify_claim_partial_failure(self, mock_star):
        mock_star.return_value = False

        claim = UserClaim(username="testuser")
        result = self.verifier.verify_claim(claim, self.sample_issue)
        self.assertFalse(result.star_verified)

    def test_extract_bounty_requirements(self):
        issue_body = """### Requirements
        - Star this repository ⭐
        - Follow @scottcjn on GitHub
        - Have an active RustChain wallet
        - Write a dev.to article (min 300 words)"""

        requirements = self.verifier.extract_bounty_requirements(issue_body)
        self.assertIn("star", requirements)
        self.assertIn("follow", requirements)
        self.assertIn("wallet", requirements)
        self.assertIn("article", requirements)

    @patch('requests.post')
    def test_post_verification_comment(self, mock_post):
        mock_post.return_value = mock_response({"id": 12345})

        claim = UserClaim(username="testuser", wallet="test-wallet")
        verification = MagicMock()
        verification.star_verified = True
        verification.follow_verified = True
        verification.wallet_verified = True
        verification.article_verified = False

        self.verifier.post_verification_comment(123, claim, verification)
        mock_post.assert_called_once()

    def test_api_rate_limit_handling(self):
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("API rate limit exceeded")
            result = self.verifier.check_star("testuser")
            self.assertFalse(result)

    def test_network_error_handling(self):
        with patch('requests.get') as mock_get:
            mock_get.side_effect = ConnectionError("Network unreachable")
            result = self.verifier.check_wallet("test-wallet")
            self.assertFalse(result)

    @patch('requests.get')
    def test_medium_article_verification(self, mock_get):
        mock_get.return_value = mock_response("<html><article>Medium article content</article></html>")
        result = self.verifier.check_article_url("https://medium.com/@user/article")
        self.assertTrue(result)


class TestUserClaim(unittest.TestCase):

    def test_user_claim_creation(self):
        claim = UserClaim(
            username="testuser",
            wallet="test-wallet-123",
            article_url="https://dev.to/test/article"
        )
        self.assertEqual(claim.username, "testuser")
        self.assertEqual(claim.wallet, "test-wallet-123")
        self.assertEqual(claim.article_url, "https://dev.to/test/article")

    def test_user_claim_minimal(self):
        claim = UserClaim(username="user")
        self.assertEqual(claim.username, "user")
        self.assertIsNone(claim.wallet)
        self.assertIsNone(claim.article_url)


if __name__ == "__main__":
    unittest.main()
