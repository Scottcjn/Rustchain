#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unified RustChain Node Liveness & Impostor Validator (Bounty #17180 Solution).

Stdlib-only (Python 3.9+) shared `/health` body validator for all five RustChain monitors:
  1. `status/status_server.py` (`check_node()`)
  2. `health-dashboard/server.py` (`check_node_health()`)
  3. `monitoring/rustchain-exporter.py` (`fetch_json()` + Prometheus gauges)
  4. `tools/node_health_monitor.py`
  5. `tools/node-health-cli/node_health.py`

States:
  - `up`: HTTP 200, JSON Content-Type, valid JSON dict containing `ok: True`, `version` (non-empty str),
    `uptime_s` (number >= 0), optional `db_rw` is not False, and `tip_age_slots` <= threshold.
  - `impostor`: HTTP 200 where `Content-Type` is `text/html`, OR body is not valid JSON object,
    OR JSON object is missing required keys (`ok`, `version`, `uptime_s`).
  - `degraded`: Valid RustChain `/health` JSON object where `ok` is False, `db_rw` is False,
    or `tip_age_slots` > `max_tip_age_slots`.
  - `down`: Non-200 HTTP status code (e.g., 500, 502, 503, 404).
  - `unreachable`: Network timeout, DNS failure, connection refused, or TLS error.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

VALID_STATES = ("up", "down", "impostor", "degraded", "unreachable")
REQUIRED_HEALTH_KEYS = ("ok", "version", "uptime_s")


@dataclass(frozen=True)
class ProbeResult:
    url: str
    state: str  # "up" | "down" | "impostor" | "degraded" | "unreachable"
    http_status: Optional[int]
    content_type: str
    version: Optional[str]
    uptime_s: Optional[float]
    db_rw: Optional[bool]
    tip_age_slots: Optional[int]
    reason: str
    latency_ms: float
    checked_at: float
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_up(self) -> bool:
        return self.state == "up"

    @property
    def is_impostor(self) -> bool:
        return self.state == "impostor"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["up"] = self.state == "up"
        return d


HttpFetcher = Callable[[str, float], Tuple[int, Dict[str, str], bytes]]


def _default_fetcher(url: str, timeout: float) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "RustChain-NodeProbe/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers, resp.read(65536)
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        body = exc.read(65536) if exc.fp else b""
        return exc.code, headers, body


def probe_health(
    url: str,
    timeout: float = 5.0,
    max_tip_age_slots: int = 120,
    fetcher: Optional[HttpFetcher] = None,
) -> ProbeResult:
    """Validate `/health` HTTP status, Content-Type, and JSON schema to prevent SPA impostor green-lighting."""
    t0 = time.monotonic()
    now = time.time()
    do_fetch = fetcher or _default_fetcher

    try:
        status, headers, raw_bytes = do_fetch(url, timeout)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
        latency_ms = round((time.monotonic() - t0) * 1000.0, 2)
        return ProbeResult(
            url=url,
            state="unreachable",
            http_status=None,
            content_type="",
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason=f"unreachable: {type(exc).__name__}: {exc}",
            latency_ms=latency_ms,
            checked_at=now,
        )

    latency_ms = round((time.monotonic() - t0) * 1000.0, 2)
    ctype = str(headers.get("content-type") or "").lower()

    if status != 200:
        return ProbeResult(
            url=url,
            state="down",
            http_status=status,
            content_type=ctype,
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason=f"HTTP {status}",
            latency_ms=latency_ms,
            checked_at=now,
        )

    # HTTP 200 received: check for HTML impostor Content-Type or HTML body prefix
    text_body = raw_bytes.decode("utf-8", errors="replace").strip()
    if "text/html" in ctype or text_body.lower().startswith(("<!doctype html", "<html")):
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=status,
            content_type=ctype,
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason="impostor: HTTP 200 returned HTML instead of RustChain JSON",
            latency_ms=latency_ms,
            checked_at=now,
        )

    try:
        data = json.loads(text_body)
    except (ValueError, TypeError):
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=status,
            content_type=ctype,
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason="impostor: HTTP 200 body is not valid JSON",
            latency_ms=latency_ms,
            checked_at=now,
        )

    if not isinstance(data, dict):
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=status,
            content_type=ctype,
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason="impostor: JSON root is not an object",
            latency_ms=latency_ms,
            checked_at=now,
        )

    missing_keys = [k for k in REQUIRED_HEALTH_KEYS if k not in data]
    if missing_keys:
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=status,
            content_type=ctype,
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason=f"impostor: JSON missing required keys: {', '.join(missing_keys)}",
            latency_ms=latency_ms,
            checked_at=now,
            raw_data=data,
        )

    ok_val = data.get("ok")
    version_val = data.get("version")
    uptime_val = data.get("uptime_s")

    if not isinstance(ok_val, bool) or not isinstance(version_val, str) or not version_val.strip():
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=status,
            content_type=ctype,
            version=None,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason="impostor: invalid types for ok/version",
            latency_ms=latency_ms,
            checked_at=now,
            raw_data=data,
        )

    try:
        uptime_f = float(uptime_val)
        if uptime_f < 0:
            raise ValueError("negative uptime")
    except (TypeError, ValueError):
        return ProbeResult(
            url=url,
            state="impostor",
            http_status=status,
            content_type=ctype,
            version=version_val,
            uptime_s=None,
            db_rw=None,
            tip_age_slots=None,
            reason="impostor: invalid uptime_s",
            latency_ms=latency_ms,
            checked_at=now,
            raw_data=data,
        )

    db_rw = data.get("db_rw")
    tip_age = data.get("tip_age_slots")

    # Check degraded conditions on genuine RustChain node responses
    degraded_reasons = []
    if ok_val is False:
        degraded_reasons.append("ok is false")
    if db_rw is False:
        degraded_reasons.append("db_rw is false")
    if isinstance(tip_age, (int, float)) and tip_age > max_tip_age_slots:
        degraded_reasons.append(f"tip_age_slots ({tip_age}) > {max_tip_age_slots}")

    if degraded_reasons:
        return ProbeResult(
            url=url,
            state="degraded",
            http_status=status,
            content_type=ctype,
            version=version_val,
            uptime_s=uptime_f,
            db_rw=db_rw if isinstance(db_rw, bool) else None,
            tip_age_slots=int(tip_age) if isinstance(tip_age, (int, float)) else None,
            reason="degraded: " + "; ".join(degraded_reasons),
            latency_ms=latency_ms,
            checked_at=now,
            raw_data=data,
        )

    return ProbeResult(
        url=url,
        state="up",
        http_status=status,
        content_type=ctype,
        version=version_val,
        uptime_s=uptime_f,
        db_rw=db_rw if isinstance(db_rw, bool) else True,
        tip_age_slots=int(tip_age) if isinstance(tip_age, (int, float)) else 0,
        reason="ok",
        latency_ms=latency_ms,
        checked_at=now,
        raw_data=data,
    )


class PrometheusNodeExporterState:
    """Tracks rustchain_node_health and rustchain_last_successful_scrape_timestamp gauges."""

    def __init__(self) -> None:
        self.node_health: Dict[str, int] = {}
        self.node_state: Dict[str, str] = {}
        self.last_successful_scrape_ts: Dict[str, float] = {}

    def record_probe(self, node_id: str, result: ProbeResult) -> Dict[str, Any]:
        if result.state == "up":
            self.node_health[node_id] = 1
            self.last_successful_scrape_ts[node_id] = result.checked_at
        else:
            # Must explicitly set gauge to 0 on ANY failed/impostor/degraded/unreachable scrape
            self.node_health[node_id] = 0
        self.node_state[node_id] = result.state
        return {
            "rustchain_node_health": self.node_health[node_id],
            "rustchain_node_state": self.node_state[node_id],
            "rustchain_last_successful_scrape_timestamp": self.last_successful_scrape_ts.get(node_id, 0.0),
        }
