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
                CREATE TABLE bounty_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    github_user TEXT NOT NULL,
                    wallet_address TEXT,
                    claim_type TEXT NOT NULL,
                    claim_data TEXT,
                    article_url TEXT,
                    verification_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified_at TIMESTAMP,
                    claim_hash TEXT UNIQUE
                )
            ''')

        self.verifier = BountyVerifier()
        # Override DB_PATH for testing
        self.verifier.DB_PATH = self.db_path
        # Override the DB_PATH in the module
        import bounty_verifier
        bounty_verifier.DB_PATH = self.db_path

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

    def test_store_claim(self):
        success, message = self.verifier.store_claim('testuser', 'star', 'owner/repo', 'verified')
        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
