#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One shared /health body validator for every RustChain node monitor.

Every node monitor used to decide "up" from the HTTP status code alone.
A host replaced by an unrelated single-page app answers 200 on every path,
so the fleet looked healthy while a node was gone for months. This module
is the single place that decides what a /health answer means. All five
monitors (status page, health dashboard, Prometheus exporter,
tools/node_health_monitor.py, tools/node-health-cli/node_health.py) classify
through :func:`classify_health` (or :func:`probe_health`, which fetches with
the standard library and then classifies).

Probe states
------------
``up``
    A genuine node body: HTTP 200, JSON object carrying ``ok`` (bool),
    ``version`` (non-empty string) and ``uptime_s`` (number >= 0), with
    ``ok`` true, ``db_rw`` not false, and ``tip_age_slots`` within threshold.
``degraded``
    A real node (valid body shape) that reports ``ok: false``,
    ``db_rw: false``, or ``tip_age_slots`` above ``tip_age_slots_threshold``.
``impostor``
    HTTP 200, but the body is not a node body: ``text/html`` content (an SPA
    answering every path), a body that is not JSON, JSON that is not an
    object, or JSON missing ``ok`` / ``version`` / ``uptime_s``.
``down``
    The node answered with an HTTP error status (or a non-200 status with a
    body that is not a valid node body). The detail is the HTTP status.
``unreachable``
    No HTTP response at all: connection refused, DNS failure, timeout.

The genuine body shape comes from the node itself
(``node/rustchain_v2_integrated_v2.2.1_rip200.py``, ``api_health``)::

    {"ok": bool, "version": str, "uptime_s": int, "db_rw": bool,
     "backup_age_hours": float | None, "tip_age_slots": int | None,
     "settlement_lag_epochs": int | None, "last_settled_epoch": int | None}

The node answers 200 when ``ok`` is true and 503 when it is false, so a
valid body with ``ok: false`` is ``degraded`` whatever the status code is.

``tip_age_slots_threshold`` (default 600) is the staleness line: a node whose
tip is further behind than that is serving stale state. It is a parameter,
not a protocol constant — pass a different value if the network retunes it.

Standard library only, Python 3.9+.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

__all__ = [
    "STATE_UP",
    "STATE_DOWN",
    "STATE_IMPOSTOR",
    "STATE_DEGRADED",
    "STATE_UNREACHABLE",
    "STATES",
    "REQUIRED_KEYS",
    "DEFAULT_TIP_AGE_SLOTS_THRESHOLD",
    "ProbeResult",
    "classify_health",
    "probe_health",
]

# ── VENDORED-REGION-START ──
# Everything between these markers is copied verbatim into
# health-dashboard/server.py and into the fallback path of
# tools/node_health_monitor.py and tools/node-health-cli/node_health.py.
# It must stay self-contained: only json / dataclasses / typing names.
# The parity test in monitoring/test_impostor_across_monitors.py asserts
# every copy returns the canonical verdict on all fixtures.
STATE_UP = "up"
STATE_DOWN = "down"
STATE_IMPOSTOR = "impostor"
STATE_DEGRADED = "degraded"
STATE_UNREACHABLE = "unreachable"

STATES = (STATE_UP, STATE_DOWN, STATE_IMPOSTOR, STATE_DEGRADED, STATE_UNREACHABLE)

# A /health body without any of these is not a node body.
REQUIRED_KEYS = ("ok", "version", "uptime_s")

# Slots behind the tip before a live node counts as degraded.
DEFAULT_TIP_AGE_SLOTS_THRESHOLD = 600


@dataclass
class ProbeResult:
    """The verdict of one /health probe."""

    state: str
    status_code: Optional[int] = None
    ok: Optional[bool] = None
    version: Optional[str] = None
    uptime_s: Optional[int] = None
    db_rw: Optional[bool] = None
    tip_age_slots: Optional[int] = None
    detail: str = ""
    response_ms: Optional[float] = None
    content_type: Optional[str] = None
    # Parsed JSON object when the body was one, else None. Monitors read
    # extra fields (active_miners, epoch, ...) from here without re-parsing.
    body: Optional[Dict] = None


def _coerce_content_type(content_type) -> str:
    if isinstance(content_type, str):
        return content_type
    return ""


def _coerce_body(body) -> bytes:
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return b""


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def classify_health(status_code, content_type, body, *,
                    tip_age_slots_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD
                    ) -> ProbeResult:
    """Classify one /health answer. Pure function — no I/O.

    ``status_code`` is the HTTP status (None when there was no response),
    ``content_type`` the response Content-Type header, ``body`` the raw
    response bytes (a str is accepted for convenience).
    """
    content_type = _coerce_content_type(content_type)
    raw = _coerce_body(body)
    media = content_type.split(";")[0].strip().lower()

    if status_code is None:
        return ProbeResult(state=STATE_UNREACHABLE, detail="no HTTP response")

    head = raw.lstrip()[:200].decode("utf-8", errors="replace").lower()
    is_html = (
        media == "text/html"
        or head.startswith("<!doctype html")
        or head.startswith("<html")
    )
    if is_html:
        if status_code == 200:
            return ProbeResult(
                state=STATE_IMPOSTOR,
                status_code=status_code,
                content_type=content_type,
                detail=("HTTP 200 with text/html body — an unrelated site "
                        "(e.g. a single-page app) is answering on this address, "
                        "not a RustChain node"),
            )
        # An HTML error page from a proxy is the node being down, not an impostor.
        return ProbeResult(
            state=STATE_DOWN,
            status_code=status_code,
            content_type=content_type,
            detail="HTTP %s" % status_code,
        )

    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else None
    except (ValueError, UnicodeDecodeError):
        parsed = None
    data = parsed if isinstance(parsed, dict) else None
    if data is None:
        if status_code == 200:
            return ProbeResult(
                state=STATE_IMPOSTOR,
                status_code=status_code,
                content_type=content_type,
                detail="HTTP 200 but /health body is not a JSON object",
            )
        return ProbeResult(
            state=STATE_DOWN,
            status_code=status_code,
            content_type=content_type,
            detail="HTTP %s" % status_code,
        )

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if "ok" in data and not isinstance(data["ok"], bool):
        missing.append("ok (not a boolean)")
    if "version" in data and not (isinstance(data["version"], str)
                                  and data["version"]):
        missing.append("version (not a non-empty string)")
    if "uptime_s" in data and (not _is_number(data["uptime_s"])
                               or data["uptime_s"] < 0):
        missing.append("uptime_s (not a number >= 0)")
    if missing:
        if status_code == 200:
            return ProbeResult(
                state=STATE_IMPOSTOR,
                status_code=status_code,
                content_type=content_type,
                body=data,
                detail=("HTTP 200 but /health JSON is missing required field(s): "
                        + ", ".join(missing)),
            )
        return ProbeResult(
            state=STATE_DOWN,
            status_code=status_code,
            content_type=content_type,
            body=data,
            detail="HTTP %s" % status_code,
        )

    ok = data["ok"]
    db_rw = data.get("db_rw")
    tip_age = data.get("tip_age_slots")
    tip_age = tip_age if _is_number(tip_age) else None

    result = ProbeResult(
        state=STATE_UP,
        status_code=status_code,
        ok=ok,
        version=data["version"],
        uptime_s=data["uptime_s"],
        db_rw=db_rw if isinstance(db_rw, bool) else None,
        tip_age_slots=tip_age,
        content_type=content_type,
        body=data,
    )
    if ok is False:
        result.state = STATE_DEGRADED
        result.detail = "node reports ok:false"
        return result
    if db_rw is False:
        result.state = STATE_DEGRADED
        result.detail = "node reports db_rw:false"
        return result
    if tip_age is not None and tip_age > tip_age_slots_threshold:
        result.state = STATE_DEGRADED
        result.detail = ("tip_age_slots %s is above threshold %s"
                         % (tip_age, tip_age_slots_threshold))
        return result
    if status_code != 200:
        # A valid healthy body behind an HTTP error status: the transport
        # says something is wrong, so do not call it up.
        result.state = STATE_DOWN
        result.detail = "HTTP %s" % status_code
        return result
    return result


# ── VENDORED-REGION-END ──


def probe_health(url, timeout=10, *,
                 tip_age_slots_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD
                 ) -> ProbeResult:
    """Fetch ``url`` (a /health URL) and classify the answer.

    Standard library only. A timeout or connection failure is
    ``unreachable``, never an exception — callers get a verdict for every
    outcome.
    """
    start = time.monotonic()
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "RustChain-NodeProbe/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            status = getattr(resp, "status", 200)
            if not isinstance(status, int) or isinstance(status, bool):
                status = 200
            content_type = _response_content_type(resp)
            result = classify_health(
                status, content_type, resp.read(),
                tip_age_slots_threshold=tip_age_slots_threshold,
            )
            result.response_ms = elapsed_ms
            return result
    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        try:
            raw = exc.read() or b""
        except Exception:
            raw = b""
        result = classify_health(
            exc.code, _response_content_type(exc), raw,
            tip_age_slots_threshold=tip_age_slots_threshold,
        )
        result.response_ms = elapsed_ms
        return result
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return ProbeResult(
            state=STATE_UNREACHABLE,
            detail="unreachable: %s" % reason,
            response_ms=round((time.monotonic() - start) * 1000, 1),
        )
    except Exception as exc:  # never let a probe take its caller down
        return ProbeResult(
            state=STATE_UNREACHABLE,
            detail="unreachable: %s" % exc,
            response_ms=round((time.monotonic() - start) * 1000, 1),
        )


def _response_content_type(resp) -> str:
    """Best-effort Content-Type from a urllib response (or HTTPError)."""
    headers = getattr(resp, "headers", None)
    if headers is None:
        return ""
    get_type = getattr(headers, "get_content_type", None)
    if callable(get_type):
        try:
            value = get_type()
        except Exception:
            value = ""
        return value if isinstance(value, str) else ""
    try:
        value = headers.get("Content-Type", "")
    except Exception:
        return ""
    return value if isinstance(value, str) else ""
