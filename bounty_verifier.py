# SPDX-License-Identifier: MIT

import re
import json
import sqlite3
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
import requests
from dataclasses import dataclass

# Configuration constants
DB_PATH = 'rustchain.db'
GITHUB_API_BASE = 'https://api.github.com'
RUSTCHAIN_NODE_API = 'http://localhost:8000/api'
REQUEST_TIMEOUT = 30
GITHUB_RATE_LIMIT_DELAY = 1.0
MAX_RETRIES = 3

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ClaimData:
    """Parsed claim information from comment"""
    github_username: str
    wallet_address: str
    article_urls: List[str]
    claim_type: str
    raw_comment: str
    comment_id: int
    issue_number: int

@dataclass
class VerificationResult:
    """Complete verification result"""
    is_valid: bool
    star_verified: bool = False
    follow_verified: bool = False
    wallet_exists: bool = False
    articles_valid: List[bool] = None
    duplicate_claim: bool = False
    error_messages: List[str] = None

    def __post_init__(self):
        if self.articles_valid is None:
            self.articles_valid = []
        if self.error_messages is None:
            self.error_messages = []

class BountyVerifier:
    """Core verification engine for bounty claims"""

    def __init__(self, github_token: str, owner: str = 'Scottcjn', repo: str = 'Rustchain'):
        self.github_token = github_token
        self.owner = owner
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': f'RustChain-BountyBot/{owner}/{repo}'
        })
        self._init_database()

    def _init_database(self):
        """Initialize verification tracking database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bounty_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER UNIQUE,
                    issue_number INTEGER,
                    github_username TEXT,
                    wallet_address TEXT,
                    claim_type TEXT,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    star_verified BOOLEAN DEFAULT FALSE,
                    follow_verified BOOLEAN DEFAULT FALSE,
                    wallet_verified BOOLEAN DEFAULT FALSE,
                    articles_count INTEGER DEFAULT 0,
                    is_duplicate BOOLEAN DEFAULT FALSE,
                    verification_result TEXT
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_username_claim
                ON bounty_verifications(github_username, claim_type)
            ''')

    def parse_comment_claim(self, comment_body: str, comment_id: int, issue_number: int) -> Optional[ClaimData]:
        """Parse bounty claim from comment text"""
        if not self._is_bounty_claim(comment_body):
            return None

        # Extract GitHub username (often same as commenter)
        github_match = re.search(r'(?:github\.com/|@)([a-zA-Z0-9_-]+)', comment_body, re.IGNORECASE)
        if not github_match:
            # Try to extract from context or assume it's in the claim format
            username_match = re.search(r'username[:\s]+([a-zA-Z0-9_-]+)', comment_body, re.IGNORECASE)
            github_username = username_match.group(1) if username_match else None
        else:
            github_username = github_match.group(1)

        # Extract wallet address (RTC addresses)
        wallet_pattern = r'(?:wallet|address)[:\s]*([a-zA-Z0-9]{32,64})'
        wallet_match = re.search(wallet_pattern, comment_body, re.IGNORECASE)
        wallet_address = wallet_match.group(1) if wallet_match else None

        # Extract article URLs
        url_pattern = r'https?://(?:dev\.to|medium\.com|[^\s]+)(?:/[^\s]*)?'
        article_urls = re.findall(url_pattern, comment_body)

        # Determine claim type
        claim_type = self._detect_claim_type(comment_body)

        if not github_username:
            return None

        return ClaimData(
            github_username=github_username,
            wallet_address=wallet_address or '',
            article_urls=article_urls,
            claim_type=claim_type,
            raw_comment=comment_body,
            comment_id=comment_id,
            issue_number=issue_number
        )

    def _is_bounty_claim(self, comment: str) -> bool:
        """Check if comment contains a bounty claim"""
        claim_indicators = [
            'claim', 'claiming', 'bounty', 'starred', 'following',
            'completed', 'done', 'finished', 'wallet', 'rtc'
        ]
        comment_lower = comment.lower()
        return any(indicator in comment_lower for indicator in claim_indicators)

    def _detect_claim_type(self, comment: str) -> str:
        """Detect the type of bounty claim"""
        comment_lower = comment.lower()

        if 'article' in comment_lower or 'dev.to' in comment_lower or 'medium' in comment_lower:
            return 'article'
        elif 'star' in comment_lower:
            return 'star'
        elif 'follow' in comment_lower:
            return 'follow'
        else:
            return 'general'

    def verify_claim(self, claim: ClaimData) -> VerificationResult:
        """Perform complete verification of a bounty claim"""
        result = VerificationResult(is_valid=True)

        try:
            # Check for duplicate claims first
            result.duplicate_claim = self._check_duplicate_claim(claim)
            if result.duplicate_claim:
                result.error_messages.append(f"User {claim.github_username} already has a verified claim")
                result.is_valid = False

            # Verify GitHub star status
            if claim.claim_type in ['star', 'general']:
                result.star_verified = self._verify_star_status(claim.github_username)
                if not result.star_verified:
                    result.error_messages.append(f"Repository not starred by {claim.github_username}")

            # Verify GitHub follow status
            if claim.claim_type in ['follow', 'general']:
                result.follow_verified = self._verify_follow_status(claim.github_username)
                if not result.follow_verified:
                    result.error_messages.append(f"User {claim.github_username} not following {self.owner}")

            # Verify wallet exists on RustChain
            if claim.wallet_address:
                result.wallet_exists = self._verify_wallet_exists(claim.wallet_address)
                if not result.wallet_exists:
                    result.error_messages.append(f"Wallet {claim.wallet_address} not found on RustChain")

            # Verify article URLs
            if claim.article_urls:
                result.articles_valid = []
                for url in claim.article_urls:
                    is_valid = self._verify_article_url(url)
                    result.articles_valid.append(is_valid)
                    if not is_valid:
                        result.error_messages.append(f"Article URL not accessible: {url}")

            # Overall validity check
            if claim.claim_type == 'star':
                result.is_valid = result.star_verified and not result.duplicate_claim
            elif claim.claim_type == 'follow':
                result.is_valid = result.follow_verified and not result.duplicate_claim
            elif claim.claim_type == 'article':
                result.is_valid = (len(result.articles_valid) > 0 and
                                 all(result.articles_valid) and not result.duplicate_claim)
            else:
                result.is_valid = ((result.star_verified or result.follow_verified or
                                  any(result.articles_valid or [])) and not result.duplicate_claim)

        except Exception as e:
            logger.error(f"Verification failed for {claim.github_username}: {e}")
            result.is_valid = False
            result.error_messages.append(f"Verification error: {str(e)}")

        # Store verification result
        self._store_verification_result(claim, result)

        return result

    def _check_duplicate_claim(self, claim: ClaimData) -> bool:
        """Check if user already has a verified claim for this type"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM bounty_verifications
                WHERE github_username = ? AND claim_type = ?
                AND (star_verified = 1 OR follow_verified = 1 OR articles_count > 0)
            ''', (claim.github_username, claim.claim_type))
            return cursor.fetchone()[0] > 0

    def _verify_star_status(self, username: str) -> bool:
        """Check if user has starred the repository"""
        time.sleep(GITHUB_RATE_LIMIT_DELAY)

        for attempt in range(MAX_RETRIES):
            try:
                url = f'{GITHUB_API_BASE}/user/starred/{self.owner}/{self.repo}'

                # Use user's token to check their own starred status
                user_session = requests.Session()
                user_session.headers.update({
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': f'RustChain-BountyBot/{self.owner}/{self.repo}'
                })

                response = user_session.get(url, timeout=REQUEST_TIMEOUT)

                if response.status_code == 204:
                    return True
                elif response.status_code == 404:
                    return False
                else:
                    logger.warning(f"Unexpected status checking star for {username}: {response.status_code}")

            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed checking star for {username}: {e}")
                if attempt == MAX_RETRIES - 1:
                    return False
                time.sleep(2 ** attempt)

        return False

    def _verify_follow_status(self, username: str) -> bool:
        """Check if user is following the repository owner"""
        time.sleep(GITHUB_RATE_LIMIT_DELAY)

        for attempt in range(MAX_RETRIES):
            try:
                url = f'{GITHUB_API_BASE}/user/following/{self.owner}'

                response = self.session.get(url, timeout=REQUEST_TIMEOUT)

                if response.status_code == 204:
                    return True
                elif response.status_code == 404:
                    return False
                else:
                    logger.warning(f"Unexpected status checking follow for {username}: {response.status_code}")

            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed checking follow for {username}: {e}")
                if attempt == MAX_RETRIES - 1:
                    return False
                time.sleep(2 ** attempt)

        return False

    def _verify_wallet_exists(self, wallet_address: str) -> bool:
        """Verify wallet exists on RustChain network"""
        if not wallet_address or len(wallet_address) < 32:
            return False

        try:
            # Query RustChain node API for wallet
            url = f'{RUSTCHAIN_NODE_API}/wallet/{wallet_address}'

            response = requests.get(url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                return data.get('exists', False)
            elif response.status_code == 404:
                return False
            else:
                logger.warning(f"Wallet API returned {response.status_code} for {wallet_address}")
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to verify wallet {wallet_address}: {e}")
            return False

    def _verify_article_url(self, url: str) -> bool:
        """Verify article URL is accessible and valid"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False

            # Check if URL is accessible
            response = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)

            if response.status_code == 200:
                return True
            elif response.status_code in [301, 302, 307, 308]:
                # Follow redirects
                response = requests.get(url, timeout=REQUEST_TIMEOUT)
                return response.status_code == 200
            else:
                return False

        except requests.RequestException as e:
            logger.warning(f"Failed to verify article URL {url}: {e}")
            return False

    def _store_verification_result(self, claim: ClaimData, result: VerificationResult):
        """Store verification result in database"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO bounty_verifications
                    (comment_id, issue_number, github_username, wallet_address, claim_type,
                     star_verified, follow_verified, wallet_verified, articles_count,
                     is_duplicate, verification_result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    claim.comment_id, claim.issue_number, claim.github_username,
                    claim.wallet_address, claim.claim_type, result.star_verified,
                    result.follow_verified, result.wallet_exists, len(result.articles_valid),
                    result.duplicate_claim, json.dumps(result.error_messages)
                ))
        except sqlite3.Error as e:
            logger.error(f"Failed to store verification result: {e}")

    def format_verification_comment(self, claim: ClaimData, result: VerificationResult) -> str:
        """Format verification result as GitHub comment"""
        if result.is_valid:
            comment = f"✅ **Verification Successful** for @{claim.github_username}\n\n"
        else:
            comment = f"❌ **Verification Failed** for @{claim.github_username}\n\n"

        # Add detailed results
        comment += "**Verification Details:**\n"

        if claim.claim_type in ['star', 'general']:
            status = "✅" if result.star_verified else "❌"
            comment += f"- Repository Starred: {status}\n"

        if claim.claim_type in ['follow', 'general']:
            status = "✅" if result.follow_verified else "❌"
            comment += f"- Following @{self.owner}: {status}\n"

        if claim.wallet_address:
            status = "✅" if result.wallet_exists else "❌"
            comment += f"- Wallet Verified: {status} (`{claim.wallet_address[:8]}...`)\n"

        if claim.article_urls:
            comment += f"- Articles: {len([v for v in result.articles_valid if v])}/{len(result.articles_valid)} verified\n"

        if result.duplicate_claim:
            comment += "- ⚠️ Duplicate claim detected\n"

        # Add errors if any
        if result.error_messages:
            comment += "\n**Issues Found:**\n"
            for error in result.error_messages:
                comment += f"- {error}\n"

        comment += f"\n*Verification completed at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}*"

        return comment

    def get_verification_stats(self) -> Dict[str, Any]:
        """Get verification statistics"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_verifications,
                    SUM(CASE WHEN star_verified = 1 THEN 1 ELSE 0 END) as stars_verified,
                    SUM(CASE WHEN follow_verified = 1 THEN 1 ELSE 0 END) as follows_verified,
                    SUM(CASE WHEN wallet_verified = 1 THEN 1 ELSE 0 END) as wallets_verified,
                    SUM(articles_count) as articles_verified,
                    SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END) as duplicates_found
                FROM bounty_verifications
            ''')

            row = cursor.fetchone()
            return {
                'total_verifications': row[0],
                'stars_verified': row[1],
                'follows_verified': row[2],
                'wallets_verified': row[3],
                'articles_verified': row[4],
                'duplicates_found': row[5]
            }
