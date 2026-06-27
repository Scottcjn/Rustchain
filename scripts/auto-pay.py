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

import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
GITHUB_REQUEST_TIMEOUT_SECONDS = 15
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
PAYMENT_STARTED_MARKER = "RTC-AutoPay-Started"
MANUAL_PAYMENT_MARKER = "RTC-AutoPay-Manual-Required"
TRUSTED_BOT_LOGINS = {"github-actions[bot]"}
STARTED_LOCK_TTL_SECONDS = 10 * 60
LOCK_REF_PREFIX = "refs/heads/rtc-autopay-locks"

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
        resp = requests.get(
            url,
            headers=gh_headers(),
            params={"per_page": 100, "page": page},
            timeout=GITHUB_REQUEST_TIMEOUT_SECONDS,
        )
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
    resp = requests.post(
        url,
        headers=gh_headers(),
        json={"body": body},
        timeout=GITHUB_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    print(f"Posted confirmation comment on PR #{pr_number}")


def resolve_lock_sha() -> str:
    """Return an existing commit SHA to attach the GitHub lock ref to."""
    sha = os.environ.get("GITHUB_SHA", "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return sha

    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = ""

    if re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return sha

    print("::error::Unable to resolve a commit SHA for the auto-pay lock ref")
    sys.exit(1)


def lock_ref_name(pr_number: str, payment_key: str) -> str:
    """Build a deterministic per-claim Git ref name used as the mutex."""
    return f"{LOCK_REF_PREFIX}/pr-{pr_number}/{payment_key}"


def acquire_payment_lock(repo: str, pr_number: str, payment_key: str) -> bool:
    """Atomically create a per-payment Git ref.

    GitHub's create-ref endpoint is conditional: it succeeds for exactly one
    concurrent caller and returns 422 once the ref already exists. This is a
    real mutex, unlike checking for a marker comment before posting one.
    """
    ref = lock_ref_name(pr_number, payment_key)
    url = f"{GITHUB_API}/repos/{repo}/git/refs"
    resp = requests.post(
        url,
        headers=gh_headers(),
        json={"ref": ref, "sha": resolve_lock_sha()},
        timeout=GITHUB_REQUEST_TIMEOUT_SECONDS,
    )
    if resp.status_code == 422:
        print(f"Payment already in progress (lock ref exists: {ref}). Skipping.")
        return False
    resp.raise_for_status()
    print(f"Acquired payment lock ref: {ref}")
    return True


def release_payment_lock(repo: str, pr_number: str, payment_key: str) -> None:
    """Best-effort unlock for failures before a transfer is accepted."""
    ref_path = lock_ref_name(pr_number, payment_key).removeprefix("refs/")
    url = f"{GITHUB_API}/repos/{repo}/git/refs/{ref_path}"
    try:
        resp = requests.delete(
            url,
            headers=gh_headers(),
            timeout=GITHUB_REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code not in (204, 404):
            resp.raise_for_status()
        print(f"Released payment lock ref: refs/{ref_path}")
    except requests.exceptions.RequestException as e:
        print(f"::warning::Failed to release payment lock ref refs/{ref_path}: {e}")


def transfer_rtc(vps_host: str, admin_key: str, to_wallet: str,
                 amount: float, memo: str, payment_key: str) -> dict:
    """Call the RustChain VPS transfer endpoint."""
    url = f"http://{vps_host}:{VPS_PORT}/wallet/transfer"
    payload = {
        "from_miner": FROM_WALLET,
        "to_miner": to_wallet,
        "amount_rtc": amount,
        "memo": memo,
        "idempotency_key": payment_key,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Admin-Key": admin_key,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def trusted_marker_author(comment: dict, repo_owner: str) -> bool:
    """Return True if a comment author may create auto-pay state markers."""
    author = ((comment.get("user") or {}).get("login") or "").lower()
    return author == repo_owner.lower() or author in TRUSTED_BOT_LOGINS


def trusted_started_marker_is_fresh(comment: dict, now: datetime | None = None) -> bool:
    """Return True when a started marker is recent enough to act as a lock.

    GitHub issue comments carry a server-side ``created_at`` timestamp.  Treat
    only fresh started comments as in-progress locks so a second workflow run
    cannot race past the first one and submit a duplicate transfer.  Missing or
    malformed timestamps are ignored instead of becoming permanent locks, which
    preserves recovery from old comments and simplified test fixtures.
    """
    created_at = comment.get("created_at")
    if not created_at:
        return False

    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False

    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    current = now or datetime.now(timezone.utc)
    return 0 <= (current - created).total_seconds() <= STARTED_LOCK_TTL_SECONDS


def build_payment_key(repo: str, pr_number: str, payment_comment_id: object,
                      amount: float, to_wallet: str) -> str:
    """Build a stable key for a specific owner payment directive."""
    raw = f"{repo}:{pr_number}:{payment_comment_id}:{amount:.6f}:{to_wallet}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def find_existing_payment_marker(comments: list, repo_owner: str,
                                 payment_key: str) -> str:
    """Find a trusted final or fresh in-progress payment marker for this key."""
    for c in comments:
        if not trusted_marker_author(c, repo_owner):
            continue
        body = c.get("body") or ""
        if (
            PAYMENT_STARTED_MARKER in body
            and f"payment_key={payment_key}" in body
            and trusted_started_marker_is_fresh(c)
        ):
            return PAYMENT_STARTED_MARKER
        if ALREADY_PAID_MARKER not in body:
            continue
        if f"{ALREADY_PAID_MARKER}:MANUAL" in body:
            continue
        if f"payment_key={payment_key}" in body:
            return ALREADY_PAID_MARKER
        if "payment_key=" not in body:
            return ALREADY_PAID_MARKER
    return ""


def find_existing_manual_marker(comments: list, repo_owner: str,
                                payment_key: str) -> str:
    """Find a trusted manual-transfer notice for this payment key."""
    for c in comments:
        if not trusted_marker_author(c, repo_owner):
            continue
        body = c.get("body") or ""
        if MANUAL_PAYMENT_MARKER in body and f"payment_key={payment_key}" in body:
            return MANUAL_PAYMENT_MARKER
        if f"{ALREADY_PAID_MARKER}:MANUAL" in body and f"payment_key={payment_key}" in body:
            return MANUAL_PAYMENT_MARKER
    return ""


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
    payment_key = build_payment_key(repo, pr_number, payment_comment_id, payment_amount, to_wallet)

    # --- Check for duplicate run ------------------------------------------
    marker = find_existing_payment_marker(comments, repo_owner, payment_key)
    if marker:
        print(f"Payment already processed or in progress (found trusted {marker}). Skipping.")
        return

    print(f"Initiating transfer: {payment_amount} RTC from {FROM_WALLET} to {to_wallet}")

    # --- Check if VPS secrets are configured ------------------------------
    if not vps_host or not admin_key:
        manual_marker = find_existing_manual_marker(comments, repo_owner, payment_key)
        if manual_marker:
            print(f"Manual transfer notice already posted (found trusted {manual_marker}). Skipping.")
            return

        print("::warning::RTC_VPS_HOST or RTC_ADMIN_KEY not configured — posting manual transfer notice.")
        manual_body = (
            f"**RTC Auto-Pay — Manual Transfer Required**\n\n"
            f"Payment directive found: **{payment_amount} RTC** for @{to_wallet}\n\n"
            f"VPS secrets not configured — please process this payment manually.\n\n"
            f"<!-- {MANUAL_PAYMENT_MARKER} payment_key={payment_key} "
            f"payment_comment_id={payment_comment_id} -->"
        )
        post_comment(repo, pr_number, manual_body)
        print(f"Manual transfer notice posted for {payment_amount} RTC to {to_wallet}")
        return

    if not acquire_payment_lock(repo, pr_number, payment_key):
        return

    started_body = (
        f"**RTC Auto-Pay Started**\n\n"
        f"Preparing to pay **{payment_amount} RTC** to `{to_wallet}`.\n\n"
        f"<!-- {PAYMENT_STARTED_MARKER} payment_key={payment_key} "
        f"payment_comment_id={payment_comment_id} -->"
    )
    post_comment(repo, pr_number, started_body)

    # --- Call VPS transfer API --------------------------------------------
    try:
        result = transfer_rtc(vps_host, admin_key, to_wallet, payment_amount, memo, payment_key)
    except requests.exceptions.ConnectionError as e:
        release_payment_lock(repo, pr_number, payment_key)
        print(f"::error::Cannot reach VPS at {vps_host}:{VPS_PORT} — {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        release_payment_lock(repo, pr_number, payment_key)
        print(f"::error::VPS returned error: {e.response.status_code} — {e.response.text}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        release_payment_lock(repo, pr_number, payment_key)
        print("::error::VPS request timed out after 30s")
        sys.exit(1)

    ok = result.get("ok", False)
    pending_id = result.get("pending_id", result.get("tx_id", "n/a"))
    error = result.get("error", "")

    if not ok:
        print(f"::error::Transfer failed: {error}")
        release_payment_lock(repo, pr_number, payment_key)
        # Post failure notice so humans know
        fail_body = (
            f"**RTC Auto-Pay Failed**\n\n"
            f"Attempted to pay **{payment_amount} RTC** to `{to_wallet}` "
            f"but the transfer was rejected:\n\n"
            f"```\n{error}\n```\n\n"
            f"Please process this payment manually.\n\n"
            f"<!-- {ALREADY_PAID_MARKER}:FAILED payment_key={payment_key} "
            f"payment_comment_id={payment_comment_id} -->"
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
        f"<!-- {ALREADY_PAID_MARKER} payment_key={payment_key} "
        f"payment_comment_id={payment_comment_id} pending_id={pending_id} -->"
    )
    post_comment(repo, pr_number, confirm_body)

    print(f"Payment complete: {payment_amount} RTC to {to_wallet} (pending_id={pending_id})")


if __name__ == "__main__":
    main()
