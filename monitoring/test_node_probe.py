#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for the shared /health probe (monitoring/node_probe.py).

Every fixture below is a recorded body shape: the genuine body is the exact
field set the node returns (see ``api_health`` in
``node/rustchain_v2_integrated_v2.2.1_rip200.py``); the HTML body is what an
SPA actually returns on every path (the body that kept a departed node
"online" for months); the rest are the failure shapes the bounty names.
"""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitoring.node_probe import (
    DEFAULT_TIP_AGE_SLOTS_THRESHOLD,
    ProbeResult,
    classify_health,
    probe_health,
)

# ── Recorded fixtures ────────────────────────────────────────────────────────

GENUINE_BODY = {
    "ok": True,
    "version": "2.2.1",
    "uptime_s": 3600,
    "db_rw": True,
    "backup_age_hours": 1.0,
    "tip_age_slots": 1,
    "settlement_lag_epochs": 1,
    "last_settled_epoch": 1234,
}
GENUINE_BYTES = json.dumps(GENUINE_BODY).encode()

# What a single-page app returns on every path, including /health.
SPA_HTML = (b'<!doctype html><html lang="en"><head><title>New API</title>'
            b'</head><body><div id="root"></div></body></html>')

# Valid JSON, but not a node body: none of the required keys.
MISSING_KEYS_BYTES = json.dumps({"version": "2.2.1"}).encode()

# The node answers 503 when ok is false — same body, error status.
NOT_OK_BODY = dict(GENUINE_BODY, ok=False, db_rw=False)
NOT_OK_BYTES = json.dumps(NOT_OK_BODY).encode()

DB_DOWN_BODY = dict(GENUINE_BODY, db_rw=False)
STALE_TIP_BODY = dict(GENUINE_BODY, tip_age_slots=9999)

JSON_CT = "application/json"
HTML_CT = "text/html; charset=utf-8"


class _Resp(io.BytesIO):
    """Minimal stand-in for a urllib response."""

    def __init__(self, payload: bytes, status: int = 200,
                 content_type: str = JSON_CT):
        super().__init__(payload)
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_content_type(self):
        return self.headers["Content-Type"].split(";")[0].strip()


class TestClassifyGenuine(unittest.TestCase):

    def test_genuine_body_is_up(self):
        result = classify_health(200, JSON_CT, GENUINE_BYTES)
        self.assertEqual(result.state, "up")
        self.assertEqual(result.version, "2.2.1")
        self.assertEqual(result.uptime_s, 3600)
        self.assertTrue(result.ok)
        self.assertTrue(result.db_rw)
        self.assertEqual(result.tip_age_slots, 1)
        self.assertEqual(result.body, GENUINE_BODY)

    def test_genuine_body_without_optional_fields_is_up(self):
        body = json.dumps(
            {"ok": True, "version": "2.2.1", "uptime_s": 60}).encode()
        self.assertEqual(classify_health(200, JSON_CT, body).state, "up")

    def test_content_type_with_charset_is_accepted(self):
        result = classify_health(200, "application/json; charset=utf-8",
                                 GENUINE_BYTES)
        self.assertEqual(result.state, "up")


class TestClassifyImpostor(unittest.TestCase):
    """HTTP 200 must never mean "up" on its own."""

    def test_html_spa_with_200_is_impostor(self):
        result = classify_health(200, HTML_CT, SPA_HTML)
        self.assertEqual(result.state, "impostor")
        self.assertIn("text/html", result.detail)

    def test_html_without_content_type_header_is_impostor(self):
        # An SPA that does not even label its HTML is still not a node.
        result = classify_health(200, "", SPA_HTML)
        self.assertEqual(result.state, "impostor")

    def test_non_json_body_with_200_is_impostor(self):
        result = classify_health(200, "text/plain", b"OK")
        self.assertEqual(result.state, "impostor")

    def test_json_missing_keys_with_200_is_impostor(self):
        result = classify_health(200, JSON_CT, MISSING_KEYS_BYTES)
        self.assertEqual(result.state, "impostor")
        self.assertIn("uptime_s", result.detail)

    def test_json_array_with_200_is_impostor(self):
        result = classify_health(200, JSON_CT, b"[1, 2, 3]")
        self.assertEqual(result.state, "impostor")

    def test_empty_body_with_200_is_impostor(self):
        result = classify_health(200, JSON_CT, b"")
        self.assertEqual(result.state, "impostor")

    def test_wrongly_typed_required_fields_are_impostor(self):
        body = json.dumps({"ok": "yes", "version": "2.2.1",
                           "uptime_s": 60}).encode()
        result = classify_health(200, JSON_CT, body)
        self.assertEqual(result.state, "impostor")
        body = json.dumps({"ok": True, "version": "", "uptime_s": 60}).encode()
        self.assertEqual(classify_health(200, JSON_CT, body).state,
                         "impostor")


class TestClassifyDegraded(unittest.TestCase):

    def test_ok_false_is_degraded(self):
        # The node returns 503 with this body; the verdict is degraded
        # either way — a real node saying it is not ok.
        for status in (200, 503):
            result = classify_health(status, JSON_CT, NOT_OK_BYTES)
            self.assertEqual(result.state, "degraded")
            self.assertIn("ok:false", result.detail)

    def test_db_rw_false_is_degraded(self):
        body = json.dumps(DB_DOWN_BODY).encode()
        result = classify_health(200, JSON_CT, body)
        self.assertEqual(result.state, "degraded")
        self.assertIn("db_rw:false", result.detail)

    def test_stale_tip_is_degraded(self):
        body = json.dumps(STALE_TIP_BODY).encode()
        result = classify_health(200, JSON_CT, body)
        self.assertEqual(result.state, "degraded")
        self.assertIn("tip_age_slots", result.detail)

    def test_tip_at_threshold_is_not_degraded(self):
        body = json.dumps(dict(
            GENUINE_BODY,
            tip_age_slots=DEFAULT_TIP_AGE_SLOTS_THRESHOLD)).encode()
        self.assertEqual(classify_health(200, JSON_CT, body).state, "up")

    def test_threshold_is_tunable(self):
        body = json.dumps(dict(GENUINE_BODY, tip_age_slots=50)).encode()
        result = classify_health(200, JSON_CT, body,
                                 tip_age_slots_threshold=10)
        self.assertEqual(result.state, "degraded")


class TestClassifyDown(unittest.TestCase):

    def test_500_is_down(self):
        result = classify_health(500, JSON_CT, b'{"error": "boom"}')
        self.assertEqual(result.state, "down")
        self.assertEqual(result.detail, "HTTP 500")
        self.assertEqual(result.status_code, 500)

    def test_500_with_html_error_page_is_down_not_impostor(self):
        # A proxy error page is the node being down, not an impostor SPA:
        # the SPA case is defined by a 200.
        result = classify_health(500, HTML_CT, SPA_HTML)
        self.assertEqual(result.state, "down")

    def test_503_with_missing_keys_is_down_not_impostor(self):
        result = classify_health(503, JSON_CT, MISSING_KEYS_BYTES)
        self.assertEqual(result.state, "down")

    def test_healthy_body_behind_error_status_is_down(self):
        result = classify_health(503, JSON_CT, GENUINE_BYTES)
        self.assertEqual(result.state, "down")

    def test_no_response_is_unreachable(self):
        result = classify_health(None, JSON_CT, b"")
        self.assertEqual(result.state, "unreachable")


class TestProbeHealth(unittest.TestCase):
    """probe_health: fetch + classify over the standard library."""

    def test_genuine_url_is_up(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=_Resp(GENUINE_BYTES)):
            result = probe_health("http://127.0.0.1:8099/health", timeout=5)
        self.assertEqual(result.state, "up")
        self.assertIsNotNone(result.response_ms)

    def test_html_200_url_is_impostor(self):
        with mock.patch(
                "urllib.request.urlopen",
                return_value=_Resp(SPA_HTML, content_type=HTML_CT)):
            result = probe_health("http://127.0.0.1:8099/health", timeout=5)
        self.assertEqual(result.state, "impostor")

    def test_timeout_is_unreachable_not_an_exception(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=TimeoutError("timed out")):
            result = probe_health("http://127.0.0.1:8099/health", timeout=1)
        self.assertEqual(result.state, "unreachable")
        self.assertIsInstance(result, ProbeResult)

    def test_connection_refused_is_unreachable(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError(
                            "Connection refused")):
            result = probe_health("http://127.0.0.1:8099/health", timeout=1)
        self.assertEqual(result.state, "unreachable")

    def test_http_500_is_down(self):
        import urllib.error
        error = urllib.error.HTTPError(
            "http://127.0.0.1:8099/health", 500, "Server Error", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=error):
            result = probe_health("http://127.0.0.1:8099/health", timeout=5)
        self.assertEqual(result.state, "down")
        self.assertEqual(result.status_code, 500)

    def test_http_503_with_ok_false_body_is_degraded(self):
        import urllib.error
        error = urllib.error.HTTPError(
            "http://127.0.0.1:8099/health", 503, "Service Unavailable",
            {}, io.BytesIO(NOT_OK_BYTES))
        with mock.patch("urllib.request.urlopen", side_effect=error):
            result = probe_health("http://127.0.0.1:8099/health", timeout=5)
        self.assertEqual(result.state, "degraded")


if __name__ == "__main__":
    unittest.main(verbosity=2)
