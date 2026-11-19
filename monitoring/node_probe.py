#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared RustChain node ``/health`` liveness and body validator.

Stdlib-only (Python 3.9+). Prevents monitors from reporting a node as healthy
("up") based solely on an HTTP 200 status code when the host has been replaced
by an unrelated single-page app (SPA), parking page, captive portal, or a
service returning non-RustChain JSON.

States returned by :func:`probe_health` and :func:`validate_health_response`:
- ``up``: HTTP 200 with valid JSON object containing ``ok: true``, ``version``
  (non-empty string), and ``uptime_s`` (non-negative number), with ``db_rw``
  not ``False`` and ``tip_age_slots`` within threshold.
- ``degraded``: genuine RustChain ``/health`` JSON payload where ``ok`` is
  ``False``, ``db_rw`` is ``False``, or ``tip_age_slots`` exceeds
  ``max_tip_age_slots``.
- ``impostor``: HTTP 200 where ``Content-Type`` is ``text/html`` /
  ``application/xhtml+xml``, body is not a JSON object (e.g. HTML SPA), or
  JSON object is missing required RustChain ``/health`` keys (``ok``,
  ``version``, ``uptime_s``).
- ``down``: non-200 HTTP response (e.g. HTTP 500, 502, 503, 404).
- ``unreachable``: timeout, DNS failure, connection refused, or TLS/transport
  error before an HTTP response is received.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple, Union

VALID_PROBE_STATES: Tuple[str, ...] = (
    "up",
    "down",
    "impostor",
    "degraded",
    "unreachable",
)
REQUIRED_HEALTH_KEYS: Tuple[str, ...] = ("ok", "version", "uptime_s")
DEFAULT_MAX_TIP_AGE_SLOTS: int = 120


@dataclass(frozen=True)
class ProbeResult:
    """Normalized result of probing a RustChain node's ``/health`` endpoint."""

    url: str
    state: str
    ok: bool
    status_code: Optional[int] = None
    response_ms: Optional[float] = None
    version: Optional[str] = None
    uptime_s: Optional[int] = None
    db_rw: Optional[bool] = None
    tip_age_slots: Optional[int] = None
    backup_age_hours: Optional[float] = None
    content_type: Optional[str] = None
    error: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_up(self) -> bool:
        return self.state == "up"

    @property
    def is_impostor(self) -> bool:
        return self.state == "impostor"

    @property
    def is_degraded(self) -> bool:
        return self.state == "degraded"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_health_url(url: str) -> str:
    """Ensure ``url`` points to a ``/health`` path unless an explicit path is given."""
    clean = (url or "").strip()
    if not clean:
        return "/health"
    parsed = urllib.parse.urlsplit(clean)
    if not parsed.path or parsed.path == "/":
        return clean.rstrip("/") + "/health"
    return clean


def _looks_like_html(raw_text: str, content_type: Optional[str]) -> bool:
    if isinstance(content_type, str):
        ct_lower = content_type.lower()
        if "text/html" in ct_lower or "application/xhtml" in ct_lower:
            return True
    stripped = raw_text.lstrip()[:256].lower()
    return (
        stripped.startswith("<!doctype html")
        or stripped.startswith("<html")
        or stripped.startswith("<head")
        or stripped.startswith("<body")
        or "<html" in stripped
    )


def _is_valid_uptime(val: Any) -> bool:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return val >= 0


def validate_health_response(
    status_code: Optional[int],
    body: Union[bytes, str, Dict[str, Any], None],
    content_type: Optional[str] = None,
    *,
    url: str = "",
    response_ms: Optional[float] = None,
    max_tip_age_slots: int = DEFAULT_MAX_TIP_AGE_SLOTS,
) -> ProbeResult:
    """Validate an HTTP response from ``/health`` and classify the node state."""
    if status_code is None:
        return ProbeResult(
            url=url,
            state="unreachable",
            ok=False,
            status_code=None,
            response_ms=response_ms,
            content_type=content_type,
            error="No HTTP status code received",
        )

    if status_code != 200:
        return ProbeResult(
            url=url,
            state="down",
            ok=False,
            status_code=status_code,
            response_ms=response_ms,
            content_type=content_type,
            error=f"HTTP {status_code}",
        )

    # Check Content-Type header for HTML impostors on HTTP 200
    if isinstance(content_type, str):
        ct_lower = content_type.lower()
        if "text/html" in ct_lower or "application/xhtml" in ct_lower:
            return ProbeResult(
                url=url,
                state="impostor",
                ok=False,
                status_code=status_code,
                response_ms=response_ms,
                content_type=content_type,
                error=f"impostor response: HTTP 200 with Content-Type '{content_type}'",
            )

    parsed_data: Optional[Dict[str, Any]] = None
    raw_text = ""

    if isinstance(body, dict):
        parsed_data = body
    elif isinstance(body, (bytes, bytearray)):
        raw_text = bytes(body).decode("utf-8", errors="replace")
    elif isinstance(body, str):
        raw_text = body
    else:
        return ProbeResult(
            url=url,
            state="impostor",
            ok=False,
            status_code=status_code,
            response_ms=response_ms,
            content_type=content_type,
            error="impostor response: HTTP 200 with unreadable body",
        )

    if parsed_data is None:
        if _looks_like_html(raw_text, content_type):
            return ProbeResult(
                url=url,
                state="impostor",
                ok=False,
                status_code=status_code,
                response_ms=response_ms,
                content_type=content_type,
                error="impostor response: HTTP 200 with HTML body instead of RustChain /health JSON",
            )
        try:
            loaded = json.loads(raw_text)
        except (ValueError, TypeError) as exc:
            return ProbeResult(
                url=url,
                state="impostor",
                ok=False,
                status_code=status_code,
                response_ms=response_ms,
                content_type=content_type,
                error=f"impostor response: HTTP 200 with non-JSON body ({exc})",
            )
        if not isinstance(loaded, dict):
            return ProbeResult(
                url=url,
                state="impostor",
                ok=False,
                status_code=status_code,
                response_ms=response_ms,
                content_type=content_type,
                error="impostor response: HTTP 200 JSON payload is not an object",
            )
        parsed_data = loaded

    # Validate required RustChain /health keys: ok, version, uptime_s
    missing_keys = [k for k in REQUIRED_HEALTH_KEYS if k not in parsed_data]
    if missing_keys:
        return ProbeResult(
            url=url,
            state="impostor",
            ok=False,
            status_code=status_code,
            response_ms=response_ms,
            content_type=content_type,
            error=(
                "impostor response: HTTP 200 JSON missing required /health keys: "
                + ", ".join(missing_keys)
            ),
            payload=dict(parsed_data),
        )

    ok_field = parsed_data.get("ok")
    version_field = parsed_data.get("version")
    uptime_field = parsed_data.get("uptime_s")

    if (
        not isinstance(ok_field, bool)
        or not isinstance(version_field, str)
        or not version_field.strip()
        or not _is_valid_uptime(uptime_field)
    ):
        return ProbeResult(
            url=url,
            state="impostor",
            ok=False,
            status_code=status_code,
            response_ms=response_ms,
            content_type=content_type,
            error="impostor response: HTTP 200 JSON has invalid types for ok/version/uptime_s",
            payload=dict(parsed_data),
        )

    uptime_int = int(uptime_field)
    db_rw = parsed_data.get("db_rw")
    if db_rw is not None and not isinstance(db_rw, bool):
        db_rw = bool(db_rw)

    tip_age = parsed_data.get("tip_age_slots")
    try:
        tip_age_int: Optional[int] = int(tip_age) if tip_age is not None else None
    except (TypeError, ValueError):
        tip_age_int = None

    backup_age = parsed_data.get("backup_age_hours")
    try:
        backup_age_float: Optional[float] = float(backup_age) if backup_age is not None else None
    except (TypeError, ValueError):
        backup_age_float = None

    # Check degraded conditions on a genuine RustChain node
    degraded_reasons = []
    if ok_field is False:
        degraded_reasons.append("node reported ok=false")
    if db_rw is False:
        degraded_reasons.append("node reported db_rw=false")
    if tip_age_int is not None and tip_age_int > max_tip_age_slots:
        degraded_reasons.append(
            f"tip_age_slots={tip_age_int} exceeds max_tip_age_slots={max_tip_age_slots}"
        )

    if degraded_reasons:
        return ProbeResult(
            url=url,
            state="degraded",
            ok=False,
            status_code=status_code,
            response_ms=response_ms,
            version=version_field,
            uptime_s=uptime_int,
            db_rw=db_rw,
            tip_age_slots=tip_age_int,
            backup_age_hours=backup_age_float,
            content_type=content_type,
            error="; ".join(degraded_reasons),
            payload=dict(parsed_data),
        )

    return ProbeResult(
        url=url,
        state="up",
        ok=True,
        status_code=status_code,
        response_ms=response_ms,
        version=version_field,
        uptime_s=uptime_int,
        db_rw=db_rw if db_rw is not None else True,
        tip_age_slots=tip_age_int,
        backup_age_hours=backup_age_float,
        content_type=content_type,
        error=None,
        payload=dict(parsed_data),
    )


def _build_ssl_context(verify_ssl: Union[bool, str]) -> Optional[ssl.SSLContext]:
    if isinstance(verify_ssl, str) and os.path.exists(verify_ssl):
        return ssl.create_default_context(cafile=verify_ssl)
    if verify_ssl is False:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # nosec B501
        return ctx
    default_cert = os.path.expanduser("~/.rustchain/node_cert.pem")
    if os.path.exists(default_cert):
        return ssl.create_default_context(cafile=default_cert)
    return None


def validate_requests_response(
    resp: Any,
    *,
    url: str = "",
    response_ms: Optional[float] = None,
    max_tip_age_slots: int = DEFAULT_MAX_TIP_AGE_SLOTS,
) -> ProbeResult:
    """Validate a ``requests.Response`` (or test Mock) using :func:`validate_health_response`."""
    status_code = getattr(resp, "status_code", None)
    if not isinstance(status_code, int):
        status_code = None

    content_type: Optional[str] = None
    headers = getattr(resp, "headers", None)
    if headers is not None and hasattr(headers, "get"):
        ct = headers.get("Content-Type") or headers.get("content-type")
        if isinstance(ct, str):
            content_type = ct

    text_attr = getattr(resp, "text", None)
    content_attr = getattr(resp, "content", None)
    body: Union[bytes, str, Dict[str, Any], None]
    if isinstance(text_attr, str):
        body = text_attr
    elif isinstance(content_attr, (bytes, bytearray)):
        body = bytes(content_attr)
    elif hasattr(resp, "json") and callable(resp.json):
        try:
            json_val = resp.json()
            body = json_val if isinstance(json_val, dict) else json.dumps(json_val)
        except Exception:
            body = ""
    else:
        body = None

    return validate_health_response(
        status_code=status_code,
        body=body,
        content_type=content_type,
        url=url,
        response_ms=response_ms,
        max_tip_age_slots=max_tip_age_slots,
    )


def probe_health(
    url: str,
    timeout: float = 10.0,
    *,
    max_tip_age_slots: int = DEFAULT_MAX_TIP_AGE_SLOTS,
    verify_ssl: Union[bool, str] = True,
    opener: Optional[Callable[..., Any]] = None,
) -> ProbeResult:
    """Probe a RustChain node's ``/health`` endpoint and validate its body.

    Stdlib-only implementation using ``urllib.request``.
    """
    target_url = normalize_health_url(url)
    start = time.monotonic()
    req = urllib.request.Request(
        target_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "RustChain-NodeProbe/1.0",
        },
    )
    open_fn = opener or urllib.request.urlopen
    ctx = _build_ssl_context(verify_ssl) if target_url.startswith("https://") else None

    try:
        if opener is not None:
            resp_cm = open_fn(req, timeout=timeout)
        elif ctx is not None:
            resp_cm = open_fn(req, timeout=timeout, context=ctx)  # nosec B310
        else:
            resp_cm = open_fn(req, timeout=timeout)  # nosec B310

        with resp_cm as resp:
            elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)
            raw_bytes = resp.read()
            status_code = getattr(resp, "status", None) or getattr(resp, "code", 200)
            if not isinstance(status_code, int):
                status_code = 200
            headers = getattr(resp, "headers", None)
            content_type = None
            if headers is not None and hasattr(headers, "get"):
                ct = headers.get("Content-Type") or headers.get("content-type")
                if isinstance(ct, str):
                    content_type = ct

        return validate_health_response(
            status_code=status_code,
            body=raw_bytes,
            content_type=content_type,
            url=target_url,
            response_ms=elapsed_ms,
            max_tip_age_slots=max_tip_age_slots,
        )
    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)
        return ProbeResult(
            url=target_url,
            state="down",
            ok=False,
            status_code=exc.code,
            response_ms=elapsed_ms,
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except (TimeoutError, socket.timeout) as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)
        return ProbeResult(
            url=target_url,
            state="unreachable",
            ok=False,
            status_code=None,
            response_ms=elapsed_ms,
            error=f"Timeout: {exc}",
        )
    except urllib.error.URLError as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            err_msg = f"Timeout: {reason}"
        else:
            err_msg = f"Connection error: {reason}"
        return ProbeResult(
            url=target_url,
            state="unreachable",
            ok=False,
            status_code=None,
            response_ms=elapsed_ms,
            error=err_msg,
        )
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)
        return ProbeResult(
            url=target_url,
            state="unreachable",
            ok=False,
            status_code=None,
            response_ms=elapsed_ms,
            error=str(exc),
        )
