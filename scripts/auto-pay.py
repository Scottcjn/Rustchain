#!/usr/bin/env python3
"""
RTC Auto-Pay — GitHub Actions script for automatic RTC payment on PR merge.

Scans PR comments for a payment directive from the repo owner, then calls
the RustChain VPS transfer API and posts a confirmation comment.

Payment directive format (in a PR comment by repo owner):
    **Payment: 75 RTC**
    Payment: 75 RTC

Environment variables (set by the GitHub Action):
    GITHUB_TOKEN    — GitHub token for API access
    PR_NUMBER       — Pull request number
    REPO            — Repository in "owner/repo" format
    PR_AUTHOR       — GitHub username of the PR author
    RTC_VPS_HOST    — RustChain VPS IP (e.g. 50.28.86.131)
    RTC_ADMIN_KEY   — Admin key for /wallet/transfer
    REPO_OWNER      — Repository owner username (e.g. Scottcjn)
"""

import json
import os
import re
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
VPS_PORT = 8088
FROM_WALLET = "founder_community"

# Payment directive pattern — matches both bold and plain variants:
#   **Payment: 75 RTC**
#   **Payment: 75.5 RTC**
#   Payment: 75 RTC
PAYMENT_RE = re.compile(
    r"\*{0,2}Payment:\s*([\d]+(?:\.[\d]+)?)\s*RTC\*{0,2}",
    re.IGNORECASE,
)

# Duplicate-detection: if this string appears in any comment, payment was
# already processed for this PR.
ALREADY_PAID_MARKER = "RTC-AutoPay-Confirmed"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def env(name: str, required: bool = True) -> str:
    val = os.environ.get(name, "")
    if required and not val:
        print(f"::error::Missing required environment variable: {name}")
        sys.exit(1)
    return val


def gh_headers() -> dict:
    return {
        "Authorization": f"token {env('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_pr_comments(repo: str, pr_number: str) -> list:
    """Fetch all comments on a PR (issue comments endpoint)."""
    comments = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
        resp = requests.get(url, headers=gh_foot(), params={"per_page": 100, "page": page})
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        comments.extend(batch)
        page += 1
    return comments


def post_comment(repo: str, pr_number: str, body: str) -> None:
    """Post a comment on a PR."""
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=gh_foot(), json={"body": body})
    resp.raise_for_status()
    print(f"Posted confirmation comment on PR #{pr_number}")


def transfer_rtc(vps_host: str, admin_key: str, to_wallet: str,
                 amount: float, memo: str) -> dict:
    """Call the RustChain VPS transfer endpoint."""
    url = f"http://{vps_host}:{VPS_PORT}/wallet/transfer"
    payload = {
        "from_miner": FROM_WALLET,
        "to_miner": to_wallet,
        "amount_rtc": amount,
        "memo": memo,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Admin-Key": admin_key,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    repo = env("REPO")
    pr_number = env("PR_NUMBER")
    pr_author = env("PR_AUTHOR")
    vps_host = env("RTC_VPS_HOST", required=False)
    admin_key = env("RTC_ADMIN_KEY", required=False)
    repo_owner = env("REPO_OWNER")

    print(f"Processing PR #{pr_number} in {repo} (author: {pr_author})")

    # --- Fetch comments ---------------------------------------------------
    comments = fetch_pr_comments(repo, pr_number)
    print(f"Found {len(comments)} comment(s) on PR #{pr_number}")

    # --- Check for duplicate run ------------------------------------------
    for c in comments:
        if ALREADY_PAID_MARKER in (c.get("body") or ""):
            print(f"Payment already processed (found {ALREADY_PAID_MARKER}). Skipping.")
            return

    # --- Find payment directive from repo owner ---------------------------
    payment_amount = None
    payment_comment_id = None

    for c in comments:
        author = (c.get("user") or {}).get("login", "")
        body = c.get("body") or ""

        # Only accept directives from the repo owner
        if author.lower() != repo_owner.lower():
            continue

        match = PAYMENT_RE.search(body)
        if match:
            payment_amount = float(match.group(1))
            payment_comment_id = c.get("id")
            print(f"Found payment directive: {payment_amount} RTC "
                  f"(comment {payment_comment_id} by {author})")
            # Use the LAST matching directive from the owner in case of updates
            # (don't break — keep scanning)

    if payment_amount is None:
        print("No payment directive found from repo owner. Nothing to do.")
        return

    if payment_amount <= 0:
        print(f"::warning::Payment amount is {payment_amount} RTC — skipping.")
        return

    if payment_amount > 10000:
        print(f"::error::Payment amount {payment_amount} RTC exceeds safety limit of 10,000 RTC. "
              "Process manually.")
        sys.exit(1)

    # --- Determine recipient wallet ---------------------------------------
    # Wallet is the contributor's GitHub username
    to_wallet = pr_author
    memo = f"PR #{pr_number} in {repo} — auto-pay"

    print(f"Initiating transfer: {payment_amount} RTC from {FROM_WALLET} to {to_wallet}")

    # --- Check if VPS secrets are configured ------------------------------
    if not vps_host or not admin_key:
        print("::warning::RTC_VPS_HOST or RTC_ADMIN_KEY not configured — posting manual transfer notice.")
        manual_body = (
            f"**RTC Auto-Pay — Manual Transfer Required**\n\n"
            f"Payment directive found: **{payment_amount} RTC** for @{to_wallet}\n\n"
            f"VPS secrets not configured — please process this payment manually.\n\n"
            f"<!-- {ALREADY_PAID_MARKER}:MANUAL -->"
        )
        post_comment(repo, pr_number, manual_body)
        print(f"Manual transfer notice posted for {payment_amount} RTC to {to_wallet}")
        return

    # --- Call VPS transfer API --------------------------------------------
    try:
        result = transfer_rtc(vps_host, admin_key, to_wallet, payment_amount, memo)
    except requests.exceptions.ConnectionError as e:
        print(f"::error::Cannot reach VPS at {vps_host}:{VPS_PORT} — {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"::error::VPS returned error: {e.response.status_code} — {e.response.text}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"::error::VPS request timed out after 30s")
        sys.exit(1)

    ok = result.get("ok", False)
    pending_id = result.get("pending_id", result.get("tx_id", "n/a"))
    error = result.get("error", "")

    if not ok:
        print(f"::error::Transfer failed: {error}")
        # Post failure notice so humans know
        fail_body = (
            f"**RTC Auto-Pay Failed**\n\n"
            f"Attempted to pay **{payment_amount} RTC** to `{to_wallet}` "
            f"but the transfer was rejected:\n\n"
            f"```\n{error}\n```\n\n"
            f"Please process this payment manually.\n\n"
            f"<!-- {ALREADY_PAID_MARKER}:FAILED -->"
        )
        post_comment(repo, pr_number, fail_body)
        sys.exit(1)

    # --- Post confirmation comment ----------------------------------------
    confirm_body = (
        f"**RTC Payment Sent**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Amount | **{payment_amount} RTC** |\n"
        f"| Recipient | `{to_wallet}` |\n"
        f"| From | `{FROM_WALLET}` |\n"
        f"| Memo | {memo} |\n"
        f"| pending_id | `{pending_id}` |\n\n"
        f"Transfer confirmed on RustChain.\n\n"
        f"<!-- {ALREADY_PAID_MARKER} pending_id={pending_id} -->"
    )
    post_comment(repo, pr_number, confirm_body)

    print(f"Payment complete: {payment_amount} RTC to {to_wallet} (pending_id={pending_id})")


if __name__ == "__main__":
    main()
