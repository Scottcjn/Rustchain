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

        self.verifier = BountyVerifier()
        # Override DB_PATH for testing
        self.verifier.DB_PATH = self.db_path

    def tearDown(self):
        os.unlink(self.db_path)

    @patch('requests.get')
    def test_verify_github_star_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'login': 'testuser'}, {'login': 'otheruser'}]
        mock_get.return_value = mock_response

        success, message = self.verifier.verify_github_star('testuser', 'testowner', 'testrepo')

        self.assertTrue(success)
        self.assertIn('has starred', message)
        mock_get.assert_called_once_with(
            'https://api.github.com/repos/testowner/testrepo/stargazers'
        )

    @patch('requests.get')
    def test_verify_github_star_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        success, message = self.verifier.verify_github_star('testuser', 'nonexistent', 'repo')

        self.assertFalse(success)
        self.assertIn('API Error', message)

    @patch('requests.get')
    def test_verify_github_follow_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_get.return_value = mock_response

        success, message = self.verifier.verify_github_follow('testuser', 'targetuser')

        self.assertTrue(success)
        self.assertIn('is following', message)
        mock_get.assert_called_once_with(
            'https://api.github.com/users/testuser/following/targetuser'
        )

    @patch('requests.get')
    def test_verify_article_mention_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'This article mentions Rustchain blockchain technology.'
        mock_get.return_value = mock_response

        success, message = self.verifier.verify_article_mention('https://example.com/article', 'Rustchain')

        self.assertTrue(success)
        self.assertIn('contains required mention', message)

    def test_store_claim(self):
        success, message = self.verifier.store_claim('testuser', 'star', 'owner/repo', 'verified')

        self.assertTrue(success)
        self.assertIn('Claim stored', message)

    def test_process_claim_star(self):
        with patch.object(self.verifier, 'verify_github_star') as mock_star:
            mock_star.return_value = (True, 'Success')

            results = self.verifier.process_claim('testuser', 'I want to CLAIM: STAR owner/repo')

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['type'], 'star')
            self.assertTrue(results[0]['success'])

if __name__ == '__main__':
    unittest.main()
