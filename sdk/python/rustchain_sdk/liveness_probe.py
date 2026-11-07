"""Shared liveness probe for RustChain node monitors (Bounty #17180).
Validates that /health returns a genuine RustChain JSON payload rather than
an arbitrary HTTP 200 HTML page or captive portal.
"""
from typing import Any, Dict, Tuple

REQUIRED_HEALTH_KEYS = ("ok", "status", "version")

def verify_health_payload(status_code: int, content_type: str, body: Any) -> Tuple[bool, str]:
    if status_code != 200:
        return False, f"unexpected HTTP status {status_code}"
    if "html" in (content_type or "").lower():
        return False, "rejected HTML response masquerading as 200 OK"
    if not isinstance(body, dict):
        return False, "payload is not a JSON object"
    has_marker = any(k in body for k in REQUIRED_HEALTH_KEYS) or "epoch" in body or "node" in body
    if not has_marker:
        return False, "missing canonical RustChain health fields"
    if body.get("ok") is False or str(body.get("status", "")).lower() in ("down", "error"):
        return False, "node explicitly reported unhealthy status"
    return True, "verified rustchain node health"