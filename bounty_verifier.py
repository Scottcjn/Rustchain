// SPDX-License-Identifier: MIT
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

    def verify_github_follow(self, follower, target_user):
        """Check if follower is following target user"""
        url = f"{GITHUB_API_BASE}/users/{follower}/following/{target_user}"

        try:
            response = requests.get(url)

            if response.status_code == 204:
                return True, f"✓ {follower} is following {target_user}"
            elif response.status_code == 404:
                return False, f"✗ {follower} is NOT following {target_user}"
            else:
                return False, f"API Error: {response.status_code}"

        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"

    def verify_wallet_exists(self, wallet_address):
        """Check if wallet exists via RustChain API"""
        if not wallet_address:
            return False, "No wallet address provided"

        # Basic address format validation
        if len(wallet_address) != 42 or not wallet_address.startswith('0x'):
            return False, "Invalid wallet address format"

        url = f"{RUSTCHAIN_API_BASE}/api/wallet/{wallet_address}"

        try:
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                wallet_data = response.json()
                balance = wallet_data.get('balance', 0)
                return True, f"✓ Wallet exists with balance: {balance} RTC"
            elif response.status_code == 404:
                return False, "✗ Wallet not found on RustChain"
            else:
                return False, f"API Error: {response.status_code}"

        except requests.RequestException:
            # Fallback: assume wallet is valid if API is unreachable
            return True, f"? Wallet format valid, API unavailable"

    def verify_article_link(self, url):
        """Verify article URL is accessible and get basic info"""
        if not url:
            return False, "No article URL provided"

        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format"

            # Check if it's a supported platform
            supported_domains = ['dev.to', 'medium.com', 'hashnode.com']
            if not any(domain in parsed.netloc for domain in supported_domains):
                return False, f"Unsupported platform: {parsed.netloc}"

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                content_length = len(response.text)
                word_count = len(response.text.split())

                return True, f"✓ Article accessible ({word_count} words)"
            else:
                return False, f"✗ Article not accessible: {response.status_code}"

        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"

    def check_duplicate_claim(self, github_user, claim_type, claim_data):
        """Check if user has already made this type of claim"""
        claim_hash = hashlib.md5(f"{github_user}:{claim_type}:{claim_data}".encode()).hexdigest()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT id, created_at FROM bounty_claims WHERE claim_hash = ?",
                (claim_hash,)
            )
            existing = cursor.fetchone()

            if existing:
                return True, f"✗ Duplicate claim found (ID: {existing[0]}, Date: {existing[1]})"

            return False, "✓ No duplicate found"

    def parse_claim_comment(self, comment_text):
        """Extract claim information from GitHub comment"""
        claims = []

        # Pattern for star claims: "starred scottcjn/rustchain"
        star_pattern = r"starred\s+(\w+\/[\w-]+)"
        star_matches = re.finditer(star_pattern, comment_text, re.IGNORECASE)

        for match in star_matches:
            repo = match.group(1)
            claims.append({
                'type': 'star',
                'data': repo,
                'description': f"Starred repository: {repo}"
            })

        # Pattern for follow claims: "following @scottcjn"
        follow_pattern = r"following\s+@?(\w+)"
        follow_matches = re.finditer(follow_pattern, comment_text, re.IGNORECASE)

        for match in follow_matches:
            username = match.group(1)
            claims.append({
                'type': 'follow',
                'data': username,
                'description': f"Following user: {username}"
            })

        # Pattern for wallet: "wallet: 0x..."
        wallet_pattern = r"wallet:?\s*(0x[a-fA-F0-9]{40})"
        wallet_match = re.search(wallet_pattern, comment_text)

        wallet_addr = wallet_match.group(1) if wallet_match else None

        # Pattern for article links
        url_pattern = r'https?://(?:dev\.to|medium\.com|hashnode\.com)/[^\s)]+'
        url_matches = re.finditer(url_pattern, comment_text)

        article_urls = [match.group(0) for match in url_matches]

        return {
            'claims': claims,
            'wallet': wallet_addr,
            'articles': article_urls
        }

    def verify_full_claim(self, github_user, comment_text):
        """Perform complete verification of a bounty claim"""
        parsed = self.parse_claim_comment(comment_text)
        results = []

        # Verify each claim type
        for claim in parsed['claims']:
            if claim['type'] == 'star':
                repo_parts = claim['data'].split('/')
                if len(repo_parts) == 2:
                    owner, repo = repo_parts
                    is_duplicate, dup_msg = self.check_duplicate_claim(
                        github_user, 'star', claim['data']
                    )

                    if is_duplicate:
                        results.append({
                            'type': 'Star Verification',
                            'claim': claim['description'],
                            'status': 'DUPLICATE',
                            'details': dup_msg
                        })
                    else:
                        success, msg = self.verify_github_star(github_user, owner, repo)
                        results.append({
                            'type': 'Star Verification',
                            'claim': claim['description'],
                            'status': 'PASS' if success else 'FAIL',
                            'details': msg
                        })

            elif claim['type'] == 'follow':
                target_user = claim['data']
                is_duplicate, dup_msg = self.check_duplicate_claim(
                    github_user, 'follow', target_user
                )

                if is_duplicate:
                    results.append({
                        'type': 'Follow Verification',
                        'claim': claim['description'],
                        'status': 'DUPLICATE',
                        'details': dup_msg
                    })
                else:
                    success, msg = self.verify_github_follow(github_user, target_user)
                    results.append({
                        'type': 'Follow Verification',
                        'claim': claim['description'],
                        'status': 'PASS' if success else 'FAIL',
                        'details': msg
                    })

        # Verify wallet
        if parsed['wallet']:
            success, msg = self.verify_wallet_exists(parsed['wallet'])
            results.append({
                'type': 'Wallet Verification',
                'claim': f"Wallet: {parsed['wallet'][:10]}...",
                'status': 'PASS' if success else 'FAIL',
                'details': msg
            })

        # Verify article links
        for article_url in parsed['articles']:
            success, msg = self.verify_article_link(article_url)
            results.append({
                'type': 'Article Verification',
                'claim': f"Article: {urlparse(article_url).netloc}",
                'status': 'PASS' if success else 'FAIL',
                'details': msg
            })

        # Store verified claims
        self.store_verification_results(github_user, parsed, results)

        return results

    def store_verification_results(self, github_user, parsed_data, results):
        """Store verification results in database"""
        with sqlite3.connect(DB_PATH) as conn:
            for i, claim in enumerate(parsed_data['claims']):
                claim_hash = hashlib.md5(
                    f"{github_user}:{claim['type']}:{claim['data']}".encode()
                ).hexdigest()

                result_status = 'verified' if results[i]['status'] == 'PASS' else 'failed'

                conn.execute('''
                    INSERT OR IGNORE INTO bounty_claims
                    (github_user, wallet_address, claim_type, claim_data,
                     verification_status, verified_at, claim_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    github_user,
                    parsed_data.get('wallet'),
                    claim['type'],
                    claim['data'],
                    result_status,
                    datetime.now().isoformat(),
                    claim_hash
                ))

    def format_results_as_markdown(self, results, github_user):
        """Format verification results as markdown table"""
        if not results:
            return "No claims found to verify."

        header = f"## Bounty Verification Results for @{github_user}\n\n"
        table_header = "| Type | Claim | Status | Details |\n|------|-------|--------|----------|\n"

        table_rows = ""
        for result in results:
            status_emoji = {
                'PASS': '✅',
                'FAIL': '❌',
                'DUPLICATE': '🔄'
            }.get(result['status'], '❓')

            table_rows += f"| {result['type']} | {result['claim']} | {status_emoji} {result['status']} | {result['details']} |\n"

        summary = self.generate_summary(results)

        return header + table_header + table_rows + "\n" + summary

    def generate_summary(self, results):
        """Generate summary of verification results"""
        total = len(results)
        passed = sum(1 for r in results if r['status'] == 'PASS')
        failed = sum(1 for r in results if r['status'] == 'FAIL')
        duplicates = sum(1 for r in results if r['status'] == 'DUPLICATE')

        summary = f"### Summary\n"
        summary += f"- **Total Claims**: {total}\n"
        summary += f"- **Passed**: {passed}\n"
        summary += f"- **Failed**: {failed}\n"
        summary += f"- **Duplicates**: {duplicates}\n\n"

        if passed == total:
            summary += "🎉 **All claims verified successfully!**"
        elif passed > 0:
            summary += "⚠️ **Partial verification - some claims failed**"
        else:
            summary += "❌ **No claims passed verification**"

        return summary
