# SPDX-License-Identifier: MIT
"""Every monitor must see the same impostor.

An SPA was served from a decommissioned node's address. It answered 200 on
``/health``, ``/status``, and everything else, and each of the five monitors
decided "up" in its own way — so the fleet looked healthy for weeks.

This test feeds the same HTML-200 response to all five and asserts that none
of them reports a healthy node. If a new monitor copies the probe logic
instead of importing it, this is where the divergence shows up.
"""

import importlib.util
import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
CLI = os.path.join(TOOLS, "node-health-cli")
DASHBOARD = os.path.join(ROOT, "health-dashboard")
STATUS = os.path.join(ROOT, "status")
MONITORING = os.path.join(ROOT, "monitoring")

for path in (ROOT, TOOLS, CLI, DASHBOARD, STATUS, MONITORING):
    if path not in sys.path:
        sys.path.insert(0, path)

SPA_HTML = (b"<!doctype html><html lang=\"en\"><head><title>New API</title>"
            b"</head><body><div id=\"root\"></div></body></html>")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _RawResponse(io.BytesIO):
    """urlopen stand-in: context manager over the body bytes."""

    def __init__(self, payload, status=200, headers=None):
        super().__init__(payload)
        self.status = status
        self.headers = headers or {"Content-Type": "text/html"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _RequestsResponse:
    """requests.Response stand-in for a 200 + HTML page."""

    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def json(self):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


class ImpostorAcrossMonitorsTest(unittest.TestCase):

    def test_status_page_reports_impostor(self):
        with mock.patch.object(threading, "Thread") as thread_cls, \
                mock.patch("requests.get", side_effect=RuntimeError("offline")):
            status_server = load("status_server", os.path.join(STATUS, "status_server.py"))
        thread_cls.return_value.start.assert_called_once()
        with mock.patch.object(status_server.requests, "get", return_value=_RequestsResponse()):
            result = status_server.check_node(status_server.NODES[0])
        self.assertFalse(result["up"])
        self.assertEqual(result["state"], "impostor")

    def test_health_dashboard_reports_impostor(self):
        dashboard = load("dashboard_server", os.path.join(DASHBOARD, "server.py"))
        with mock.patch.object(dashboard.requests, "get", return_value=_RequestsResponse()):
            result = dashboard.check_node_health(dashboard.NODES[0])
        self.assertEqual(result.status, "impostor")
        self.assertNotEqual(result.status, "up")
        self.assertIn("text/html", result.error)

    def test_exporter_zeroes_health_and_keeps_last_success(self):
        from monitoring import node_probe

        exporter = load("rustchain_exporter", os.path.join(MONITORING, "rustchain-exporter.py"))
        impostor = node_probe.ProbeResult(
            url="https://node.example/health",
            state=node_probe.STATE_IMPOSTOR,
            status_code=200,
            reason="HTTP 200 but the body is HTML, not node state",
        )
        with mock.patch.object(exporter, "probe_health", return_value=impostor), \
                mock.patch.object(exporter, "fetch_json", return_value=None):
            exporter.node_health.set(1)  # a previous good scrape
            exporter.collect_metrics()
        self.assertEqual(exporter.node_health._value.get(), 0)
        self.assertEqual(exporter.last_successful_scrape._value.get(), 0)

    def test_node_health_monitor_reports_impostor_state(self):
        module = load("node_health_monitor", os.path.join(TOOLS, "node_health_monitor.py"))
        monitor = module.NodeHealthMonitor(nodes=["http://parked.example"])
        with mock.patch.object(module.urllib.request, "urlopen",
                               return_value=_RawResponse(SPA_HTML)):
            result = monitor.check_node("http://parked.example")
        self.assertEqual(result.status, "offline")
        self.assertEqual(result.state, "impostor")

    def test_node_health_cli_reports_impostor(self):
        cli = load("node_health_cli", os.path.join(CLI, "node_health.py"))
        response = mock.MagicMock()
        response.read.return_value = SPA_HTML
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with mock.patch.object(cli, "urlopen", return_value=response):
            result = cli.check_health("https://parked.example", timeout=1)
        self.assertFalse(result.ok)
        self.assertEqual(result.state, "impostor")


if __name__ == "__main__":
    unittest.main()
