# SPDX-License-Identifier: MIT
"""
Star verification for bounty claims.

Cherry-picked from LaphoqueRC PR #1712 with fixes:
  - Paginates /repos/{owner}/{repo}/stargazers to check if a user starred.
    The original PR used /user/starred/{owner}/{repo} which checks the
    *authenticated bot's* stars, not the claimant's.
  - Node URL fixed to https://50.28.86.131.
"""

import logging
import re
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

RUSTCHAIN_NODE_URL = "https://50.28.86.131"
RUSTCHAIN_REPO_OWNER = "Scottcjn"
RUSTCHAIN_REPO_NAME = "Rustchain"
FTC_DISCLOSURE_PHRASE = "i received rtc compensation for this review"
URL_PATTERN = re.compile(r"https?://[^\s<>\[\]\"')]+", re.IGNORECASE)
MIN_REVIEW_SENTENCES = 2
MIN_REVIEW_SENTENCE_WORDS = 3


def _response_json_list(resp) -> list:
    try:
        body = resp.json()
    except ValueError as exc:
        logger.warning("GitHub API returned invalid JSON: %s", exc)
        return []
    if not isinstance(body, list):
        logger.warning("GitHub API returned %s JSON, expected list", type(body).__name__)
        return []
    return [item for item in body if isinstance(item, dict)]


def _count_review_sentences(body: str) -> int:
    """Count substantive sentences, ignoring URL fragments."""
    stripped = URL_PATTERN.sub(" ", body)
    return sum(
        1
        for sentence in re.split(r"[.!?]+", stripped)
        if len(sentence.split()) >= MIN_REVIEW_SENTENCE_WORDS
    )


def validate_star_review_comment(body: str) -> Tuple[bool, List[str]]:
    """Validate FTC-compliant star-bounty review comments (issue #773).

    Requires:
    - Disclosure: "I received RTC compensation for this review."
    - At least one review link (URL)
    - At least two substantive sentences
    """
    errors: List[str] = []

    if FTC_DISCLOSURE_PHRASE not in body.lower():
        errors.append(
            "Missing FTC disclosure: 'I received RTC compensation for this review.'"
        )

    if not URL_PATTERN.search(body):
        errors.append("Missing review link (at least one URL required)")

    if _count_review_sentences(body) < MIN_REVIEW_SENTENCES:
        errors.append(
            f"Comment must contain at least {MIN_REVIEW_SENTENCES} substantive sentences"
        )

    return len(errors) == 0, errors


def check_user_starred_repo(
    username: str,
    owner: str,
    repo: str,
    token: str,
) -> bool:
    """Return True if *username* has starred *owner*/*repo*.

    Paginates the stargazers list (100 per page) rather than relying
    on the authenticated-user endpoint.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "RustChain-Bounty-Verifier/1.0",
    }
    page = 1
    per_page = 100

    while True:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/stargazers?per_page={per_page}&page={page}"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning(
                    "Stargazers API returned %d for %s/%s page %d",
                    resp.status_code, owner, repo, page,
                )
                return False

            stargazers = _response_json_list(resp)
            if not stargazers:
                break

            for sg in stargazers:
                login = sg.get("login", "")
                if login.lower() == username.lower():
                    return True

            if len(stargazers) < per_page:
                break
            page += 1

        except Exception as exc:
            logger.error("Error checking stargazers: %s", exc)
            return False

    return False


def count_user_stars(
    username: str,
    owner: str,
    token: str,
    repos: Optional[List[str]] = None,
) -> int:
    """Count how many of *owner*'s repos *username* has starred.

    If *repos* is None, fetches the owner's public repos first.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "RustChain-Bounty-Verifier/1.0",
    }

    if repos is None:
        repos = []
        page = 1
        while True:
            url = (
                f"https://api.github.com/users/{owner}"
                f"/repos?per_page=100&page={page}&type=public"
            )
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    break
                data = _response_json_list(resp)
                if not data:
                    break
                repos.extend(r["name"] for r in data if isinstance(r.get("name"), str))
                if len(data) < 100:
                    break
                page += 1
            except Exception:
                break

    count = 0
    for repo in repos:
        if check_user_starred_repo(username, owner, repo, token):
            count += 1
    return count


def check_wallet_exists(wallet_address: str) -> bool:
    """Verify that a wallet address exists on the RustChain node."""
    try:
        url = f"{RUSTCHAIN_NODE_URL}/wallet/balance"
        import os
        _cert = os.path.expanduser("~/.rustchain/node_cert.pem")
        _verify = _cert if os.path.exists(_cert) else True
        resp = requests.get(
            url,
            params={"miner_id": wallet_address},
            verify=_verify,
            timeout=10,
        )
        if resp.status_code == 200:
            try:
                body = resp.json()
            except ValueError:
                return False
            return isinstance(body, dict)
    except Exception as exc:
        logger.error("Error checking wallet %s: %s", wallet_address, exc)
    return False
