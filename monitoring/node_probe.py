#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared RustChain node liveness probe — the ONLY place a monitor decides
what "up" means.

Every monitor used to decide health from the HTTP status code alone. When an
attestation node's IP was repurposed to serve an unrelated single-page app,
every path returned 200 with HTML and all five monitors kept reporting the
host healthy forever. A 200 is not evidence of a node: only a /health body
that actually carries RustChain node state is.

States:
    up           — genuine RustChain node reporting healthy
    degraded     — genuine node reporting ok=false, db_rw=false, or a stale tip
    impostor     — HTTP 200 but not a RustChain node (HTML SPA / parking page /
                   captive portal / JSON API without node keys)
    down         — HTTP response with a non-200 status
    unreachable  — timeout, refused connection, DNS or TLS failure

stdlib-only, Python 3.9+. Import from a monitor, or call classify_health_data()
when the monitor already has its own HTTP client.
"""
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

STATE_UP = "up"
STATE_DOWN = "down"
STATE_IMPOSTOR = "impostor"
STATE_DEGRADED = "degraded"
STATE_UNREACHABLE = "unreachable"

# /health keys only a RustChain node emits. A JSON body carrying none of them
# is some other service sharing the address, not a node.
IDENTITY_KEYS = ("ok", "version", "uptime_s")

# tip_age_slots counts slots (~30s each); a synced node stays under 2. 120 is
# roughly an hour of lag: tolerant of one normal resync, still same-day loud on
# a stalled tip.
TIP_AGE_SLOTS_LIMIT = 120


@dataclass
class ProbeResult:
    state: str
    status_code: Optional[int] = None
    response_ms: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


def classify_health_data(
    status_code: int,
    content_type: str,
    data: Any,
    identity_keys: Tuple[str, ...] = IDENTITY_KEYS,
) -> Tuple[str, Optional[str]]:
    """Decide the probe state from an HTTP answer's *body*, not just its code.

    status_code     — HTTP status that produced this response
    content_type    — Content-Type header value (may be empty)
    data            — JSON-parsed body, or None when parsing failed / non-200
    identity_keys   — keys proving the responder is the kind of endpoint asked
                      (defaults to the /health triple; /epoch probes pass epoch
                      keys instead)

    Returns (state, reason). reason is None only for "up".
    """
    if status_code != 200:
        return STATE_DOWN, f"HTTP {status_code}"
    if not isinstance(data, dict):
        return STATE_IMPOSTOR, "HTTP 200 but body is non-JSON or not a JSON object"
    if content_type and "text/html" in str(content_type).lower():
        return STATE_IMPOSTOR, "HTTP 200 with text/html body (SPA/parking page?)"
    if not any(key in data for key in identity_keys):
        return STATE_IMPOSTOR, (
            f"JSON body has no {'/'.join(identity_keys)} keys "
            "(not a RustChain node)"
        )
    if data.get("ok") is False:
        return STATE_DEGRADED, "node reports ok=false"
    if data.get("db_rw") is False:
        return STATE_DEGRADED, "node reports db_rw=false"
    tip = data.get("tip_age_slots")
    try:
        tip = int(tip) if tip is not None else None
    except (TypeError, ValueError):
        tip = None
    if tip is not None and tip > TIP_AGE_SLOTS_LIMIT:
        return STATE_DEGRADED, f"tip_age_slots={tip} exceeds {TIP_AGE_SLOTS_LIMIT}"
    return STATE_UP, None


def probe_health(
    url: str,
    timeout: float = 10,
    opener=None,
    identity_keys: Tuple[str, ...] = IDENTITY_KEYS,
) -> ProbeResult:
    """Fetch a node endpoint and classify the body. Never "up" on status alone.

    opener        — optional callable replacing urllib.request.urlopen;
                    single-file tools pass their module-level urlopen so
                    monkeypatch seams keep working.
    identity_keys — keys proving the responder is the endpoint asked about;
                    /epoch probes pass ("epoch", "current_epoch") instead of
                    the /health default.
    """
    do_open = opener or urllib.request.urlopen
    start = time.monotonic()
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "RustChain-NodeProbe/1.0",
            },
        )
        with do_open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            # Minimal fake responses in tests may not carry headers at all.
            headers = getattr(resp, "headers", None)
            content_type = ""
            if headers is not None:
                content_type = str(headers.get("Content-Type", "") or "")
        status_code = 200  # urlopen raises HTTPError for every non-2xx answer
    except urllib.error.HTTPError as exc:
        return ProbeResult(
            state=STATE_DOWN,
            status_code=exc.code,
            response_ms=round((time.monotonic() - start) * 1000, 1),
            reason=f"HTTP {exc.code}",
        )
    except (urllib.error.URLError, OSError) as exc:
        # URLError covers refused/DNS/TLS; socket.timeout subclasses OSError.
        return ProbeResult(
            state=STATE_UNREACHABLE,
            response_ms=round((time.monotonic() - start) * 1000, 1),
            reason=str(exc)[:200],
        )

    elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    state, reason = classify_health_data(status_code, content_type, data, identity_keys)
    return ProbeResult(
        state=state,
        status_code=status_code,
        response_ms=elapsed_ms,
        data=data if isinstance(data, dict) else None,
        reason=reason,
    )
