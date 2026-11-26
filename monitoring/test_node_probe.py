# SPDX-License-Identifier: MIT
"""Fixtures for the shared liveness probe.

These are recorded response bodies, not live calls: the point of the probe is
that a 200 carrying an SPA page or an unrelated JSON API is never "up".
"""

import json
import os
import socket
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from monitoring import node_probe as probe  # noqa: E402


GENUINE = {
    "ok": True,
    "version": "2.2.1",
    "uptime_s": 86400,
    "db_rw": True,
    "tip_age_slots": 2,
}

# What an SPA returns on every path, with a 200.
SPA_HTML = (b"<!doctype html><html lang=\"en\"><head><title>New API</title>"
            b"</head><body><div id=\"root\"></div></body></html>")

# Valid JSON from an unrelated service that happens to share the address.
FOREIGN_JSON = b'{"status": "ok", "service": "new-api", "region": "us-east-1"}'


class ClassifyHealthTest(unittest.TestCase):

    def test_genuine_health_body_is_up(self):
        result = probe.classify_health(200, GENUINE)
        self.assertEqual(result.state, probe.STATE_UP)
        self.assertTrue(result.is_up)
        self.assertEqual(result.version, "2.2.1")
        self.assertEqual(result.uptime_s, 86400)
        self.assertIs(result.db_rw, True)

    def test_html_200_is_impostor(self):
        result = probe.classify_health(
            200, probe.parse_json_object(SPA_HTML),
            content_type="text/html; charset=utf-8",
        )
        self.assertEqual(result.state, probe.STATE_IMPOSTOR)
        self.assertFalse(result.is_up)

    def test_html_body_without_content_type_is_impostor(self):
        result = probe.classify_health(200, probe.parse_json_object(SPA_HTML))
        self.assertEqual(result.state, probe.STATE_IMPOSTOR)

    def test_json_without_health_keys_is_impostor(self):
        result = probe.classify_health(200, probe.parse_json_object(FOREIGN_JSON))
        self.assertEqual(result.state, probe.STATE_IMPOSTOR)
        self.assertIn("none of", result.reason)

    def test_empty_body_is_impostor(self):
        result = probe.classify_health(200, probe.parse_json_object(b""))
        self.assertEqual(result.state, probe.STATE_IMPOSTOR)

    def test_non_object_json_is_impostor(self):
        result = probe.classify_health(200, probe.parse_json_object(b"[1, 2, 3]"))
        self.assertEqual(result.state, probe.STATE_IMPOSTOR)

    def test_ok_false_is_degraded(self):
        result = probe.classify_health(200, {**GENUINE, "ok": False})
        self.assertEqual(result.state, probe.STATE_DEGRADED)
        self.assertTrue(result.is_up)

    def test_db_rw_false_is_degraded(self):
        result = probe.classify_health(200, {**GENUINE, "db_rw": False})
        self.assertEqual(result.state, probe.STATE_DEGRADED)
        self.assertIn("db_rw", result.reason)

    def test_stale_tip_is_degraded(self):
        result = probe.classify_health(200, {**GENUINE, "tip_age_slots": 5000})
        self.assertEqual(result.state, probe.STATE_DEGRADED)

    def test_http_500_is_down(self):
        result = probe.classify_health(500, None)
        self.assertEqual(result.state, probe.STATE_DOWN)
        self.assertEqual(result.reason, "HTTP 500")

    def test_error_is_unreachable(self):
        result = probe.classify_health(None, None, error="connection refused")
        self.assertEqual(result.state, probe.STATE_UNREACHABLE)


class ProbeHealthTest(unittest.TestCase):

    def _response(self, body, status=200, content_type="application/json"):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = body
        response.status = status
        response.headers = {"Content-Type": content_type} if content_type else {}
        return response

    def test_live_shaped_response_is_up(self):
        with mock.patch.object(probe.urllib.request, "urlopen",
                               return_value=self._response(json.dumps(GENUINE).encode())):
            result = probe.probe_health("https://node.example/health")
        self.assertEqual(result.state, probe.STATE_UP)

    def test_spa_page_is_impostor(self):
        response = self._response(SPA_HTML, content_type="text/html")
        with mock.patch.object(probe.urllib.request, "urlopen", return_value=response):
            result = probe.probe_health("https://parked.example/health")
        self.assertEqual(result.state, probe.STATE_IMPOSTOR)

    def test_timeout_is_unreachable(self):
        with mock.patch.object(probe.urllib.request, "urlopen",
                               side_effect=socket.timeout("timed out")):
            result = probe.probe_health("https://node.example/health", timeout=1)
        self.assertEqual(result.state, probe.STATE_UNREACHABLE)
        self.assertIn("timeout", result.reason)

    def test_connection_error_is_unreachable(self):
        with mock.patch.object(probe.urllib.request, "urlopen",
                               side_effect=ConnectionRefusedError("refused")):
            result = probe.probe_health("https://node.example/health")
        self.assertEqual(result.state, probe.STATE_UNREACHABLE)

    def test_probe_never_raises(self):
        with mock.patch.object(probe.urllib.request, "urlopen",
                               side_effect=RuntimeError("weird")):
            result = probe.probe_health("https://node.example/health")
        self.assertEqual(result.state, probe.STATE_UNREACHABLE)


if __name__ == "__main__":
    unittest.main()
