# SPDX-License-Identifier: MIT
"""
Tests for the bounty verifier system.
Tests GitHub API checks, wallet verification, article validation, and claim processing.
"""
import json
import unittest
from unittest.mock import patch, MagicMock, call
import requests

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from bounty_verifier.core import BountyVerifier, ClaimParser
from bounty_verifier.github_api import GitHubAPI
from bounty_verifier.validators import WalletValidator, ArticleValidator


def mock_response(data=None, ok=True, status_code=200, text=None):
    """Create a mock response object"""
    r = MagicMock()
    r.ok = ok
    r.status_code = status_code
    if data:
        r.json.return_value = data
        r.text = text or json.dumps(data)
    else:
        r.text = text or ""
        r.json.side_effect = json.JSONDecodeError("No JSON", "", 0)
    return r


class TestClaimParser(unittest.TestCase):

    def setUp(self):
        self.parser = ClaimParser()

    def test_parse_star_claim(self):
        comment = "I claim the star bounty! My GitHub: @testuser123"
        result = self.parser.parse_claim(comment)
        self.assertIn('github_username', result)
        self.assertEqual(result['github_username'], 'testuser123')
        self.assertIn('claim_type', result)

    def test_parse_follow_claim(self):
        comment = "Claiming follow task - username: developer42"
        result = self.parser.parse_claim(comment)
        self.assertIn('github_username', result)
        self.assertEqual(result['github_username'], 'developer42')

    def test_parse_wallet_claim(self):
        comment = "claim wallet: rtc_wallet_abc123xyz"
        result = self.parser.parse_claim(comment)
        self.assertIn('wallet_address', result)
        self.assertEqual(result['wallet_address'], 'rtc_wallet_abc123xyz')

    def test_parse_article_claim(self):
        comment = """claim article verification
        Link: https://dev.to/myuser/rustchain-guide-1234
        GitHub: @articleauthor"""
        result = self.parser.parse_claim(comment)
        self.assertIn('article_url', result)
        self.assertIn('github_username', result)
        self.assertEqual(result['article_url'], 'https://dev.to/myuser/rustchain-guide-1234')

    def test_parse_invalid_claim(self):
        comment = "Just a regular comment, no claim here"
        result = self.parser.parse_claim(comment)
        self.assertIsNone(result)


class TestGitHubAPI(unittest.TestCase):

    def setUp(self):
        self.api = GitHubAPI("fake_token")

    @patch('bounty_verifier.github_api.requests.get')
    def test_check_user_starred_success(self, mock_get):
        mock_get.return_value = mock_response(status_code=204)
        result = self.api.check_user_starred("testuser", "owner", "repo")
        self.assertTrue(result)
        mock_get.assert_called_once()

    @patch('bounty_verifier.github_api.requests.get')
    def test_check_user_starred_not_starred(self, mock_get):
        mock_get.return_value = mock_response(status_code=404)
        result = self.api.check_user_starred("testuser", "owner", "repo")
        self.assertFalse(result)

    @patch('bounty_verifier.github_api.requests.get')
    def test_check_user_follows_success(self, mock_get):
        mock_get.return_value = mock_response(status_code=204)
        result = self.api.check_user_follows("follower", "target")
        self.assertTrue(result)

    @patch('bounty_verifier.github_api.requests.get')
    def test_check_user_follows_not_following(self, mock_get):
        mock_get.return_value = mock_response(status_code=404)
        result = self.api.check_user_follows("follower", "target")
        self.assertFalse(result)

    @patch('bounty_verifier.github_api.requests.get')
    def test_get_issue_comments(self, mock_get):
        comments_data = [
            {"id": 1, "user": {"login": "user1"}, "body": "First comment"},
            {"id": 2, "user": {"login": "user2"}, "body": "Second comment"}
        ]
        mock_get.return_value = mock_response(comments_data)
        result = self.api.get_issue_comments("owner", "repo", 123)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["user"]["login"], "user1")


class TestWalletValidator(unittest.TestCase):

    def setUp(self):
        self.validator = WalletValidator("http://test-node:8545")

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_wallet_exists(self, mock_get):
        mock_get.return_value = mock_response({
            "amount_rtc": 50.25,
            "miner_id": "rtc_test_wallet123"
        })
        result = self.validator.validate_wallet("rtc_test_wallet123")
        self.assertTrue(result)

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_wallet_not_found(self, mock_get):
        mock_get.return_value = mock_response(status_code=404)
        result = self.validator.validate_wallet("invalid_wallet")
        self.assertFalse(result)

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_wallet_network_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Network unreachable")
        result = self.validator.validate_wallet("some_wallet")
        self.assertFalse(result)


class TestArticleValidator(unittest.TestCase):

    def setUp(self):
        self.validator = ArticleValidator()

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_dev_to_article(self, mock_get):
        html_content = """
        <html>
        <head><title>RustChain Guide</title></head>
        <body>
        <article>
        <p>This is a comprehensive guide to RustChain development.</p>
        <p>It covers blockchain fundamentals, consensus mechanisms, and practical implementation details.</p>
        <p>The RustChain ecosystem provides developers with powerful tools for building decentralized applications.</p>
        </article>
        </body>
        </html>
        """
        mock_get.return_value = mock_response(text=html_content, status_code=200)
        result = self.validator.validate_article("https://dev.to/user/rustchain-guide")
        self.assertTrue(result['is_valid'])
        self.assertGreater(result['word_count'], 20)

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_article_not_found(self, mock_get):
        mock_get.return_value = mock_response(status_code=404)
        result = self.validator.validate_article("https://dev.to/user/nonexistent")
        self.assertFalse(result['is_valid'])

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_medium_article(self, mock_get):
        html_content = """
        <html>
        <body>
        <div class="section-content">
        <p>Medium article about blockchain technology and RustChain implementation.</p>
        <p>This article explores the technical aspects of consensus algorithms.</p>
        <p>We discuss proof-of-work, proof-of-stake, and hybrid approaches in modern blockchain systems.</p>
        </div>
        </body>
        </html>
        """
        mock_get.return_value = mock_response(text=html_content, status_code=200)
        result = self.validator.validate_article("https://medium.com/@user/blockchain-guide")
        self.assertTrue(result['is_valid'])

    @patch('bounty_verifier.validators.requests.get')
    def test_validate_article_insufficient_content(self, mock_get):
        html_content = "<html><body><p>Too short</p></body></html>"
        mock_get.return_value = mock_response(text=html_content, status_code=200)
        result = self.validator.validate_article("https://dev.to/user/short-post")
        self.assertFalse(result['is_valid'])
        self.assertLess(result['word_count'], 10)


class TestBountyVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = BountyVerifier(
            github_token="fake_token",
            node_url="http://test-node:8545",
            owner="testowner",
            repo="testrepo"
        )

    @patch.object(GitHubAPI, 'check_user_starred')
    @patch.object(GitHubAPI, 'post_comment')
    def test_verify_star_claim_success(self, mock_post, mock_starred):
        mock_starred.return_value = True

        claim_data = {
            'claim_type': 'star',
            'github_username': 'testuser',
            'user_login': 'testuser'
        }

        result = self.verifier.verify_claim(123, claim_data)
        self.assertTrue(result['verified'])
        mock_post.assert_called_once()

    @patch.object(GitHubAPI, 'check_user_starred')
    @patch.object(GitHubAPI, 'post_comment')
    def test_verify_star_claim_failure(self, mock_post, mock_starred):
        mock_starred.return_value = False

        claim_data = {
            'claim_type': 'star',
            'github_username': 'testuser',
            'user_login': 'testuser'
        }

        result = self.verifier.verify_claim(123, claim_data)
        self.assertFalse(result['verified'])
        mock_post.assert_called_once()

    @patch.object(GitHubAPI, 'get_issue_comments')
    def test_check_duplicate_claims(self, mock_comments):
        mock_comments.return_value = [
            {"user": {"login": "user1"}, "body": "claim star - @user1"},
            {"user": {"login": "user2"}, "body": "claim follow - @user2"},
            {"user": {"login": "user1"}, "body": "claim wallet: rtc_123"}
        ]

        has_duplicate = self.verifier.check_duplicate_claims(123, "user1", "star")
        self.assertTrue(has_duplicate)

        no_duplicate = self.verifier.check_duplicate_claims(123, "user3", "star")
        self.assertFalse(no_duplicate)

    @patch.object(WalletValidator, 'validate_wallet')
    @patch.object(GitHubAPI, 'post_comment')
    def test_verify_wallet_claim(self, mock_post, mock_wallet):
        mock_wallet.return_value = True

        claim_data = {
            'claim_type': 'wallet',
            'wallet_address': 'rtc_valid_wallet123',
            'user_login': 'testuser'
        }

        result = self.verifier.verify_claim(123, claim_data)
        self.assertTrue(result['verified'])
        mock_post.assert_called_once()

    @patch.object(ArticleValidator, 'validate_article')
    @patch.object(GitHubAPI, 'post_comment')
    def test_verify_article_claim(self, mock_post, mock_article):
        mock_article.return_value = {
            'is_valid': True,
            'word_count': 150,
            'quality_score': 85
        }

        claim_data = {
            'claim_type': 'article',
            'article_url': 'https://dev.to/user/great-article',
            'user_login': 'testuser'
        }

        result = self.verifier.verify_claim(123, claim_data)
        self.assertTrue(result['verified'])
        mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
