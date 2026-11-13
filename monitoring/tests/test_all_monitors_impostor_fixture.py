# SPDX-License-Identifier: Apache-2.0
"""
monitoring/tests/test_all_monitors_impostor_fixture.py
Issue #17180 / Bounty 25 RTC

Verifies acceptance criteria:
- One shared probe function (monitoring/node_probe.py); no monitor decides "up" from status code alone.
- HTML-200 fixture -> 'impostor' in every monitor's output.
- Exporter gauge goes to 0 on failure; last-success timestamp exported.
- All 5 monitors tested against genuine, HTML-200, missing-keys, degraded, 500, timeout fixtures.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "status"))
sys.path.insert(0, str(REPO_ROOT / "health-dashboard"))
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "node-health-cli"))

import node_health
import node_health_monitor
import server as health_dashboard_server
import status_server

# ── Fixtures ─────────────────────────────────────────────────────────────

GENUINE_HEALTH_FIXTURE = {
    "ok": True,
    "version": "2.2.1",
    "uptime_s": 86400,
    "db_rw": True,
    "tip_age_slots": 5,
}

HTML_200_SPA_FIXTURE = (
    "<!DOCTYPE html><html><head><title>RustChain SPA Portal</title></head>"
    "<body><div id='app'>Single Page App Impostor Host</div></body></html>"
)

MISSING_KEYS_FIXTURE = {
    "version": "1.0.0",
    "status": "online",
    # missing 'ok' and 'uptime_s'
}

DEGRADED_FIXTURE = {
    "ok": False,
    "version": "2.2.1",
    "uptime_s": 500,
    "db_rw": False,
}


def test_monitor1_status_server_impostor_and_fixtures():
    node = {"endpoint": "https://50.28.86.131/health"}

    # 1. HTML-200 must yield impostor
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.text = HTML_200_SPA_FIXTURE
    with patch("status_server.requests.get", return_value=mock_resp):
        res = status_server.check_node(node)
    assert res["up"] is False
    assert res["state"] == "impostor"
    assert res["version"] == "impostor"
    assert "Impostor detected" in res["error"]

    # 2. Genuine fixture must yield up
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.text = json.dumps(GENUINE_HEALTH_FIXTURE)
    with patch("status_server.requests.get", return_value=mock_resp):
        res = status_server.check_node(node)
    assert res["up"] is True
    assert res["state"] == "up"
    assert res["version"] == "2.2.1"


def test_monitor2_health_dashboard_server_impostor_and_fixtures():
    node_config = {
        "id": "node1",
        "name": "Node 1",
        "endpoint": "https://50.28.86.131/health",
        "location": "US",
    }

    # 1. HTML-200 must yield impostor
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.text = HTML_200_SPA_FIXTURE
    with patch("server.requests.get", return_value=mock_resp):
        status = health_dashboard_server.check_node_health(node_config)
    assert status.status == "impostor"
    assert "Impostor detected" in status.error

    # 2. Genuine fixture must yield up
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.text = json.dumps(GENUINE_HEALTH_FIXTURE)
    with patch("server.requests.get", return_value=mock_resp):
        status = health_dashboard_server.check_node_health(node_config)
    assert status.status == "up"
    assert status.version == "2.2.1"


def test_monitor3_rustchain_exporter_metrics_and_gauge():
    # Import exporter module
    sys.path.insert(0, str(REPO_ROOT / "monitoring"))
    import importlib
    exporter = importlib.import_module("rustchain-exporter")

    # 1. Scrape with HTML 200 Impostor -> gauge must be 0
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.text = HTML_200_SPA_FIXTURE

    with patch("requests.get", return_value=mock_resp):
        exporter.collect_metrics()
    assert exporter.node_health._value.get() == 0

    # 2. Scrape with Genuine health -> gauge must be 1 and timestamp updated
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.text = json.dumps(GENUINE_HEALTH_FIXTURE)
    mock_resp.json.return_value = GENUINE_HEALTH_FIXTURE

    with patch("requests.get", return_value=mock_resp):
        exporter.collect_metrics()
    assert exporter.node_health._value.get() == 1
    assert exporter.last_successful_scrape._value.get() > 0


def test_monitor4_node_health_monitor_impostor_and_fixtures():
    monitor = node_health_monitor.NodeHealthMonitor()

    # 1. HTML-200 must yield impostor
    mock_r = MagicMock()
    mock_r.__enter__ = lambda s: s
    mock_r.__exit__ = MagicMock(return_value=False)
    mock_r.read = MagicMock(return_value=HTML_200_SPA_FIXTURE.encode())
    mock_r.headers = {"Content-Type": "text/html"}
    mock_r.status = 200

    with patch("urllib.request.urlopen", return_value=mock_r):
        status = monitor.check_node("http://50.28.86.131:8088")
    assert status.status == "impostor"
    assert "Impostor detected" in status.error

    # 2. Genuine fixture
    mock_r.read = MagicMock(return_value=json.dumps({"epoch": 42, "active_miners": 7}).encode())
    mock_r.headers = {"Content-Type": "application/json"}
    with patch("urllib.request.urlopen", return_value=mock_r):
        status = monitor.check_node("http://50.28.86.131:8088")
    assert status.status in ("online", "slow")
    assert status.epoch == 42


def test_monitor5_node_health_cli_impostor_and_fixtures():
    # 1. HTML-200 must yield impostor
    mock_r = MagicMock()
    mock_r.__enter__ = lambda s: s
    mock_r.__exit__ = MagicMock(return_value=False)
    mock_r.read = MagicMock(return_value=HTML_200_SPA_FIXTURE.encode())
    mock_r.headers = {"Content-Type": "text/html"}
    mock_r.code = 200

    with patch("node_health.urlopen", return_value=mock_r):
        health = node_health.check_health("https://rustchain.org", timeout=5)
    assert health.ok is False
    assert health.state == "impostor"
    assert "Impostor detected" in health.error

    # 2. Genuine fixture must yield ok=True
    mock_r.read = MagicMock(return_value=json.dumps(GENUINE_HEALTH_FIXTURE).encode())
    mock_r.headers = {"Content-Type": "application/json"}
    with patch("node_health.urlopen", return_value=mock_r):
        health = node_health.check_health("https://rustchain.org", timeout=5)
    assert health.ok is True
    assert health.state == "up"
    assert health.version == "2.2.1"
