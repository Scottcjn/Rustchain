#!/usr/bin/env python3
"""
RustChain Payment Reconciler
==============================
Cross-references GitHub PR payment promises against the actual RTC ledger.

Scans merged PRs in Scottcjn/Rustchain and Scottcjn/rustchain-bounties for
payment comments by the repo owner (Scottcjn), extracts promised RTC amounts,
then compares against the on-chain ledger to flag discrepancies.

Usage:
    # With local DB copy:
    python3 payment_reconciler.py --github-token TOKEN --db-path /path/to/rustchain_v2.db

    # Via SSH to VPS (production):
    python3 payment_reconciler.py --github-token TOKEN --ssh-host 50.28.86.131

    # Output JSON report:
    python3 payment_reconciler.py --github-token TOKEN --ssh-host 50.28.86.131 --json

    # Scan specific repos only:
    python3 payment_reconciler.py --github-token TOKEN --ssh-host 50.28.86.131 \
        --repos Scottcjn/Rustchain Scottcjn/BoTTube

Environment variables (alternative to CLI flags):
    GITHUB_TOKEN        GitHub personal access token
    RC_SSH_HOST         VPS hostname (default: 50.28.86.131)
    RC_SSH_USER         VPS SSH user (default: root)
    RC_SSH_PASS         VPS SSH password
    RC_DB_PATH          Local path to rustchain_v2.db
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_REPOS = [
    "Scottcjn/Rustchain",
    "Scottcjn/rustchain-bounties",
    "Scottcjn/BoTTube",
]

REPO_OWNER = "Scottcjn"

# Scale factor: ledger stores micro-RTC (1 RTC = 1_000_000 units)
MICRO_RTC = 1_000_000

# GitHub API base
GH_API = "https://api.github.com"

# Founder wallets that pay out bounties
PAYOUT_WALLETS = {"founder_community", "founder_team_bounty", "founder_dev_fund", "team_bounty"}

# Payment comment patterns (case-insensitive).
# Matches things like:
#   "Payment: 150 RTC"
#   "Merged. 50 RTC"
#   "75 RTC —"
#   "**250 RTC** paid"
#   "Approved for 100 RTC"
#   "Paying 300 RTC"
#   "200 RTC to createkr"
PAYMENT_PATTERNS = [
    # "Payment: 150 RTC" or "Payment: **150 RTC**"
    re.compile(r"payment[:\s]+\*{0,2}(\d+(?:\.\d+)?)\s*RTC\b", re.IGNORECASE),
    # "Merged. 50 RTC" or "Merged — 50 RTC"
    re.compile(r"merged[\.\s—\-]+\*{0,2}(\d+(?:\.\d+)?)\s*RTC\b", re.IGNORECASE),
    # "X RTC —" (amount followed by dash, common in payment notes)
    re.compile(r"\b(\d+(?:\.\d+)?)\s*RTC\s*[—\-]", re.IGNORECASE),
    # "X RTC paid" or "X RTC approved" or "**X RTC** paid"
    re.compile(r"\*{0,2}(\d+(?:\.\d+)?)\s*RTC\*{0,2}\s*(?:paid|approved|sent|transferred|awarded)", re.IGNORECASE),
    # "Approved for X RTC" or "Paying X RTC"
    re.compile(r"(?:approved\s+for|paying|pay|awarding|award)\s+\*{0,2}(\d+(?:\.\d+)?)\s*RTC\b", re.IGNORECASE),
    # "**X RTC** to username" or "X RTC to username"
    re.compile(r"\b\*{0,2}(\d+(?:\.\d+)?)\s*RTC\*{0,2}\s+to\s+\w+", re.IGNORECASE),
    # Bounty table rows: "| 150 RTC |" or "| **150 RTC** |"
    re.compile(r"\|\s*\*{0,2}(\d+(?:\.\d+)?)\s*RTC\*{0,2}\s*\|", re.IGNORECASE),
]

# Known GitHub username -> wallet ID mappings.
# The reconciler also tries lowercase github username as a fallback.
USERNAME_TO_WALLET = {
    "createkr": "createkr",
    "B1tor": "B1tor",
    "LaphoqueRC": "LaphoqueRC",
    "simplereally": "simplereally",
    "ArokyaMatthew": "aroky-x86-miner",
    "BuilderFred": "BuilderFred",
    "allornothingai": "allornothingai",
    "ApextheBoss": "ApextheBoss",
    "danielalanbates": "danielalanbates",
    "mtarcure": "mtarcure",
    "wirework": "wirework",
    "nox-ventures": "nox-ventures",
    "zhanglinqian": "zhanglinqian",
    "liu971227-sys": "liu971227-sys",
    "davidtang-codex": "davidtang-codex",
    # Add mappings here as contributors register wallets
}


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def gh_request(endpoint: str, token: str, params: dict | None = None) -> dict | list:
    """Make a GitHub API request using curl (no requests dependency)."""
    url = f"{GH_API}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    cmd = [
        "curl", "-s", "-f",
        "-H", f"Authorization: token {token}",
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28",
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"GitHub API error for {endpoint}: {result.stderr[:200]}")

    return json.loads(result.stdout)


def gh_paginate(endpoint: str, token: str, params: dict | None = None,
                max_pages: int = 50) -> list:
    """Paginate through GitHub API results."""
    params = dict(params or {})
    params.setdefault("per_page", "100")
    all_items = []

    for page in range(1, max_pages + 1):
        params["page"] = str(page)
        items = gh_request(endpoint, token, params)
        if not items or not isinstance(items, list):
            break
        all_items.extend(items)
        if len(items) < int(params["per_page"]):
            break
        # Respect rate limits
        time.sleep(0.5)

    return all_items


def get_pr_comments(repo: str, pr_number: int, token: str) -> list:
    """Get all comments on a PR (issue comments + review comments)."""
    comments = gh_paginate(f"/repos/{repo}/issues/{pr_number}/comments", token)
    return comments


# ---------------------------------------------------------------------------
# Payment extraction
# ---------------------------------------------------------------------------

def extract_payment_amount(text: str) -> float | None:
    """Extract the RTC payment amount from a comment body.

    Returns the largest amount found (comments sometimes mention amounts
    in context like 'originally 50 RTC, now paying 75 RTC').
    """
    if not text:
        return None

    amounts = []
    for pattern in PAYMENT_PATTERNS:
        for match in pattern.finditer(text):
            try:
                amt = float(match.group(1))
                if 0.001 <= amt <= 100000:  # sanity bounds
                    amounts.append(amt)
            except (ValueError, IndexError):
                continue

    return max(amounts) if amounts else None


def extract_recipient_from_comment(text: str, pr_author: str) -> str | None:
    """Try to extract who the payment is for from the comment text.

    Falls back to the PR author if no explicit recipient mentioned.
    """
    # "X RTC to @username" or "X RTC to username"
    m = re.search(r"\bRTC\b.*?\bto\s+@?(\w[\w-]*)", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # "paying @username" or "paid @username"
    m = re.search(r"(?:paying|paid|awarded?\s+to)\s+@?(\w[\w-]*)", text, re.IGNORECASE)
    if m:
        candidate = m.group(1)
        if candidate.lower() not in ("the", "for", "this", "a", "an"):
            return candidate

    return pr_author


def scan_repo_payments(repo: str, token: str) -> list[dict]:
    """Scan a repo for merged PRs with payment comments from the owner.

    Returns list of payment records:
        {repo, pr_number, pr_title, pr_author, amount_rtc, recipient_github,
         wallet_id, comment_url, comment_date, comment_body_snippet}
    """
    print(f"  Scanning {repo} for merged PRs with payments...")

    # Get merged PRs
    prs = gh_paginate(
        f"/repos/{repo}/pulls",
        token,
        params={"state": "closed", "sort": "updated", "direction": "desc"},
    )

    merged_prs = [pr for pr in prs if pr.get("merged_at")]
    print(f"    Found {len(merged_prs)} merged PRs (of {len(prs)} closed)")

    payments = []
    for i, pr in enumerate(merged_prs):
        pr_number = pr["number"]
        pr_author = pr["user"]["login"]
        pr_title = pr.get("title", "")

        # Rate limit: check comments every 2 PRs
        if i > 0 and i % 10 == 0:
            time.sleep(1.0)

        comments = get_pr_comments(repo, pr_number, token)

        for comment in comments:
            commenter = comment.get("user", {}).get("login", "")
            # Only count payments from the repo owner
            if commenter.lower() != REPO_OWNER.lower():
                continue

            body = comment.get("body", "")
            amount = extract_payment_amount(body)
            if amount is None:
                continue

            recipient_gh = extract_recipient_from_comment(body, pr_author)
            wallet_id = resolve_wallet(recipient_gh)

            payments.append({
                "repo": repo,
                "pr_number": pr_number,
                "pr_title": pr_title,
                "pr_author": pr_author,
                "amount_rtc": amount,
                "recipient_github": recipient_gh,
                "wallet_id": wallet_id,
                "comment_url": comment.get("html_url", ""),
                "comment_date": comment.get("created_at", ""),
                "comment_body_snippet": body[:200],
            })

    print(f"    Extracted {len(payments)} payment promises")
    return payments


def resolve_wallet(github_username: str) -> str | None:
    """Resolve a GitHub username to a RustChain wallet ID."""
    if not github_username:
        return None

    # Direct mapping
    if github_username in USERNAME_TO_WALLET:
        return USERNAME_TO_WALLET[github_username]

    # Try lowercase
    lower = github_username.lower()
    for k, v in USERNAME_TO_WALLET.items():
        if k.lower() == lower:
            return v

    # Fallback: use github username as wallet ID (common pattern)
    return github_username


# ---------------------------------------------------------------------------
# Ledger queries (via SSH or local DB)
# ---------------------------------------------------------------------------

def get_db_connection(args) -> sqlite3.Connection:
    """Get a SQLite connection, either local or via SSH-fetched copy."""
    if args.db_path and os.path.exists(args.db_path):
        print(f"  Using local DB: {args.db_path}")
        return sqlite3.connect(args.db_path)

    # Fetch via SSH
    ssh_host = args.ssh_host or os.environ.get("RC_SSH_HOST", "50.28.86.131")
    ssh_user = args.ssh_user or os.environ.get("RC_SSH_USER", "root")
    ssh_pass = args.ssh_pass or os.environ.get("RC_SSH_PASS", "")

    if not ssh_pass:
        print("ERROR: No SSH password provided (--ssh-pass or RC_SSH_PASS)")
        sys.exit(1)

    remote_db = "/root/rustchain/rustchain_v2.db"
    local_tmp = os.path.join(tempfile.gettempdir(), "rustchain_v2_reconciler.db")

    print(f"  Fetching DB from {ssh_user}@{ssh_host}:{remote_db} ...")

    cmd = [
        "sshpass", "-p", ssh_pass,
        "scp", "-o", "StrictHostKeyChecking=no",
        f"{ssh_user}@{ssh_host}:{remote_db}",
        local_tmp,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"ERROR: SCP failed: {result.stderr[:200]}")
        sys.exit(1)

    print(f"  DB fetched to {local_tmp} ({os.path.getsize(local_tmp) / 1024 / 1024:.1f} MB)")
    return sqlite3.connect(local_tmp)


def query_ledger_payments(conn: sqlite3.Connection) -> dict[str, float]:
    """Query actual RTC payments from founder wallets to contributors.

    Returns {wallet_id: total_rtc_received}.
    """
    cur = conn.cursor()

    # Sum all transfer_in entries from founder payout wallets
    # The reason format is: transfer_in:<from_wallet>:<tx_hash>
    payout_patterns = [f"transfer_in:{w}%" for w in PAYOUT_WALLETS]

    totals: dict[str, float] = defaultdict(float)

    for pattern in payout_patterns:
        cur.execute(
            "SELECT miner_id, SUM(delta_i64) FROM ledger "
            "WHERE reason LIKE ? GROUP BY miner_id",
            (pattern,),
        )
        for row in cur.fetchall():
            miner_id, sum_micro = row
            # Skip internal transfers between founder wallets
            if miner_id in PAYOUT_WALLETS or miner_id.startswith("founder_"):
                continue
            totals[miner_id] += sum_micro / MICRO_RTC

    return dict(totals)


def query_pending_transfers(conn: sqlite3.Connection) -> dict[str, float]:
    """Query pending (in-transit) transfers."""
    cur = conn.cursor()
    cur.execute(
        "SELECT to_miner, SUM(amount_i64) FROM pending_ledger "
        "WHERE status = 'pending' GROUP BY to_miner"
    )
    return {row[0]: row[1] / MICRO_RTC for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Reconciliation logic
# ---------------------------------------------------------------------------

def reconcile(
    github_payments: list[dict],
    ledger_payments: dict[str, float],
    pending_payments: dict[str, float],
) -> dict:
    """Cross-reference GitHub promises against ledger reality.

    Returns a structured report.
    """
    # Aggregate GitHub promises by recipient wallet
    promised: dict[str, dict] = defaultdict(lambda: {
        "total_rtc": 0.0,
        "prs": [],
        "github_username": None,
    })

    for p in github_payments:
        wallet = p["wallet_id"] or p["recipient_github"] or p["pr_author"]
        promised[wallet]["total_rtc"] += p["amount_rtc"]
        promised[wallet]["github_username"] = p["recipient_github"]
        promised[wallet]["prs"].append({
            "repo": p["repo"],
            "pr": p["pr_number"],
            "title": p["pr_title"],
            "amount": p["amount_rtc"],
            "date": p["comment_date"],
            "url": p["comment_url"],
        })

    # Build reconciliation entries
    all_wallets = set(promised.keys()) | set(ledger_payments.keys())
    entries = []

    for wallet in sorted(all_wallets):
        promise_total = promised.get(wallet, {}).get("total_rtc", 0.0)
        paid_total = ledger_payments.get(wallet, 0.0)
        pending_total = pending_payments.get(wallet, 0.0)
        effective_paid = paid_total + pending_total

        diff = effective_paid - promise_total

        if promise_total == 0 and paid_total > 0:
            status = "NO_PR_REFERENCE"
        elif abs(diff) < 0.01:
            status = "OK"
        elif diff < -0.01:
            status = "UNPAID"
        elif diff > 0.01:
            status = "OVERPAID"
        else:
            status = "OK"

        entry = {
            "wallet": wallet,
            "github_username": promised.get(wallet, {}).get("github_username"),
            "promised_rtc": round(promise_total, 6),
            "paid_rtc": round(paid_total, 6),
            "pending_rtc": round(pending_total, 6),
            "effective_paid_rtc": round(effective_paid, 6),
            "discrepancy_rtc": round(diff, 6),
            "status": status,
            "prs": promised.get(wallet, {}).get("prs", []),
        }
        entries.append(entry)

    # Summary stats
    total_promised = sum(e["promised_rtc"] for e in entries)
    total_paid = sum(e["paid_rtc"] for e in entries)
    total_pending = sum(e["pending_rtc"] for e in entries)
    unpaid_entries = [e for e in entries if e["status"] == "UNPAID"]
    overpaid_entries = [e for e in entries if e["status"] == "OVERPAID"]
    no_ref_entries = [e for e in entries if e["status"] == "NO_PR_REFERENCE"]
    ok_entries = [e for e in entries if e["status"] == "OK"]

    total_unpaid = sum(abs(e["discrepancy_rtc"]) for e in unpaid_entries)
    total_overpaid = sum(e["discrepancy_rtc"] for e in overpaid_entries)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_promised_rtc": round(total_promised, 2),
            "total_paid_rtc": round(total_paid, 2),
            "total_pending_rtc": round(total_pending, 2),
            "total_unpaid_rtc": round(total_unpaid, 2),
            "total_overpaid_rtc": round(total_overpaid, 2),
            "count_ok": len(ok_entries),
            "count_unpaid": len(unpaid_entries),
            "count_overpaid": len(overpaid_entries),
            "count_no_pr_reference": len(no_ref_entries),
            "total_contributors": len(entries),
        },
        "entries": entries,
    }

    return report


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_report(report: dict) -> None:
    """Print a human-readable reconciliation report."""
    s = report["summary"]
    print("\n" + "=" * 72)
    print("  RUSTCHAIN PAYMENT RECONCILIATION REPORT")
    print(f"  Generated: {report['generated_at']}")
    print("=" * 72)

    print(f"\n  Total promised (from GitHub PRs):  {s['total_promised_rtc']:>12.2f} RTC")
    print(f"  Total paid (on-chain):             {s['total_paid_rtc']:>12.2f} RTC")
    print(f"  Total pending (in transit):        {s['total_pending_rtc']:>12.2f} RTC")
    print(f"  Total unpaid shortfall:            {s['total_unpaid_rtc']:>12.2f} RTC")
    print(f"  Total overpaid surplus:            {s['total_overpaid_rtc']:>12.2f} RTC")

    print(f"\n  Contributors: {s['total_contributors']}")
    print(f"    OK:               {s['count_ok']}")
    print(f"    UNPAID:           {s['count_unpaid']}")
    print(f"    OVERPAID:         {s['count_overpaid']}")
    print(f"    NO_PR_REFERENCE:  {s['count_no_pr_reference']}")

    # Show problem entries
    entries = report["entries"]

    unpaid = [e for e in entries if e["status"] == "UNPAID"]
    if unpaid:
        print(f"\n{'=' * 72}")
        print("  UNPAID (Promised > Paid)")
        print(f"{'=' * 72}")
        for e in sorted(unpaid, key=lambda x: x["discrepancy_rtc"]):
            print(f"\n  {e['wallet']}"
                  f" ({e['github_username'] or '?'})")
            print(f"    Promised: {e['promised_rtc']:>10.2f} RTC")
            print(f"    Paid:     {e['paid_rtc']:>10.2f} RTC"
                  f"  (+ {e['pending_rtc']:.2f} pending)")
            print(f"    OWED:     {abs(e['discrepancy_rtc']):>10.2f} RTC")
            for pr in e["prs"]:
                print(f"      PR #{pr['pr']}: {pr['amount']:.2f} RTC"
                      f" - {pr['title'][:50]}")
                if pr.get("url"):
                    print(f"        {pr['url']}")

    overpaid = [e for e in entries if e["status"] == "OVERPAID"]
    if overpaid:
        print(f"\n{'=' * 72}")
        print("  OVERPAID (Paid > Promised) -- may indicate direct payments without PR")
        print(f"{'=' * 72}")
        for e in sorted(overpaid, key=lambda x: -x["discrepancy_rtc"])[:20]:
            print(f"\n  {e['wallet']}"
                  f" ({e['github_username'] or '?'})")
            print(f"    Promised: {e['promised_rtc']:>10.2f} RTC")
            print(f"    Paid:     {e['paid_rtc']:>10.2f} RTC")
            print(f"    SURPLUS:  {e['discrepancy_rtc']:>10.2f} RTC")

    no_ref = [e for e in entries if e["status"] == "NO_PR_REFERENCE"]
    if no_ref:
        # Only show top 20 by amount
        no_ref_sorted = sorted(no_ref, key=lambda x: -x["paid_rtc"])[:20]
        print(f"\n{'=' * 72}")
        print(f"  NO PR REFERENCE (top 20 of {len(no_ref)} -- paid on-chain, no matching PR)")
        print(f"{'=' * 72}")
        for e in no_ref_sorted:
            print(f"  {e['wallet']:<35s} {e['paid_rtc']:>10.2f} RTC")

    print(f"\n{'=' * 72}")
    print("  END OF REPORT")
    print(f"{'=' * 72}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="RustChain Payment Reconciler")
    p.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""),
                    help="GitHub personal access token")
    p.add_argument("--db-path", default=os.environ.get("RC_DB_PATH", ""),
                    help="Path to local rustchain_v2.db")
    p.add_argument("--ssh-host", default=os.environ.get("RC_SSH_HOST", "50.28.86.131"),
                    help="VPS SSH host")
    p.add_argument("--ssh-user", default=os.environ.get("RC_SSH_USER", "root"),
                    help="VPS SSH user")
    p.add_argument("--ssh-pass", default=os.environ.get("RC_SSH_PASS", ""),
                    help="VPS SSH password")
    p.add_argument("--repos", nargs="+", default=DEFAULT_REPOS,
                    help="GitHub repos to scan (owner/repo)")
    p.add_argument("--json", action="store_true",
                    help="Output JSON report to stdout")
    p.add_argument("--json-file", default="",
                    help="Write JSON report to file")
    p.add_argument("--wallet-map", default="",
                    help="JSON file mapping github usernames to wallet IDs")
    p.add_argument("--max-prs", type=int, default=500,
                    help="Maximum PRs to scan per repo")
    return p.parse_args()


def main():
    args = parse_args()

    if not args.github_token:
        print("ERROR: --github-token required (or set GITHUB_TOKEN env var)")
        sys.exit(1)

    # Load custom wallet mappings if provided
    if args.wallet_map and os.path.exists(args.wallet_map):
        with open(args.wallet_map) as f:
            USERNAME_TO_WALLET.update(json.load(f))
        print(f"  Loaded {len(USERNAME_TO_WALLET)} wallet mappings")

    # Phase 1: Scan GitHub PRs for payment promises
    print("\n[Phase 1] Scanning GitHub for payment promises...")
    all_payments = []
    for repo in args.repos:
        try:
            payments = scan_repo_payments(repo, args.github_token)
            all_payments.extend(payments)
        except Exception as e:
            print(f"  WARNING: Failed to scan {repo}: {e}")

    print(f"\n  Total payment promises found: {len(all_payments)}")

    # Phase 2: Query the RustChain ledger
    print("\n[Phase 2] Querying RustChain ledger...")
    conn = get_db_connection(args)
    ledger_payments = query_ledger_payments(conn)
    pending_payments = query_pending_transfers(conn)
    conn.close()

    print(f"  Ledger: {len(ledger_payments)} wallets with founder transfers")
    print(f"  Pending: {len(pending_payments)} wallets with pending transfers")

    # Phase 3: Reconcile
    print("\n[Phase 3] Reconciling...")
    report = reconcile(all_payments, ledger_payments, pending_payments)

    # Output
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.json_file:
        with open(args.json_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  JSON report written to {args.json_file}")

    # Exit code: non-zero if unpaid entries exist
    if report["summary"]["count_unpaid"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
