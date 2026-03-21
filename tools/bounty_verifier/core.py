# SPDX-License-Identifier: MIT

import re
import requests
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import time


@dataclass
class VerificationResult:
    """Result of a bounty verification check"""
    success: bool
    message: str
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class BountyVerifier:
    """Core bounty verification logic for RustChain bounty claims"""

    def __init__(self, github_token: str, rustchain_node_url: str = "http://localhost:3031"):
        self.github_token = github_token
        self.node_url = rustchain_node_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'RustChain-BountyVerifier/1.0'
        })

    def verify_github_follow(self, username: str, target_user: str) -> VerificationResult:
        """Verify if user follows target user on GitHub"""
        try:
            url = f"https://api.github.com/users/{username}/following/{target_user}"
            response = self.session.get(url)

            if response.status_code == 204:
                return VerificationResult(
                    True,
                    f"✅ @{username} is following @{target_user}",
                    {"following": True}
                )
            elif response.status_code == 404:
                return VerificationResult(
                    False,
                    f"❌ @{username} is not following @{target_user}",
                    {"following": False}
                )
            else:
                return VerificationResult(
                    False,
                    f"⚠️ Could not verify follow status (HTTP {response.status_code})",
                    {"error": "api_error", "status_code": response.status_code}
                )
        except Exception as e:
            return VerificationResult(
                False,
                f"⚠️ Error checking follow status: {str(e)}",
                {"error": "exception", "exception": str(e)}
            )

    def verify_github_star(self, username: str, repo_owner: str, repo_name: str) -> VerificationResult:
        """Verify if user starred a repository"""
        try:
            url = f"https://api.github.com/users/{username}/starred/{repo_owner}/{repo_name}"
            response = self.session.get(url)

            if response.status_code == 204:
                return VerificationResult(
                    True,
                    f"⭐ @{username} has starred {repo_owner}/{repo_name}",
                    {"starred": True}
                )
            elif response.status_code == 404:
                return VerificationResult(
                    False,
                    f"❌ @{username} has not starred {repo_owner}/{repo_name}",
                    {"starred": False}
                )
            else:
                return VerificationResult(
                    False,
                    f"⚠️ Could not verify star status (HTTP {response.status_code})",
                    {"error": "api_error", "status_code": response.status_code}
                )
        except Exception as e:
            return VerificationResult(
                False,
                f"⚠️ Error checking star status: {str(e)}",
                {"error": "exception", "exception": str(e)}
            )

    def verify_wallet_balance(self, wallet_address: str) -> VerificationResult:
        """Check if wallet exists on RustChain node and get balance"""
        try:
            url = f"{self.node_url}/balance/{wallet_address}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                balance = data.get("amount_rtc", 0)
                miner_id = data.get("miner_id", "")

                if miner_id:
                    return VerificationResult(
                        True,
                        f"💰 Wallet {wallet_address} exists with {balance:.2f} RTC",
                        {"balance": balance, "miner_id": miner_id, "exists": True}
                    )
                else:
                    return VerificationResult(
                        False,
                        f"❌ Wallet {wallet_address} not found on network",
                        {"exists": False}
                    )
            else:
                return VerificationResult(
                    False,
                    f"⚠️ Could not verify wallet (HTTP {response.status_code})",
                    {"error": "api_error", "status_code": response.status_code}
                )
        except Exception as e:
            return VerificationResult(
                False,
                f"⚠️ Error checking wallet: {str(e)}",
                {"error": "exception", "exception": str(e)}
            )

    def verify_article_url(self, url: str) -> VerificationResult:
        """Verify article URL is live and accessible"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Check if it's a supported platform
            supported_domains = ['dev.to', 'medium.com', 'hashnode.dev', 'blog.', 'substack.com']
            is_supported = any(domain in url.lower() for domain in supported_domains)

            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; RustChain-BountyVerifier/1.0)'
            })

            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' in content_type:
                    return VerificationResult(
                        True,
                        f"🔗 Article URL is live and accessible",
                        {
                            "url": url,
                            "status_code": response.status_code,
                            "supported_platform": is_supported,
                            "content_length": len(response.text)
                        }
                    )
                else:
                    return VerificationResult(
                        False,
                        f"⚠️ URL doesn't appear to be an article (content-type: {content_type})",
                        {"url": url, "content_type": content_type}
                    )
            else:
                return VerificationResult(
                    False,
                    f"❌ Article URL returned HTTP {response.status_code}",
                    {"url": url, "status_code": response.status_code}
                )
        except Exception as e:
            return VerificationResult(
                False,
                f"⚠️ Error checking article URL: {str(e)}",
                {"error": "exception", "exception": str(e)}
            )

    def verify_article_wordcount(self, url: str, min_words: int = 300) -> VerificationResult:
        """Check dev.to/Medium article word count and basic quality"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; RustChain-BountyVerifier/1.0)'
            })

            if response.status_code != 200:
                return VerificationResult(
                    False,
                    f"❌ Could not fetch article (HTTP {response.status_code})",
                    {"status_code": response.status_code}
                )

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Try to find article content
            article_content = ""
            if 'dev.to' in url:
                content_div = soup.find('div', {'id': 'article-body'}) or soup.find('div', class_='spec__body')
                if content_div:
                    article_content = content_div.get_text()
            elif 'medium.com' in url:
                content_div = soup.find('article') or soup.find('div', class_='postArticle-content')
                if content_div:
                    article_content = content_div.get_text()
            else:
                # Generic approach
                article_tag = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|post|article'))
                if article_tag:
                    article_content = article_tag.get_text()
                else:
                    article_content = soup.get_text()

            # Clean and count words
            clean_text = ' '.join(article_content.split())
            word_count = len(clean_text.split())

            # Basic quality checks
            has_rustchain_mention = 'rustchain' in clean_text.lower()
            has_code_blocks = '<code>' in response.text or '```' in response.text or '<pre>' in response.text

            if word_count >= min_words:
                quality_notes = []
                if has_rustchain_mention:
                    quality_notes.append("mentions RustChain")
                if has_code_blocks:
                    quality_notes.append("contains code examples")

                quality_msg = f" ({', '.join(quality_notes)})" if quality_notes else ""

                return VerificationResult(
                    True,
                    f"📝 Article has {word_count} words (≥{min_words}){quality_msg}",
                    {
                        "word_count": word_count,
                        "min_words": min_words,
                        "has_rustchain_mention": has_rustchain_mention,
                        "has_code_blocks": has_code_blocks
                    }
                )
            else:
                return VerificationResult(
                    False,
                    f"❌ Article only has {word_count} words (need ≥{min_words})",
                    {"word_count": word_count, "min_words": min_words}
                )

        except ImportError:
            return VerificationResult(
                False,
                "⚠️ BeautifulSoup4 not installed - cannot check word count",
                {"error": "missing_dependency"}
            )
        except Exception as e:
            return VerificationResult(
                False,
                f"⚠️ Error analyzing article: {str(e)}",
                {"error": "exception", "exception": str(e)}
            )

    def check_duplicate_claims(self, repo_owner: str, repo_name: str, issue_number: int, username: str) -> VerificationResult:
        """Check if user has already claimed this bounty"""
        try:
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}/comments"
            all_comments = []
            page = 1

            while True:
                response = self.session.get(url, params={'page': page, 'per_page': 100})
                if response.status_code != 200:
                    break

                comments = response.json()
                if not comments:
                    break

                all_comments.extend(comments)
                page += 1

            # Look for previous claims by this user
            user_claims = []
            claim_patterns = [
                r'\bclaim\b',
                r'\bi claim\b',
                r'\bworking on this\b',
                r'\btaking this\b'
            ]

            for comment in all_comments:
                if comment['user']['login'].lower() == username.lower():
                    body = comment['body'].lower()
                    for pattern in claim_patterns:
                        if re.search(pattern, body):
                            user_claims.append({
                                'comment_id': comment['id'],
                                'created_at': comment['created_at'],
                                'body': comment['body'][:100] + '...'
                            })
                            break

            if len(user_claims) > 1:
                return VerificationResult(
                    False,
                    f"❌ @{username} has {len(user_claims)} previous claims on this issue",
                    {"duplicate_claims": user_claims, "claim_count": len(user_claims)}
                )
            elif len(user_claims) == 1:
                return VerificationResult(
                    True,
                    f"✅ This appears to be @{username}'s first claim on this issue",
                    {"previous_claims": user_claims, "claim_count": len(user_claims)}
                )
            else:
                return VerificationResult(
                    True,
                    f"✅ No previous claims found for @{username} on this issue",
                    {"claim_count": 0}
                )

        except Exception as e:
            return VerificationResult(
                False,
                f"⚠️ Error checking duplicate claims: {str(e)}",
                {"error": "exception", "exception": str(e)}
            )

    def parse_claim_comment(self, comment_body: str) -> Dict[str, str]:
        """Extract verification data from comment body"""
        result = {}

        # Look for GitHub username
        github_match = re.search(r'@([a-zA-Z0-9-]+)', comment_body)
        if github_match:
            result['github_user'] = github_match.group(1)

        # Look for wallet address
        wallet_match = re.search(r'\b([a-fA-F0-9]{40,64})\b', comment_body)
        if wallet_match:
            result['wallet'] = wallet_match.group(1)

        # Look for URLs
        url_pattern = r'https?://[^\s)]+|(?:dev\.to|medium\.com|hashnode\.dev)/[^\s)]+'
        urls = re.findall(url_pattern, comment_body, re.IGNORECASE)
        if urls:
            result['article_url'] = urls[0]

        return result

    def verify_full_claim(self, repo_owner: str, repo_name: str, issue_number: int,
                         username: str, comment_body: str) -> Dict[str, VerificationResult]:
        """Run all verification checks on a bounty claim"""
        results = {}
        claim_data = self.parse_claim_comment(comment_body)

        # Always check duplicate claims
        results['duplicate_check'] = self.check_duplicate_claims(repo_owner, repo_name, issue_number, username)

        # GitHub follow check (follow repo owner)
        results['github_follow'] = self.verify_github_follow(username, repo_owner)

        # GitHub star check
        results['github_star'] = self.verify_github_star(username, repo_owner, repo_name)

        # Wallet verification
        if 'wallet' in claim_data:
            results['wallet_check'] = self.verify_wallet_balance(claim_data['wallet'])

        # Article URL verification
        if 'article_url' in claim_data:
            results['article_url'] = self.verify_article_url(claim_data['article_url'])

            # Word count check for dev.to/Medium articles
            url = claim_data['article_url'].lower()
            if any(domain in url for domain in ['dev.to', 'medium.com']):
                results['article_wordcount'] = self.verify_article_wordcount(claim_data['article_url'])

        return results
