# SPDX-License-Identifier: MIT

import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import requests
from bs4 import BeautifulSoup


@dataclass
class ClaimData:
    username: str
    wallet_address: str
    article_url: Optional[str] = None
    claim_type: str = "star_follow"
    timestamp: float = 0.0
    comment_id: int = 0


class BountyVerifier:
    def __init__(self, github_token: str, node_url: str = "http://localhost:3030"):
        self.github_token = github_token
        self.node_url = node_url.rstrip('/')
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'RustChain-Bounty-Verifier/1.0'
        }

    def parse_claim_comment(self, comment_body: str) -> Optional[ClaimData]:
        """Extract claim data from comment text."""
        lines = comment_body.strip().split('\n')
        claim_data = {}

        # Look for claim keyword
        has_claim = any('claim' in line.lower() for line in lines)
        if not has_claim:
            return None

        # Extract wallet address
        wallet_pattern = r'[0-9a-fA-F]{40,64}'
        for line in lines:
            wallet_match = re.search(wallet_pattern, line)
            if wallet_match:
                claim_data['wallet_address'] = wallet_match.group()
                break

        # Extract article URL
        url_pattern = r'https?://(?:dev\.to|medium\.com|[^\s]+)'
        for line in lines:
            url_match = re.search(url_pattern, line)
            if url_match:
                claim_data['article_url'] = url_match.group()
                break

        if 'wallet_address' not in claim_data:
            return None

        return ClaimData(
            username="",  # Will be filled by caller
            wallet_address=claim_data['wallet_address'],
            article_url=claim_data.get('article_url'),
            timestamp=time.time()
        )

    def check_github_star(self, username: str, owner: str, repo: str) -> bool:
        """Check if user has starred the repository."""
        url = f"https://api.github.com/user/starred/{owner}/{repo}"
        try:
            resp = requests.get(url, headers={
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
            if resp.status_code == 204:
                return True
            elif resp.status_code == 404:
                return False
            else:
                # Check via stargazers endpoint as fallback
                return self.check_star_fallback(username, owner, repo)
        except Exception:
            return self.check_star_fallback(username, owner, repo)

    def check_star_fallback(self, username: str, owner: str, repo: str) -> bool:
        """Fallback method to check stars via stargazers endpoint."""
        url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
        try:
            page = 1
            while page <= 10:  # Limit to avoid rate limits
                resp = requests.get(f"{url}?page={page}&per_page=100", headers=self.headers)
                if resp.status_code != 200:
                    break

                stargazers = resp.json()
                if not stargazers:
                    break

                for stargazer in stargazers:
                    if stargazer['login'].lower() == username.lower():
                        return True
                page += 1
        except Exception:
            pass
        return False

    def check_github_follow(self, username: str, target_user: str) -> bool:
        """Check if user follows the target user."""
        url = f"https://api.github.com/users/{username}/following/{target_user}"
        try:
            resp = requests.get(url, headers=self.headers)
            return resp.status_code == 204
        except Exception:
            return False

    def check_wallet_exists(self, wallet_address: str) -> Tuple[bool, Optional[float]]:
        """Check if wallet exists on RustChain node and get balance."""
        try:
            url = f"{self.node_url}/balance/{wallet_address}"
            resp = requests.get(url, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                balance = data.get('amount_rtc', 0)
                return True, float(balance)
            else:
                return False, None
        except Exception:
            return False, None

    def verify_article_url(self, url: str) -> Dict[str, Any]:
        """Verify article URL and extract metadata."""
        result = {
            'valid': False,
            'status_code': None,
            'word_count': 0,
            'title': '',
            'platform': 'unknown'
        }

        try:
            # Determine platform
            if 'dev.to' in url:
                result['platform'] = 'dev.to'
            elif 'medium.com' in url:
                result['platform'] = 'medium'

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=15)
            result['status_code'] = resp.status_code

            if resp.status_code == 200:
                result['valid'] = True
                soup = BeautifulSoup(resp.content, 'html.parser')

                # Extract title
                title_tag = soup.find('title')
                if title_tag:
                    result['title'] = title_tag.get_text().strip()

                # Extract and count words
                article_text = self.extract_article_text(soup, result['platform'])
                if article_text:
                    words = re.findall(r'\b\w+\b', article_text)
                    result['word_count'] = len(words)

        except Exception as e:
            result['error'] = str(e)

        return result

    def extract_article_text(self, soup: BeautifulSoup, platform: str) -> str:
        """Extract main article text based on platform."""
        text = ""

        try:
            if platform == 'dev.to':
                # Dev.to uses specific article selectors
                article = soup.find('div', {'data-article-id': True}) or soup.find('article')
                if article:
                    text = article.get_text()
            elif platform == 'medium':
                # Medium article content
                article = soup.find('article') or soup.find('div', {'role': 'main'})
                if article:
                    text = article.get_text()
            else:
                # Generic extraction
                main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|article|post'))
                if main:
                    text = main.get_text()

        except Exception:
            pass

        return text

    def check_duplicate_claim(self, username: str, issue_comments: List[Dict]) -> bool:
        """Check if user has already made a valid claim."""
        user_comments = [c for c in issue_comments if c.get('user', {}).get('login', '').lower() == username.lower()]

        claim_count = 0
        for comment in user_comments:
            if self.parse_claim_comment(comment.get('body', '')):
                claim_count += 1

        return claim_count > 1

    def generate_verification_result(self, claim: ClaimData, owner: str, repo: str,
                                   issue_comments: List[Dict]) -> str:
        """Generate automated verification comment."""
        results = []
        total_score = 0

        # Check star
        has_star = self.check_github_star(claim.username, owner, repo)
        star_status = "✅" if has_star else "❌"
        results.append(f"**GitHub Star**: {star_status} {'Confirmed' if has_star else 'Not found'}")
        if has_star:
            total_score += 20

        # Check follow (assume following repository owner)
        has_follow = self.check_github_follow(claim.username, owner)
        follow_status = "✅" if has_follow else "❌"
        results.append(f"**GitHub Follow**: {follow_status} {'Confirmed' if has_follow else 'Not found'}")
        if has_follow:
            total_score += 20

        # Check wallet
        wallet_exists, balance = self.check_wallet_exists(claim.wallet_address)
        wallet_status = "✅" if wallet_exists else "❌"
        wallet_text = f"Confirmed (Balance: {balance:.2f} RTC)" if wallet_exists else "Not found"
        results.append(f"**Wallet Check**: {wallet_status} {wallet_text}")
        if wallet_exists:
            total_score += 15

        # Check article if provided
        if claim.article_url:
            article_data = self.verify_article_url(claim.article_url)
            if article_data['valid']:
                article_status = "✅"
                word_count = article_data['word_count']
                title = article_data.get('title', 'Unknown')[:50]

                quality_bonus = 0
                if word_count >= 500:
                    quality_bonus = 10
                elif word_count >= 200:
                    quality_bonus = 5

                results.append(f"**Article**: {article_status} Live ({word_count} words)")
                results.append(f"  - Title: {title}...")
                results.append(f"  - Platform: {article_data['platform']}")
                results.append(f"  - Quality bonus: +{quality_bonus} points")
                total_score += 15 + quality_bonus
            else:
                article_status = "❌"
                results.append(f"**Article**: {article_status} Not accessible")
        else:
            results.append("**Article**: ⚪ Not provided")

        # Check duplicates
        is_duplicate = self.check_duplicate_claim(claim.username, issue_comments)
        dup_status = "❌" if is_duplicate else "✅"
        dup_text = "Duplicate claim detected" if is_duplicate else "First claim"
        results.append(f"**Duplicate Check**: {dup_status} {dup_text}")
        if is_duplicate:
            total_score = max(0, total_score - 30)

        # Generate summary
        verification_summary = "\n".join(results)

        if total_score >= 50:
            verdict = "🎉 **CLAIM APPROVED** - All requirements met!"
        elif total_score >= 30:
            verdict = "⚠️ **PARTIAL** - Some requirements missing"
        else:
            verdict = "❌ **CLAIM REJECTED** - Requirements not met"

        comment = f"""## 🤖 Bounty Verification Results

**Claimant**: @{claim.username}
**Wallet**: `{claim.wallet_address}`

{verification_summary}

---
**Total Score**: {total_score}/100
**Verdict**: {verdict}

*This verification was performed automatically. If you believe there's an error, please contact a maintainer.*
"""

        return comment
