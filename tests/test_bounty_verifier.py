// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import tempfile
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bounty_verifier import BountyVerifier

class TestBountyVerifier(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE verified_claims (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    claim_type TEXT,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, claim_type)
                )
            ''')

        self.verifier = BountyVerifier(db_path=self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    @patch('requests.get')
    def test_verify_github_star_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'stargazers_count': 42}
        mock_get.return_value = mock_response

        result = self.verifier.verify_github_star('testuser', 'testowner/testrepo')

        self.assertTrue(result['success'])
        self.assertEqual(result['star_count'], 42)
        mock_get.assert_called_once_with(
            'https://api.github.com/repos/testowner/testrepo',
            headers={'Accept': 'application/vnd.github.v3+json'}
        )

    @patch('requests.get')
    def test_verify_github_star_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.verifier.verify_github_star('testuser', 'nonexistent/repo')

        self.assertFalse(result['success'])
        self.assertIn('Repository not found', result['error'])

    @patch('requests.get')
    def test_verify_github_follow_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        result = self.verifier.verify_github_follow('follower', 'following')

        self.assertTrue(result['success'])
        mock_get.assert_called_once_with(
            'https://api.github.com/users/follower/following/following',
            headers={'Accept': 'application/vnd.github.v3+json'}
        )

    @patch('requests.get')
    def test_verify_github_follow_not_following(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.verifier.verify_github_follow('user1', 'user2')

        self.assertFalse(result['success'])
        self.assertIn('not following', result['error'])

    @patch('requests.get')
    def test_verify_wallet_exists(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'balance': 100.50, 'transactions': 5}
        mock_get.return_value = mock_response

        result = self.verifier.verify_wallet_exists('RTC1a2b3c4d5e6f')

        self.assertTrue(result['success'])
        self.assertEqual(result['balance'], 100.50)

    @patch('requests.get')
    def test_verify_wallet_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.verifier.verify_wallet_exists('RTCinvalid')

        self.assertFalse(result['success'])
        self.assertIn('Wallet not found', result['error'])

    @patch('requests.get')
    def test_verify_url_live_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.text = '<html><body>Test article content</body></html>'
        mock_get.return_value = mock_response

        result = self.verifier.verify_url_live('https://dev.to/user/article')

        self.assertTrue(result['success'])
        self.assertIn('Article is accessible', result['message'])

    @patch('requests.get')
    def test_verify_url_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.verifier.verify_url_live('https://dev.to/missing/article')

        self.assertFalse(result['success'])
        self.assertIn('URL not accessible', result['error'])

    def test_parse_claim_comment_star(self):
        comment = "I starred the repo! My wallet: RTC1a2b3c4d5e6f"
        claims = self.verifier.parse_claim_comment(comment)

        self.assertIn('star', claims)
        self.assertEqual(claims['wallet'], 'RTC1a2b3c4d5e6f')

    def test_parse_claim_comment_follow(self):
        comment = "Following now! Wallet address: RTC9z8y7x6w5v"
        claims = self.verifier.parse_claim_comment(comment)

        self.assertIn('follow', claims)
        self.assertEqual(claims['wallet'], 'RTC9z8y7x6w5v')

    def test_parse_claim_comment_article_devto(self):
        comment = "Posted article: https://dev.to/user123/rustchain-tutorial-abc Wallet: RTCtest123"
        claims = self.verifier.parse_claim_comment(comment)

        self.assertIn('article', claims)
        self.assertEqual(claims['article_url'], 'https://dev.to/user123/rustchain-tutorial-abc')
        self.assertEqual(claims['wallet'], 'RTCtest123')

    def test_parse_claim_comment_article_medium(self):
        comment = "My Medium post: https://medium.com/@user/rustchain-guide-456 RTC wallet: RTCmedium789"
        claims = self.verifier.parse_claim_comment(comment)

        self.assertIn('article', claims)
        self.assertEqual(claims['article_url'], 'https://medium.com/@user/rustchain-guide-456')

    def test_parse_claim_comment_multiple_claims(self):
        comment = """
        I completed multiple tasks:
        - Starred the repository ⭐
        - Following the account now
        - Article published: https://dev.to/author/complete-guide-789
        My RustChain wallet: RTCmulti123abc
        """
        claims = self.verifier.parse_claim_comment(comment)

        self.assertIn('star', claims)
        self.assertIn('follow', claims)
        self.assertIn('article', claims)
        self.assertEqual(claims['wallet'], 'RTCmulti123abc')

    def test_check_duplicate_claim_new(self):
        is_duplicate = self.verifier.check_duplicate_claim('newuser', 'star')
        self.assertFalse(is_duplicate)

    def test_check_duplicate_claim_existing(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO verified_claims (username, claim_type) VALUES (?, ?)',
                ('existinguser', 'star')
            )

        is_duplicate = self.verifier.check_duplicate_claim('existinguser', 'star')
        self.assertTrue(is_duplicate)

    def test_record_verified_claim(self):
        self.verifier.record_verified_claim('testuser', 'follow')

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT username, claim_type FROM verified_claims WHERE username = ? AND claim_type = ?',
                ('testuser', 'follow')
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'testuser')
        self.assertEqual(result[1], 'follow')

    @patch('requests.get')
    def test_verify_devto_word_count(self, mock_get):
        html_content = """
        <html><body>
        <article>
            <p>This is a test article about RustChain blockchain technology.</p>
            <p>It explains the consensus mechanism and mining process in detail.</p>
            <p>The article covers advanced topics including smart contracts and DeFi.</p>
        </article>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.verifier.verify_devto_word_count('https://dev.to/user/article')

        self.assertTrue(result['success'])
        self.assertGreater(result['word_count'], 0)

    def test_validate_wallet_format(self):
        valid_wallet = 'RTC1a2b3c4d5e6f7g8h9i0'
        invalid_wallet = 'BTC1invalid'

        self.assertTrue(self.verifier.validate_wallet_format(valid_wallet))
        self.assertFalse(self.verifier.validate_wallet_format(invalid_wallet))

if __name__ == '__main__':
    unittest.main()
