#!/usr/bin/env python3
"""
award_rtc.py — GitHub Action helper for automatic RTC bounty awards on PR merge.

Reads the contributor wallet from the PR body (``wallet: <addr>`` directive)
or a ``.rtc-wallet`` file at the repository root, calls the RustChain admin
transfer API (``POST /wallet/transfer``), and posts a confirmation comment
on the merged PR.

Designed to be invoked by the composite action
``.github/actions/rtc-auto-bounty/action.yml``.

Environment variables (set by the action):
    INPUT_RTC_AMOUNT       — Default RTC amount per merge
    INPUT_RTC_VPS_HOST     — RustChain VPS host
    INPUT_RTC_ADMIN_KEY    — Admin key for /wallet/transfer
    INPUT_FROM_WALLET      — Source wallet (default: founder_community)
    INPUT_DRY_RUN          — "true" to simulate without calling the API
    INPUT_POST_COMMENT     — "true" to post a PR comment
    INPUT_GITHUB_TOKEN     — GitHub token
    INPUT_REPO_PATH        — Path to the checked-out repo
    INPUT_MAX_AMOUNT       — Safety cap for transfer amount
    GITHUB_REPOSITORY      — "owner/repo"
    PR_NUMBER              — Pull request number
    PR_AUTHOR              — GitHub username of the PR author
    PR_MERGED              — "true" if the PR was merged
    PR_BODY                — Full PR body text
    PR_HEAD_SHA            — Head commit SHA
    PR_TITLE               — PR title
"""

from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
VPS_PORT = 8099

# Wallet directive patterns in the PR body.
# Accepted forms:
#   wallet: RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#   Wallet: RTCxxxx...
#   wallet: my-github-username
#   .rtc-wallet: RTCxxxx...
_WALLET_RE = re.compile(
    r"(?:^|\n)\s*(?:wallet|\.rtc-wallet)\s*:\s*(\S+)\s*(?:\n|$)",
    re.IGNORECASE,
)

# Payment-amount override in the PR body (owner can specify a custom amount).
#   bounty: 100 RTC
#   bounty: 75.5 RTC
_BOUNTY_RE = re.compile(
    r"(?:^|\n)\s*bounty\s*:\s*([\d]+(?:\.[\d]+)?)\s*RTC\s*(?:\n|$)",
    re.IGNORECASE,
)

# Marker to prevent duplicate awards.
_AWARD_MARKER = "RTC-AutoBounty-Awarded"

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    return _env(name, str(default)).lower() in ("true", "1", "yes")


def _env_float(name: str, default: float = 0.0) -> float:
    try:
        return float(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


class Config:
    """Immutable configuration gathered from environment variables."""

    def __init__(self) -> None:
        self.rtc_amount: float = _env_float("INPUT_RTC_AMOUNT", 50.0)
        self.vps_host: str = _env("INPUT_RTC_VPS_HOST").strip()
        self.admin_key: str = _env("INPUT_RTC_ADMIN_KEY").strip()
        self.from_wallet: str = _env("INPUT_FROM_WALLET", "founder_community")
        self.dry_run: bool = _env_bool("INPUT_DRY_RUN")
        self.post_comment: bool = _env_bool("INPUT_POST_COMMENT", True)
        self.github_token: str = _env("INPUT_GITHUB_TOKEN", _env("GITHUB_TOKEN"))
        self.repo_path: str = _env("INPUT_REPO_PATH", ".")
        self.max_amount: float = _env_float("INPUT_MAX_AMOUNT", 10000.0)
        self.repo: str = _env("GITHUB_REPOSITORY")
        self.pr_number: str = _env("PR_NUMBER")
        self.pr_author: str = _env("PR_AUTHOR", _env("PR_AUTHOR"))
        self.pr_merged: str = _env("PR_MERGED")
        self.pr_body: str = _env("PR_BODY", "")
        self.pr_head_sha: str = _env("PR_HEAD_SHA", "")
        self.pr_title: str = _env("PR_TITLE", "")

    def validate(self) -> Optional[str]:
        """Return an error string if required config is missing, else None."""
        if not self.github_token:
            return "GITHUB_TOKEN is not set"
        if not self.repo:
            return "GITHUB_REPOSITORY is not set"
        if not self.pr_number:
            return "PR_NUMBER is not set"
        if not self.dry_run and not self.vps_host:
            return "INPUT_RTC_VPS_HOST is required (unless dry-run is enabled)"
        if not self.dry_run and not self.admin_key:
            return "INPUT_RTC_ADMIN_KEY is required (unless dry-run is enabled)"
        if self.rtc_amount <= 0:
            return f"rtc-amount must be positive, got {self.rtc_amount}"
        return None


# ---------------------------------------------------------------------------
# Wallet resolution
# ---------------------------------------------------------------------------


def resolve_wallet_from_pr_body(pr_body: str) -> Optional[str]:
    """Extract wallet address from a ``wallet: <addr>`` directive in the PR body."""
    match = _WALLET_RE.search(pr_body)
    if match:
        return match.group(1).strip().rstrip(",")
    return None


def resolve_wallet_from_file(repo_path: str) -> Optional[str]:
    """Read wallet address from a ``.rtc-wallet`` file at the repo root."""
    wallet_file = Path(repo_path) / ".rtc-wallet"
    if wallet_file.is_file():
        content = wallet_file.read_text().strip()
        # Skip blank lines and comments
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def resolve_wallet(pr_body: str, repo_path: str) -> Optional[str]:
    """
    Resolve the recipient wallet.

    Priority:
      1. ``wallet:`` directive in the PR body
      2. ``.rtc-wallet`` file at the repository root
      3. Fallback to the PR author's GitHub username
    """
    wallet = resolve_wallet_from_pr_body(pr_body)
    if wallet:
        return wallet
    wallet = resolve_wallet_from_file(repo_path)
    if wallet:
        return wallet
    return None


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def _gh_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def fetch_pr_comments(repo: str, pr_number: str, token: str) -> list:
    """Fetch all issue comments on a PR (with pagination)."""
    comments: list = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
        req = Request(
            url,
            headers=_gh_headers(token),
            method="GET",
        )
        # Add pagination params
        full_url = f"{url}?per_page=100&page={page}"
        req = Request(full_url, headers=_gh_headers(token), method="GET")
        try:
            resp = urlopen(req, timeout=15)
            batch = json.loads(resp.read().decode())
        except (HTTPError, URLError):
            break
        if not batch:
            break
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return comments


def post_pr_comment(repo: str, pr_number: str, body: str, token: str) -> bool:
    """Post a comment on a PR. Returns True on success."""
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    req = Request(
        url,
        data=json.dumps({"body": body}).encode("utf-8"),
        headers=_gh_headers(token),
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=15)
        return resp.status == 201
    except HTTPError as e:
        print(f"::warning::Failed to post PR comment: {e.code} {e.reason}")
        return False
    except URLError as e:
        print(f"::warning::Failed to post PR comment: {e.reason}")
        return False


def check_already_awarded(comments: list) -> bool:
    """Check if any existing comment contains a successful award marker."""
    for c in comments:
        body = c.get("body") or ""
        if _AWARD_MARKER not in body:
            continue

        marker_tail = body[body.find(_AWARD_MARKER):].lower()
        marker_end = marker_tail.find("-->")
        if marker_end != -1:
            marker_tail = marker_tail[:marker_end]

        if "(dry-run)" in marker_tail or ":failed" in marker_tail:
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# RustChain transfer API
# ---------------------------------------------------------------------------


def transfer_rtc(
    vps_host: str,
    admin_key: str,
    from_wallet: str,
    to_wallet: str,
    amount: float,
    memo: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Call the RustChain ``POST /wallet/transfer`` admin endpoint.

    Returns ``(success, response_body_dict)``.
    """
    url = f"http://{vps_host}:{VPS_PORT}/wallet/transfer"
    payload = {
        "from_miner": from_wallet,
        "to_miner": to_wallet,
        "amount_rtc": amount,
        "memo": memo,
    }
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": admin_key,
        },
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        return result.get("ok", False), result
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            result = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            result = {"error": body}
        return False, result
    except URLError as e:
        return False, {"error": f"Connection failed: {e.reason}"}


# ---------------------------------------------------------------------------
# GitHub Actions output helpers
# ---------------------------------------------------------------------------


def set_output(key: str, value: str) -> None:
    """Set a GitHub Actions output parameter."""
    output_file = _env("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"::set-output name={key}::{value}")


def log_info(msg: str) -> None:
    print(f"::info::{msg}")


def log_warning(msg: str) -> None:
    print(f"::warning::{msg}")


def log_error(msg: str) -> None:
    print(f"::error::{msg}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    cfg = Config()

    # --- Validate config ---------------------------------------------------
    config_err = cfg.validate()
    if config_err:
        log_error(config_err)
        set_output("awarded", "false")
        set_output("skip_reason", config_err)
        return 1

    # --- Merge guard -------------------------------------------------------
    if cfg.pr_merged != "true":
        log_info("PR is not merged — skipping award.")
        set_output("awarded", "false")
        set_output("skip_reason", "pr_not_merged")
        return 0

    pr_number = cfg.pr_number
    repo = cfg.repo
    print(f"Processing merged PR #{pr_number} in {repo}")

    # --- Check for duplicate award -----------------------------------------
    comments = fetch_pr_comments(repo, pr_number, cfg.github_token)
    if check_already_awarded(comments):
        log_info(f"PR #{pr_number} already has an award marker — skipping.")
        set_output("awarded", "false")
        set_output("skip_reason", "already_awarded")
        return 0

    # --- Resolve recipient wallet ------------------------------------------
    wallet = resolve_wallet(cfg.pr_body, cfg.repo_path)
    if not wallet:
        # Fallback: use PR author's GitHub username as the wallet identifier
        wallet = cfg.pr_author
        log_info(f"No wallet found in PR body or .rtc-wallet file; "
                 f"falling back to PR author: {wallet}")

    print(f"Recipient wallet: {wallet}")

    # --- Determine award amount --------------------------------------------
    amount = cfg.rtc_amount
    # Check for a bounty override in the PR body
    bounty_match = _BOUNTY_RE.search(cfg.pr_body)
    if bounty_match:
        override = float(bounty_match.group(1))
        if 0 < override <= cfg.max_amount:
            amount = override
            print(f"Bounty override in PR body: {amount} RTC")
        else:
            log_warning(f"Bounty override {override} RTC out of range — "
                        f"using default {cfg.rtc_amount} RTC")

    # Safety cap
    if amount > cfg.max_amount:
        log_error(f"Award amount {amount} RTC exceeds safety cap of {cfg.max_amount} RTC. "
                  f"Process manually.")
        set_output("awarded", "false")
        set_output("skip_reason", "amount_exceeds_cap")
        return 1

    memo = f"PR #{pr_number} in {repo} — auto-bounty"

    # --- Dry-run mode ------------------------------------------------------
    if cfg.dry_run:
        print(f"[DRY-RUN] Would award {amount} RTC to `{wallet}`")
        print(f"[DRY-RUN] From: {cfg.from_wallet}")
        print(f"[DRY-RUN] Memo: {memo}")
        set_output("awarded", "true")
        set_output("amount", str(amount))
        set_output("recipient_wallet", wallet)
        set_output("tx_hash", "dry-run")
        set_output("pending_id", "dry-run")
        set_output("skip_reason", "")

        if cfg.post_comment:
            dry_body = (
                f"**RTC Auto-Bounty (Dry-Run)** 🧪\n\n"
                f"| Field | Value |\n"
                f"|-------|-------|\n"
                f"| Amount | **{amount} RTC** |\n"
                f"| Recipient | `{wallet}` |\n"
                f"| From | `{cfg.from_wallet}` |\n"
                f"| Memo | {memo} |\n\n"
                f"This is a **dry-run** — no actual transfer was made.\n\n"
                f"<!-- { _AWARD_MARKER } (dry-run) -->"
            )
            post_pr_comment(repo, pr_number, dry_body, cfg.github_token)
        return 0

    # --- Execute transfer --------------------------------------------------
    print(f"Initiating transfer: {amount} RTC from {cfg.from_wallet} to {wallet}")
    ok, result = transfer_rtc(
        cfg.vps_host,
        cfg.admin_key,
        cfg.from_wallet,
        wallet,
        amount,
        memo,
    )

    tx_hash = result.get("tx_hash", "")
    pending_id = result.get("pending_id", "")
    error_msg = result.get("error", "")

    if not ok:
        log_error(f"Transfer failed: {error_msg}")
        set_output("awarded", "false")
        set_output("skip_reason", f"transfer_failed: {error_msg}")

        if cfg.post_comment:
            fail_body = (
                f"**RTC Auto-Bounty Failed** ❌\n\n"
                f"Attempted to award **{amount} RTC** to `{wallet}` "
                f"but the transfer was rejected:\n\n"
                f"```\n{error_msg}\n```\n\n"
                f"Please process this award manually.\n\n"
                f"<!-- { _AWARD_MARKER }:FAILED -->"
            )
            post_pr_comment(repo, pr_number, fail_body, cfg.github_token)
        return 1

    # --- Post confirmation comment -----------------------------------------
    set_output("awarded", "true")
    set_output("amount", str(amount))
    set_output("recipient_wallet", wallet)
    set_output("tx_hash", tx_hash)
    set_output("pending_id", str(pending_id))
    set_output("skip_reason", "")

    if cfg.post_comment:
        phase = result.get("phase", "completed")
        confirms_info = ""
        if result.get("confirms_in_hours"):
            confirms_info = (
                f"| Confirms in | {result['confirms_in_hours']:.0f} hours |\n"
            )

        confirm_body = textwrap.dedent(f"""\
            **RTC Bounty Awarded** ✅

            | Field | Value |
            |-------|-------|
            | Amount | **{amount} RTC** |
            | Recipient | `{wallet}` |
            | From | `{cfg.from_wallet}` |
            | Memo | {memo} |
            | Phase | {phase} |
            | tx_hash | `{tx_hash}` |
            | pending_id | `{pending_id}` |
            {confirms_info}
            Transfer recorded on RustChain.

            <!-- { _AWARD_MARKER } tx_hash={tx_hash} pending_id={pending_id} -->
        """)
        posted = post_pr_comment(repo, pr_number, confirm_body, cfg.github_token)
        if not posted:
            log_warning("Failed to post confirmation comment, but transfer succeeded.")

    print(f"Award complete: {amount} RTC to {wallet} "
          f"(tx_hash={tx_hash}, pending_id={pending_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
