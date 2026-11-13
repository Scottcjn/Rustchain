#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for monitoring/rustchain-exporter.py (issue #17180).

The exporter must drive rustchain_node_health from the shared probe: 0 on any
non-up state (including impostor) and never left stale, plus the
rustchain_last_successful_scrape_timestamp gauge.
"""

import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prometheus_client import REGISTRY  # noqa: E402

from monitoring.node_probe import UP, DOWN, IMPOSTOR, DEGRADED, UNREACHABLE, ProbeResult  # noqa: E402
from monitoring.tests._loader import load_exporter  # noqa: E402
from monitoring.tests.fixture_server import make_server, json_route, html_route  # noqa: E402

exporter = load_exporter()


def gauge_value(name, labels=None):
    return REGISTRY.get_sample_value(name, labels or {})


class TestExporterProbeStates(unittest.TestCase):
    """collect_metrics() with the probe mocked to each state."""

    def setUp(self):
        self._orig_probe = exporter.probe_node_health
        self._orig_fetch = exporter.fetch_json
        # Keep the /epoch and /api/miners scrapes off the network in unit tests.
        exporter.fetch_json = lambda endpoint: None

    def tearDown(self):
        exporter.probe_node_health = self._orig_probe
        exporter.fetch_json = self._orig_fetch

    def _collect_with(self, result):
        exporter.probe_node_health = lambda: result
        exporter.collect_metrics()

    def test_up_sets_health_1_and_last_success(self):
        before = time.time()
        self._collect_with(ProbeResult(
            state=UP, url="http://x/health", status_code=200, response_ms=12.0,
            ok=True, version="2.2.1", uptime_s=100, db_rw=True, tip_age_slots=1,
            data={"ok": True, "version": "2.2.1", "uptime_s": 100, "db_rw": True},
        ))
        self.assertEqual(gauge_value("rustchain_node_health"), 1)
        ts = gauge_value("rustchain_last_successful_scrape_timestamp")
        self.assertIsNotNone(ts)
        self.assertGreaterEqual(ts, before)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "up"}), 1)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "impostor"}), 0)

    def test_impostor_sets_health_0(self):
        self._collect_with(ProbeResult(
            state=IMPOSTOR, url="http://x/health", status_code=200, response_ms=9.0,
            content_type="text/html",
            detail="HTTP 200 with Content-Type text/html — not a RustChain node",
        ))
        self.assertEqual(gauge_value("rustchain_node_health"), 0)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "impostor"}), 1)

    def test_down_sets_health_0(self):
        self._collect_with(ProbeResult(state=DOWN, url="http://x/health", status_code=500, detail="HTTP 500"))
        self.assertEqual(gauge_value("rustchain_node_health"), 0)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "down"}), 1)

    def test_degraded_sets_health_0_but_counts_as_successful_scrape(self):
        self._collect_with(ProbeResult(
            state=DEGRADED, url="http://x/health", status_code=200, ok=False,
            data={"ok": False, "version": "2.2.1", "uptime_s": 5, "db_rw": False},
            detail="ok=False; db_rw=false",
        ))
        self.assertEqual(gauge_value("rustchain_node_health"), 0)
        self.assertGreater(gauge_value("rustchain_last_successful_scrape_timestamp"), 0)

    def test_unreachable_sets_health_0(self):
        self._collect_with(ProbeResult(state=UNREACHABLE, url="http://x/health", detail="Timeout"))
        self.assertEqual(gauge_value("rustchain_node_health"), 0)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "unreachable"}), 1)

    def test_probe_exception_sets_health_0(self):
        def boom():
            raise RuntimeError("kaboom")
        exporter.probe_node_health = boom
        exporter.collect_metrics()
        self.assertEqual(gauge_value("rustchain_node_health"), 0)


class TestExporterLiveAgainstFixtures(unittest.TestCase):
    """End-to-end: exporter pointed at a local server replaying fixtures."""

    def setUp(self):
        self._node = exporter.RUSTCHAIN_NODE
        self._probe = exporter.probe_node_health
        exporter.probe_node_health = self._probe  # keep original for live use

    def tearDown(self):
        exporter.RUSTCHAIN_NODE = self._node

    def test_html_200_fixture_makes_health_gauge_0(self):
        routes = {
            "/health": html_route(),  # SPA answering 200 on every path
            "/epoch": json_route("health_ok.json"),
            "/api/miners": (200, "application/json", b"[]", 0),
        }
        with make_server(routes) as srv:
            exporter.RUSTCHAIN_NODE = srv.base_url
            exporter.collect_metrics()
        self.assertEqual(gauge_value("rustchain_node_health"), 0)
        self.assertEqual(gauge_value("rustchain_node_probe_state", {"state": "impostor"}), 1)

    def test_genuine_fixture_makes_health_gauge_1(self):
        routes = {
            "/health": json_route("health_ok.json"),
            "/epoch": json_route("health_ok.json"),
            "/api/miners": (200, "application/json", b"[]", 0),
        }
        with make_server(routes) as srv:
            exporter.RUSTCHAIN_NODE = srv.base_url
            before = time.time()
            exporter.collect_metrics()
        self.assertEqual(gauge_value("rustchain_node_health"), 1)
        self.assertGreaterEqual(gauge_value("rustchain_last_successful_scrape_timestamp"), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
