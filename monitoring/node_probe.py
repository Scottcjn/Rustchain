#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared RustChain node /health body liveness validator (Bounty #17180).

Validates that an HTTP response from a node's ``/health`` endpoint is a genuine
RustChain node rather than an unrelated web server, captive portal, or SPA
returning HTTP 200 with HTML or unrelated JSON.

States:
- ``up``: HTTP 200, JSON object with RustChain health keys (``ok == True``,
  ``version`` string, ``uptime_s`` / ``uptime`` numeric), ``db_rw`` not False,
  and ``tip_age_slots`` within threshold.
- ``degraded``: Genuine RustChain health JSON, but ``ok`` is False,
  ``db_rw`` is False, or ``tip_age_slots`` exceeds ``tip_age_threshold_slots``.
- ``impostor``: HTTP 200, but ``Content-Type`` is ``text/html``, body is not
  valid JSON object, or JSON lacks required RustChain node identity keys
  (``ok``, ``version``, ``uptime_s``/``uptime``).
- ``down``: Non-200 HTTP status code (e.g. 404, 500, 502, 503).
- ``unreachable``: Network timeout, DNS failure, TLS error, or connection reset.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Optional

VALID_STATES = ("up", "degraded", "impostor", "down", "unreachable")
DEFAULT_TIP_AGE_THRESHOLD_SLOTS = 120


@dataclass
class ProbeResult:
    """Normalized result of probing a RustChain node's /health endpoint."""

    url: str
    state: str  # "up" | "degraded" | "impostor" | "down" | "unreachable"
    http_status: Optional[int] = None
    response_ms: Optional[float] = None
    version: Optional[str] = None
    uptime_s: Optional[float] = None
    db_rw: Optional[bool] = None
    tip_age_slots: Optional[int] = None
    backup_age_hours: Optional[float] = None
    active_miners: Optional[int] = None
    epoch: Optional[int] = None
    error: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_up(self) -> bool:
        return self.state == "up"

    @property
    def is_impostor(self) -> bool:
        return self.state == "impostor"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_health_response(
    url: str,
    status_code: int,
    body_text: str,
    content_type: str = "",
    response_ms: float = 0.0,
    tip_age_threshold_slots: int = DEFAULT_TIP_AGE_THRESHOLD_SLOTS,
) -> ProbeResult:
    """Classify a recorded or live HTTP response into a ``ProbeResult``."""
    ms = round(float(response_ms), 2)
    if status_code != 200:
        return ProbeResult(
            url=url,
            state="down",
            http_status=status_code,
            response_ms=ms,
            error=f"HTTP {status_code}",
        )

    ct_lower = (content_type or "").lower()
    stripped = (body_text or "").lstrip()
    if "text/html" in ct_lower or stripped.startswith(("<!DOCTYPE", "<html", "<HTML", "<head", "<body")):
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=200,
            response_ms=ms,
            error="impostor: HTTP 200 with HTML body instead of RustChain /health JSON",
        )

    try:
        data = json.loads(body_text)
    except (ValueError, TypeError) as exc:
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=200,
            response_ms=ms,
            error=f"impostor: HTTP 200 with non-JSON body ({exc})",
        )

    if not isinstance(data, dict):
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=200,
            response_ms=ms,
            error="impostor: HTTP 200 JSON payload is not an object",
        )

    # A genuine RustChain node /health payload carries 'ok', 'version', and 'uptime_s' (or 'uptime')
    has_ok = "ok" in data and isinstance(data.get("ok"), bool)
    has_version = isinstance(data.get("version"), str) and bool(data.get("version", "").strip())
    uptime_raw = data.get("uptime_s", data.get("uptime", data.get("uptime_seconds")))
    has_uptime = isinstance(uptime_raw, (int, float)) and not isinstance(uptime_raw, bool)

    if not (has_ok and has_version and has_uptime):
        missing = [
            name
            for name, present in (("ok", has_ok), ("version", has_version), ("uptime_s", has_uptime))
            if not present
        ]
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=200,
            response_ms=ms,
            error=f"impostor: HTTP 200 JSON missing RustChain /health keys: {', '.join(missing)}",
            raw_data=data,
        )

    ok_flag = bool(data["ok"])
    version = str(data["version"])
    uptime_s = float(uptime_raw)
    db_rw = data.get("db_rw") if isinstance(data.get("db_rw"), bool) else None
    tip_age = data.get("tip_age_slots") if isinstance(data.get("tip_age_slots"), int) else None
    backup_age = (
        float(data["backup_age_hours"])
        if isinstance(data.get("backup_age_hours"), (int, float))
        else None
    )
    active_miners = data.get("active_miners", data.get("miners"))
    epoch = data.get("epoch", data.get("current_epoch"))

    degraded_reasons = []
    if not ok_flag:
        degraded_reasons.append("ok=false")
    if db_rw is False:
        degraded_reasons.append("db_rw=false")
    if tip_age is not None and tip_age > tip_age_threshold_slots:
        degraded_reasons.append(f"tip_age_slots={tip_age}>{tip_age_threshold_slots}")

    if degraded_reasons:
        return ProbeResult(
            url=url,
            state="degraded",
            http_status=200,
            response_ms=ms,
            version=version,
            uptime_s=uptime_s,
            db_rw=db_rw,
            tip_age_slots=tip_age,
            backup_age_hours=backup_age,
            active_miners=active_miners,
            epoch=epoch,
            error="degraded: " + ", ".join(degraded_reasons),
            raw_data=data,
        )

    return ProbeResult(
        url=url,
        state="up",
        http_status=200,
        response_ms=ms,
        version=version,
        uptime_s=uptime_s,
        db_rw=db_rw,
        tip_age_slots=tip_age,
        backup_age_hours=backup_age,
        active_miners=active_miners,
        epoch=epoch,
        error=None,
        raw_data=data,
    )


def probe_health(
    url: str,
    timeout: float = 10.0,
    verify_tls: Any = True,
    tip_age_threshold_slots: int = DEFAULT_TIP_AGE_THRESHOLD_SLOTS,
    http_SimpleGetter: Optional[Callable[[str, float], tuple]] = None,
) -> ProbeResult:
    """Probe a node's ``/health`` URL and validate its body."""
    target_url = url if url.rstrip("/").endswith("/health") else f"{url.rstrip('/')}/health"
    start = time.monotonic()

    try:
        if http_SimpleGetter is not None:
            status_code, body_text, content_type = http_SimpleGetter(target_url, timeout)
            elapsed_ms = (time.monotonic() - start) * 1000.0
            return classify_health_response(
                target_url,
                status_code,
                body_text,
                content_type=content_type,
                response_ms=elapsed_ms,
                tip_age_threshold_slots=tip_age_threshold_slots,
            )

        context = None
        if target_url.startswith("https://"):
            if verify_tls is False:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            elif isinstance(verify_tls, str) and verify_tls:
                context = ssl.create_default_context(cafile=verify_tls)

        req = urllib.request.Request(
            target_url,
            headers={"Accept": "application/json", "User-Agent": "RustChain-NodeProbe/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            status_code = resp.status
            content_type = resp.headers.get("Content-Type", "")
            body_text = resp.read().decode("utf-8", errors="replace")

        return classify_health_response(
            target_url,
            status_code,
            body_text,
            content_type=content_type,
            response_ms=elapsed_ms,
            tip_age_threshold_slots=tip_age_threshold_slots,
        )
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return ProbeResult(
            url=target_url,
            state="down",
            http_status=exc.code,
            response_ms=round(elapsed_ms, 2),
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        return ProbeResult(
            url=target_url,
            state="unreachable",
            http_status=None,
            response_ms=round(elapsed_ms, 2),
            error=str(exc)[:200],
        )
