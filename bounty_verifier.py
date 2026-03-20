# SPDX-License-Identifier: MIT

import sqlite3
import requests
import re
from datetime import datetime
from urllib.parse import urlparse
import hashlib

DB_PATH = 'bounty_claims.db'
GITHUB_API_BASE = 'https://api.github.com'
RUSTCHAIN_API_BASE = 'http://localhost:8000'

class BountyVerifier:

    def __init__(self):
        self.DB_PATH = DB_PATH
        self.init_database()

    def init_database(self):
        """Initialize the bounty claims database"""
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bounty_claims (
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
            conn.commit()

    def verify_github_star(self, username, repo_owner, repo_name):
        """Check if user has starred the repository"""
        url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/stargazers"

        try:
            response = requests.get(url)
            if response.status_code != 200:
                return False, f"API Error: {response.status_code}"

            stargazers = response.json()
            starred_users = [user['login'].lower() for user in stargazers]

            if username.lower() in starred_users:
                return True, f"✓ User {username} has starred {repo_owner}/{repo_name}"
            else:
                return False, f"✗ User {username} has NOT starred {repo_owner}/{repo_name}"

        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"

    def verify_github_follow(self, username, target_user):
        """Check if user is following the target user"""
        url = f"{GITHUB_API_BASE}/users/{username}/following/{target_user}"

        try:
            response = requests.get(url)
            if response.status_code == 204:
                return True, f"✓ User {username} is following {target_user}"
            elif response.status_code == 404:
                return False, f"✗ User {username} is NOT following {target_user}"
            else:
                return False, f"API Error: {response.status_code}"

        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"

    def store_claim(self, username, claim_type, claim_data, verification_status):
        """Store a bounty claim in the database"""
        try:
            claim_hash = hashlib.md5(f"{username}{claim_type}{claim_data}".encode()).hexdigest()

            with sqlite3.connect(self.DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO bounty_claims
                    (github_user, claim_type, claim_data, verification_status, claim_hash, verified_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, claim_type, claim_data, verification_status, claim_hash, datetime.now()))
                conn.commit()

            return True, "Claim stored successfully"

        except sqlite3.Error as e:
            return False, f"Database error: {str(e)}"

    def get_claims(self, username=None):
        """Retrieve bounty claims from the database"""
        try:
            with sqlite3.connect(self.DB_PATH) as conn:
                if username:
                    cursor = conn.execute(
                        'SELECT * FROM bounty_claims WHERE github_user = ? ORDER BY created_at DESC',
                        (username,)
                    )
                else:
                    cursor = conn.execute(
                        'SELECT * FROM bounty_claims ORDER BY created_at DESC'
                    )

                columns = [description[0] for description in cursor.description]
                claims = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return True, claims

        except sqlite3.Error as e:
            return False, f"Database error: {str(e)}"

    def verify_claim(self, username, claim_type, claim_data):
        """Verify a bounty claim based on type"""
        if claim_type == 'star':
            parts = claim_data.split('/')
            if len(parts) != 2:
                return False, "Invalid repository format. Use 'owner/repo'"
            return self.verify_github_star(username, parts[0], parts[1])

        elif claim_type == 'follow':
            return self.verify_github_follow(username, claim_data)

        else:
            return False, f"Unknown claim type: {claim_type}"
