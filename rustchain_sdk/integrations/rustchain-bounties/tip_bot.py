#!/usr/bin/env python3
"""
tip_bot.py — GitHub tip bot for RustChain /tip commands.

Triggered by GitHub Actions on issue_comment events.
Parses /tip @username <amount> RTC commands, validates them,
prevents duplicate processing, and posts confirmation/failure comments.

Usage (GitHub Action):
    python tip_bot.py

Required environment variables:
    GITHUB_TOKEN       — Auto-provided by GitHub Actions
    GITHUB_EVENT_PATH  — Auto-provided by GitHub Actions
    GITHUB_REPOSITORY  — Auto-provided by GitHub Actions
    WEBHOOK_SECRET     — GitHub webhook HMAC secret (optional but recommended)
    RUSTCHAIN_NODE_URL — Override for the RustChain node URL (optional)

Optional secrets (documented in README):
    WALLET_ADDRESS     — Maintainer's RustChain wallet for outgoing tips
    WALLET_PRIVATE_KEY — Only needed for auto-payout mode (v2)
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

import requests
import yaml

from auth import RateLimiter, is_authorized_sender, verify_webhook_signature
from state import TipState


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    with open(config_path) as f:
        return yaml.safe_load(f)["tip_bot"]


# ---------------------------------------------------------------------------
# Command Parser
# ---------------------------------------------------------------------------

# Accepted format: /tip @username <amount> RTC
# Flexible on whitespace and case of token symbol.
_TIP_PATTERN = re.compile(
    r"(?:^|\s)/tip\s+"          # /tip command (start-of-line or after whitespace)
    r"@([A-Za-z0-9_-]{1,39})\s+"  # @username (GitHub max 39 chars)
    r"(\d+(?:\.\d+)?)\s+"       # amount (integer or decimal)
    r"([A-Za-z]{1,10})"         # token symbol
    r"(?:\s|$)",                 # followed by whitespace or end
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class TipCommand:
    recipient: str
    amount: float
    token: str
    raw: str


@dataclass
class ParseResult:
    command: Optional[TipCommand]
    error: Optional[str]


def parse_tip_command(comment_body: str, expected_token: str) -> ParseResult:
    """
    Parse a /tip command from a comment body.

    Returns ParseResult with either a valid TipCommand or an error string.
    Returns command=None, error=None if no /tip command is present at all
    (so callers can distinguish "no command" from "malformed command").
    """
    # Check if any /tip attempt exists (catch near-misses too)
    has_tip_attempt = bool(re.search(r"(?:^|\s)/tip\b", comment_body, re.IGNORECASE | re.MULTILINE))
    if not has_tip_attempt:
        return ParseResult(command=None, error=None)

    match = _TIP_PATTERN.search(comment_body)
    if not match:
        return ParseResult(
            command=None,
            error=(
                "Malformed `/tip` command. Expected format:\n"
                "```\n/tip @username <amount> RTC\n```\n"
                "- `@username` must be a valid GitHub username\n"
                "- `<amount>` must be a positive number\n"
                "- Token symbol must be `RTC`"
            ),
        )

    recipient, amount_str, token = match.group(1), match.group(2), match.group(3)

    # Validate token symbol
    if token.upper() != expected_token.upper():
        return ParseResult(
            command=None,
            error=f"Unknown token `{token}`. Only `{expected_token}` tips are supported.",
        )

    # Validate amount
    try:
        amount = float(amount_str)
    except ValueError:
        return ParseResult(
            command=None,
            error=f"Invalid amount `{amount_str}`. Must be a positive number.",
        )

    if amount <= 0:
        return ParseResult(
            command=None,
            error=f"Amount must be greater than 0. Got `{amount}`.",
        )

    # Reject obviously invalid amounts (too many decimal places for RTC)
    if amount != round(amount, 8):
        return ParseResult(
            command=None,
            error=f"Amount `{amount}` has too many decimal places. Max 8.",
        )

    return ParseResult(
        command=TipCommand(
            recipient=recipient,
            amount=amount,
            token=token.upper(),
            raw=match.group(0).strip(),
        ),
        error=None,
    )


def validate_tip(
    cmd: TipCommand,
    sender: str,
    config: dict,
    rate_limiter: RateLimiter,
) -> Optional[str]:
    """
    Validate a parsed tip command beyond basic parsing.

    Returns an error string if invalid, None if valid.
    """
    # Self-tipping is not allowed
    if cmd.recipient.lower() == sender.lower():
        return "You cannot tip yourself."

    # Amount bounds
    if cmd.amount < config["min_amount"]:
        return f"Minimum tip is {config['min_amount']} {config['token_symbol']}."
    if cmd.amount > config["max_amount"]:
        return f"Maximum tip is {config['max_amount']} {config['token_symbol']}."

    # Rate limit
    if not rate_limiter.check(sender):
        limit = config["rate_limit"]["max_per_hour"]
        return f"Rate limit exceeded. Max {limit} tips per hour."

    return None


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def github_post_comment(repo: str, issue_number: int, body: str, token: str) -> bool:
    """Post a comment on an issue or PR. Returns True on success."""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(url, headers=headers, json={"body": body}, timeout=15)
    return resp.status_code == 201


def github_commit_state(repo: str, state_file: str, token: str) -> bool:
    """
    Commit the updated state file back to the repository.
    Uses the GitHub Contents API to create/update the file.
    Returns True on success.
    """
    import base64

    url = f"https://api.github.com/repos/{repo}/contents/{state_file}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Read current state
    with open(state_file, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    # Get current SHA (needed for updates)
    resp = requests.get(url, headers=headers, timeout=15)
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    payload: dict = {
        "message": "chore: update tip state [skip ci]",
        "content": content,
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=headers, json=payload, timeout=15)
    return resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Comment builders
# ---------------------------------------------------------------------------

def build_success_comment(sender: str, cmd: TipCommand, context_url: str) -> str:
    return (
        f"**Tip recorded** ✅\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| From | @{sender} |\n"
        f"| To | @{cmd.recipient} |\n"
        f"| Amount | {cmd.amount} {cmd.token} |\n\n"
        f"This tip has been logged and is **pending manual payout** by the maintainer. "
        f"@{cmd.recipient} will receive `{cmd.amount} {cmd.token}` once processed.\n\n"
        f"---\n"
        f"*🤖 [rustchain-tip-bot](https://github.com/mtarcure/rustchain-tip-bot) — "
        f"maintainer approval required for payout*"
    )


def build_failure_comment(sender: str, error: str) -> str:
    return (
        f"**Tip failed** ❌\n\n"
        f"@{sender}: {error}\n\n"
        f"---\n"
        f"*🤖 [rustchain-tip-bot](https://github.com/mtarcure/rustchain-tip-bot)*"
    )


def build_duplicate_comment(sender: str, cmd: TipCommand) -> str:
    return (
        f"**Duplicate tip ignored** ⚠️\n\n"
        f"@{sender}: This tip (`{cmd.amount} {cmd.token}` → @{cmd.recipient}) "
        f"was already recorded from this comment. No action taken.\n\n"
        f"---\n"
        f"*🤖 [rustchain-tip-bot](https://github.com/mtarcure/rustchain-tip-bot)*"
    )


def build_unauthorized_comment(sender: str) -> str:
    return (
        f"**Unauthorized** ❌\n\n"
        f"@{sender}: Only designated maintainers can issue `/tip` commands.\n\n"
        f"---\n"
        f"*🤖 [rustchain-tip-bot](https://github.com/mtarcure/rustchain-tip-bot)*"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_event(
    event: dict,
    config: dict,
    state: TipState,
    token: str,
    repo: str,
    rate_limiter: Optional[RateLimiter] = None,
) -> str:
    """
    Core processing logic. Separated from I/O for testability.

    Returns one of: "no_command", "unauthorized", "duplicate",
                    "parse_error", "validation_error", "success"
    """
    if rate_limiter is None:
        rate_limiter = RateLimiter(max_per_hour=config["rate_limit"]["max_per_hour"])

    comment = event.get("comment", {})
    issue = event.get("issue", event.get("pull_request", {}))

    comment_body: str = comment.get("body", "")
    sender: str = comment.get("user", {}).get("login", "")
    comment_id: int = comment.get("id", 0)
    issue_number: int = issue.get("number", 0)
    comment_url: str = comment.get("html_url", "")

    # Parse command first (before auth — to give useful errors even to unauthorized)
    parse_result = parse_tip_command(comment_body, config["token_symbol"])

    if parse_result.command is None and parse_result.error is None:
        # No /tip in comment at all
        return "no_command"

    # Authorization check
    if not is_authorized_sender(sender, config["maintainers"]):
        if parse_result.command is not None or parse_result.error is not None:
            # They tried to use /tip but aren't authorized
            github_post_comment(repo, issue_number, build_unauthorized_comment(sender), token)
        return "unauthorized"

    # Malformed command
    if parse_result.error:
        github_post_comment(repo, issue_number, build_failure_comment(sender, parse_result.error), token)
        return "parse_error"

    cmd = parse_result.command
    assert cmd is not None

    # Idempotency check
    idempotency_key = f"{repo}/{comment_id}"
    if state.is_processed(idempotency_key):
        github_post_comment(repo, issue_number, build_duplicate_comment(sender, cmd), token)
        return "duplicate"

    # Validation (amount bounds, self-tip, rate limit)
    validation_error = validate_tip(cmd, sender, config, rate_limiter)
    if validation_error:
        github_post_comment(repo, issue_number, build_failure_comment(sender, validation_error), token)
        return "validation_error"

    # Post confirmation first — only record tip if comment succeeds
    posted = github_post_comment(
        repo,
        issue_number,
        build_success_comment(sender, cmd, comment_url),
        token,
    )
    if not posted:
        print(f"ERROR: Failed to post confirmation comment for comment {comment_id}")
        return "comment_error"

    # Record the tip (only after successful comment)
    state.record_tip(
        idempotency_key=idempotency_key,
        issue_or_pr=issue_number,
        sender=sender,
        recipient=cmd.recipient,
        amount=cmd.amount,
        token=cmd.token,
        context_url=comment_url,
        status="pending_payout",
    )
    state.save()

    # Persist state back to repo
    github_commit_state(repo, config["state_file"], token)

    print(f"Tip recorded: {sender} -> {cmd.recipient} {cmd.amount} {cmd.token} (comment {comment_id})")
    return "success"


def main() -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not os.path.exists(event_path):
        print("No event payload found. Running in test mode — exiting.")
        sys.exit(0)

    with open(event_path) as f:
        event = json.load(f)

    # Verify webhook signature if secret is configured AND a signature header
    # is present. In GitHub Actions, the payload comes from GitHub's own
    # infrastructure (GITHUB_EVENT_PATH) — no HTTP signature header exists.
    # WEBHOOK_SECRET is only useful for external webhook deployments.
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "")
    sig = os.environ.get("HTTP_X_HUB_SIGNATURE_256", "")
    if webhook_secret and sig:
        raw_payload = open(event_path, "rb").read()
        if not verify_webhook_signature(raw_payload, sig):
            print("Webhook signature verification failed. Aborting.")
            sys.exit(1)

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    if not token or not repo:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY must be set.")
        sys.exit(1)

    config = load_config()

    # Override node URL from environment if set
    node_url_env = os.environ.get("RUSTCHAIN_NODE_URL")
    if node_url_env:
        config["rustchain_node_url"] = node_url_env

    state = TipState(config["state_file"])
    rate_limiter = RateLimiter(max_per_hour=config["rate_limit"]["max_per_hour"])

    result = process_event(event, config, state, token, repo, rate_limiter=rate_limiter)
    print(f"Result: {result}")

    # Exit 0 for all handled business logic outcomes (unauthorized, no command,
    # parse error, duplicate). Reserve non-zero for infrastructure failures only.


if __name__ == "__main__":
    main()
