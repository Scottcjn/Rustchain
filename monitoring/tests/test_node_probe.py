#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for the shared node liveness probe (monitoring/node_probe.py).

Issue #17180: every case below uses a recorded fixture body. The HTML-200 case
must classify as `impostor`, never `up`.
"""

import socket
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from monitoring.node_probe import (  # noqa: E402
    UP, DOWN, IMPOSTOR, DEGRADED, UNREACHABLE, STATES,
    ProbeResult, classify_health_response, probe_health,
    REQUIRED_KEYS, DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
)
from monitoring.tests.fixture_server import (  # noqa: E402
    fixture_bytes, make_server, json_route, html_route, text_route, slow_route,
)

URL = "http://node.invalid/health"


class TestClassifyWithRecordedFixtures(unittest.TestCase):
    """Pure classification of recorded bodies — no HTTP involved."""

    def test_genuine_health_body_is_up(self):
        r = classify_health_response(URL, 200, "application/json", fixture_bytes("health_ok.json"))
        self.assertEqual(r.state, UP)
        self.assertTrue(r.is_up)
        self.assertEqual(r.version, "2.2.1")
        self.assertEqual(r.uptime_s, 1834521)
        self.assertTrue(r.db_rw)
        self.assertEqual(r.tip_age_slots, 1)
        self.assertIsNone(r.detail)
        self.assertIn("ok", r.data)

    def test_html_200_is_impostor_never_up(self):
        """The exact incident: an SPA answering 200 on every path."""
        r = classify_health_response(URL, 200, "text/html", fixture_bytes("spa_200.html"))
        self.assertEqual(r.state, IMPOSTOR)
        self.assertNotEqual(r.state, UP)
        self.assertFalse(r.is_up)
        self.assertIn("impostor", r.detail.lower())

    def test_html_200_with_json_content_type_still_impostor_when_not_json(self):
        # Content-Type says JSON but the body is an HTML page (captive portal).
        r = classify_health_response(URL, 200, "application/json", fixture_bytes("spa_200.html"))
        self.assertEqual(r.state, IMPOSTOR)

    def test_json_missing_required_keys_is_impostor(self):
        r = classify_health_response(URL, 200, "application/json", fixture_bytes("json_missing_keys.json"))
        self.assertEqual(r.state, IMPOSTOR)
        for key in REQUIRED_KEYS:
            self.assertIn(key, r.detail)

    def test_ok_false_is_degraded_not_impostor(self):
        r = classify_health_response(URL, 200, "application/json", fixture_bytes("health_ok_false.json"))
        self.assertEqual(r.state, DEGRADED)
        self.assertIn("ok=False", r.detail)
        self.assertIn("db_rw=false", r.detail)

    def test_high_tip_age_is_degraded(self):
        r = classify_health_response(
            URL, 200, "application/json", fixture_bytes("health_degraded_tip_age.json"),
            tip_age_slots_threshold=DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
        )
        self.assertEqual(r.state, DEGRADED)
        self.assertIn("tip_age_slots", r.detail)

    def test_http_500_is_down(self):
        r = classify_health_response(URL, 500, "text/plain", fixture_bytes("error_500.txt"))
        self.assertEqual(r.state, DOWN)
        self.assertEqual(r.status_code, 500)

    def test_json_array_is_impostor(self):
        r = classify_health_response(URL, 200, "application/json", b"[1, 2, 3]")
        self.assertEqual(r.state, IMPOSTOR)

    def test_empty_body_is_impostor(self):
        r = classify_health_response(URL, 200, "application/json", b"")
        self.assertEqual(r.state, IMPOSTOR)


class TestProbeHealthLive(unittest.TestCase):
    """End-to-end probe_health() against a local server replaying fixtures."""

    def test_genuine_node_is_up(self):
        with make_server({"/health": json_route("health_ok.json")}) as srv:
            r = probe_health(f"{srv.base_url}/health", timeout=5)
        self.assertEqual(r.state, UP)
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.response_ms)
        self.assertEqual(r.version, "2.2.1")

    def test_html_200_is_impostor(self):
        with make_server({"/health": html_route()}) as srv:
            r = probe_health(f"{srv.base_url}/health", timeout=5)
        self.assertEqual(r.state, IMPOSTOR)
        self.assertNotEqual(r.state, UP)
        self.assertEqual(r.status_code, 200)

    def test_json_missing_keys_is_impostor(self):
        with make_server({"/health": json_route("json_missing_keys.json")}) as srv:
            r = probe_health(f"{srv.base_url}/health", timeout=5)
        self.assertEqual(r.state, IMPOSTOR)

    def test_ok_false_is_degraded(self):
        with make_server({"/health": json_route("health_ok_false.json")}) as srv:
            r = probe_health(f"{srv.base_url}/health", timeout=5)
        self.assertEqual(r.state, DEGRADED)

    def test_http_500_is_down(self):
        with make_server({"/health": text_route("error_500.txt", status=500)}) as srv:
            r = probe_health(f"{srv.base_url}/health", timeout=5)
        self.assertEqual(r.state, DOWN)
        self.assertEqual(r.status_code, 500)
        self.assertIn("500", r.detail)

    def test_timeout_is_unreachable(self):
        with make_server({"/health": slow_route(1.5)}) as srv:
            r = probe_health(f"{srv.base_url}/health", timeout=0.3)
        self.assertEqual(r.state, UNREACHABLE)
        self.assertEqual(r.detail, "Timeout")
        self.assertIsNone(r.response_ms)

    def test_connection_refused_is_unreachable(self):
        # Find a port that is guaranteed closed.
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        r = probe_health(f"http://127.0.0.1:{port}/health", timeout=2)
        self.assertEqual(r.state, UNREACHABLE)
        self.assertIsNone(r.status_code)

    def test_states_are_stable_strings(self):
        self.assertEqual(set(STATES), {UP, DOWN, IMPOSTOR, DEGRADED, UNREACHABLE})

    def test_result_to_dict_is_json_safe(self):
        import json
        r = ProbeResult(state=UP, url=URL, status_code=200, data={"ok": True})
        json.dumps(r.to_dict())


if __name__ == "__main__":
    unittest.main(verbosity=2)
