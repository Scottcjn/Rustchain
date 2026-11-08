#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recorded-fixture tests for ``monitoring/node_probe.py`` and all five monitors (#17180).

Covers the six required fixtures:
1. Genuine ``/health`` body (recorded from ``https://50.28.86.131/health``) -> ``up``
2. HTML SPA body with HTTP 200 -> ``impostor`` (never ``up``)
3. JSON body missing required keys (``ok``, ``version``, ``uptime_s``) -> ``impostor``
4. Genuine node with ``ok: false`` (or ``db_rw: false`` / stale ``tip_age_slots``) -> ``degraded``
5. HTTP 500 -> ``down``
6. Timeout / connection error -> ``unreachable``

And asserts that every one of the five monitors:
- ``status/status_server.py``
- ``health-dashboard/server.py``
- ``monitoring/rustchain-exporter.py``
- ``tools/node_health_monitor.py``
- ``tools/node-health-cli/node_health.py``
classifies the HTML-200 fixture as ``impostor`` (and never ``up``/healthy).
"""

from __future__ import annotations

import importlib.util
import io
import json
import socket
import sys
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

# Locate repository root robustly whether invoked from tests/ or monitoring/tests/
ROOT = next((p for p in Path(__file__).resolve().parents if (p / "monitoring" / "node_probe.py").exists()), Path(__file__).resolve().parent.parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitoring.node_probe import (
    ProbeResult,
    probe_health,
    validate_health_response,
    validate_requests_response,
)

# ---------------------------------------------------------------------------
# Recorded Fixtures
# ---------------------------------------------------------------------------

FIXTURE_GENUINE_HEALTH_JSON = json.dumps(
    {
        "backup_age_hours": 4.994941502544615,
        "db_rw": True,
        "ok": True,
        "tip_age_slots": 0,
        "uptime_s": 867443,
        "version": "2.2.1-rip200",
    }
)

FIXTURE_HTML_SPA_200 = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"/><title>Welcome to Parked Domain SPA</title></head>\n"
    "<body><div id=\"root\">Loading application...</div><script src=\"/app.js\"></script></body>\n"
    "</html>"
)

FIXTURE_JSON_MISSING_KEYS = json.dumps(
    {"status": "ok", "service": "unrelated-json-service"}
)

FIXTURE_JSON_OK_FALSE = json.dumps(
    {
        "ok": False,
        "version": "2.2.1-rip200",
        "uptime_s": 867443,
        "db_rw": True,
        "tip_age_slots": 0,
    }
)

FIXTURE_JSON_DB_RW_FALSE = json.dumps(
    {
        "ok": True,
        "version": "2.2.1-rip200",
        "uptime_s": 867443,
        "db_rw": False,
        "tip_age_slots": 0,
    }
)

FIXTURE_JSON_STALE_TIP = json.dumps(
    {
        "ok": True,
        "version": "2.2.1-rip200",
        "uptime_s": 867443,
        "db_rw": True,
        "tip_age_slots": 500,
    }
)


class _FakeUrllibResponse:
    """In-memory context manager mimicking ``urllib.request.urlopen`` response."""

    def __init__(
        self,
        body: str,
        status: int = 200,
        content_type: str = "application/json",
    ):
        self._raw = body.encode("utf-8")
        self.status = status
        self.code = status
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeUrllibResponse":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def _make_requests_mock(
    body: str,
    status_code: int = 200,
    content_type: str = "application/json",
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.text = body
    resp.content = body.encode("utf-8")
    try:
        parsed = json.loads(body)
        resp.json.return_value = parsed
    except ValueError as exc:
        resp.json.side_effect = ValueError(str(exc))
    return resp


def _load_module(name: str, rel_path: str):
    full_path = ROOT / rel_path
    parent = str(full_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(name, full_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Core monitoring.node_probe tests across all recorded fixtures
# ---------------------------------------------------------------------------


def test_probe_health_genuine_fixture_is_up():
    res = probe_health(
        "https://50.28.86.131/health",
        timeout=5,
        opener=lambda req, timeout=5: _FakeUrllibResponse(FIXTURE_GENUINE_HEALTH_JSON),
    )
    assert res.state == "up"
    assert res.ok is True
    assert res.is_up is True
    assert res.is_impostor is False
    assert res.version == "2.2.1-rip200"
    assert res.uptime_s == 867443
    assert res.db_rw is True
    assert res.tip_age_slots == 0
    assert res.error is None


@pytest.mark.parametrize(
    "content_type",
    [
        "text/html; charset=utf-8",
        "application/json",  # Even if a misconfigured SPA sends application/json with HTML body
    ],
)
def test_probe_health_html_200_fixture_is_impostor(content_type: str):
    res = probe_health(
        "https://50.28.86.131/health",
        timeout=5,
        opener=lambda req, timeout=5: _FakeUrllibResponse(
            FIXTURE_HTML_SPA_200, status=200, content_type=content_type
        ),
    )
    assert res.state == "impostor"
    assert res.ok is False
    assert res.is_up is False
    assert res.is_impostor is True
    assert res.status_code == 200
    assert res.error is not None and "impostor" in res.error.lower()


@pytest.mark.parametrize(
    "bad_json",
    [
        FIXTURE_JSON_MISSING_KEYS,
        json.dumps({"ok": True, "version": "2.2.1-rip200"}),  # missing uptime_s
        json.dumps({"ok": True, "uptime_s": 100}),  # missing version
        json.dumps({"version": "2.2.1-rip200", "uptime_s": 100}),  # missing ok
        json.dumps(["array", "not", "object"]),
        "plain text 200 OK",
    ],
)
def test_probe_health_json_missing_keys_or_non_object_is_impostor(bad_json: str):
    res = probe_health(
        "https://50.28.86.131/health",
        timeout=5,
        opener=lambda req, timeout=5: _FakeUrllibResponse(bad_json, status=200),
    )
    assert res.state == "impostor"
    assert res.ok is False


@pytest.mark.parametrize(
    "degraded_fixture,expected_substr",
    [
        (FIXTURE_JSON_OK_FALSE, "ok=false"),
        (FIXTURE_JSON_DB_RW_FALSE, "db_rw=false"),
        (FIXTURE_JSON_STALE_TIP, "tip_age_slots=500"),
    ],
)
def test_probe_health_degraded_fixtures(degraded_fixture: str, expected_substr: str):
    res = probe_health(
        "https://50.28.86.131/health",
        timeout=5,
        opener=lambda req, timeout=5: _FakeUrllibResponse(degraded_fixture, status=200),
    )
    assert res.state == "degraded"
    assert res.ok is False
    assert res.is_degraded is True
    assert res.version == "2.2.1-rip200"
    assert expected_substr in (res.error or "")


def test_probe_health_http_500_fixture_is_down():
    def _raise_500(req, timeout=5):
        raise urllib.error.HTTPError(
            req.full_url, 500, "Internal Server Error", {}, io.BytesIO(b"error")
        )

    res = probe_health("https://50.28.86.131/health", timeout=5, opener=_raise_500)
    assert res.state == "down"
    assert res.ok is False
    assert res.status_code == 500
    assert "500" in (res.error or "")


def test_probe_health_timeout_fixture_is_unreachable():
    def _raise_timeout(req, timeout=5):
        raise socket.timeout("timed out waiting for node")

    res = probe_health("https://50.28.86.131/health", timeout=5, opener=_raise_timeout)
    assert res.state == "unreachable"
    assert res.ok is False
    assert res.status_code is None
    assert "timeout" in (res.error or "").lower()


# ---------------------------------------------------------------------------
# 2. All Five Monitors: HTML-200 fixture -> impostor (never up)
# ---------------------------------------------------------------------------


def test_monitor_1_status_server_html_200_is_impostor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("STATUS_DATA_DIR", str(tmp_path))
    with patch("requests.get", return_value=_make_requests_mock(FIXTURE_GENUINE_HEALTH_JSON)):
        status_mod = _load_module("status_server_under_test", "status/status_server.py")

    html_mock = _make_requests_mock(
        FIXTURE_HTML_SPA_200, status_code=200, content_type="text/html; charset=utf-8"
    )
    with patch.object(status_mod.requests, "get", return_value=html_mock):
        res = status_mod.check_node(status_mod.NODES[0])
    assert res["up"] is False
    assert res["state"] == "impostor"
    assert "impostor" in (res.get("error") or "").lower()

    # Missing keys on 200 also reports impostor, never up
    missing_mock = _make_requests_mock(FIXTURE_JSON_MISSING_KEYS, status_code=200)
    with patch.object(status_mod.requests, "get", return_value=missing_mock):
        res_missing = status_mod.check_node(status_mod.NODES[0])
    assert res_missing["up"] is False
    assert res_missing["state"] == "impostor"


def test_monitor_2_health_dashboard_html_200_is_impostor():
    hd_mod = _load_module("health_dashboard_under_test", "health-dashboard/server.py")
    html_mock = _make_requests_mock(
        FIXTURE_HTML_SPA_200, status_code=200, content_type="text/html; charset=utf-8"
    )
    with patch.object(hd_mod.requests, "get", return_value=html_mock):
        status = hd_mod.check_node_health(hd_mod.NODES[0])
    assert status.status == "impostor"
    assert status.status != "up"
    assert "impostor" in (status.error or "").lower()

    # Genuine fixture -> up
    up_mock = _make_requests_mock(FIXTURE_GENUINE_HEALTH_JSON, status_code=200)
    with patch.object(hd_mod.requests, "get", return_value=up_mock):
        status_up = hd_mod.check_node_health(hd_mod.NODES[0])
    assert status_up.status == "up"
    assert status_up.version == "2.2.1-rip200"


def test_monitor_3_prometheus_exporter_zeros_gauge_on_impostor_and_tracks_timestamp():
    from prometheus_client import REGISTRY

    # Reuse already-loaded exporter module if present to avoid duplicate Prometheus registration
    exp_mod = sys.modules.get("rustchain_exporter_under_test")
    if exp_mod is None:
        exp_mod = _load_module(
            "rustchain_exporter_under_test", "monitoring/rustchain-exporter.py"
        )
        sys.modules["rustchain_exporter_under_test"] = exp_mod

    # 1. Genuine healthy scrape sets rustchain_node_health=1 and updates last_successful_scrape_timestamp
    up_mock = _make_requests_mock(FIXTURE_GENUINE_HEALTH_JSON, status_code=200)
    with patch.object(exp_mod.requests, "get", return_value=up_mock), patch.object(
        exp_mod, "fetch_json", return_value=None
    ):
        exp_mod.collect_metrics()

    assert REGISTRY.get_sample_value("rustchain_node_health") == 1.0
    ts_val = REGISTRY.get_sample_value("rustchain_last_successful_scrape_timestamp")
    assert ts_val is not None and ts_val > 0

    # 2. HTML-200 impostor scrape MUST drop rustchain_node_health from 1 -> 0!
    html_mock = _make_requests_mock(
        FIXTURE_HTML_SPA_200, status_code=200, content_type="text/html"
    )
    with patch.object(exp_mod.requests, "get", return_value=html_mock), patch.object(
        exp_mod, "fetch_json", return_value=None
    ):
        exp_mod.collect_metrics()

    assert REGISTRY.get_sample_value("rustchain_node_health") == 0.0

    # 3. Timeout / connection error ALSO keeps/sets rustchain_node_health to 0
    exp_mod.node_health.set(1)
    with patch.object(
        exp_mod.requests, "get", side_effect= RuntimeError("connection refused")
    ), patch.object(exp_mod, "fetch_json", return_value=None):
        exp_mod.collect_metrics()

    assert REGISTRY.get_sample_value("rustchain_node_health") == 0.0


def test_monitor_4_node_health_monitor_html_200_is_impostor():
    from tools.node_health_monitor import NodeHealthMonitor

    mon = NodeHealthMonitor(nodes=["http://50.28.86.131:8088"], timeout=5)
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeUrllibResponse(
            FIXTURE_HTML_SPA_200, status=200, content_type="text/html"
        ),
    ):
        status = mon.check_node("http://50.28.86.131:8088")

    assert status.status == "impostor"
    assert status.state == "impostor"
    assert status.status not in ("online", "up")
    net_health = mon.get_network_health([status])
    assert net_health.nodes_online == 0
    assert any("impostor" in a.lower() for a in net_health.alerts)


def test_monitor_5_node_health_cli_html_200_is_impostor():
    cli_mod = _load_module(
        "node_health_cli_under_test", "tools/node-health-cli/node_health.py"
    )
    with patch.object(
        cli_mod,
        "urlopen",
        return_value=_FakeUrllibResponse(
            FIXTURE_HTML_SPA_200, status=200, content_type="text/html"
        ),
    ):
        h_status = cli_mod.check_health("https://50.28.86.131", timeout=5)

    assert h_status.ok is False
    assert h_status.state == "impostor"
    assert "impostor" in (h_status.error or "").lower()
