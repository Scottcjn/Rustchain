// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import re
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = 'rustchain.db'
GITHUB_API_BASE = 'https://api.github.com'
RUSTCHAIN_API_BASE = 'http://localhost:8080/api'

class BountyVerifier:
    def __init__(self, github_token: str = None):
        self.github_token = github_token
        self.headers = {
            'User-Agent': 'RustChain-BountyBot/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        if github_token:
            self.headers['Authorization'] = f'token {github_token}'

        self.init_db()

    def init_db(self):
        """Initialize database tables for bounty verification"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bounty_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    github_username TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    issue_number INTEGER,
                    comment_id INTEGER,
                    wallet_address TEXT,
                    article_url TEXT,
                    claim_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    verification_status TEXT DEFAULT 'pending',
                    verification_results TEXT,
                    payout_amount REAL DEFAULT 0,
                    UNIQUE(github_username, claim_type, issue_number)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS verification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER,
                    verification_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (claim_id) REFERENCES bounty_claims (id)
                )
            ''')
            conn.commit()

    def parse_bounty_claim(self, comment_body: str, username: str) -> Dict:
        """Extract bounty claim information from comment"""
        claim_data = {
            'github_username': username,
            'wallet_address': None,
            'article_url': None,
            'claim_types': []
        }

        # Look for wallet address
        wallet_pattern = r'(?:wallet|address)[:=]\s*([a-zA-Z0-9]{26,44})'
        wallet_match = re.search(wallet_pattern, comment_body, re.IGNORECASE)
        if wallet_match:
            claim_data['wallet_address'] = wallet_match.group(1)

        # Look for article URLs
        url_patterns = [
            r'https?://dev\.to/[^\s]+',
            r'https?://medium\.com/[^\s]+',
            r'https?://[^\s]+\.medium\.com/[^\s]+',
            r'https?://hashnode\.com/[^\s]+',
            r'https?://[a-zA-Z0-9-]+\.hashnode\.dev/[^\s]+'
        ]

        for pattern in url_patterns:
            url_match = re.search(pattern, comment_body)
            if url_match:
                claim_data['article_url'] = url_match.group(0)
                break

        # Detect claim types from keywords
        comment_lower = comment_body.lower()
        if any(word in comment_lower for word in ['starred', 'star', 'github star']):
            claim_data['claim_types'].append('github_star')
        if any(word in comment_lower for word in ['followed', 'follow', 'github follow']):
            claim_data['claim_types'].append('github_follow')
        if claim_data['article_url']:
            claim_data['claim_types'].append('article_submission')

        return claim_data

    def verify_github_star(self, username: str, repo_owner: str = 'Scottcjn', repo_name: str = 'Rustchain') -> Tuple[bool, str]:
        """Verify if user has starred the repository"""
        try:
            url = f"{GITHUB_API_BASE}/user/starred/{repo_owner}/{repo_name}"
            response = requests.get(url, headers=self.headers, auth=(username, ''))

            if response.status_code == 204:
                return True, "Repository is starred"
            elif response.status_code == 404:
                return False, "Repository not starred or user not found"
            else:
                return False, f"API error: {response.status_code}"
        except requests.RequestException as e:
            logger.error(f"GitHub star verification failed: {e}")
            return False, f"Request failed: {str(e)}"

    def verify_github_follow(self, username: str, target_user: str = 'Scottcjn') -> Tuple[bool, str]:
        """Verify if user is following the target user"""
        try:
            url = f"{GITHUB_API_BASE}/user/following/{target_user}"
            response = requests.get(url, headers=self.headers, auth=(username, ''))

            if response.status_code == 204:
                return True, "User is following"
            elif response.status_code == 404:
                return False, "User not following or not found"
            else:
                return False, f"API error: {response.status_code}"
        except requests.RequestException as e:
            logger.error(f"GitHub follow verification failed: {e}")
            return False, f"Request failed: {str(e)}"

    def verify_wallet_exists(self, wallet_address: str) -> Tuple[bool, str]:
        """Check if wallet exists on RustChain network"""
        try:
            url = f"{RUSTCHAIN_API_BASE}/wallet/{wallet_address}/balance"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return True, f"Wallet found with balance: {data.get('balance', 0)} RTC"
            elif response.status_code == 404:
                return False, "Wallet not found on network"
            else:
                return False, f"API error: {response.status_code}"
        except requests.RequestException as e:
            logger.error(f"Wallet verification failed: {e}")
            return False, f"Network request failed: {str(e)}"

    def verify_article_url(self, url: str) -> Tuple[bool, str, int]:
        """Verify article URL is accessible and get word count"""
        try:
            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; RustChain-Bot/1.0)'
            })

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}", 0

            # Simple word count estimation
            text_content = re.sub(r'<[^>]+>', ' ', response.text)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            word_count = len(text_content.split())

            # Quality checks
            quality_indicators = 0
            if word_count >= 500:
                quality_indicators += 1
            if 'rustchain' in text_content.lower():
                quality_indicators += 1
            if any(term in text_content.lower() for term in ['blockchain', 'cryptocurrency', 'rust']):
                quality_indicators += 1

            quality_score = f"Quality: {quality_indicators}/3"
            return True, f"Article accessible - {quality_score}", word_count

        except requests.RequestException as e:
            logger.error(f"Article verification failed: {e}")
            return False, f"Failed to access: {str(e)}", 0

    def check_duplicate_claims(self, username: str, claim_type: str, issue_number: int) -> bool:
        """Check if user has already claimed this bounty type"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM bounty_claims
                WHERE github_username = ? AND claim_type = ? AND issue_number = ?
            ''', (username, claim_type, issue_number))

            count = cursor.fetchone()[0]
            return count > 0

    def calculate_payout(self, verification_results: Dict) -> float:
        """Calculate suggested payout based on verification results"""
        payout = 0.0

        # Base payouts per verification type
        if verification_results.get('github_star', {}).get('verified'):
            payout += 15.0
        if verification_results.get('github_follow', {}).get('verified'):
            payout += 15.0
        if verification_results.get('wallet_exists', {}).get('verified'):
            payout += 10.0

        article_result = verification_results.get('article_verification', {})
        if article_result.get('verified'):
            payout += 10.0  # Base article bonus

            word_count = article_result.get('word_count', 0)
            if word_count >= 500:
                payout += 5.0  # Word count bonus
            if word_count >= 1000:
                payout += 5.0  # Extended article bonus

        return min(payout, 75.0)  # Cap at maximum bounty amount

    def verify_claim(self, comment_body: str, username: str, issue_number: int, comment_id: int) -> Dict:
        """Main verification function"""
        claim_data = self.parse_bounty_claim(comment_body, username)
        verification_results = {}

        logger.info(f"Verifying claim from {username} on issue #{issue_number}")

        # Check for duplicates
        duplicates_found = []
        for claim_type in claim_data['claim_types']:
            if self.check_duplicate_claims(username, claim_type, issue_number):
                duplicates_found.append(claim_type)

        if duplicates_found:
            verification_results['duplicate_claims'] = duplicates_found

        # Verify GitHub actions
        if 'github_star' in claim_data['claim_types']:
            verified, message = self.verify_github_star(username)
            verification_results['github_star'] = {
                'verified': verified,
                'message': message
            }

        if 'github_follow' in claim_data['claim_types']:
            verified, message = self.verify_github_follow(username)
            verification_results['github_follow'] = {
                'verified': verified,
                'message': message
            }

        # Verify wallet
        if claim_data['wallet_address']:
            verified, message = self.verify_wallet_exists(claim_data['wallet_address'])
            verification_results['wallet_exists'] = {
                'verified': verified,
                'message': message,
                'address': claim_data['wallet_address']
            }

        # Verify article
        if claim_data['article_url']:
            verified, message, word_count = self.verify_article_url(claim_data['article_url'])
            verification_results['article_verification'] = {
                'verified': verified,
                'message': message,
                'word_count': word_count,
                'url': claim_data['article_url']
            }

        # Calculate suggested payout
        suggested_payout = self.calculate_payout(verification_results)
        verification_results['suggested_payout'] = suggested_payout

        # Store in database
        self.store_claim(claim_data, issue_number, comment_id, verification_results)

        return verification_results

    def store_claim(self, claim_data: Dict, issue_number: int, comment_id: int, verification_results: Dict):
        """Store claim and verification results in database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            for claim_type in claim_data['claim_types']:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO bounty_claims
                        (github_username, claim_type, issue_number, comment_id,
                         wallet_address, article_url, verification_results, payout_amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        claim_data['github_username'],
                        claim_type,
                        issue_number,
                        comment_id,
                        claim_data.get('wallet_address'),
                        claim_data.get('article_url'),
                        json.dumps(verification_results),
                        verification_results.get('suggested_payout', 0)
                    ))
                    conn.commit()
                except sqlite3.IntegrityError:
                    logger.warning(f"Duplicate claim attempt: {claim_data['github_username']} - {claim_type}")

    def format_verification_comment(self, verification_results: Dict, username: str) -> str:
        """Format verification results as GitHub comment"""
        comment_lines = [
            f"## 🤖 Bounty Verification Results for @{username}",
            ""
        ]

        # Check for duplicates first
        if verification_results.get('duplicate_claims'):
            comment_lines.extend([
                "⚠️ **DUPLICATE CLAIMS DETECTED**",
                f"Found existing claims for: {', '.join(verification_results['duplicate_claims'])}",
                ""
            ])

        total_points = 0

        # GitHub verifications
        if 'github_star' in verification_results:
            result = verification_results['github_star']
            status = "✅" if result['verified'] else "❌"
            comment_lines.append(f"{status} **GitHub Star**: {result['message']}")
            if result['verified']:
                total_points += 15

        if 'github_follow' in verification_results:
            result = verification_results['github_follow']
            status = "✅" if result['verified'] else "❌"
            comment_lines.append(f"{status} **GitHub Follow**: {result['message']}")
            if result['verified']:
                total_points += 15

        # Wallet verification
        if 'wallet_exists' in verification_results:
            result = verification_results['wallet_exists']
            status = "✅" if result['verified'] else "❌"
            comment_lines.append(f"{status} **Wallet Check**: {result['message']}")
            if result['verified']:
                total_points += 10

        # Article verification
        if 'article_verification' in verification_results:
            result = verification_results['article_verification']
            status = "✅" if result['verified'] else "❌"
            comment_lines.append(f"{status} **Article**: {result['message']}")
            if result.get('word_count'):
                comment_lines.append(f"   📝 Word count: {result['word_count']}")

        # Payout calculation
        suggested_payout = verification_results.get('suggested_payout', 0)
        comment_lines.extend([
            "",
            f"💰 **Suggested Payout**: {suggested_payout} RTC",
            "",
            "_Automated verification completed._"
        ])

        return "\n".join(comment_lines)

def main():
    """Example usage"""
    verifier = BountyVerifier()

    # Example comment verification
    test_comment = """
    I've starred the repo and followed @Scottcjn!
    My wallet: RTC1234567890abcdef1234567890abcdef
    Article: https://dev.to/example/my-rustchain-article
    """

    results = verifier.verify_claim(test_comment, "testuser", 123, 456)
    formatted_response = verifier.format_verification_comment(results, "testuser")

    print("Verification Results:")
    print("=" * 50)
    print(formatted_response)

if __name__ == "__main__":
    main()
