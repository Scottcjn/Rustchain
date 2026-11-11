# SPDX-License-Identifier: MIT
"""Shared RustChain node liveness probe — stdlib-only, Python 3.9+.

Every node monitor used to decide "up" from the HTTP status code alone. When
an attestation node's IP was repurposed to serve an unrelated single-page app,
the SPA answered **200 on every path** and all five monitors reported the host
healthy forever. A 200 is not evidence of a node: the /health BODY must be
validated too.

States returned by probe_health() / classify_response():

    up           HTTP 200, JSON body carrying node identity (ok/version/uptime_s),
                 ok not false, db_rw not false, tip_age_slots below threshold
    degraded     a real RustChain node that reports itself unhealthy
                 (ok: false, db_rw: false, or tip_age_slots above threshold)
    impostor     HTTP 200 but the responder is not a RustChain node:
                 Content-Type is text/html, body is not JSON, or JSON without
                 any of the ok/version/uptime_s identity keys
    down         HTTP response with a non-200 status code
    unreachable  connection failure: timeout, refused, DNS error

Monitors that already hold their own HTTP client (requests-based dashboards,
cert-pinned pollers) pass their response into classify_response(); monitors
without one call probe_health() directly. One validator, five monitors.
"""

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# A /health body is a few hundred bytes; cap the read so an SPA that streams
# an unbounded page cannot stall the probe.
MAX_BODY_BYTES = 65536

# Keys that only a RustChain node puts in its /health JSON. A service that
# merely speaks JSON on this address has none of them.
NODE_IDENTITY_KEYS: Tuple[str, ...] = ("ok", "version", "uptime_s")

# Slots since the chain tip above which an otherwise-ok node is "degraded".
# Comfortably above normal slot production jitter, low enough to catch a real
# stall within minutes rather than days.
TIP_AGE_SLOTS_THRESHOLD = 120

USER_AGENT = "RustChain-NodeProbe/1.0"

UP = "up"
DOWN = "down"
IMPOSTOR = "impostor"
DEGRADED = "degraded"
UNREACHABLE = "unreachable"

_MISSING = object()


@dataclass
class ProbeResult:
    """Outcome of one /health probe."""

    state: str                       # up | down | impostor | degraded | unreachable
    status_code: Optional[int] = None
    response_ms: float = 0.0
    error: Optional[str] = None      # why it is not "up" (None when up)
    data: Optional[Dict[str, Any]] = field(default=None, repr=False)

    @property
    def is_node(self) -> bool:
        """True when a real RustChain node answered (healthy or not)."""
        return self.state in (UP, DEGRADED)


def classify_response(
    status_code: int,
    content_type: str = "",
    body: Optional[str] = None,
    data: Any = _MISSING,
    identity_keys: Tuple[str, ...] = NODE_IDENTITY_KEYS,
    tip_age_slots_threshold: int = TIP_AGE_SLOTS_THRESHOLD,
) -> ProbeResult:
    """Classify one HTTP response into a probe state from its BODY.

    ``data`` may be a pre-parsed JSON payload (pass it when the caller already
    parsed the body); when omitted it is parsed from ``body``. Pass an
    identity_keys override such as ``("epoch",)`` for endpoints like /epoch
    that carry node state under different names.
    """
    if status_code != 200:
        return ProbeResult(state=DOWN, status_code=status_code,
                           error=f"HTTP {status_code}")

    ct = str(content_type or "").lower()
    if "text/html" in ct or "xhtml" in ct:
        return ProbeResult(
            state=IMPOSTOR, status_code=status_code,
            error=(f"200 but Content-Type is '{content_type}' "
                   f"(a web page, not a RustChain node)"),
        )

    if data is _MISSING:
        try:
            data = json.loads(body) if body is not None else None
        except (TypeError, ValueError):
            data = None

    if data is None:
        return ProbeResult(
            state=IMPOSTOR, status_code=status_code,
            error="200 but the body is not JSON (no RustChain node behind this host)",
        )
    if not isinstance(data, dict):
        return ProbeResult(
            state=IMPOSTOR, status_code=status_code,
            error="200 but the JSON body is not an object (not a RustChain node)",
        )
    if not any(k in data for k in identity_keys):
        return ProbeResult(
            state=IMPOSTOR, status_code=status_code, data=data,
            error=(f"200 with JSON but no node state — missing all of "
                   f"{', '.join(identity_keys)} (some other service on this address)"),
        )

    # A real node: is it reporting itself healthy?
    if data.get("ok") is False:
        return ProbeResult(state=DEGRADED, status_code=status_code, data=data,
                           error="node reports ok: false")
    if "db_rw" in data and not data["db_rw"]:
        return ProbeResult(state=DEGRADED, status_code=status_code, data=data,
                           error="node reports db_rw: false")
    tip = data.get("tip_age_slots")
    try:
        tip = int(tip) if tip is not None else None
    except (TypeError, ValueError):
        tip = None
    if tip is not None and tip > tip_age_slots_threshold:
        return ProbeResult(
            state=DEGRADED, status_code=status_code, data=data,
            error=f"tip_age_slots={tip} above threshold {tip_age_slots_threshold}",
        )
    return ProbeResult(state=UP, status_code=status_code, data=data)


def _ssl_context(verify: Any) -> ssl.SSLContext:
    """requests-style verify semantics: True, False, or a CA bundle path."""
    if verify is False:
        return ssl._create_unverified_context()
    if isinstance(verify, str):
        return ssl.create_default_context(cafile=verify)
    return ssl.create_default_context()


def probe_health(url: str, timeout: float = 10, verify: Any = True,
                 identity_keys: Tuple[str, ...] = NODE_IDENTITY_KEYS) -> ProbeResult:
    """Fetch ``url`` and classify the response body — never just the status."""
    start = time.monotonic()
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        ctx = _ssl_context(verify) if url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, "status", None) or 200
            headers = getattr(resp, "headers", None)
            ct = headers.get("Content-Type", "") if headers is not None else ""
            body = resp.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
        result = classify_response(status, ct, body=body, identity_keys=identity_keys)
    except urllib.error.HTTPError as exc:          # non-2xx answer: down, not dead
        result = ProbeResult(state=DOWN, status_code=exc.code,
                             error=f"HTTP {exc.code}")
    except (TimeoutError, socket.timeout, socket.gaierror,
            urllib.error.URLError, OSError) as exc:
        result = ProbeResult(state=UNREACHABLE,
                             error=f"{type(exc).__name__}: {exc}")
    result.response_ms = round((time.monotonic() - start) * 1000, 1)
    return result
