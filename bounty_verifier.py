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
        self.init_database()

    def init_database(self):
        """Initialize the bounty claims database"""
        with sqlite3.connect(DB_PATH) as conn:
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
        """Check if user is following target user"""
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

    def verify_article_mention(self, article_url, required_mention):
        """Verify if article mentions required content"""
        try:
            response = requests.get(article_url, timeout=10)
            if response.status_code != 200:
                return False, f"Failed to fetch article: {response.status_code}"

            content = response.text.lower()
            if required_mention.lower() in content:
                return True, f"✓ Article contains required mention: {required_mention}"
            else:
                return False, f"✗ Article does NOT contain: {required_mention}"

        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"

    def store_claim(self, github_user, claim_type, claim_data, verification_status="pending", **kwargs):
        """Store bounty claim in database"""
        claim_hash = hashlib.md5(f"{github_user}_{claim_type}_{claim_data}".encode()).hexdigest()

        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute('''
                    INSERT INTO bounty_claims
                    (github_user, claim_type, claim_data, verification_status, claim_hash, wallet_address, article_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (github_user, claim_type, claim_data, verification_status, claim_hash,
                     kwargs.get('wallet_address'), kwargs.get('article_url')))
                conn.commit()
                return True, f"Claim stored with hash: {claim_hash}"
            except sqlite3.IntegrityError:
                return False, "Duplicate claim already exists"

    def get_claims_by_user(self, github_user):
        """Get all claims by a specific user"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT * FROM bounty_claims WHERE github_user = ? ORDER BY created_at DESC',
                (github_user,)
            )
            return cursor.fetchall()

    def update_claim_status(self, claim_hash, status, verified_at=None):
        """Update claim verification status"""
        if verified_at is None:
            verified_at = datetime.now()

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'UPDATE bounty_claims SET verification_status = ?, verified_at = ? WHERE claim_hash = ?',
                (status, verified_at, claim_hash)
            )
            conn.commit()

    def process_claim(self, github_user, claim_text):
        """Process and verify a bounty claim"""
        results = []

        # Parse claim for star verification
        star_pattern = r'STAR\s+([\w-]+/[\w-]+)'
        star_matches = re.findall(star_pattern, claim_text, re.IGNORECASE)

        for repo in star_matches:
            repo_owner, repo_name = repo.split('/')
            success, message = self.verify_github_star(github_user, repo_owner, repo_name)
            self.store_claim(github_user, 'star', repo, 'verified' if success else 'failed')
            results.append({'type': 'star', 'target': repo, 'success': success, 'message': message})

        # Parse claim for follow verification
        follow_pattern = r'FOLLOW\s+([\w-]+)'
        follow_matches = re.findall(follow_pattern, claim_text, re.IGNORECASE)

        for target_user in follow_matches:
            success, message = self.verify_github_follow(github_user, target_user)
            self.store_claim(github_user, 'follow', target_user, 'verified' if success else 'failed')
            results.append({'type': 'follow', 'target': target_user, 'success': success, 'message': message})

        # Parse claim for article mention
        article_pattern = r'ARTICLE\s+(https?://[^\s]+)\s+MENTION\s+"([^"]+)"'
        article_matches = re.findall(article_pattern, claim_text, re.IGNORECASE)

        for article_url, mention in article_matches:
            success, message = self.verify_article_mention(article_url, mention)
            self.store_claim(github_user, 'article', f"{article_url}|{mention}",
                           'verified' if success else 'failed', article_url=article_url)
            results.append({'type': 'article', 'target': article_url, 'success': success, 'message': message})

        return results
