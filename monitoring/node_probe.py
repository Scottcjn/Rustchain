#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared RustChain node liveness probe — ONE probe for every monitor.

Issue #17180: an HTTP 200 is not evidence that a RustChain node is answering.
When an attestation node's IP was repurposed to serve an unrelated single-page
app, `/health` returned 200 with HTML and every status-code-based monitor kept
the node green for weeks.

Every monitor in this repo (status page, health dashboard, Prometheus exporter,
node health monitor, node-health CLI) must decide "up" through this module,
never from the status code alone.

Stdlib-only, Python 3.9+. No third-party imports on purpose so any monitor can
use it without adding a dependency.

Probe states:
    up          genuine RustChain node, /health JSON with ok/version/uptime_s
                and ok=true, db_rw not false, tip_age_slots within threshold
    degraded    genuine node shape, but the node reports ok=false, db_rw=false
                or tip_age_slots above the threshold
    impostor    HTTP 2xx but the answerer is NOT a RustChain node: body is not
                JSON, JSON is not an object, required keys (ok/version/uptime_s)
                are missing, or Content-Type is text/html
    down        the host answered with a non-2xx HTTP status
    unreachable no HTTP answer at all (DNS, refused, timeout, TLS failure)
"""

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

# ── Probe states ──────────────────────────────────────────────────────────────
UP = "up"
DOWN = "down"
IMPOSTOR = "impostor"
DEGRADED = "degraded"
UNREACHABLE = "unreachable"
STATES = (UP, DOWN, IMPOSTOR, DEGRADED, UNREACHABLE)

# A genuine /health body always carries these keys (see node api_health).
REQUIRED_KEYS = ("ok", "version", "uptime_s")

DEFAULT_TIMEOUT = 10

# One full epoch without a new tip (EPOCH_SLOTS = 144 at 10-min slots) means
# the chain has stalled; the node is real but degraded.
DEFAULT_TIP_AGE_SLOTS_THRESHOLD = 144

USER_AGENT = "RustChain-NodeProbe/1.0"


@dataclass
class ProbeResult:
    """Outcome of one probe_health() call."""

    state: str
    url: str
    status_code: Optional[int] = None
    response_ms: Optional[float] = None
    content_type: Optional[str] = None
    ok: Optional[bool] = None
    version: Optional[str] = None
    uptime_s: Optional[int] = None
    db_rw: Optional[bool] = None
    tip_age_slots: Optional[int] = None
    data: Optional[Dict[str, Any]] = None      # parsed /health body, when genuine
    detail: Optional[str] = None               # human-readable explanation

    @property
    def is_up(self) -> bool:
        return self.state == UP

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ssl_context_for(verify: bool = True, ca_file: Optional[str] = None) -> ssl.SSLContext:
    """Build an stdlib SSL context for HTTPS probes (mirrors requests' verify=)."""
    if ca_file:
        return ssl.create_default_context(cafile=ca_file)
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def classify_health_response(
    url: str,
    status_code: Optional[int],
    content_type: Optional[str],
    body: bytes,
    response_ms: Optional[float] = None,
    tip_age_slots_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
) -> ProbeResult:
    """Classify an already-fetched /health response.

    Pure function (no I/O) so tests can drive it with recorded fixture bodies
    and so monitors that already hold a response can reuse the exact same
    rules as probe_health().
    """
    ct = (content_type or "").split(";")[0].strip().lower()

    if status_code is not None and not (200 <= status_code < 300):
        return ProbeResult(
            state=DOWN, url=url, status_code=status_code,
            response_ms=response_ms, content_type=content_type,
            detail=f"HTTP {status_code}",
        )

    # 2xx from here on. A 200 is not evidence of a node.
    if ct == "text/html":
        return ProbeResult(
            state=IMPOSTOR, url=url, status_code=status_code,
            response_ms=response_ms, content_type=content_type,
            detail=("HTTP 200 with Content-Type text/html — an HTML page, "
                    "not a RustChain node (impostor)"),
        )

    text = body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return ProbeResult(
            state=IMPOSTOR, url=url, status_code=status_code,
            response_ms=response_ms, content_type=content_type,
            detail=(f"HTTP 200 with non-JSON body ({len(body)} bytes, "
                    f"content-type {content_type or 'none'}) — not a RustChain node (impostor)"),
        )
    if not isinstance(data, dict):
        return ProbeResult(
            state=IMPOSTOR, url=url, status_code=status_code,
            response_ms=response_ms, content_type=content_type,
            detail="HTTP 200 with JSON that is not an object — not a RustChain node (impostor)",
        )

    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        return ProbeResult(
            state=IMPOSTOR, url=url, status_code=status_code,
            response_ms=response_ms, content_type=content_type,
            detail=(f"HTTP 200 JSON missing required node keys {missing} — "
                    "not a RustChain node (impostor)"),
        )

    # Genuine node shape. Now decide up vs degraded from what the node reports.
    ok = data.get("ok")
    version = data.get("version")
    uptime_s = _coerce_int(data.get("uptime_s"))
    db_rw = data.get("db_rw", data.get("db_ok"))
    tip_age_slots = _coerce_int(data.get("tip_age_slots"))

    problems = []
    if ok is not True:
        problems.append(f"ok={ok!r}")
    if db_rw is False:
        problems.append("db_rw=false")
    if tip_age_slots is not None and tip_age_slots > tip_age_slots_threshold:
        problems.append(f"tip_age_slots={tip_age_slots} > {tip_age_slots_threshold}")

    state = DEGRADED if problems else UP
    return ProbeResult(
        state=state, url=url, status_code=status_code,
        response_ms=response_ms, content_type=content_type,
        ok=ok if isinstance(ok, bool) else None,
        version=str(version) if version is not None else None,
        uptime_s=uptime_s,
        db_rw=db_rw if isinstance(db_rw, bool) else None,
        tip_age_slots=tip_age_slots,
        data=data,
        detail="; ".join(problems) if problems else None,
    )


def probe_health(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    *,
    ssl_context: Optional[ssl.SSLContext] = None,
    tip_age_slots_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
) -> ProbeResult:
    """Probe a node's /health URL and classify the answer.

    Never raises for network/HTTP problems — those become UNREACHABLE/DOWN
    results — so callers can rely on getting a ProbeResult back.
    """
    start = time.monotonic()
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        if ssl_context is not None and url.lower().startswith("https://"):
            resp = urllib.request.urlopen(req, timeout=timeout, context=ssl_context)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout)
        with resp:
            status_code = getattr(resp, "status", None) or 200
            headers = getattr(resp, "headers", None)
            content_type = headers.get("Content-Type") if headers is not None else None
            body = resp.read()
        response_ms = (time.monotonic() - start) * 1000
    except urllib.error.HTTPError as exc:
        response_ms = (time.monotonic() - start) * 1000
        ct = None
        try:
            if exc.headers is not None:
                ct = exc.headers.get("Content-Type")
        except Exception:
            ct = None
        return ProbeResult(
            state=DOWN, url=url, status_code=exc.code, response_ms=response_ms,
            content_type=ct, detail=f"HTTP {exc.code}: {exc.reason}",
        )
    except (socket.timeout, TimeoutError):
        return ProbeResult(
            state=UNREACHABLE, url=url, response_ms=None, detail="Timeout",
        )
    except urllib.error.URLError as exc:
        return ProbeResult(
            state=UNREACHABLE, url=url, response_ms=None,
            detail=f"Connection error: {exc.reason}",
        )
    except Exception as exc:  # noqa: BLE001 — any transport failure is "unreachable"
        return ProbeResult(
            state=UNREACHABLE, url=url, response_ms=None,
            detail=str(exc) or type(exc).__name__,
        )

    return classify_health_response(
        url, status_code, content_type, body,
        response_ms=response_ms,
        tip_age_slots_threshold=tip_age_slots_threshold,
    )


if __name__ == "__main__":
    # Manual smoke test: python monitoring/node_probe.py https://rustchain.org/health
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://rustchain.org/health"
    result = probe_health(target, timeout=DEFAULT_TIMEOUT)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    sys.exit(0 if result.state == UP else 1)
