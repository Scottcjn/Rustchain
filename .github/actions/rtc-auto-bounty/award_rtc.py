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

import hashlib
import json
import math
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

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
#   payout wallet: RTCxxxx...
#   payout address if accepted: RTCxxxx...
#   RTC wallet: RTCxxxx...
#   .rtc-wallet: RTCxxxx...
_WALLET_RE = re.compile(
    r"""(?:^|\n)\s*
        (?:
            wallet
            | \.rtc-wallet
            | payout\s+wallet
            | payout\s+address(?:\s+if\s+accepted)?
            | rtc\s+wallet
        )
        \s*:\s*(\S+)\s*(?:\n|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Lazy-pay directive: a GitHub username / miner ID instead of an RTC address.
#   miner ID: github:alice
#   miner ID for payout if accepted: lazy-pay-bob
#   miner_id: carol
_MINER_ID_RE = re.compile(
    r"""(?:^|\n)\s*
        miner[_\s]+id(?:\s+for\s+payout(?:\s+if\s+accepted)?)?
        \s*:\s*(\S+)\s*(?:\n|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Last-resort contextual scan: an RTC address on a line that mentions one of
# these labels. Distinct from the anchored validation regex (_RTC_ADDRESS_RE)
# below — this one is unanchored so it can locate an address mid-line.
_RTC_ADDRESS_SCAN_RE = re.compile(r"\bRTC[0-9a-fA-F]{40}\b")
_RTC_CONTEXT_LABELS = ("payout", "wallet", "address")

# Payment-amount override in the PR body (owner can specify a custom amount).
#   bounty: 100 RTC
#   bounty: 75.5 RTC
_BOUNTY_RE = re.compile(
    r"(?:^|\n)\s*bounty\s*:\s*([\d]+(?:\.[\d]+)?)\s*RTC\s*(?:\n|$)",
    re.IGNORECASE,
)

# Marker to prevent duplicate awards.
_AWARD_MARKER = "RTC-AutoBounty-Awarded"

# --- Recipient validation (security) ---------------------------------------
# A resolved recipient must be EITHER a canonical RTC address (RTC + 40 hex)
# OR a conservative wallet-name / GitHub-username grammar. Anything else
# (markdown junk, zero-width / non-ASCII confusables, multi-token garbage)
# is rejected so a malformed or spoofed directive cannot misroute funds.
_RTC_ADDRESS_RE = re.compile(r"^RTC[0-9A-Fa-f]{40}$")
_WALLET_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")

# Platform / treasury wallets must never be auto-selected as a *recipient*
# from PR-controlled text (prevents misrouting and self-dealing loops).
_BLOCKED_RECIPIENTS = frozenset({
    "founder_community",
    "founder_dev_fund",
    "founder_team_bounty",
    "founder_founders",
    "community",
    "dev_wallet",
    "foundation",
    "treasury",
})

_ENDPOINT_UNREACHABLE_PATTERNS = (
    "connection failed:",
    "connection refused",
    "connection reset",
    "connection aborted",
    "timed out",
    "timeout",
    "temporary failure in name resolution",
    "name or service not known",
    "no route to host",
    "network is unreachable",
    "host is unreachable",
)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_stripped(name: str, default: str = "") -> str:
    return _env(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    return _env_stripped(name, str(default)).lower() in ("true", "1", "yes")


def _env_float(name: str, default: float = 0.0) -> float:
    raw_value = _env_stripped(name, "")
    if raw_value == "":
        return default
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return math.nan


def _is_finite_amount(value: float) -> bool:
    return math.isfinite(value)


class Config:
    """Immutable configuration gathered from environment variables."""

    def __init__(self) -> None:
        self.rtc_amount: float = _env_float("INPUT_RTC_AMOUNT", 50.0)
        self.rtc_api_url: str = _env_stripped("INPUT_RTC_API_URL")
        self.vps_host: str = _env_stripped("INPUT_RTC_VPS_HOST")
        self.admin_key: str = _env_stripped("INPUT_RTC_ADMIN_KEY")
        self.from_wallet: str = _env_stripped("INPUT_FROM_WALLET", "founder_community")
        self.dry_run: bool = _env_bool("INPUT_DRY_RUN")
        self.post_comment: bool = _env_bool("INPUT_POST_COMMENT", True)
        self.github_token: str = _env_stripped(
            "INPUT_GITHUB_TOKEN",
            _env_stripped("GITHUB_TOKEN"),
        )
        self.repo_path: str = _env_stripped("INPUT_REPO_PATH", ".")
        self.max_amount: float = _env_float("INPUT_MAX_AMOUNT", 10000.0)
        self.repo: str = _env_stripped("GITHUB_REPOSITORY")
        self.pr_number: str = _env_stripped("PR_NUMBER")
        self.pr_author: str = _env_stripped("PR_AUTHOR", _env_stripped("PR_AUTHOR"))
        self.pr_merged: str = _env_stripped("PR_MERGED")
        self.pr_body: str = _env("PR_BODY", "")
        self.pr_head_sha: str = _env_stripped("PR_HEAD_SHA", "")
        self.pr_title: str = _env_stripped("PR_TITLE", "")

    def validate(self) -> Optional[str]:
        """Return an error string if required config is missing, else None."""
        if not self.github_token:
            return "GITHUB_TOKEN is not set"
        if not self.repo:
            return "GITHUB_REPOSITORY is not set"
        if not self.pr_number:
            return "PR_NUMBER is not set"
        if not self.dry_run and not (self.rtc_api_url or self.vps_host):
            return "INPUT_RTC_API_URL or INPUT_RTC_VPS_HOST is required (unless dry-run is enabled)"
        if not self.dry_run and not self.admin_key:
            return "INPUT_RTC_ADMIN_KEY is required (unless dry-run is enabled)"
        if not _is_finite_amount(self.rtc_amount):
            return f"rtc-amount must be finite, got {self.rtc_amount}"
        if not _is_finite_amount(self.max_amount):
            return f"max-amount must be finite, got {self.max_amount}"
        if self.rtc_amount <= 0:
            return f"rtc-amount must be positive, got {self.rtc_amount}"
        if self.max_amount <= 0:
            return f"max-amount must be positive, got {self.max_amount}"
        return None


# ---------------------------------------------------------------------------
# Wallet resolution
# ---------------------------------------------------------------------------


def _clean_wallet_candidate(value: str) -> str:
    """Strip surrounding whitespace, trailing sentence punctuation, and markdown
    backticks from a captured directive value."""
    return value.strip().rstrip(",.;").strip("`")


def resolve_wallet_from_pr_body(pr_body: str) -> Optional[str]:
    """Extract a recipient (RTC wallet or lazy-pay miner ID) from a PR body.

    Resolution stages, in precedence order:
      1. An explicit ``wallet:`` / ``payout wallet:`` / ``payout address:`` /
         ``rtc wallet:`` / ``.rtc-wallet:`` directive.
      2. A lazy-pay ``miner ID:`` directive (GitHub username / miner ID).
      3. A last-resort contextual scan: an RTC address on a line that mentions
         a payout/wallet/address label.

    Every candidate returned here is still gated by ``validate_recipient``
    before any transfer, so a malformed match cannot misroute funds.
    """
    match = _WALLET_RE.search(pr_body)
    if match:
        return _clean_wallet_candidate(match.group(1))

    match = _MINER_ID_RE.search(pr_body)
    if match:
        return _clean_wallet_candidate(match.group(1))

    for line in pr_body.splitlines():
        lowered = line.lower()
        if not any(label in lowered for label in _RTC_CONTEXT_LABELS):
            continue
        rtc_match = _RTC_ADDRESS_SCAN_RE.search(line)
        if rtc_match:
            return rtc_match.group(0)
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
    Resolve the explicitly declared recipient wallet.

    Priority:
      1. ``wallet:`` directive in the PR body
      2. ``.rtc-wallet`` file at the repository root
    """
    wallet = resolve_wallet_from_pr_body(pr_body)
    if wallet:
        return wallet
    wallet = resolve_wallet_from_file(repo_path)
    if wallet:
        return wallet
    return None


def distinct_wallet_directives(pr_body: str) -> list:
    """Return the distinct recipient candidates found across *all* resolution
    stages that ``resolve_wallet_from_pr_body`` considers — explicit ``wallet:``
    directives, lazy-pay ``miner ID:`` directives, and the contextual RTC scan.

    Used to fail closed when a body declares multiple *conflicting* recipients
    (an attacker appending a second directive should not silently win or lose —
    it requires manual review). The conflict guard must cover every stage the
    resolver can return from, otherwise a second directive of a different *type*
    (e.g. a ``miner ID:`` added under a ``wallet:``) would slip past it.

    Candidates are de-duplicated by value, so a single directive that two stages
    both see (e.g. ``payout wallet: RTC…`` matched by both the wallet regex and
    the contextual scan) does not register as a false conflict.
    """
    body = pr_body or ""
    seen: list = []

    def _add(value: str) -> None:
        if value and value not in seen:
            seen.append(value)

    for raw in _WALLET_RE.findall(body):
        _add(_clean_wallet_candidate(raw))
    for raw in _MINER_ID_RE.findall(body):
        _add(_clean_wallet_candidate(raw))

    # The contextual RTC scan is a last-resort fallback in resolution; mirror
    # that precedence here so an incidental RTC address mentioned in prose
    # (on a line that happens to contain "wallet"/"address"/"payout") does not
    # trigger a spurious conflict when an explicit directive already exists.
    if not seen:
        for line in body.splitlines():
            if any(label in line.lower() for label in _RTC_CONTEXT_LABELS):
                rtc_match = _RTC_ADDRESS_SCAN_RE.search(line)
                if rtc_match:
                    _add(rtc_match.group(0))
    return seen


def validate_recipient(wallet: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate a resolved recipient before it is used in a transfer.

    Returns ``(ok, reason)``. ``reason`` is a short machine-readable skip code
    when ``ok`` is False. A recipient is accepted only when it is a canonical
    RTC address or a conservative wallet-name/username, and is not a
    platform/treasury wallet.
    """
    if not wallet:
        return False, "recipient_wallet_missing"
    candidate = wallet.strip()
    if candidate != wallet:
        # Trailing/leading whitespace already stripped by the parser; a
        # mismatch here means embedded control/space chars — reject.
        return False, "recipient_wallet_whitespace"
    try:
        candidate.encode("ascii")
    except UnicodeEncodeError:
        return False, "recipient_wallet_non_ascii"
    if _RTC_ADDRESS_RE.match(candidate):
        return True, None
    if _WALLET_NAME_RE.match(candidate):
        if candidate.lower() in _BLOCKED_RECIPIENTS or candidate.lower().startswith("founder_"):
            return False, "recipient_platform_wallet_blocked"
        return True, None
    return False, "recipient_wallet_invalid_format"


def compute_idempotency_key(repo: str, pr_number: str, wallet: str, amount: float) -> str:
    """Deterministic idempotency key so workflow re-runs collapse to one payout.

    The node's /wallet/transfer endpoint returns the existing pending row for a
    repeated key instead of inserting a new one, making retries safe.
    """
    basis = f"{repo}:{pr_number}:{wallet}:{amount}"
    return "award-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()


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

        if (
            "(dry-run)" in marker_tail
            or ":failed" in marker_tail
        ):
            continue
        return True
    return False


def is_endpoint_unreachable_error(error_msg: str) -> bool:
    """Return True when transfer failed because the RustChain endpoint was unreachable."""
    normalized = (error_msg or "").lower()
    return any(pattern in normalized for pattern in _ENDPOINT_UNREACHABLE_PATTERNS)


# ---------------------------------------------------------------------------
# RustChain transfer API
# ---------------------------------------------------------------------------


def transfer_rtc(
    transfer_url: str,
    admin_key: str,
    from_wallet: str,
    to_wallet: str,
    amount: float,
    memo: str,
    idempotency_key: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Call the RustChain ``POST /wallet/transfer`` admin endpoint.

    Returns ``(success, response_body_dict)``.
    """
    transfer_url = build_transfer_url(transfer_url)
    admin_key = admin_key.strip()
    from_wallet = from_wallet.strip()
    to_wallet = to_wallet.strip()

    payload = {
        "from_miner": from_wallet,
        "to_miner": to_wallet,
        "amount_rtc": amount,
        "memo": memo,
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    req = Request(
        transfer_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": admin_key,
        },
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=30)
        body = resp.read().decode(errors="replace")
        try:
            result = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return False, {"error": "Invalid JSON response from transfer endpoint"}
        if not isinstance(result, dict):
            return False, {"error": "Transfer endpoint response must be a JSON object"}
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


def build_transfer_url(value: str) -> str:
    """
    Build the wallet transfer URL.

    Full URLs are used as-is, except a bare origin gets ``/wallet/transfer``
    appended. Bare hosts keep the legacy ``http://host:8099`` behavior.
    """
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        if parsed.path and parsed.path != "/":
            return value
        return f"{value}/wallet/transfer"
    return f"http://{value}:{VPS_PORT}/wallet/transfer"


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
        skip_reason = "recipient_wallet_missing"
        log_error("No recipient wallet found in PR body or .rtc-wallet file; "
                  "skipping automatic RTC transfer.")
        if cfg.post_comment:
            missing_wallet_body = (
                f"**RTC Auto-Bounty Skipped**\n\n"
                f"No recipient wallet was found, so no RTC transfer was attempted.\n\n"
                f"To receive this award, add a line such as "
                f"`wallet: RTC...` to the PR body or add a `.rtc-wallet` file "
                f"at the repository root, then rerun the award workflow.\n\n"
                f"<!-- {_AWARD_MARKER}:FAILED recipient_wallet_missing -->"
            )
            post_pr_comment(repo, pr_number, missing_wallet_body, cfg.github_token)
        set_output("awarded", "false")
        set_output("skip_reason", skip_reason)
        return 1

    # --- Fail closed on conflicting recipient directives -------------------
    directives = distinct_wallet_directives(cfg.pr_body)
    if len(directives) > 1:
        skip_reason = "recipient_wallet_conflict"
        log_error(
            "Multiple conflicting `wallet:` directives in PR body "
            f"({directives}); refusing to auto-select a recipient."
        )
        if cfg.post_comment:
            conflict_body = (
                f"**RTC Auto-Bounty Skipped — manual review required**\n\n"
                f"This PR body declares more than one recipient wallet "
                f"({', '.join(f'`{d}`' for d in directives)}). To avoid "
                f"misrouting funds, no automatic transfer was made. A "
                f"maintainer must confirm the correct recipient.\n\n"
                f"<!-- {_AWARD_MARKER}:FAILED recipient_wallet_conflict -->"
            )
            post_pr_comment(repo, pr_number, conflict_body, cfg.github_token)
        set_output("awarded", "false")
        set_output("skip_reason", skip_reason)
        return 1

    # --- Validate recipient format / blocklist ----------------------------
    recipient_ok, recipient_err = validate_recipient(wallet)
    if not recipient_ok:
        log_error(
            f"Resolved recipient `{wallet}` failed validation "
            f"({recipient_err}); refusing automatic RTC transfer."
        )
        if cfg.post_comment:
            invalid_body = (
                f"**RTC Auto-Bounty Skipped — invalid recipient**\n\n"
                f"The resolved recipient `{wallet}` did not pass safety "
                f"validation (`{recipient_err}`). A recipient must be a "
                f"canonical `RTC...` address or a simple wallet name, and "
                f"may not be a platform/treasury wallet. No transfer was "
                f"made; a maintainer can process this manually.\n\n"
                f"<!-- {_AWARD_MARKER}:FAILED {recipient_err} -->"
            )
            post_pr_comment(repo, pr_number, invalid_body, cfg.github_token)
        set_output("awarded", "false")
        set_output("skip_reason", recipient_err)
        return 1

    print(f"Recipient wallet: {wallet}")

    # --- Determine award amount --------------------------------------------
    amount = cfg.rtc_amount
    # Check for a bounty override in the PR body
    bounty_match = _BOUNTY_RE.search(cfg.pr_body)
    if bounty_match:
        override = float(bounty_match.group(1))
        if _is_finite_amount(override) and 0 < override <= cfg.max_amount:
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
                f"<!-- {_AWARD_MARKER} (dry-run) -->"
            )
            post_pr_comment(repo, pr_number, dry_body, cfg.github_token)
        return 0

    # --- Execute transfer --------------------------------------------------
    print(f"Initiating transfer: {amount} RTC from {cfg.from_wallet} to {wallet}")
    idempotency_key = compute_idempotency_key(repo, pr_number, wallet, amount)
    ok, result = transfer_rtc(
        cfg.rtc_api_url or cfg.vps_host,
        cfg.admin_key,
        cfg.from_wallet,
        wallet,
        amount,
        memo,
        idempotency_key=idempotency_key,
    )

    tx_hash = result.get("tx_hash", "")
    pending_id = result.get("pending_id", "")
    error_msg = result.get("error", "")

    if not ok:
        log_error(f"Transfer failed: {error_msg}")
        set_output("awarded", "false")
        set_output("skip_reason", f"transfer_failed: {error_msg}")

        if is_endpoint_unreachable_error(error_msg):
            if cfg.post_comment:
                manual_body = (
                    f"**RTC Auto-Bounty Manual Transfer Required**\n\n"
                    f"The merged PR qualifies for an RTC award, but the RustChain "
                    f"transfer endpoint was unreachable when the workflow ran:\n\n"
                    f"```\n{error_msg}\n```\n\n"
                    f"| Field | Value |\n"
                    f"|-------|-------|\n"
                    f"| Amount | **{amount} RTC** |\n"
                    f"| Recipient | `{wallet}` |\n"
                    f"| From | `{cfg.from_wallet}` |\n"
                    f"| Memo | {memo} |\n\n"
                    f"Please rerun the award after the endpoint is healthy or process "
                    f"this transfer manually. This marker intentionally blocks automatic "
                    f"retries to avoid duplicate payouts; remove it only if no manual "
                    f"transfer was completed.\n\n"
                    f"<!-- {_AWARD_MARKER}:MANUAL-REQUIRED -->"
                )
                if not post_pr_comment(repo, pr_number, manual_body, cfg.github_token):
                    log_error("Manual transfer notice could not be posted.")
                    set_output("skip_reason", f"manual_notice_failed: {error_msg}")
                    return 1
            return 0

        if cfg.post_comment:
            fail_body = (
                f"**RTC Auto-Bounty Failed** ❌\n\n"
                f"Attempted to award **{amount} RTC** to `{wallet}` "
                f"but the transfer was rejected:\n\n"
                f"```\n{error_msg}\n```\n\n"
                f"Please process this award manually.\n\n"
                f"<!-- {_AWARD_MARKER}:FAILED -->"
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

            <!-- {_AWARD_MARKER} tx_hash={tx_hash} pending_id={pending_id} -->
        """)
        posted = post_pr_comment(repo, pr_number, confirm_body, cfg.github_token)
        if not posted:
            log_warning("Failed to post confirmation comment, but transfer succeeded.")

    print(f"Award complete: {amount} RTC to {wallet} "
          f"(tx_hash={tx_hash}, pending_id={pending_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
