# SPDX-License-Identifier: MIT
"""Recorded fixture tests for monitoring/node_probe.py and all 5 monitors (Bounty #17180)."""

from __future__ import annotations

import importlib.util
import json
import sys
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

SPA_HTML_200 = "<!DOCTYPE html><html><head><title>Parked Domain SPA</title></head><body><div id='app'></div></body></html>"
MISSING_KEYS_JSON = json.dumps({"status": "alive", "hello": "world"})
DEGRADED_JSON = json.dumps({"ok": False, "version": "2.4.1-rip200", "uptime_s": 400, "db_rw": False})


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

    deg_res = classify_health_response("https://node2/health", 200, DEGRADED_JSON, "application/json", 30.0)
    assert deg_res.state == "degraded"
    assert deg_res.is_up is False

    down_res = classify_health_response("https://node3/health", 500, "Internal Server Error", "text/plain", 12.0)
    assert down_res.state == "down"

    unreach_res = probe_health("http://127.0.0.1:1", timeout=0.2)
    assert unreach_res.state == "unreachable"


def test_all_five_monitors_flag_html_200_as_impostor_and_never_up(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. status/status_server.py
    from status import status_server

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = SPA_HTML_200
    fake_resp.headers = {"Content-Type": "text/html"}
    monkeypatch.setattr(status_server.requests, "get", lambda *a, **kw: fake_resp)
    st_out = status_server.check_node({"id": "n4", "name": "Node 4", "endpoint": "http://node4/health"})
    assert st_out["up"] is False
    assert st_out["state"] == "impostor"

    # 2. health-dashboard/server.py
    hd_spec = importlib.util.spec_from_file_location("hd_server", ROOT / "health-dashboard" / "server.py")
    hd_mod = importlib.util.module_from_spec(hd_spec)
    hd_spec.loader.exec_module(hd_mod)
    monkeypatch.setattr(hd_mod.requests, "get", lambda *a, **kw: fake_resp)
    hd_out = hd_mod.check_node_health({
        "id": "n4", "name": "Node 4", "endpoint": "http://node4/health", "location": "HK"
    })
    assert hd_out.status == "impostor"

    # 3. monitoring/rustchain-exporter.py
    exp_spec = importlib.util.spec_from_file_location("rc_exporter", ROOT / "monitoring" / "rustchain-exporter.py")
    exp_mod = importlib.util.module_from_spec(exp_spec)
    exp_spec.loader.exec_module(exp_mod)
    monkeypatch.setattr(exp_mod.requests, "get", lambda *a, **kw: fake_resp)
    monkeypatch.setattr(exp_mod, "fetch_json", lambda ep: None)
    exp_mod.node_health.set(1)  # pre-set to 1 to verify failed scrape resets gauge to 0
    exp_mod.collect_metrics()
    assert exp_mod.node_health._value.get() == 0.0

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
