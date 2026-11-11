#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""HTML-200 must come out "impostor" in EVERY monitor's output (issue #17180).

Five monitors, one shared validator (monitoring/node_probe.py). Each test here
drives the real monitor module with the recorded SPA-HTML-200 fixture and
asserts its own output distinguishes the impostor from a genuine node — plus a
genuine-body case so hardening never makes a real node look broken.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(
        name, str(REPO_ROOT / rel_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


probe = _load("node_probe", "monitoring/node_probe.py")

# Same recorded fixtures as tests/test_node_probe.py (kept duplicated on
# purpose: each monitor test must stand on its own).
REAL_HEALTH_BODY = {
    "ok": True, "version": "2.2.1", "uptime_s": 86400, "db_rw": True,
    "backup_age_hours": 1.5, "tip_age_slots": 3, "active_miners": 21, "epoch": 174,
}
SPA_HTML_BODY = (
    '<!doctype html><html lang="en"><head><title>New API</title></head>'
    '<body><div id="root"></div><script src="/static/js/main.js"></script>'
    "</body></html>"
)


class _FakeRequestsResp:
    """Stand-in for requests.Response (status_code / headers / json)."""

    def __init__(self, status_code=200, content_type="application/json", body=""):
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.text = body

    def json(self):
        return json.loads(self.text)  # raises ValueError on HTML — like requests


class _FakeUrlResp(io.BytesIO):
    """Stand-in for the urlopen context manager, with headers."""

    def __init__(self, payload: bytes, content_type: str = "application/json"):
        super().__init__(payload)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ── Monitor 1: status/status_server.py ────────────────────────────────────────

# The module polls all four nodes at import time; keep that offline and cheap.
os.environ.setdefault("STATUS_DATA_DIR", tempfile.mkdtemp(prefix="rc-status-test-"))
with mock.patch("requests.get", side_effect=ConnectionError("offline")):
    status_server = _load("status_server", "status/status_server.py")


def test_status_server_html_200_is_impostor():
    resp = _FakeRequestsResp(200, "text/html; charset=utf-8", SPA_HTML_BODY)
    with mock.patch("requests.get", return_value=resp):
        result = status_server.check_node(status_server.NODES[0])
    assert result["state"] == "impostor"
    assert result["up"] is False, "the status page must not count an SPA as a node"


def test_status_server_genuine_body_is_up():
    resp = _FakeRequestsResp(200, "application/json", json.dumps(REAL_HEALTH_BODY))
    with mock.patch("requests.get", return_value=resp):
        result = status_server.check_node(status_server.NODES[0])
    assert result["state"] == "up"
    assert result["up"] is True


# ── Monitor 2: health-dashboard/server.py ─────────────────────────────────────

dashboard = _load("rc_health_dashboard", "health-dashboard/server.py")


def test_dashboard_html_200_is_impostor():
    resp = _FakeRequestsResp(200, "text/html; charset=utf-8", SPA_HTML_BODY)
    with mock.patch("requests.get", return_value=resp):
        st = dashboard.check_node_health(dashboard.NODES[0])
    assert st.status == "impostor"
    assert st.error and "not a RustChain node" in st.error


def test_dashboard_genuine_body_is_up():
    resp = _FakeRequestsResp(200, "application/json", json.dumps(REAL_HEALTH_BODY))
    with mock.patch("requests.get", return_value=resp):
        st = dashboard.check_node_health(dashboard.NODES[0])
    assert st.status == "up"
    assert st.version == "2.2.1"


# ── Monitor 3: monitoring/rustchain-exporter.py ───────────────────────────────

class _FakeMetric:
    """Records every set/inc/info so the test can read exported values."""

    def __init__(self, *args, **kwargs):
        self.values = []

    def set(self, value):
        self.values.append(value)

    def inc(self, amount=1):
        self.values.append(("inc", amount))

    def info(self, items):
        self.values.append(("info", items))

    def labels(self, **_labels):
        return self


def _load_exporter():
    stub = types.ModuleType("prometheus_client")
    stub.Gauge = _FakeMetric
    stub.Counter = _FakeMetric
    stub.Info = _FakeMetric
    stub.start_http_server = lambda *a, **k: None
    sys.modules["prometheus_client"] = stub
    return _load("rc_monitoring_exporter", "monitoring/rustchain-exporter.py")


def test_exporter_gauge_zero_and_no_timestamp_on_html_200():
    exporter = _load_exporter()
    html_verdict = probe.classify_response(200, "text/html; charset=utf-8", body=SPA_HTML_BODY)
    assert html_verdict.state == "impostor"
    with mock.patch.object(exporter, "probe_health", return_value=html_verdict), \
            mock.patch("requests.get", side_effect=ConnectionError("offline")):
        exporter.collect_metrics()
    assert exporter.node_health.values[-1] == 0, "failed scrape must drive the gauge to 0"
    assert exporter.last_successful_scrape_timestamp.values == [], \
        "an impostor scrape is not a successful scrape"


def test_exporter_gauge_one_and_timestamp_on_real_node():
    exporter = _load_exporter()
    real_verdict = probe.classify_response(200, "application/json", body=json.dumps(REAL_HEALTH_BODY))
    with mock.patch.object(exporter, "probe_health", return_value=real_verdict), \
            mock.patch("requests.get", side_effect=ConnectionError("offline")):
        exporter.collect_metrics()
    assert 1 in exporter.node_health.values
    assert len(exporter.last_successful_scrape_timestamp.values) == 1


# ── Monitor 4: tools/node_health_monitor.py ───────────────────────────────────

monitor = _load("node_health_monitor", "tools/node_health_monitor.py")


def _monitor_probe(payload: bytes, content_type: str = "application/json"):
    mon = monitor.NodeHealthMonitor(nodes=["http://example.invalid"])
    with mock.patch.object(monitor.urllib.request, "urlopen",
                           return_value=_FakeUrlResp(payload, content_type)):
        return mon.check_node("http://example.invalid")


def test_cli_monitor_html_200_is_impostor():
    st = _monitor_probe(SPA_HTML_BODY.encode(), "text/html; charset=utf-8")
    assert st.status == "offline"
    assert st.state == "impostor"
    assert "non-JSON" in st.error


def test_cli_monitor_genuine_epoch_body_is_up():
    st = _monitor_probe(json.dumps({"epoch": 254, "enrolled_miners": 16}).encode())
    assert st.status == "online"
    assert st.state == "up"


def test_cli_monitor_network_health_alerts_on_impostor():
    st = monitor.NodeStatus(url="http://x", status="offline", response_time_ms=5.0,
                            epoch=None, miners=None, error="not JSON", state="impostor")
    health = monitor.NodeHealthMonitor().get_network_health([st])
    assert any("IMPOSTOR" in a for a in health.alerts)


# ── Monitor 5: tools/node-health-cli/node_health.py ───────────────────────────

cli = _load("rc_node_health_cli", "tools/node-health-cli/node_health.py")


def test_cli_html_200_is_impostor():
    with mock.patch.object(cli, "urlopen", return_value=_FakeUrlResp(SPA_HTML_BODY.encode())):
        hs = cli.check_health("http://example.invalid", timeout=5)
    assert hs.state == "impostor"
    assert hs.ok is False
    assert hs.error and "impostor" in hs.error


def test_cli_genuine_body_is_up():
    body = json.dumps(REAL_HEALTH_BODY).encode()
    with mock.patch.object(cli, "urlopen", return_value=_FakeUrlResp(body)):
        hs = cli.check_health("http://example.invalid", timeout=5)
    assert hs.state == "up"
    assert hs.ok is True


def test_cli_ok_false_is_degraded_not_up():
    body = json.dumps(dict(REAL_HEALTH_BODY, ok=False)).encode()
    with mock.patch.object(cli, "urlopen", return_value=_FakeUrlResp(body)):
        hs = cli.check_health("http://example.invalid", timeout=5)
    assert hs.state == "degraded"
    assert hs.ok is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
