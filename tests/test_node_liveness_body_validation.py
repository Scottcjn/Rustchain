# SPDX-License-Identifier: MIT
"""Issue #17180 — monitors must validate the /health BODY, not just HTTP 200.

Recorded fixtures for the real incident: an attestation node's IP was repurposed
to serve an unrelated SPA, every path answered 200 with HTML, and all five
monitors kept reporting the host healthy forever. Every monitor must now report
that answer as "impostor", never "up".
"""
import importlib.util
import json
import os
import socket
import sys
import tempfile
import types
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "monitoring"))

# ── Recorded fixtures ────────────────────────────────────────────────────────

GENUINE_HEALTH = {
    "ok": True,
    "version": "2.2.1",
    "uptime_s": 86400,
    "db_rw": True,
    "backup_age_hours": 1.5,
    "tip_age_slots": 1,
    "epoch": 312,
    "enrolled_miners": 7,
}
GENUINE_HEALTH_BODY = json.dumps(GENUINE_HEALTH)

# The SPA that actually hijacked an attestation IP: HTTP 200, text/html on
# every path including /health and /epoch.
SPA_HTML_200 = (
    "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
    "<title>Frontend App</title></head><body><div id='root'></div>"
    "<script src='/assets/index-abc123.js'></script></body></html>"
)

# JSON, served with 200, but carrying none of ok/version/uptime_s.
KEYLESS_JSON_BODY = json.dumps({"status": "ok", "service": "frontend-app"})

# A genuine node reporting its own problems.
OK_FALSE_HEALTH_BODY = json.dumps({**GENUINE_HEALTH, "ok": False})


def _load(name, rel_path):
    """Load a repo file as a module (monitors live outside any package)."""
    spec = importlib.util.spec_from_file_location(name, str(REPO_ROOT / rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


import node_probe  # noqa: E402 — the shared probe all monitors bootstrap-import


# ── Shared probe (monitoring/node_probe.py) ──────────────────────────────────


class FakeHTTPResponse:
    """Stands in for a successful urlopen/requests answer (2xx only)."""

    def __init__(self, body, content_type="application/json", status_code=200):
        self._body = body.encode() if isinstance(body, str) else body
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code

    def read(self):
        return self._body

    def json(self):
        # Mirrors requests.Response.json(): raises ValueError on non-JSON.
        return json.loads(self._body.decode())

    def raise_for_status(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(body, content_type="application/json"):
    def _open(req, timeout=None):
        return FakeHTTPResponse(body, content_type)
    return _open


def _raiser(exc):
    def _open(req, timeout=None):
        raise exc
    return _open


HTTP_500 = urllib.error.HTTPError(
    "https://node.example/health", 500, "Internal Server Error", None, None
)


def test_probe_genuine_body_is_up():
    result = node_probe.probe_health("https://node.example/health", opener=_opener(GENUINE_HEALTH_BODY))
    assert result.state == "up"
    assert result.status_code == 200
    assert result.data["version"] == "2.2.1"
    assert result.reason is None


def test_probe_html_200_is_impostor_never_up():
    result = node_probe.probe_health("https://node.example/health", opener=_opener(SPA_HTML_200, "text/html"))
    assert result.state == "impostor"
    assert "not a JSON object" in result.reason


def test_probe_keyless_json_200_is_impostor():
    result = node_probe.probe_health("https://node.example/health", opener=_opener(KEYLESS_JSON_BODY))
    assert result.state == "impostor"
    assert "ok/version/uptime_s" in result.reason


def test_probe_html_body_with_json_content_type_is_still_impostor():
    # A parking page can set Content-Type: application/json on garbage.
    result = node_probe.probe_health("https://node.example/health", opener=_opener(SPA_HTML_200))
    assert result.state == "impostor"


def test_probe_ok_false_is_degraded():
    result = node_probe.probe_health("https://node.example/health", opener=_opener(OK_FALSE_HEALTH_BODY))
    assert result.state == "degraded"
    assert "ok=false" in result.reason


@pytest.mark.parametrize(
    "field,value,fragment",
    [("db_rw", False, "db_rw=false"), ("tip_age_slots", 10_000, "tip_age_slots")],
)
def test_probe_degraded_signals(field, value, fragment):
    body = json.dumps({**GENUINE_HEALTH, field: value})
    state, reason = node_probe.classify_health_data(200, "application/json", json.loads(body))
    assert state == "degraded"
    assert fragment in reason


def test_probe_http_500_is_down():
    result = node_probe.probe_health("https://node.example/health", opener=_raiser(HTTP_500))
    assert result.state == "down"
    assert result.status_code == 500


def test_probe_timeout_is_unreachable():
    result = node_probe.probe_health("https://node.example/health", opener=_raiser(socket.timeout("timed out")))
    assert result.state == "unreachable"


def test_probe_connection_refused_is_unreachable():
    result = node_probe.probe_health(
        "https://node.example/health",
        opener=_raiser(urllib.error.URLError("Connection refused")),
    )
    assert result.state == "unreachable"
    assert "Connection refused" in result.reason


# ── Monitor 1: status/status_server.py check_node() ──────────────────────────

os.environ.setdefault("STATUS_DATA_DIR", tempfile.mkdtemp(prefix="rc-status-17180-"))
with patch("requests.get", return_value=FakeHTTPResponse(GENUINE_HEALTH_BODY)):
    status_server = _load("status_server_17180", "status/status_server.py")


def test_status_server_genuine_body_is_up():
    with patch.object(status_server.requests, "get", return_value=FakeHTTPResponse(GENUINE_HEALTH_BODY)):
        result = status_server.check_node(status_server.NODES[0])
    assert result["up"] is True
    assert result["state"] == "up"
    assert result["version"] == "2.2.1"


def test_status_server_html_200_is_impostor():
    resp = FakeHTTPResponse(SPA_HTML_200, "text/html")
    resp.json = Mock(side_effect=ValueError("Expecting value: line 1 column 1"))
    with patch.object(status_server.requests, "get", return_value=resp):
        result = status_server.check_node(status_server.NODES[0])
    assert result["state"] == "impostor"
    assert result["up"] is False  # never green on a bare 200 again


def test_status_server_ok_false_is_degraded_not_up():
    resp = FakeHTTPResponse(OK_FALSE_HEALTH_BODY)
    with patch.object(status_server.requests, "get", return_value=resp):
        result = status_server.check_node(status_server.NODES[0])
    assert result["state"] == "degraded"


def test_status_server_http_500_is_down():
    resp = FakeHTTPResponse("err", "text/plain", status_code=500)
    with patch.object(status_server.requests, "get", return_value=resp):
        result = status_server.check_node(status_server.NODES[0])
    assert result["state"] == "down"
    assert result["up"] is False


# ── Monitor 2: health-dashboard/server.py check_node_health() ────────────────

dashboard = _load("health_dashboard_17180", "health-dashboard/server.py")


def _dash_resp(body, content_type="application/json", status_code=200):
    resp = Mock()
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    if status_code != 200:
        resp.json = Mock(side_effect=ValueError("no json"))
    elif body in (SPA_HTML_200,):
        resp.json = Mock(side_effect=ValueError("Expecting value"))
    else:
        resp.json = Mock(return_value=json.loads(body))
    return resp


def test_dashboard_genuine_body_is_up():
    with patch.object(dashboard.requests, "get", return_value=_dash_resp(GENUINE_HEALTH_BODY)):
        status = dashboard.check_node_health(dashboard.NODES[0])
    assert status.status == "up"
    assert status.error is None


def test_dashboard_html_200_is_impostor():
    with patch.object(dashboard.requests, "get", return_value=_dash_resp(SPA_HTML_200, "text/html")):
        status = dashboard.check_node_health(dashboard.NODES[0])
    assert status.status == "impostor"  # was: generic ValueError "down"
    assert status.error is not None


def test_dashboard_keyless_json_is_impostor():
    with patch.object(dashboard.requests, "get", return_value=_dash_resp(KEYLESS_JSON_BODY)):
        status = dashboard.check_node_health(dashboard.NODES[0])
    assert status.status == "impostor"


def test_dashboard_ok_false_is_degraded():
    with patch.object(dashboard.requests, "get", return_value=_dash_resp(OK_FALSE_HEALTH_BODY)):
        status = dashboard.check_node_health(dashboard.NODES[0])
    assert status.status == "degraded"
    assert status.version == "2.2.1"


def test_dashboard_impostor_transition_logs_incident(tmp_path):
    original_db = dashboard.DB_PATH
    dashboard.DB_PATH = tmp_path / "h.db"
    try:
        dashboard.init_database()
        dashboard.incident_log.clear()
        new_status = dashboard.NodeStatus(
            node_id="node1", name="Node 1", endpoint="e", location="l",
            status="impostor", response_time_ms=10, version="unknown",
            uptime_s=0, active_miners=0, current_epoch=0,
            timestamp=dashboard.datetime.now(), error="HTTP 200 but body is not a JSON object",
        )
        dashboard.detect_status_change({"status": "up"}, new_status)
        assert dashboard.incident_log[-1]["incident_type"] == "node_impostor"
    finally:
        dashboard.DB_PATH = original_db
        dashboard.incident_log.clear()


# ── Monitor 3: monitoring/rustchain-exporter.py gauges ───────────────────────


class RecordingMetric:
    def __init__(self, *args, **kwargs):
        self.values = []

    def labels(self, **labels):
        return self

    def set(self, value):
        self.values.append(value)

    def inc(self):
        self.values.append("inc")

    def info(self, value):
        self.values.append(value)


prom_stub = types.ModuleType("prometheus_client")
prom_stub.start_http_server = lambda *a, **k: None
prom_stub.Gauge = RecordingMetric
prom_stub.Counter = RecordingMetric
prom_stub.Info = RecordingMetric
sys.modules["prometheus_client"] = prom_stub
exporter = _load("rustchain_exporter_17180", "monitoring/rustchain-exporter.py")


def _scrape(health_resp, other=None, clear=False):
    if clear:
        exporter.node_health.values.clear()
        exporter.last_successful_scrape_timestamp.values.clear()

    def fake_get(url, **kwargs):
        if url.endswith("/health"):
            if isinstance(health_resp, Exception):
                raise health_resp
            return health_resp
        if other is not None:
            return other
        return FakeHTTPResponse(json.dumps({"epoch": 1}) if url.endswith("/epoch") else "[]")
    with patch.object(exporter.requests, "get", side_effect=fake_get):
        exporter.collect_metrics()


def test_exporter_genuine_node_sets_health_1_and_timestamp():
    _scrape(FakeHTTPResponse(GENUINE_HEALTH_BODY), clear=True)
    assert exporter.node_health.values[-1] == 1
    assert len(exporter.last_successful_scrape_timestamp.values) == 1
    assert exporter.last_successful_scrape_timestamp.values[-1] > 0


def test_exporter_html_200_zeros_gauge_and_freezes_timestamp():
    # The exact false green from the issue: gauge used to keep its last value (1).
    _scrape(FakeHTTPResponse(GENUINE_HEALTH_BODY), clear=True)  # start healthy
    exporter.last_successful_scrape_timestamp.values.clear()
    html = FakeHTTPResponse(SPA_HTML_200, "text/html")
    html.json = Mock(side_effect=ValueError("Expecting value"))
    _scrape(html)
    assert exporter.node_health.values[-1] == 0
    assert exporter.last_successful_scrape_timestamp.values == []


def test_exporter_ok_false_zeros_gauge_but_scrape_succeeded():
    _scrape(FakeHTTPResponse(OK_FALSE_HEALTH_BODY), clear=True)
    assert exporter.node_health.values[-1] == 0
    assert len(exporter.last_successful_scrape_timestamp.values) == 1


def test_exporter_timeout_zeros_gauge():
    _scrape(RuntimeError("connection refused"), clear=True)
    assert exporter.node_health.values[-1] == 0
    assert exporter.last_successful_scrape_timestamp.values == []


# ── Monitor 4: tools/node_health_monitor.py ──────────────────────────────────

monitor_mod = _load("node_health_monitor_17180", "tools/node_health_monitor.py")


def test_monitor_genuine_epoch_body_is_online():
    body = json.dumps({"epoch": 312, "enrolled_miners": 7, "settlement_lag_epochs": 1})
    with patch("urllib.request.urlopen", side_effect=_opener(body)):
        st = monitor_mod.NodeHealthMonitor(nodes=["http://node.example"]).check_node("http://node.example")
    assert st.status == "online"
    assert st.state == "up"
    assert st.epoch == 312


def test_monitor_html_200_is_impostor():
    with patch("urllib.request.urlopen", side_effect=_opener(SPA_HTML_200, "text/html")):
        st = monitor_mod.NodeHealthMonitor(nodes=["http://node.example"]).check_node("http://node.example")
    assert st.state == "impostor"  # was: silently offline with a raw-bytes error
    assert st.status == "offline"


def test_monitor_impostor_alerts_network():
    with patch("urllib.request.urlopen", side_effect=_opener(SPA_HTML_200, "text/html")):
        m = monitor_mod.NodeHealthMonitor(nodes=["http://node.example"])
        statuses = m.check_all()
    health = m.get_network_health(statuses)
    assert any("IMPOSTOR" in a for a in health.alerts)


def test_monitor_timeout_is_unreachable_offline():
    with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
        st = monitor_mod.NodeHealthMonitor(nodes=["http://node.example"]).check_node("http://node.example")
    assert st.status == "offline"
    assert st.state == "unreachable"


# ── Monitor 5: tools/node-health-cli/node_health.py ──────────────────────────

cli = _load("node_health_cli_17180", "tools/node-health-cli/node_health.py")


def test_cli_genuine_body_is_up():
    with patch.object(cli, "urlopen", return_value=FakeHTTPResponse(GENUINE_HEALTH_BODY)):
        health = cli.check_health("https://node.example", timeout=5)
    assert health.state == "up"
    assert health.ok is True
    assert health.version == "2.2.1"
    assert health.error is None


def test_cli_html_200_is_impostor():
    # The gap from the issue: a missing ok key and an HTML page both read as
    # plain False before; now impostor is its own state.
    with patch.object(cli, "urlopen", return_value=FakeHTTPResponse(SPA_HTML_200, "text/html")):
        health = cli.check_health("https://node.example", timeout=5)
    assert health.state == "impostor"
    assert health.ok is False
    assert health.error.startswith("impostor:")


def test_cli_ok_false_is_degraded():
    with patch.object(cli, "urlopen", return_value=FakeHTTPResponse(OK_FALSE_HEALTH_BODY)):
        health = cli.check_health("https://node.example", timeout=5)
    assert health.state == "degraded"
    assert health.ok is False


def test_cli_timeout_is_unreachable():
    with patch.object(cli, "urlopen", side_effect=socket.timeout("timed out")):
        health = cli.check_health("https://node.example", timeout=5)
    assert health.state == "unreachable"
    assert health.ok is False
