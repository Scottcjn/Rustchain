# SPDX-License-Identifier: MIT
"""Recorded fixture tests for monitoring/node_probe.py and all 5 monitors (Bounty #17180)."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitoring.node_probe import classify_health_response, probe_health

GENUINE_HEALTH_JSON = json.dumps({
    "ok": True,
    "version": "2.4.1-rip200",
    "uptime_s": 172800,
    "db_rw": True,
    "tip_age_slots": 2,
    "backup_age_hours": 1.5,
    "active_miners": 14,
    "epoch": 129,
})

SPA_HTML_200 = (
    "<!DOCTYPE html><html><head><title>Parked Domain SPA</title></head>"
    "<body><div id='app'></div></body></html>"
)
MISSING_KEYS_JSON = json.dumps({"status": "alive", "hello": "world"})
DEGRADED_OK_FALSE_JSON = json.dumps({"ok": False, "version": "2.4.1-rip200", "uptime_s": 400, "db_rw": True})
DEGRADED_DB_FALSE_JSON = json.dumps({"ok": True, "version": "2.4.1-rip200", "uptime_s": 400, "db_rw": False})
DEGRADED_STALE_TIP_JSON = json.dumps({
    "ok": True,
    "version": "2.4.1-rip200",
    "uptime_s": 400,
    "db_rw": True,
    "tip_age_slots": 999,
})


class _PromValue:
    def __init__(self) -> None:
        self._val = 0.0

    def get(self) -> float:
        return self._val


class _PromMetric:
    def __init__(self, *args, **kwargs) -> None:
        self._value = _PromValue()
        self.info_payload = None
        self.inc_count = 0

    def labels(self, **labels):
        return self

    def set(self, value: float) -> None:
        self._value._val = float(value)

    def inc(self) -> None:
        self.inc_count += 1

    def info(self, payload) -> None:
        self.info_payload = payload

    def observe(self, value: float) -> None:
        self._value._val = float(value)


def _clean_prometheus_stub() -> types.ModuleType:
    stub = types.ModuleType("prometheus_client")
    stub.start_http_server = lambda *args, **kwargs: None
    stub.Gauge = _PromMetric
    stub.Counter = _PromMetric
    stub.Info = _PromMetric
    stub.Histogram = _PromMetric
    return stub


def test_shared_probe_fixtures() -> None:
    up_res = classify_health_response("https://node1/health", 200, GENUINE_HEALTH_JSON, "application/json", 42.0)
    assert up_res.state == "up"
    assert up_res.is_up is True
    assert up_res.version == "2.4.1-rip200"

    html_res = classify_health_response("https://node4/health", 200, SPA_HTML_200, "text/html; charset=utf-8", 18.0)
    assert html_res.state == "impostor"
    assert html_res.is_up is False
    assert html_res.is_impostor is True

    missing_res = classify_health_response("https://node4/health", 200, MISSING_KEYS_JSON, "application/json", 15.0)
    assert missing_res.state == "impostor"

    deg_ok = classify_health_response("https://node2/health", 200, DEGRADED_OK_FALSE_JSON, "application/json", 30.0)
    assert deg_ok.state == "degraded"
    assert deg_ok.is_up is False

    deg_db = classify_health_response("https://node2/health", 200, DEGRADED_DB_FALSE_JSON, "application/json", 30.0)
    assert deg_db.state == "degraded"

    deg_tip = classify_health_response("https://node2/health", 200, DEGRADED_STALE_TIP_JSON, "application/json", 30.0)
    assert deg_tip.state == "degraded"

    down_res = classify_health_response("https://node3/health", 500, "Internal Server Error", "text/plain", 12.0)
    assert down_res.state == "down"

    def _timeout_getter(url: str, timeout: float):
        raise TimeoutError("timed out")

    unreach_res = probe_health("http://127.0.0.1:1", timeout=0.2, http_getter=_timeout_getter)
    assert unreach_res.state == "unreachable"


def test_all_five_monitors_flag_html_200_as_impostor_and_never_up(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. status/status_server.py (must also expose impostor styling in UI template)
    status_html = (ROOT / "status" / "templates" / "status.html").read_text(encoding="utf-8")
    assert ".status-badge.impostor" in status_html
    assert "'impostor'" in status_html

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = SPA_HTML_200
    fake_resp.headers = {"Content-Type": "text/html"}

    with monkeypatch.context() as m:
        import requests
        m.setattr(requests, "get", lambda *a, **kw: fake_resp)
        from status import status_server
        m.setattr(status_server.requests, "get", lambda *a, **kw: fake_resp)
        st_out = status_server.check_node({"id": "n4", "name": "Node 4", "endpoint": "http://node4/health"})
    assert st_out["up"] is False
    assert st_out["state"] == "impostor"

    # 2. health-dashboard/server.py
    hd_spec = importlib.util.spec_from_file_location("hd_server", ROOT / "health-dashboard" / "server.py")
    hd_mod = importlib.util.module_from_spec(hd_spec)
    hd_spec.loader.exec_module(hd_mod)
    assert ".status-badge.impostor" in hd_mod.HTML_TEMPLATE
    monkeypatch.setattr(hd_mod.requests, "get", lambda *a, **kw: fake_resp)
    hd_out = hd_mod.check_node_health({
        "id": "n4", "name": "Node 4", "endpoint": "http://node4/health", "location": "HK"
    })
    assert hd_out.status == "impostor"

    # 3. monitoring/rustchain-exporter.py (isolated from test_monitoring_prometheus_exporter_miners stub)
    monkeypatch.setitem(sys.modules, "prometheus_client", _clean_prometheus_stub())
    exp_spec = importlib.util.spec_from_file_location("rc_exporter", ROOT / "monitoring" / "rustchain-exporter.py")
    exp_mod = importlib.util.module_from_spec(exp_spec)
    exp_spec.loader.exec_module(exp_mod)
    monkeypatch.setattr(exp_mod.requests, "get", lambda *a, **kw: fake_resp)
    monkeypatch.setattr(exp_mod, "fetch_json", lambda ep: None)

    # First verify genuine 200 updates last_successful_scrape_timestamp & sets health=1
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.text = GENUINE_HEALTH_JSON
    ok_resp.headers = {"Content-Type": "application/json"}
    monkeypatch.setattr(exp_mod.requests, "get", lambda *a, **kw: ok_resp)
    exp_mod.collect_metrics()
    assert exp_mod.node_health._value.get() == 1.0
    first_ts = exp_mod.last_successful_scrape_timestamp._value.get()
    assert first_ts > 0

    # Now HTML 200 impostor must reset health gauge to 0 and keep last_successful_scrape_timestamp intact
    monkeypatch.setattr(exp_mod.requests, "get", lambda *a, **kw: fake_resp)
    exp_mod.collect_metrics()
    assert exp_mod.node_health._value.get() == 0.0
    assert exp_mod.node_version.info_payload.get("state") == "impostor"
    assert exp_mod.last_successful_scrape_timestamp._value.get() == first_ts

    # 4. tools/node_health_monitor.py
    from tools import node_health_monitor

    class FakeUrlopenResp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def read(self) -> bytes:
            return SPA_HTML_200.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(node_health_monitor.urllib.request, "urlopen", lambda *a, **kw: FakeUrlopenResp())
    nhm = node_health_monitor.NodeHealthMonitor(["http://node4:8099"])
    nhm._status_path = "/health"
    nhm_out = nhm.check_node("http://node4:8099")
    assert nhm_out.status == "impostor"
    assert nhm.get_network_health([nhm_out]).nodes_online == 0

    # 5. tools/node-health-cli/node_health.py
    cli_spec = importlib.util.spec_from_file_location(
        "node_health_cli", ROOT / "tools" / "node-health-cli" / "node_health.py"
    )
    cli_mod = importlib.util.module_from_spec(cli_spec)
    cli_spec.loader.exec_module(cli_mod)
    monkeypatch.setattr(cli_mod, "urlopen", lambda *a, **kw: FakeUrlopenResp())
    cli_out = cli_mod.check_health("http://node4:8099", timeout=2)
    assert cli_out.ok is False
    assert cli_out.state == "impostor"
