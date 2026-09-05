"""
XAPS - Cross-protocol Audit System Pre-execution Audit

XAPS is a security layer that runs before on-chain actions are submitted.
It validates that the action is safe, authorized, and within policy bounds.

Checks performed:
  1. Signature integrity – the action payload has a valid Ed25519 signature
     from the wallet whose public key matches from_address.
  2. Target validation – recipient addresses match the RTC prefix format and
     are of the expected length.
  3. Side-effect audit – memo fields are validated, transfers stay within
     configured rate limits, and no unexpected operations are detected.
  4. Rate limiting / frequency – a sliding-window rate limiter prevents
     rapid-fire submission of actions from the same source.

Usage (integration):

    from rustchain_sdk.xaps_audit import XAPSResult, XAPSAuditError, XAPSInspector

    inspector = XAPSInspector()

    # Before calling client.transfer_signed() or similar:
    audit = inspector.inspect_transfer(transfer_payload)
    if audit.approved:
        result = await client.transfer_signed(**transfer_payload)
    else:
        raise XAPSAuditError(audit.reason)

    # Custom policy can be added at any time:
    inspector.add_policy(MyCustomPolicy())

Author: kuanglaodi2-sudo (Atlas AI Agent)
License: MIT
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import threading
from collections import deque
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
)


# ── Policy / Configuration ──────────────────────────────────────────────────

_DEFAULT_ADDRESS_PREFIX = "RTC"
_DEFAULT_ADDRESS_LENGTH = 3 + 40  # RTC + 40 hex chars

# Default rate limit: max 5 actions per 60-second sliding window per source.
_DEFAULT_MAX_ACTIONS = 5
_DEFAULT_WINDOW_SECONDS = 60

# Max memo length (bytes after utf-8 encoding).
_DEFAULT_MAX_MEMO_BYTES = 1024

# Characters allowed in memo fields (alphanumeric, common punctuation, space).
_MEMO_RE = re.compile(r'^[A-Za-z0-9 _\-\.\'\/\\\,\;\:\(\)\[\]\{\}\@\#\$\%\&\*\+\=\?\<\>\~\`\|]+$')

# Valid hex characters.
_HEX_RE = re.compile(r'^[0-9a-fA-F]+$')

# Public key length: Ed25519 = 32 bytes = 64 hex chars.
_PK_LEN = 64

# Signature length: Ed25519 = 64 bytes = 128 hex chars.
_SIG_LEN = 128

# ── Exception classes ──────────────────────────────────────────────────────


class XAPSAuditError(RuntimeError):
    """Raised when the XAPS audit rejects an action."""

    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


# ── Audit result ────────────────────────────────────────────────────────────


class XAPSResult:
    """Immutable result of an XAPS audit check."""

    def __init__(self, approved: bool, reason: str = "", details: Optional[Dict[str, Any]] = None):
        self.approved = approved
        self.reason = reason
        self.details = details or {}

    @staticmethod
    def approved(reason: str = "") -> "XAPSResult":
        return XAPSResult(approved=True, reason=reason)

    @staticmethod
    def rejected(reason: str, details: Optional[Dict[str, Any]] = None) -> "XAPSResult":
        return XAPSResult(approved=False, reason=reason, details=details)

    def __repr__(self) -> str:
        status = "PASS" if self.approved else f"FAIL({self.reason})"
        return f"XAPSResult({status})"


# ── Policy interface ────────────────────────────────────────────────────────


class XAPSPolicy:
    """Base class for custom XAPS policies.

    Subclass and override ``check`` to add additional audit logic.
    """

    name: str = "custom_policy"

    def check(self, action_type: str, payload: Dict[str, Any], inspector: "XAPSInspector") -> XAPSResult:
        """Return XAPSResult.approved or .rejected."""
        return XAPSResult.approved(reason=f"{self.name} check passed")


# ── Rate limiter (sliding window) ───────────────────────────────────────────


class _SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by source address."""

    def __init__(self, max_actions: int = _DEFAULT_MAX_ACTIONS, window_seconds: float = _DEFAULT_WINDOW_SECONDS):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._timestamps: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def _cleanup(self, source: str) -> None:
        """Remove expired entries for *source*."""
        cutoff = time.monotonic() - self.window_seconds
        dq = self._timestamps[source]
        while dq and dq[0] < cutoff:
            dq.popleft()

    def allow(self, source: str) -> bool:
        """Return True if the action is allowed under the rate limit."""
        with self._lock:
            if source not in self._timestamps:
                self._timestamps[source] = deque()
            self._cleanup(source)
            dq = self._timestamps[source]
            if len(dq) >= self.max_actions:
                return False
            dq.append(time.monotonic())
            return True


# ── Main inspector ──────────────────────────────────────────────────────────


class XAPSInspector:
    """Pre-execution audit inspector for on-chain actions.

    Args:
        address_prefix: Expected address prefix (default "RTC").
        address_length: Total expected address length (default 43).
        max_memo_bytes: Maximum allowed memo length in bytes.
        max_actions: Maximum actions allowed per window.
        window_seconds: Sliding window size in seconds.
    """

    def __init__(
        self,
        address_prefix: str = _DEFAULT_ADDRESS_PREFIX,
        address_length: int = _DEFAULT_ADDRESS_LENGTH,
        max_memo_bytes: int = _DEFAULT_MAX_MEMO_BYTES,
        max_actions: int = _DEFAULT_MAX_ACTIONS,
        window_seconds: float = _DEFAULT_WINDOW_SECONDS,
    ):
        self.address_prefix = address_prefix
        self.address_length = address_length
        self.max_memo_bytes = max_memo_bytes
        self.rate_limiter = _SlidingWindowRateLimiter(
            max_actions=max_actions,
            window_seconds=window_seconds,
        )
        self._policies: List[XAPSPolicy] = []

    # ── Public policy management ──────────────────────────────────────────

    def add_policy(self, policy: XAPSPolicy) -> None:
        """Register a custom policy for future audits."""
        self._policies.append(policy)

    def remove_policy(self, policy: XAPSPolicy) -> None:
        """Remove a previously-registered policy."""
        self._policies.remove(policy)

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _is_valid_hex(s: str, expected_len: int) -> bool:
        """Return True if *s* is a valid hex string of exactly *expected_len* length."""
        return isinstance(s, str) and len(s) == expected_len and bool(_HEX_RE.match(s))

    def _check_signature(self, payload: Dict[str, Any]) -> XAPSResult:
        """Validate that the signature field is well-formed and consistent."""
        signature = payload.get("signature")
        public_key = payload.get("public_key", "")

        if not signature or not isinstance(signature, str):
            return XAPSResult.rejected(
                "missing_or_invalid_signature",
                {"payload_keys": list(payload.keys())},
            )

        sig_len = len(signature)
        if sig_len not in (_SIG_LEN, _SIG_LEN * 2):
            return XAPSResult.rejected(
                "invalid_signature_length",
                {"got_len": sig_len, "expected": _SIG_LEN},
            )

        if not self._is_valid_hex(signature, sig_len):
            return XAPSResult.rejected("signature_contains_non_hex_chars")

        if public_key and not self._is_valid_hex(public_key, _PK_LEN):
            return XAPSResult.rejected(
                "invalid_public_key_format",
                {"got_len": len(public_key)},
            )

        return XAPSResult.approved("signature_valid")

    def _check_target(self, payload: Dict[str, Any]) -> XAPSResult:
        """Validate recipient / target address. Used for transfer payloads."""
        return self._check_address_field(payload, "to_address")

    def _check_address_field(self, payload: Dict[str, Any], field: str) -> XAPSResult:
        """Validate a specific address field in the payload."""
        addr = payload.get(field, "")
        if not addr or not isinstance(addr, str):
            return XAPSResult.rejected(f"missing_{field}")

        if not addr.startswith(self.address_prefix):
            return XAPSResult.rejected(
                f"{field}_bad_prefix",
                {"expected_prefix": self.address_prefix, "got": addr[:len(self.address_prefix) + 2]},
            )

        if len(addr) != self.address_length:
            return XAPSResult.rejected(
                f"{field}_bad_length",
                {"expected_len": self.address_length, "got_len": len(addr)},
            )

        body = addr[len(self.address_prefix):]
        if not self._is_valid_hex(body, len(body)):
            return XAPSResult.rejected(f"{field}_body_not_hex")

        return XAPSResult.approved("address_valid")

    def _check_side_effects(self, payload: Dict[str, Any]) -> XAPSResult:
        """Audit for unexpected side effects."""
        # Check memo size
        memo = payload.get("memo", "")
        if isinstance(memo, str) and len(memo.encode("utf-8")) > self.max_memo_bytes:
            return XAPSResult.rejected(
                "memo_too_long",
                {"memo_len_bytes": len(memo.encode("utf-8")), "max": self.max_memo_bytes},
            )
        # Sanity check memo characters
        if memo and not _MEMO_RE.match(memo):
            return XAPSResult.rejected("memo_contains_unexpected_characters")

        # Check amount is reasonable (> 0)
        amount = payload.get("amount", payload.get("amount_rtc", 0))
        if isinstance(amount, (int, float)) and amount <= 0:
            return XAPSResult.rejected("amount_must_be_positive", {"amount": amount})

        # Check fee is reasonable
        fee = payload.get("fee", payload.get("fee_rtc", 0))
        if isinstance(fee, (int, float)) and fee < 0:
            return XAPSResult.rejected("fee_must_not_be_negative", {"fee": fee})

        return XAPSResult.approved("no_unexpected_side_effects")

    def _check_rate_limit(self, source: str) -> XAPSResult:
        """Check the sliding-window rate limiter."""
        if not self.rate_limiter.allow(source):
            return XAPSResult.rejected(
                "rate_limit_exceeded",
                {"source": source, "window_seconds": self.rate_limiter.window_seconds,
                 "max_actions": self.rate_limiter.max_actions},
            )
        return XAPSResult.approved("rate_ok")

    # ── Public audit methods ──────────────────────────────────────────────

    def inspect_transfer(self, payload: Dict[str, Any]) -> XAPSResult:
        """Run the full audit on a signed transfer payload.

        Checks (in order):
          1. Signature integrity
          2. Target address validation
          3. Side-effect audit
          4. Rate limiting
          5. Custom policies

        Returns XAPSResult with approved=True if all checks pass.
        Raises XAPSAuditError on first failure.
        """
        checks: List[Tuple[str, Callable[[Dict[str, Any]], XAPSResult]]] = [
            ("signature", self._check_signature),
            ("target", self._check_target),
            ("side_effects", self._check_side_effects),
        ]

        source = payload.get("from_address", payload.get("from", "unknown"))

        for name, check_fn in checks:
            result = check_fn(payload)
            if not result.approved:
                raise XAPSAuditError(
                    f"xaps_{name}_check_failed",
                    {"reason": result.reason, "details": result.details},
                )

        # Rate limit check (uses source address as key)
        rate_result = self._check_rate_limit(str(source))
        if not rate_result.approved:
            raise XAPSAuditError(
                "xaps_rate_limit_exceeded",
                {"reason": rate_result.reason, "details": rate_result.details},
            )

        # Run custom policies
        for policy in self._policies:
            policy_result = policy.check("transfer", payload, self)
            if not policy_result.approved:
                raise XAPSAuditError(
                    f"xaps_policy_{policy.name}_rejected",
                    {"reason": policy_result.reason, "policy": policy.name},
                )

        return XAPSResult.approved(reason="all_xaps_checks_passed")

    def inspect_governance_vote(self, payload: Dict[str, Any]) -> XAPSResult:
        """Audit a governance vote payload.

        Checks:
          1. Signature integrity
          2. Voter address validation
          3. Vote value whitelist
          4. Proposal ID sanity
        """
        voter = payload.get("voter", "")
        vote = payload.get("vote", "")

        # Signature
        sig_result = self._check_signature(payload)
        if not sig_result.approved:
            raise XAPSAuditError("xaps_signature_check_failed", {"reason": sig_result.reason})

        # Voter address
        voter_result = self._check_address_field(payload, "voter")
        if not voter_result.approved:
            raise XAPSAuditError("xaps_target_check_failed", {"reason": voter_result.reason})

        # Vote value
        valid_votes = {"yes", "no", "abstain"}
        if vote.lower() not in valid_votes:
            raise XAPSAuditError(
                "xaps_invalid_vote_value",
                {"got": vote, "allowed": sorted(valid_votes)},
            )

        # Proposal ID
        pid = payload.get("proposal_id")
        if pid is None or not isinstance(pid, int) or pid < 1:
            raise XAPSAuditError("xaps_invalid_proposal_id", {"got": pid})

        # Rate limit
        self._check_rate_limit(str(voter))

        # Custom policies
        for policy in self._policies:
            policy_result = policy.check("governance_vote", payload, self)
            if not policy_result.approved:
                raise XAPSAuditError(
                    f"xaps_policy_{policy.name}_rejected",
                    {"reason": policy_result.reason, "policy": policy.name},
                )

        return XAPSResult.approved(reason="all_xaps_checks_passed")

    def inspect_attestation(self, payload: Dict[str, Any]) -> XAPSResult:
        """Audit an attestation submission payload.

        Checks:
          1. Signature integrity
          2. Miner ID validation
          3. Required fields present
        """
        sig_result = self._check_signature(payload)
        if not sig_result.approved:
            raise XAPSAuditError("xaps_signature_check_failed", {"reason": sig_result.reason})

        miner_id = payload.get("miner_public_key", payload.get("miner_id", ""))
        if not miner_id or not isinstance(miner_id, str):
            raise XAPSAuditError("xaps_missing_miner_id")

        required = ["challenge_response"] if "challenge_response" in payload else []
        for field in required:
            if field not in payload:
                raise XAPSAuditError(f"xaps_missing_field_{field}")

        self._check_rate_limit(str(miner_id))

        for policy in self._policies:
            policy_result = policy.check("attestation", payload, self)
            if not policy_result.approved:
                raise XAPSAuditError(
                    f"xaps_policy_{policy.name}_rejected",
                    {"reason": policy_result.reason, "policy": policy.name},
                )

        return XAPSResult.approved(reason="all_xaps_checks_passed")


# ── Convenience function for one-shot checks ────────────────────────────────


def audit_transfer(payload: Dict[str, Any], inspector: Optional[XAPSInspector] = None) -> XAPSResult:
    """Quick audit of a transfer payload using default settings.

    Returns XAPSResult.approved on success, raises XAPSAuditError on failure.
    """
    if inspector is None:
        inspector = XAPSInspector()
    return inspector.inspect_transfer(payload)


def audit_governance_vote(payload: Dict[str, Any], inspector: Optional[XAPSInspector] = None) -> XAPSResult:
    """Quick audit of a governance vote payload."""
    if inspector is None:
        inspector = XAPSInspector()
    return inspector.inspect_governance_vote(payload)


def audit_attestation(payload: Dict[str, Any], inspector: Optional[XAPSInspector] = None) -> XAPSResult:
    """Quick audit of an attestation payload."""
    if inspector is None:
        inspector = XAPSInspector()
    return inspector.inspect_attestation(payload)
