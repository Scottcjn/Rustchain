// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import re
from typing import Dict, List, Optional, Tuple

class ClaimParser:
    """Parses bounty claim comments to extract relevant data."""

    def __init__(self):
        # Wallet address patterns - Rustchain addresses start with 'R' or 'rust'
        self.wallet_patterns = [
            r'\b(R[a-zA-Z0-9]{25,50})\b',  # Rustchain addresses starting with R
            r'\b(rust[a-zA-Z0-9]{20,45})\b',  # Rustchain addresses starting with rust
            r'wallet[:\s]*([a-zA-Z0-9]{25,50})',  # "wallet: address" format
            r'address[:\s]*([a-zA-Z0-9]{25,50})',  # "address: address" format
        ]

        # GitHub username patterns
        self.github_patterns = [
            r'github\.com/([a-zA-Z0-9\-_]+)',  # github.com/username
            r'@([a-zA-Z0-9\-_]+)',  # @username
            r'github[:\s]*([a-zA-Z0-9\-_]+)',  # github: username
            r'user[:\s]*([a-zA-Z0-9\-_]+)',  # user: username
        ]

        # Article URL patterns
        self.article_patterns = [
            r'(https?://dev\.to/[^\s]+)',  # dev.to articles
            r'(https?://medium\.com/[^\s]+)',  # medium.com articles
            r'(https?://[a-zA-Z0-9\-_]+\.medium\.com/[^\s]+)',  # custom medium domains
            r'article[:\s]*(https?://[^\s]+)',  # "article: url" format
            r'link[:\s]*(https?://[^\s]+)',  # "link: url" format
        ]

    def parse_comment(self, comment_text: str) -> Dict[str, any]:
        """Parse a comment and extract all relevant claim data."""
        result = {
            'wallets': self._extract_wallets(comment_text),
            'github_users': self._extract_github_users(comment_text),
            'article_urls': self._extract_article_urls(comment_text),
            'has_claim': self._detect_claim_intent(comment_text),
            'raw_text': comment_text
        }
        return result

    def _extract_wallets(self, text: str) -> List[str]:
        """Extract wallet addresses from text."""
        wallets = set()

        for pattern in self.wallet_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                # Basic validation - must be reasonable length
                if 20 <= len(match) <= 60:
                    wallets.add(match.strip())

        return list(wallets)

    def _extract_github_users(self, text: str) -> List[str]:
        """Extract GitHub usernames from text."""
        users = set()

        for pattern in self.github_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                # Skip common false positives
                if match.lower() not in ['com', 'github', 'user', 'username']:
                    users.add(match.strip())

        return list(users)

    def _extract_article_urls(self, text: str) -> List[str]:
        """Extract article URLs from text."""
        urls = set()

        for pattern in self.article_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                # Basic URL validation
                if match.startswith(('http://', 'https://')):
                    urls.add(match.strip().rstrip('.,;)]}'))

        return list(urls)

    def _detect_claim_intent(self, text: str) -> bool:
        """Detect if the comment appears to be making a bounty claim."""
        claim_keywords = [
            'claim', 'claiming', 'complete', 'completed', 'done',
            'finished', 'submit', 'submitting', 'wallet', 'address',
            'starred', 'followed', 'article', 'written'
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in claim_keywords)

    def extract_structured_claim(self, comment_text: str) -> Optional[Dict[str, str]]:
        """Extract structured claim data if the comment follows expected format."""
        parsed = self.parse_comment(comment_text)

        if not parsed['has_claim']:
            return None

        # Try to match the most likely wallet and user
        wallet = parsed['wallets'][0] if parsed['wallets'] else None
        github_user = parsed['github_users'][0] if parsed['github_users'] else None
        article_url = parsed['article_urls'][0] if parsed['article_urls'] else None

        if not any([wallet, github_user, article_url]):
            return None

        return {
            'wallet_address': wallet,
            'github_username': github_user,
            'article_url': article_url,
            'confidence': self._calculate_confidence(parsed)
        }

    def _calculate_confidence(self, parsed_data: Dict) -> float:
        """Calculate confidence score for the parsed data."""
        score = 0.0

        if parsed_data['wallets']:
            score += 0.3
        if parsed_data['github_users']:
            score += 0.3
        if parsed_data['article_urls']:
            score += 0.2
        if parsed_data['has_claim']:
            score += 0.2

        return min(score, 1.0)

    def parse_multiple_comments(self, comments: List[str]) -> List[Dict[str, any]]:
        """Parse multiple comments and return results."""
        results = []
        for i, comment in enumerate(comments):
            result = self.parse_comment(comment)
            result['comment_index'] = i
            results.append(result)
        return results
