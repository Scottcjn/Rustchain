# SPDX-License-Identifier: Apache-2.0
"""
monitoring/tests/test_node_probe.py — Unit tests for shared node health probe
Issue #17180 / Bounty 25 RTC
"""

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from monitoring.node_probe import (
    ProbeResult,
    ProbeState,
    probe_health,
    validate_health_payload,
)


class TestValidateHealthPayload:
    """Direct validation tests on recorded payload fixtures."""

    def test_genuine_health_fixture_is_up(self):
        payload = {
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 86400,
            "db_rw": True,
            "tip_age_slots": 3,
        }
        state, data, reason = validate_health_payload(payload, content_type="application/json")
        assert state == ProbeState.UP
        assert data["version"] == "2.2.1"
        assert reason is None

    def test_html_spa_fixture_is_impostor(self):
        html_payload = (
            "<!DOCTYPE html><html><head><title>SPA App</title></head>"
            "<body><div id='root'></div><script src='/app.js'></script></body></html>"
        )
        state, _data, reason = validate_health_payload(html_payload, content_type="text/html; charset=utf-8")
        assert state == ProbeState.IMPOSTOR
        assert "Impostor detected" in reason

    def test_html_body_with_generic_content_type_is_impostor(self):
        html_payload = "<html><body><h1>200 OK Default Page</h1></body></html>"
        state, _data, reason = validate_health_payload(html_payload, content_type="text/plain")
        assert state == ProbeState.IMPOSTOR
        assert "Impostor detected" in reason

    def test_json_missing_essential_keys_is_impostor(self):
        # Missing 'ok', 'version', 'uptime_s'
        payload = {"status": "ok", "service": "unrelated_gateway"}
        state, _data, reason = validate_health_payload(payload, content_type="application/json")
        assert state == ProbeState.IMPOSTOR
        assert "Missing essential node health keys" in reason

    def test_json_missing_uptime_is_impostor(self):
        payload = {"ok": True, "version": "2.2.1"}
        state, _data, reason = validate_health_payload(payload, content_type="application/json")
        assert state == ProbeState.IMPOSTOR
        assert "uptime_s" in reason

    def test_degraded_when_ok_is_false(self):
        payload = {
            "ok": False,
            "version": "2.2.1",
            "uptime_s": 120,
            "db_rw": True,
        }
        state, _data, reason = validate_health_payload(payload, content_type="application/json")
        assert state == ProbeState.DEGRADED
        assert "ok is false" in reason

    def test_degraded_when_db_rw_is_false(self):
        payload = {
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 120,
            "db_rw": False,
        }
        state, _data, reason = validate_health_payload(payload, content_type="application/json")
        assert state == ProbeState.DEGRADED
        assert "db_rw is false" in reason

    def test_degraded_when_tip_age_exceeds_threshold(self):
        payload = {
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 120,
            "db_rw": True,
            "tip_age_slots": 500,
        }
        state, _data, reason = validate_health_payload(
            payload, content_type="application/json", tip_age_threshold=120
        )
        assert state == ProbeState.DEGRADED
        assert "tip_age_slots (500) exceeds threshold" in reason


class TestProbeHealthHttpMock:
    """Network-level mock tests verifying ProbeResult generation."""

    def test_probe_genuine_node(self):
        body = json.dumps({
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 1500,
            "db_rw": True,
            "tip_age_slots": 2,
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.read.return_value = body

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            result: ProbeResult = probe_health("https://node1.rustchain.org/health")

        assert result.state == ProbeState.UP.value
        assert result.is_healthy is True
        assert result.status_code == 200
        assert result.data["version"] == "2.2.1"

    def test_probe_html_spa_200_returns_impostor(self):
        body = b"<!DOCTYPE html><html><body><div id='app'>React Host</div></body></html>"

        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.read.return_value = body

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            result = probe_health("https://spa.rustchain.org/health")

        assert result.state == ProbeState.IMPOSTOR.value
        assert result.is_healthy is False
        assert result.is_impostor is True
        assert "Impostor detected" in result.reason

    def test_probe_http_500_returns_down(self):
        err = urllib.error.HTTPError(
            url="https://node.rustchain.org/health",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = probe_health("https://node.rustchain.org/health")

        assert result.state == ProbeState.DOWN.value
        assert result.status_code == 500
        assert result.is_healthy is False

    def test_probe_timeout_returns_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            result = probe_health("https://node.rustchain.org/health", timeout=1.0)

        assert result.state == ProbeState.UNREACHABLE.value
        assert result.status_code is None
        assert result.is_healthy is False
        assert "timed out" in result.error
