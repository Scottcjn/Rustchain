#!/usr/bin/env python3
"""
One-time phantom-balance sweep for RTC payouts misrouted to GitHub usernames.

Usage:
    RC_ADMIN_KEY=... python3 sweep_phantom_balances.py --commit

Defaults are intentionally review-friendly:
    - without ``--commit`` the script performs a dry run and only logs actions
    - only usernames with exactly one unambiguous declared wallet across recent
      merged PRs are auto-resolved
    - everything else is logged for manual follow-up
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from award_rtc_patched import is_valid_wallet, resolve_wallet_from_pr_body_details

DEFAULT_BASE_URL = os.environ.get("RC_BASE_URL", "https://50.28.86.131").rstrip("/")
DEFAULT_REPOS = [
    repo.strip()
    for repo in os.environ.get(
        "RC_GITHUB_REPOS",
        "Scottcjn/Rustchain,Scottcjn/bottube,Scottcjn/rustchain-bounties",
    ).split(",")
    if repo.strip()
]
DEFAULT_LOOKBACK_DAYS = int(os.environ.get("RC_LOOKBACK_DAYS", "365"))
DEFAULT_PER_PAGE = 100
UNIT = Decimal("1000000")

GITHUB_USERNAME_RE = re.compile(r"^(?!-)(?!.*--)[A-Za-z0-9-]{1,39}(?<!-)$")


@dataclass
class PhantomBalance:
    miner_id: str
    amount_i64: int
    amount_rtc: Decimal


@dataclass
class WalletEvidence:
    wallets: dict[str, list[str]] = field(default_factory=dict)

    def add(self, wallet: str, pr_ref: str) -> None:
        self.wallets.setdefault(wallet, []).append(pr_ref)

    @property
    def unique_wallets(self) -> list[str]:
        return list(self.wallets.keys())


def log(msg: str) -> None:
    print(msg)


def json_request(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Any:
    data = None
    req_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = Request(url, data=data, headers=req_headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_recent_merged_prs(
    repo: str,
    *,
    lookback_days: int,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: int = 5,
) -> Iterable[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    for page in range(1, max_pages + 1):
        query = urlencode(
            {
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": str(per_page),
                "page": str(page),
            }
        )
        url = f"https://api.github.com/repos/{repo}/pulls?{query}"
        pulls = json_request(url, headers=github_headers())
        if not pulls:
            break

        for pr in pulls:
            merged_at = pr.get("merged_at")
            if not merged_at:
                continue
            merged_dt = parse_iso8601(merged_at)
            if merged_dt < cutoff:
                continue
            yield pr


def build_author_wallet_index(
    repos: Iterable[str],
    *,
    lookback_days: int,
    max_pages_per_repo: int,
) -> dict[str, WalletEvidence]:
    index: dict[str, WalletEvidence] = {}

    for repo in repos:
        log(f"[scan] recent merged PRs in {repo}")
        for pr in fetch_recent_merged_prs(
            repo,
            lookback_days=lookback_days,
            max_pages=max_pages_per_repo,
        ):
            author = ((pr.get("user") or {}).get("login") or "").strip()
            if not author:
                continue

            wallet, reason = resolve_wallet_from_pr_body_details(pr.get("body") or "")
            if not wallet:
                if reason == "ambiguous_pr_wallets":
                    log(f"[scan] skipped ambiguous wallet declaration in {repo}#{pr['number']} by {author}")
                continue

            pr_ref = f"{repo}#{pr['number']}"
            index.setdefault(author, WalletEvidence()).add(wallet, pr_ref)

    return index


def fetch_all_balances(base_url: str, admin_key: str) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/wallet/balances/all"
    data = json_request(url, headers={"X-Admin-Key": admin_key})
    return list(data.get("balances") or [])


def looks_like_github_username(value: str) -> bool:
    return bool(GITHUB_USERNAME_RE.fullmatch((value or "").strip()))


def collect_phantom_balances(rows: Iterable[dict[str, Any]]) -> list[PhantomBalance]:
    phantom: list[PhantomBalance] = []
    for row in rows:
        miner_id = str(row.get("miner_id") or "").strip()
        if not miner_id or is_valid_wallet(miner_id):
            continue
        if not looks_like_github_username(miner_id):
            continue

        amount_i64 = int(row.get("amount_i64") or 0)
        if amount_i64 <= 0:
            continue

        phantom.append(
            PhantomBalance(
                miner_id=miner_id,
                amount_i64=amount_i64,
                amount_rtc=Decimal(amount_i64) / UNIT,
            )
        )
    return phantom


def transfer_balance(
    base_url: str,
    admin_key: str,
    source_miner: str,
    destination_wallet: str,
    amount_rtc: Decimal,
) -> dict[str, Any]:
    if not is_valid_wallet(destination_wallet):
        raise ValueError(f"invalid destination wallet: {destination_wallet!r}")

    url = f"{base_url.rstrip('/')}/wallet/transfer"
    payload = {
        "from_miner": source_miner,
        "to_miner": destination_wallet,
        "amount_rtc": float(amount_rtc),
        "memo": f"Phantom balance sweep for GitHub username {source_miner}",
    }
    return json_request(
        url,
        method="POST",
        headers={"X-Admin-Key": admin_key},
        payload=payload,
    )


def resolve_destination_wallet(
    username: str,
    wallet_index: dict[str, WalletEvidence],
) -> tuple[Optional[str], str]:
    evidence = wallet_index.get(username)
    if not evidence:
        return None, "no_recent_merged_pr_with_wallet"

    wallets = evidence.unique_wallets
    if len(wallets) != 1:
        joined = ", ".join(wallets) if wallets else "none"
        return None, f"multiple_candidate_wallets:{joined}"

    wallet = wallets[0]
    if not is_valid_wallet(wallet):
        return None, f"invalid_candidate_wallet:{wallet}"
    return wallet, ""


def print_evidence(wallet_index: dict[str, WalletEvidence], username: str) -> str:
    evidence = wallet_index.get(username)
    if not evidence:
        return "no PR evidence"
    chunks = []
    for wallet, refs in evidence.wallets.items():
        chunks.append(f"{wallet} via {', '.join(refs[:5])}")
    return "; ".join(chunks)


def run(args: argparse.Namespace) -> int:
    admin_key = os.environ.get("RC_ADMIN_KEY", "").strip()
    if not admin_key:
        log("RC_ADMIN_KEY is required.")
        return 1

    base_url = args.base_url.rstrip("/")
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        log(f"RC_BASE_URL / --base-url must be a full URL, got: {base_url}")
        return 1

    try:
        balances = fetch_all_balances(base_url, admin_key)
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        log(f"Failed to fetch /wallet/balances/all: {exc}")
        return 1

    phantom_balances = collect_phantom_balances(balances)
    log(f"[scan] found {len(phantom_balances)} phantom username balance(s)")

    wallet_index = build_author_wallet_index(
        args.repos,
        lookback_days=args.lookback_days,
        max_pages_per_repo=args.max_pages_per_repo,
    )

    resolved = 0
    unresolved: list[tuple[PhantomBalance, str]] = []
    transfer_failures: list[tuple[PhantomBalance, str]] = []

    for phantom in phantom_balances:
        wallet, reason = resolve_destination_wallet(phantom.miner_id, wallet_index)
        if not wallet:
            unresolved.append((phantom, reason))
            continue

        log(
            f"[match] {phantom.miner_id}: {phantom.amount_rtc} RTC -> {wallet} "
            f"({print_evidence(wallet_index, phantom.miner_id)})"
        )

        if not args.commit:
            continue

        try:
            result = transfer_balance(
                base_url,
                admin_key,
                phantom.miner_id,
                wallet,
                phantom.amount_rtc,
            )
        except (HTTPError, URLError, json.JSONDecodeError, ValueError) as exc:
            transfer_failures.append((phantom, str(exc)))
            continue

        if not result.get("ok"):
            transfer_failures.append((phantom, str(result)))
            continue

        resolved += 1
        log(
            f"[moved] {phantom.miner_id}: tx_hash={result.get('tx_hash')} "
            f"pending_id={result.get('pending_id')}"
        )

    log("")
    log("Summary")
    log(f"  phantom balances scanned: {len(phantom_balances)}")
    log(f"  auto-resolved candidates: {sum(1 for p in phantom_balances if resolve_destination_wallet(p.miner_id, wallet_index)[0])}")
    log(f"  transfers executed: {resolved if args.commit else 0}")
    log(f"  unresolved/manual: {len(unresolved)}")
    log(f"  transfer failures: {len(transfer_failures)}")

    if not args.commit:
        log("  mode: dry-run (add --commit to execute transfers)")

    if unresolved:
        log("")
        log("Manual follow-up required")
        for phantom, reason in unresolved:
            log(
                f"  - {phantom.miner_id}: {phantom.amount_rtc} RTC "
                f"({reason}; evidence: {print_evidence(wallet_index, phantom.miner_id)})"
            )

    if transfer_failures:
        log("")
        log("Transfer failures")
        for phantom, reason in transfer_failures:
            log(f"  - {phantom.miner_id}: {phantom.amount_rtc} RTC ({reason})")

    return 0 if not transfer_failures else 1


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="Execute admin transfers instead of dry-run logging.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"RustChain node base URL (default: {DEFAULT_BASE_URL}).")
    parser.add_argument(
        "--repos",
        nargs="+",
        default=DEFAULT_REPOS,
        help="GitHub repositories to scan for recent merged PR wallets.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"How far back to scan merged PRs (default: {DEFAULT_LOOKBACK_DAYS}).",
    )
    parser.add_argument(
        "--max-pages-per-repo",
        type=int,
        default=int(os.environ.get("RC_MAX_PAGES_PER_REPO", "5")),
        help="Maximum GitHub pull-request pages (100 PRs each) to scan per repo.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
