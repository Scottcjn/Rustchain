# SPDX-License-Identifier: MIT
"""One liveness probe for every RustChain node monitor.

A 200 is not evidence of a node.
-------------------------------
Node 4 was decommissioned by its operator and the host was reused for an
unrelated single-page app. An SPA answers **200 on every path**, so every
monitor kept reporting the node healthy for weeks while it was serving HTML.
Each monitor decided "up" from the status code alone, and the five copies had
five different failure modes.

This module is the single place that decides whether the thing answering on a
node's address is actually a RustChain node. It is stdlib-only (Python 3.9+)
so the exporters, Flask dashboards, and CLI tools can all import it without
pulling in extra dependencies.

States
------
``up``          200, JSON body carrying node state, node reports itself healthy.
``degraded``    200, a real node, but it reports ``ok: false``, ``db_rw: false``
                or a tip older than ``max_tip_age_slots``.
``impostor``    200, but the body is not a JSON object, is HTML, or is JSON
                that carries none of ``ok``/``version``/``uptime_s``.
``down``        The server answered, but with a non-200 status.
``unreachable`` We never got an HTTP response (timeout, refused, DNS, TLS).
"""

from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

STATE_UP = "up"
STATE_DEGRADED = "degraded"
STATE_IMPOSTOR = "impostor"
STATE_DOWN = "down"
STATE_UNREACHABLE = "unreachable"

ALL_STATES = (
    STATE_UP,
    STATE_DEGRADED,
    STATE_IMPOSTOR,
    STATE_DOWN,
    STATE_UNREACHABLE,
)

#: A health body is only trusted if it carries at least one of these.
HEALTH_KEYS = ("ok", "version", "uptime_s")

#: Content types that mean "a web page answered", never a node.
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")

#: A tip older than this many slots is reported as degraded. Epochs are short;
#: four hours of drift is already a stalled node, not a scheduling hiccup.
DEFAULT_MAX_TIP_AGE_SLOTS = 120


def utc_now_iso(now: Optional[datetime] = None) -> str:
    """Return an ISO-8601 UTC timestamp with a trailing ``Z``."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.isoformat() + "Z"


def content_type_of(headers: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Pull a usable Content-Type out of a response header mapping.

    Returns ``None`` for anything that is not a plain string so test doubles
    (``MagicMock`` etc.) cannot silently steer the classification.
    """
    if not headers:
        return None
    try:
        value = headers.get("Content-Type")
    except AttributeError:
        return None
    return value if isinstance(value, str) else None


def is_html_content_type(content_type: Optional[str]) -> bool:
    """True when the response advertises itself as a page, not an API."""
    if not content_type:
        return False
    base = content_type.split(";", 1)[0].strip().lower()
    return base in HTML_CONTENT_TYPES


def looks_like_html(body: Optional[bytes]) -> bool:
    """Cheap sniff for a page served without a truthful Content-Type."""
    if not body:
        return False
    head = body[:256].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def parse_json_object(body: Optional[bytes]) -> Optional[Dict[str, Any]]:
    """Decode ``body`` into a JSON object, or return ``None``.

    Lists, strings, numbers, HTML, and empty bodies are all ``None``: none of
    them is node state.
    """
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of probing one node's ``/health`` endpoint."""

    url: str
    state: str
    status_code: Optional[int] = None
    response_ms: Optional[int] = None
    content_type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    version: Optional[str] = None
    uptime_s: Optional[int] = None
    ok: Optional[bool] = None
    db_rw: Optional[bool] = None
    tip_age_slots: Optional[int] = None
    reason: str = ""
    error: Optional[str] = None
    checked_at: str = ""

    @property
    def is_up(self) -> bool:
        """A real node that is answering (healthy or degraded)."""
        return self.state in (STATE_UP, STATE_DEGRADED)

    @property
    def is_healthy(self) -> bool:
        return self.state == STATE_UP

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_health(
    status_code: Optional[int],
    payload: Optional[Mapping[str, Any]],
    *,
    url: str = "",
    content_type: Optional[str] = None,
    response_ms: Optional[int] = None,
    max_tip_age_slots: int = DEFAULT_MAX_TIP_AGE_SLOTS,
    checked_at: Optional[str] = None,
    error: Optional[str] = None,
) -> ProbeResult:
    """Classify an already-fetched response.

    ``payload`` must be the parsed JSON object, or ``None`` when the body was
    not JSON. Keeping this pure makes every monitor's decision testable with a
    recorded fixture instead of a live node.
    """
    checked = checked_at or utc_now_iso()
    common = dict(
        url=url,
        status_code=status_code,
        response_ms=response_ms,
        content_type=content_type,
        checked_at=checked,
    )

    if error is not None:
        return ProbeResult(state=STATE_UNREACHABLE, error=error,
                           reason=error, **common)

    if status_code != 200:
        reason = f"HTTP {status_code}" if status_code is not None else "no response"
        return ProbeResult(state=STATE_DOWN, reason=reason, error=reason, **common)

    # From here the server said 200. That is the part that used to be enough.
    if is_html_content_type(content_type):
        return ProbeResult(
            state=STATE_IMPOSTOR,
            reason=f"HTTP 200 with Content-Type {content_type!r} (not a node)",
            payload=None,
            **common,
        )

    if payload is None:
        return ProbeResult(
            state=STATE_IMPOSTOR,
            reason="HTTP 200 but the body is not a JSON object",
            payload=None,
            **common,
        )

    data = dict(payload)
    if not any(key in data for key in HEALTH_KEYS):
        return ProbeResult(
            state=STATE_IMPOSTOR,
            reason=(
                "HTTP 200 JSON body carries none of "
                + ", ".join(HEALTH_KEYS)
                + " (not RustChain node state)"
            ),
            payload=data,
            **common,
        )

    version = data.get("version")
    uptime = _as_int(data.get("uptime_s", data.get("uptime_seconds")))
    ok = data.get("ok")
    ok = ok if isinstance(ok, bool) else None
    db_rw = data.get("db_rw")
    db_rw = db_rw if isinstance(db_rw, bool) else None
    tip_age = _as_int(data.get("tip_age_slots"))

    fields = dict(
        payload=data,
        version=version if isinstance(version, str) else None,
        uptime_s=uptime,
        ok=ok,
        db_rw=db_rw,
        tip_age_slots=tip_age,
        **common,
    )

    if ok is False:
        return ProbeResult(state=STATE_DEGRADED, reason="node reports ok=false", **fields)
    if db_rw is False:
        return ProbeResult(state=STATE_DEGRADED, reason="node reports db_rw=false", **fields)
    if tip_age is not None and tip_age > max_tip_age_slots:
        return ProbeResult(
            state=STATE_DEGRADED,
            reason=f"tip_age_slots={tip_age} exceeds {max_tip_age_slots}",
            **fields,
        )
    return ProbeResult(state=STATE_UP, reason="healthy", **fields)


def _ssl_context(url: str, tls_verify: bool, ca_bundle: Optional[str]) -> Optional[ssl.SSLContext]:
    if not url.lower().startswith("https://"):
        return None
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    if not tls_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    return ssl.create_default_context()


def probe_health(
    url: str,
    *,
    timeout: float = 10.0,
    tls_verify: bool = True,
    ca_bundle: Optional[str] = None,
    max_tip_age_slots: int = DEFAULT_MAX_TIP_AGE_SLOTS,
    headers: Optional[Mapping[str, str]] = None,
    now: Optional[datetime] = None,
) -> ProbeResult:
    """Fetch ``url`` and classify it. Never raises."""
    started = time.monotonic()
    checked = utc_now_iso(now)
    request_headers = {"Accept": "application/json", "User-Agent": "RustChain-NodeProbe/1.0"}
    if headers:
        request_headers.update(headers)

    def elapsed_ms() -> int:
        return int(round((time.monotonic() - started) * 1000))

    try:
        request = urllib.request.Request(url, headers=request_headers)
        context = _ssl_context(url, tls_verify, ca_bundle)
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            response_headers = getattr(response, "headers", None)
            content_type = content_type_of(response_headers)
            if is_html_content_type(content_type) or looks_like_html(body):
                return ProbeResult(
                    url=url,
                    state=STATE_IMPOSTOR,
                    status_code=status,
                    response_ms=elapsed_ms(),
                    content_type=content_type,
                    reason="HTTP 200 but the body is HTML, not node state",
                    checked_at=checked,
                )
            return classify_health(
                status,
                parse_json_object(body),
                url=url,
                content_type=content_type,
                response_ms=elapsed_ms(),
                max_tip_age_slots=max_tip_age_slots,
                checked_at=checked,
            )
    except urllib.error.HTTPError as exc:
        body = None
        try:
            body = exc.read()
        except Exception:  # noqa: BLE001 - the status code is the story here
            body = None
        return classify_health(
            exc.code,
            parse_json_object(body),
            url=url,
            content_type=content_type_of(getattr(exc, "headers", None)),
            response_ms=elapsed_ms(),
            max_tip_age_slots=max_tip_age_slots,
            checked_at=checked,
        )
    except (socket.timeout, TimeoutError) as exc:
        message = f"timeout after {timeout:g}s"
        return ProbeResult(url=url, state=STATE_UNREACHABLE, response_ms=elapsed_ms(),
                           reason=message, error=str(exc) or message, checked_at=checked)
    except Exception as exc:  # noqa: BLE001 - refusal, DNS, TLS, reset...
        message = f"{type(exc).__name__}: {exc}"
        return ProbeResult(url=url, state=STATE_UNREACHABLE, response_ms=elapsed_ms(),
                           reason=message, error=message, checked_at=checked)


def summarize(results) -> Dict[str, int]:
    """Count results per state, for dashboards and exporter logs."""
    counts = {state: 0 for state in ALL_STATES}
    for result in results:
        counts[result.state] = counts.get(result.state, 0) + 1
    return counts
