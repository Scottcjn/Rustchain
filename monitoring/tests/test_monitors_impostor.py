#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Per-monitor impostor tests (issue #17180).

Every one of the five monitors is pointed at a local server that replays the
recorded HTML-SPA fixture at /health with HTTP 200 + text/html — the exact
shape of the repurposed-host incident. Each monitor must surface `impostor`
(or its equivalent not-up state), never `up`. A genuine fixture server is used
as the control so we know the monitors can still say `up`.
"""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prometheus_client import REGISTRY  # noqa: E402

from monitoring.tests._loader import (  # noqa: E402
    load_exporter, load_dashboard_server, load_node_health_monitor,
    load_node_health_cli, load_status_server,
)
from monitoring.tests.fixture_server import make_server, json_route, html_route  # noqa: E402

IMPOSTOR_ROUTES = {
    "/health": html_route("spa_200.html"),          # 200 + text/html SPA body
    "/epoch": (200, "application/json", b'{"ok": true, "epoch": 7, "slot": 3, "enrolled_miners": 2}', 0),
    "/api/miners": (200, "application/json", b"[]", 0),
}
GENUINE_ROUTES = {
    "/health": json_route("health_ok.json"),
    "/epoch": (200, "application/json", b'{"ok": true, "epoch": 7, "slot": 3, "enrolled_miners": 2}', 0),
    "/api/miners": (200, "application/json", b"[]", 0),
}


def gauge_value(name, labels=None):
    return REGISTRY.get_sample_value(name, labels or {})


class TestEveryMonitorSeesImpostor(unittest.TestCase):
    """HTML-200 fixture → impostor in every monitor's output."""

    def test_status_server_check_node(self):
        mod = load_status_server()
        with make_server(IMPOSTOR_ROUTES) as srv:
            result = mod.check_node_real({"endpoint": f"{srv.base_url}/health"})
        self.assertFalse(result["up"])
        self.assertEqual(result["state"], "impostor")
        self.assertEqual(result["status_code"], 200)
        self.assertIn("impostor", result["error"].lower())

    def test_status_page_api_marks_impostor(self):
        mod = load_status_server()
        mod.node_status.clear()
        mod.node_status["node-1"] = {
            "up": False, "state": "impostor", "name": "Node 1",
            "error": "HTTP 200 with Content-Type text/html — not a RustChain node",
            "status_code": 200, "response_ms": 20, "checked_at": "2026-01-01T00:00:00Z",
        }
        mod.app.config["TESTING"] = True
        with mod.app.test_client() as client:
            data = json.loads(client.get("/api/status").data)
        self.assertEqual(data["overall"], "impostor")
        self.assertEqual(data["nodes_impostor"], 1)
        self.assertEqual(data["nodes"][0]["state"], "impostor")

    def test_health_dashboard_check_node_health(self):
        mod = load_dashboard_server()
        with make_server(IMPOSTOR_ROUTES) as srv:
            status = mod.check_node_health({
                "id": "t1", "name": "Test", "location": "L",
                "endpoint": f"{srv.base_url}/health",
            })
        self.assertEqual(status.status, "impostor")
        self.assertNotEqual(status.status, "up")
        self.assertIn("impostor", status.error.lower())

    def test_exporter_gauge_zero_on_impostor(self):
        mod = load_exporter()
        orig_node, orig_fetch = mod.RUSTCHAIN_NODE, mod.fetch_json
        mod.fetch_json = lambda endpoint: None  # keep /epoch off the network
        try:
            with make_server(IMPOSTOR_ROUTES) as srv:
                mod.RUSTCHAIN_NODE = srv.base_url
                mod.collect_metrics()
        finally:
            mod.RUSTCHAIN_NODE = orig_node
            mod.fetch_json = orig_fetch
        self.assertEqual(gauge_value("rustchain_node_health"), 0)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "impostor"}), 1)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "up"}), 0)

    def test_node_health_monitor_check_node(self):
        mod = load_node_health_monitor()
        with make_server(IMPOSTOR_ROUTES) as srv:
            mon = mod.NodeHealthMonitor(nodes=[srv.base_url], timeout=5)
            st = mon.check_node(srv.base_url)
        self.assertEqual(st.probe_state, "impostor")
        self.assertEqual(st.status, "offline")
        self.assertIn("IMPOSTOR", st.error)
        # and the network-level alert surfaces it too
        health = mon.get_network_health([st])
        self.assertTrue(any("IMPOSTOR" in a for a in health.alerts))

    def test_node_health_cli_check_health(self):
        mod = load_node_health_cli()
        with make_server(IMPOSTOR_ROUTES) as srv:
            result = mod.check_health(srv.base_url, timeout=5)
        self.assertFalse(result.ok)
        self.assertEqual(result.probe_state, "impostor")
        self.assertIn("impostor", result.error.lower())


class TestEveryMonitorStillSaysUpForGenuineNode(unittest.TestCase):
    """Control: the genuine recorded /health fixture must classify `up`."""

    def test_status_server_check_node(self):
        mod = load_status_server()
        with make_server(GENUINE_ROUTES) as srv:
            result = mod.check_node_real({"endpoint": f"{srv.base_url}/health"})
        self.assertTrue(result["up"])
        self.assertEqual(result["state"], "up")
        self.assertEqual(result["version"], "2.2.1")

    def test_health_dashboard_check_node_health(self):
        mod = load_dashboard_server()
        with make_server(GENUINE_ROUTES) as srv:
            status = mod.check_node_health({
                "id": "t1", "name": "Test", "location": "L",
                "endpoint": f"{srv.base_url}/health",
            })
        self.assertEqual(status.status, "up")
        self.assertIsNone(status.error)

    def test_exporter_gauge_one_on_genuine(self):
        mod = load_exporter()
        orig_node, orig_fetch = mod.RUSTCHAIN_NODE, mod.fetch_json
        mod.fetch_json = lambda endpoint: None
        try:
            with make_server(GENUINE_ROUTES) as srv:
                mod.RUSTCHAIN_NODE = srv.base_url
                mod.collect_metrics()
        finally:
            mod.RUSTCHAIN_NODE = orig_node
            mod.fetch_json = orig_fetch
        self.assertEqual(gauge_value("rustchain_node_health"), 1)
        self.assertGreater(gauge_value("rustchain_last_successful_scrape_timestamp"), 0)

    def test_node_health_monitor_check_node(self):
        mod = load_node_health_monitor()
        with make_server(GENUINE_ROUTES) as srv:
            mon = mod.NodeHealthMonitor(nodes=[srv.base_url], timeout=5)
            st = mon.check_node(srv.base_url)
        self.assertEqual(st.probe_state, "up")
        self.assertEqual(st.status, "online")
        self.assertEqual(st.epoch, 7)
        self.assertIsNone(st.error)

    def test_node_health_cli_check_health(self):
        mod = load_node_health_cli()
        with make_server(GENUINE_ROUTES) as srv:
            result = mod.check_health(srv.base_url, timeout=5)
        self.assertTrue(result.ok)
        self.assertEqual(result.probe_state, "up")
        self.assertIsNone(result.error)
        self.assertEqual(result.version, "2.2.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
