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
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

RUSTCHAIN_NODE_URL = "https://50.28.86.131"


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

            stargazers = resp.json()
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
                data = resp.json()
                if not data:
                    break
                repos.extend(r["name"] for r in data)
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
        url = f"{RUSTCHAIN_NODE_URL}/api/balance/{wallet_address}"
        resp = requests.get(url, verify=False, timeout=10)
        if resp.status_code == 200:
            return True
    except Exception as exc:
        logger.error("Error checking wallet %s: %s", wallet_address, exc)
    return False
