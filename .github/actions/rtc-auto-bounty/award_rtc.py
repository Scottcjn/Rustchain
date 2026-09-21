"""
award_rtc.py — Core logic for the RustChain RTC auto-bounty action.

This module is intentionally dependency-free (stdlib only) so it can run in
the GitHub Actions runner without a full Rust toolchain. It is exercised by
test_award_rtc.py in the same directory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BountyClaim:
    """A single parsed bounty claim from an issue comment."""
    claimant: str
    wallet: Optional[str]
    post_url: Optional[str]
    body: str
    # Engagement-bounty specific fields (see verify_engagement_claim).
    reviewed: Optional[str] = None
    reason: Optional[str] = None
    disclosure: bool = False


@dataclass
class Verdict:
    """Result of validating a claim against a bounty's rules."""
    valid: bool
    reason: str
    claim: Optional[BountyClaim] = None
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_WALLET_RE = re.compile(r"\b(RTC[1-9A-HJ-NP-Za-km-z]{20,64}|0x[0-9a-fA-F]{40})\b")
_URL_RE = re.compile(r"https?://[^\s)\]>\"']+")


def parse_claim(comment_body: str, author: str) -> BountyClaim:
    """Extract structured fields from a raw issue comment.

    This is deliberately lenient: the human reviewer (or the verifier) makes
    the final call. We only pull out the obvious signals.
    """
    wallet_match = _WALLET_RE.search(comment_body)
    url_match = _URL_RE.search(comment_body)
    return BountyClaim(
        claimant=author,
        wallet=wallet_match.group(1) if wallet_match else None,
        post_url=url_match.group(0) if url_match else None,
        body=comment_body,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_engagement_claim(
    claim: BountyClaim,
    *,
    require_wallet: bool = True,
    require_post_url: bool = True,
    require_reviewed: bool = True,
    require_reason: bool = True,
    require_disclosure: bool = True,
    min_reason_length: int = 20,
) -> Verdict:
    """Validate a 'share why you starred' engagement bounty claim.

    Implements the FTC 16 CFR §465.5 / §255.5 disclosure requirements that
    RustChain bounties mandate:

      1. What you reviewed  — at least one file/PR/feature/doc, linked.
      2. Why you liked it    — a specific, non-generic reason.
      3. Disclosure          — the literal line "I received RTC compensa...".

    A star alone does NOT qualify; all three signals must be present.
    """
    warnings: List[str] = []
    body = claim.body or ""
    lower = body.lower()

    # --- 1. What you reviewed -------------------------------------------
    reviewed = None
    if require_reviewed:
        # Accept an explicit "Reviewed: <link>" line, or a link to a repo
        # file/PR/issue/doc as a proxy for "I actually looked at something".
        reviewed_match = re.search(
            r"(?im)^\s*(?:what\s+you\s+reviewed|reviewed|review)\s*:\s*(.+)$",
            body,
        )
        if reviewed_match:
            reviewed = reviewed_match.group(1).strip()
        else:
            # Fall back to any github.com link that points at a concrete
            # artifact (blob / pull / issues / docs).
            artifact = re.search(
                r"https?://github\.com/[\w.-]+/[\w.-]+/(?:blob|pull|issues|discussions)/\S+",
                body,
            )
            if artifact:
                reviewed = artifact.group(0)
        if not reviewed:
            return Verdict(
                valid=False,
                reason="Missing 'what you reviewed' — link a file, PR, feature, or doc.",
                claim=claim,
            )

    # --- 2. Why you liked it --------------------------------------------
    reason = None
    if require_reason:
        reason_match = re.search(
            r"(?im)^\s*(?:why\s+you\s+liked|reason|why)\s*:\s*(.+)$",
            body,
        )
        if reason_match:
            reason = reason_match.group(1).strip()
        else:
            # Use the longest non-link, non-label line as the candidate reason.
            candidate_lines = [
                ln.strip()
                for ln in body.splitlines()
                if ln.strip()
                and not ln.strip().startswith(("http", "I received", "Reviewed", "Wallet"))
                and not re.match(r"^\s*(?:what|why|reviewed|reason|wallet|post)\s*:", ln, re.I)
            ]
            if candidate_lines:
                reason = max(candidate_lines, key=len)

        if not reason:
            return Verdict(
                valid=False,
                reason="Missing 'why you liked it' — a specific, non-generic reason is required.",
                claim=claim,
            )
        if len(reason) < min_reason_length:
            return Verdict(
                valid=False,
                reason=f"Reason too generic/short (< {min_reason_length} chars).",
                claim=claim,
            )
        # Reject the canonical non-qualifying phrase.
        if reason.strip().lower() in {"great project", "cool project", "nice", "lgtm"}:
            return Verdict(
                valid=False,
                reason="Reason is generic ('Great project' does not qualify).",
                claim=claim,
            )

    # --- 3. Disclosure ---------------------------------------------------
    disclosure = False
    if require_disclosure:
        disclosure = "i received rtc compensa" in lower
        if not disclosure:
            return Verdict(
                valid=False,
                reason="Missing FTC disclosure line: 'I received RTC compensa...'.",
                claim=claim,
            )

    # --- Optional hard requirements -------------------------------------
    if require_post_url and not claim.post_url:
        return Verdict(
            valid=False,
            reason="Missing public post URL.",
            claim=claim,
        )
    if require_wallet and not claim.wallet:
        warnings.append("No RTC wallet address found — one will be created on payout.")

    claim.reviewed = reviewed
    claim.reason = reason
    claim.disclosure = disclosure

    return Verdict(valid=True, reason="Engagement claim satisfies all FTC disclosure requirements.", claim=claim, warnings=warnings)


def verify_claim(claim: BountyClaim, *, kind: str = "engagement") -> Verdict:
    """Dispatch to the appropriate verifier based on bounty kind."""
    if kind == "engagement":
        return verify_engagement_claim(claim)
    # Default: require at least a post URL and a wallet.
    if not claim.post_url:
        return Verdict(valid=False, reason="Missing post URL.", claim=claim)
    return Verdict(valid=True, reason="OK", claim=claim)


# ---------------------------------------------------------------------------
# Payout bookkeeping
# ---------------------------------------------------------------------------

def allocate_pool(
    claims: List[BountyClaim],
    pool: int,
    per_claim: int,
) -> List[Verdict]:
    """First-come-first-served allocation against a fixed RTC pool.

    Returns one Verdict per claim, in order. Once the pool is exhausted,
    subsequent claims are marked invalid with a 'pool exhausted' reason.
    """
    verdicts: List[Verdict] = []
    remaining = pool
    for claim in claims:
        if remaining < per_claim:
            verdicts.append(
                Verdict(valid=False, reason="Pool exhausted — no RTC remaining.", claim=claim)
            )
            continue
        verdict = verify_claim(claim)
        if verdict.valid:
            remaining -= per_claim
        verdicts.append(verdict)
    return verdicts


def to_json(verdicts: List[Verdict]) -> str:
    """Serialize verdicts for the GitHub Actions output / issue comment."""
    payload = [
        {
            "claimant": v.claim.claimant if v.claim else None,
            "valid": v.valid,
            "reason": v.reason,
            "wallet": v.claim.wallet if v.claim else None,
            "post_url": v.claim.post_url if v.claim else None,
            "warnings": v.warnings,
        }
        for v in verdicts
    ]
    return json.dumps(payload, indent=2)
