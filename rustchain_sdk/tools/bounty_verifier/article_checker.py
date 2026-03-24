# SPDX-License-Identifier: MIT
"""
Article/blog verification for bounty claims.

Cherry-picked from LaphoqueRC PR #1712.  Checks that a claimed blog post
or article URL is live, mentions RustChain, and was authored by the claimant.
"""

import logging
from typing import Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not installed; article checking disabled")


class ArticleChecker:
    """Verify that a URL points to a live article that mentions RustChain."""

    REQUIRED_KEYWORDS = ["rustchain", "rtc"]
    USER_AGENT = "RustChain-Bounty-Verifier/1.0"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def check_article(
        self,
        url: str,
        expected_author: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, str]]:
        """Return ``(passed, details)`` for the article at *url*.

        *details* always contains at least ``{"url": url}``.
        """
        details: Dict[str, str] = {"url": url}

        if not BS4_AVAILABLE:
            details["error"] = "beautifulsoup4 not installed"
            return False, details

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.timeout,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                details["error"] = f"HTTP {resp.status_code}"
                return False, details

            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(separator=" ").lower()

            # Check for RustChain mentions
            mentions_rustchain = any(kw in text for kw in self.REQUIRED_KEYWORDS)
            details["mentions_rustchain"] = str(mentions_rustchain)

            if not mentions_rustchain:
                details["error"] = "Article does not mention RustChain or RTC"
                return False, details

            # Optional author check (best-effort)
            if expected_author:
                author_found = expected_author.lower() in text
                details["author_found"] = str(author_found)
                if not author_found:
                    details["warning"] = (
                        f"Author '{expected_author}' not found in article text"
                    )

            details["title"] = (
                soup.title.string.strip() if soup.title and soup.title.string else ""
            )
            return True, details

        except requests.exceptions.Timeout:
            details["error"] = "Request timed out"
            return False, details
        except Exception as exc:
            details["error"] = str(exc)
            return False, details
