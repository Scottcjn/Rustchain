# SPDX-License-Identifier: Apache-2.0
"""
monitoring/node_probe.py — Unified RustChain Node Health & Liveness Probe
Issue #17180 / Bounty 25 RTC

Validates node health bodies against genuine RustChain node signatures.
Detects impostor endpoints (HTML SPAs, captive portals, missing keys)
that return HTTP 200 on every path.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ProbeState(str, Enum):
    UP = "up"
    DOWN = "down"
    IMPOSTOR = "impostor"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


DEFAULT_PROBE_TIMEOUT = 5.0
DEFAULT_TIP_AGE_SLOTS_THRESHOLD = 120
REQUIRED_HEALTH_KEYS = ("ok", "version", "uptime_s")


@dataclass
class ProbeResult:
    state: str  # ProbeState value: "up", "down", "impostor", "degraded", "unreachable"
    status_code: int | None
    response_time_ms: float
    data: dict[str, Any] | None = None
    error: str | None = None
    reason: str | None = None
    url: str | None = None

    @property
    def is_healthy(self) -> bool:
        return self.state == ProbeState.UP.value

    @property
    def is_impostor(self) -> bool:
        return self.state == ProbeState.IMPOSTOR.value

    @property
    def is_degraded(self) -> bool:
        return self.state == ProbeState.DEGRADED.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_health_payload(
    payload: Any,
    content_type: str = "",
    status_code: int = 200,
    tip_age_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
) -> tuple[ProbeState, dict[str, Any] | None, str | None]:
    """
    Validate decoded response payload and content type.
    Returns (state, parsed_dict, reason).
    """
    ct = content_type.lower() if isinstance(content_type, str) else ""
    if "text/html" in ct or "<html" in str(payload).lower() or "<!doctype html" in str(payload).lower():
        return (
            ProbeState.IMPOSTOR,
            None,
            "Impostor detected: Content-Type is HTML or body contains HTML markup instead of node JSON",
        )

    data: dict[str, Any] | None = None
    if isinstance(payload, dict):
        data = payload
    elif isinstance(payload, (str, bytes)):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                data = parsed
            else:
                return (
                    ProbeState.IMPOSTOR,
                    None,
                    f"Impostor detected: JSON payload is not a dictionary (got {type(parsed).__name__})",
                )
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
            return (
                ProbeState.IMPOSTOR,
                None,
                f"Impostor detected: Invalid JSON body on HTTP {status_code} ({err})",
            )
    else:
        return (
            ProbeState.IMPOSTOR,
            None,
            f"Impostor detected: Unsupported payload type {type(payload).__name__}",
        )

    # Check essential keys: 'ok', 'version', 'uptime_s'
    missing_keys = [k for k in REQUIRED_HEALTH_KEYS if k not in data]
    if missing_keys:
        return (
            ProbeState.IMPOSTOR,
            data,
            f"Impostor detected: Missing essential node health keys {missing_keys}",
        )

    # Check degraded states: ok == False, db_rw == False, or tip_age_slots > threshold
    is_ok = bool(data.get("ok"))
    db_rw = data.get("db_rw")
    tip_age = data.get("tip_age_slots")

    reasons = []
    if not is_ok:
        reasons.append("ok is false")
    if db_rw is False:
        reasons.append("db_rw is false")
    if tip_age is not None:
        try:
            if int(tip_age) > tip_age_threshold:
                reasons.append(f"tip_age_slots ({tip_age}) exceeds threshold ({tip_age_threshold})")
        except (TypeError, ValueError):
            pass

    if reasons:
        return (ProbeState.DEGRADED, data, f"Node degraded: {', '.join(reasons)}")

    return (ProbeState.UP, data, None)


def validate_response(
    resp: Any,
    tip_age_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
    response_time_ms: float = 0.0,
    url: str | None = None,
) -> ProbeResult:
    """
    Validate a response object (requests.Response or urllib HTTPResponse).
    """
    status_code = getattr(resp, "status_code", getattr(resp, "code", 200))
    headers = getattr(resp, "headers", None)
    content_type = ""
    if isinstance(headers, dict) or (hasattr(headers, "get") and not hasattr(headers, "_mock_return_value")):
        val = headers.get("Content-Type", "")
        if isinstance(val, str):
            content_type = val

    if hasattr(resp, "json") and callable(resp.json):
        try:
            j = resp.json()
            if isinstance(j, dict):
                raw_body = j
            elif hasattr(resp, "text"):
                raw_body = resp.text
            else:
                raw_body = j
        except Exception:  # noqa: BLE001
            raw_body = getattr(resp, "text", "")
    elif hasattr(resp, "text"):
        raw_body = resp.text
    elif hasattr(resp, "read"):
        raw_body = resp.read()
    elif hasattr(resp, "content"):
        raw_body = resp.content
    else:
        raw_body = str(resp)

    if status_code != 200:
        return ProbeResult(
            state=ProbeState.DOWN.value,
            status_code=status_code,
            response_time_ms=response_time_ms,
            error=f"HTTP status {status_code}",
            url=url,
        )

    state, data, reason = validate_health_payload(
        payload=raw_body,
        content_type=content_type,
        status_code=status_code,
        tip_age_threshold=tip_age_threshold,
    )

    return ProbeResult(
        state=state.value,
        status_code=status_code,
        response_time_ms=response_time_ms,
        data=data,
        reason=reason,
        error=reason if state in (ProbeState.IMPOSTOR, ProbeState.DEGRADED) else None,
        url=url,
    )


def probe_health(
    url: str,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    tip_age_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
    ssl_context: ssl.SSLContext | None = None,
    verify_ssl: bool = True,
    use_requests: bool = False,
) -> ProbeResult:
    """
    Perform synchronous health probe against a RustChain node.
    Validates both transport status code and /health body payload.
    """
    target_url = url
    if not target_url.endswith("/health"):
        # If bare node URL provided, ensure /health endpoint is targeted
        clean = target_url.rstrip("/")
        if not clean.endswith(("/health", "/status", "/epoch")):
            target_url = f"{clean}/health"

    start = time.perf_counter()

    if use_requests:
        try:
            import requests
            resp = requests.get(target_url, timeout=timeout, verify=verify_ssl)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            return validate_response(
                resp=resp,
                tip_age_threshold=tip_age_threshold,
                response_time_ms=elapsed_ms,
                url=target_url,
            )
        except Exception as err:  # noqa: BLE001
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            err_str = str(err)
            if "Timeout" in type(err).__name__ or "timeout" in err_str.lower():
                return ProbeResult(
                    state=ProbeState.UNREACHABLE.value,
                    status_code=None,
                    response_time_ms=elapsed_ms,
                    error=f"Unreachable: {err}",
                    reason=err_str,
                    url=target_url,
                )
            return ProbeResult(
                state=ProbeState.DOWN.value,
                status_code=getattr(err, "response", None) and getattr(err.response, "status_code", None),
                response_time_ms=elapsed_ms,
                error=f"Request error: {err}",
                reason=err_str,
                url=target_url,
            )

    headers = {
        "Accept": "application/json",
        "User-Agent": "RustChain-NodeProbe/2.2.1",
    }

    req = urllib.request.Request(target_url, headers=headers)

    ctx = ssl_context
    if ctx is None and not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = resp.getcode()
            content_type = resp.headers.get("Content-Type", "")
            raw_body = resp.read()

        if status_code != 200:
            return ProbeResult(
                state=ProbeState.DOWN.value,
                status_code=status_code,
                response_time_ms=elapsed_ms,
                error=f"HTTP status {status_code}",
                url=target_url,
            )

        state, data, reason = validate_health_payload(
            payload=raw_body,
            content_type=content_type,
            status_code=status_code,
            tip_age_threshold=tip_age_threshold,
        )

        return ProbeResult(
            state=state.value,
            status_code=status_code,
            response_time_ms=elapsed_ms,
            data=data,
            reason=reason,
            error=reason if state in (ProbeState.IMPOSTOR, ProbeState.DEGRADED) else None,
            url=target_url,
        )

    except urllib.error.HTTPError as err:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return ProbeResult(
            state=ProbeState.DOWN.value,
            status_code=err.code,
            response_time_ms=elapsed_ms,
            error=f"HTTP {err.code}: {err.reason}",
            reason=str(err),
            url=target_url,
        )

    except (urllib.error.URLError, TimeoutError, OSError) as err:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return ProbeResult(
            state=ProbeState.UNREACHABLE.value,
            status_code=None,
            response_time_ms=elapsed_ms,
            error=f"Unreachable: {err}",
            reason=str(err),
            url=target_url,
        )

    except Exception as err:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return ProbeResult(
            state=ProbeState.DOWN.value,
            status_code=None,
            response_time_ms=elapsed_ms,
            error=f"Unexpected error: {err}",
            reason=str(err),
            url=target_url,
        )
