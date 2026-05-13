"""
auth.py — Webhook signature verification and maintainer authorization.
"""

import hashlib
import hmac
import os
import time
from typing import Optional


def verify_webhook_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """
    Verify GitHub webhook HMAC-SHA256 signature.

    GitHub sends: X-Hub-Signature-256: sha256=<hex>
    We recompute using WEBHOOK_SECRET and compare via constant-time equality.

    Returns True if valid, False if missing/invalid.
    """
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        # No secret configured — reject (production must set WEBHOOK_SECRET)
        return False

    if not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)


def is_authorized_sender(username: str, maintainers: list[str]) -> bool:
    """
    Check if the comment author is in the maintainer allowlist.
    Comparison is case-insensitive.
    """
    return username.lower() in {m.lower() for m in maintainers}


class RateLimiter:
    """
    In-memory rate limiter: tracks tip command timestamps per sender.
    Resets when the process restarts (GitHub Actions are ephemeral).
    For persistent rate limiting, use the state file.
    """

    def __init__(self, max_per_hour: int = 20) -> None:
        self.max_per_hour = max_per_hour
        self._timestamps: dict[str, list[float]] = {}

    def check(self, username: str) -> bool:
        """Return True if allowed, False if rate limit exceeded."""
        now = time.time()
        cutoff = now - 3600  # one hour window

        timestamps = self._timestamps.get(username, [])
        # Keep only events within the window
        timestamps = [t for t in timestamps if t > cutoff]
        self._timestamps[username] = timestamps

        if len(timestamps) >= self.max_per_hour:
            return False

        timestamps.append(now)
        self._timestamps[username] = timestamps
        return True

    def count(self, username: str) -> int:
        """Return current tip count for the user in the past hour."""
        now = time.time()
        cutoff = now - 3600
        return sum(1 for t in self._timestamps.get(username, []) if t > cutoff)
