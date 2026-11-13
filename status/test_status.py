# SPDX-License-Identifier: MIT
"""Unit tests for RustChain Multi-Node Health Dashboard."""

import json
import os
import sys
import urllib.error
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitoring.node_probe import ProbeResult, UP, DOWN, IMPOSTOR, UNREACHABLE  # noqa: E402

# status_server polls all nodes once at import time; block the network for
# that import so tests never touch the real node IPs.
_import_blocker = patch(
    "urllib.request.urlopen",
    side_effect=urllib.error.URLError("blocked during test import"),
)
_import_blocker.start()
from status_server import app, check_node, poll_all, NODES, node_status, history, incidents  # noqa: E402
_import_blocker.stop()


def _up_probe(**overrides):
    """A ProbeResult for a genuine, healthy node."""
    data = overrides.pop("data", None) or {
        "ok": True, "version": "1.2.3", "uptime_s": 86400,
        "active_miners": 5, "epoch": 42,
    }
    return ProbeResult(
        state=UP, url=NODES[0]["endpoint"], status_code=200, response_ms=42.0,
        ok=True, version=data.get("version"), uptime_s=data.get("uptime_s"),
        data=data, **overrides,
    )


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global state before each test."""
    node_status.clear()
    history.clear()
    incidents.clear()


class TestCheckNode:
    """Tests for individual node health checks."""

    def test_healthy_node(self):
        with patch("status_server.probe_health", return_value=_up_probe()):
            result = check_node(NODES[0])
        assert result["up"] is True
        assert result["state"] == "up"
        assert result["version"] == "1.2.3"
        assert result["active_miners"] == 5
        assert result["current_epoch"] == 42
        assert "response_ms" in result
        assert "checked_at" in result

    def test_impostor_node_html_200(self):
        """HTTP 200 with an HTML body must NOT be up (issue #17180)."""
        impostor = ProbeResult(
            state=IMPOSTOR, url=NODES[0]["endpoint"], status_code=200,
            response_ms=31.0, content_type="text/html",
            detail="HTTP 200 with Content-Type text/html — an HTML page, not a RustChain node (impostor)",
        )
        with patch("status_server.probe_health", return_value=impostor):
            result = check_node(NODES[0])
        assert result["up"] is False
        assert result["state"] == "impostor"
        assert result["status_code"] == 200
        assert "impostor" in result["error"].lower()

    def test_down_node_http_error(self):
        down = ProbeResult(state=DOWN, url=NODES[0]["endpoint"], status_code=500, detail="HTTP 500")
        with patch("status_server.probe_health", return_value=down):
            result = check_node(NODES[0])
        assert result["up"] is False
        assert result["state"] == "down"
        assert result["status_code"] == 500

    def test_down_node_connection_error(self):
        unreach = ProbeResult(state=UNREACHABLE, url=NODES[0]["endpoint"], detail="Connection refused")
        with patch("status_server.probe_health", return_value=unreach):
            result = check_node(NODES[0])
        assert result["up"] is False
        assert result["state"] == "unreachable"
        assert "Connection refused" in result["error"]

    def test_down_node_timeout(self):
        with patch("status_server.probe_health", side_effect=Exception("timed out")):
            result = check_node(NODES[0])
        assert result["up"] is False
        assert result["state"] == "unreachable"


class TestPollAll:
    """Tests for the polling cycle."""

    def test_poll_all_healthy(self):
        with patch("status_server.probe_health", return_value=_up_probe(
                data={"ok": True, "version": "1.0", "miners": 3, "epoch": 10})):
            with patch("status_server.save_state"):
                poll_all()
        assert len(node_status) == 4
        for nid, status in node_status.items():
            assert status["up"] is True
            assert status["state"] == "up"

    def test_poll_all_impostor_marks_node_not_up(self):
        """An SPA answering 200 on /health must surface as impostor."""
        impostor = ProbeResult(
            state=IMPOSTOR, url=NODES[0]["endpoint"], status_code=200,
            content_type="text/html", response_ms=20.0,
            detail="HTTP 200 with Content-Type text/html — not a RustChain node (impostor)",
        )
        with patch("status_server.probe_health", return_value=impostor):
            with patch("status_server.save_state"):
                poll_all()
        assert node_status["node-1"]["up"] is False
        assert node_status["node-1"]["state"] == "impostor"

    def test_incident_logged_on_down(self):
        # First poll: all up
        with patch("status_server.probe_health", return_value=_up_probe()):
            with patch("status_server.save_state"):
                poll_all()
        assert len(incidents) == 0

        # Second poll: node-1 down
        def side_effect(url, **kwargs):
            if "50.28.86.131" in url:
                raise Exception("Connection refused")
            return _up_probe()

        with patch("status_server.probe_health", side_effect=side_effect):
            with patch("status_server.save_state"):
                poll_all()
        assert len(incidents) >= 1
        assert incidents[0]["event"] == "down"
        assert "Node 1" in incidents[0]["node"]

    def test_incident_logged_on_impostor(self):
        with patch("status_server.probe_health", return_value=_up_probe()):
            with patch("status_server.save_state"):
                poll_all()
        assert len(incidents) == 0

        impostor = ProbeResult(
            state=IMPOSTOR, url=NODES[0]["endpoint"], status_code=200,
            content_type="text/html", response_ms=20.0,
            detail="HTTP 200 with Content-Type text/html — not a RustChain node (impostor)",
        )

        def side_effect(url, **kwargs):
            if "50.28.86.131" in url:
                return impostor
            return _up_probe()

        with patch("status_server.probe_health", side_effect=side_effect):
            with patch("status_server.save_state"):
                poll_all()
        assert len(incidents) >= 1
        assert incidents[0]["event"] == "impostor"
        assert "Node 1" in incidents[0]["node"]

    def test_incident_recovery(self):
        # Setup: node-1 is down
        node_status["node-1"] = {"up": False, "name": "Node 1"}
        with patch("status_server.probe_health", return_value=_up_probe()):
            with patch("status_server.save_state"):
                poll_all()
        recovery = [i for i in incidents if i["event"] == "recovered" and "Node 1" in i["node"]]
        assert len(recovery) >= 1


class TestAPI:
    """Tests for API endpoints."""

    def test_status_endpoint(self, client):
        with patch("status_server.probe_health", return_value=_up_probe(
                data={"ok": True, "version": "1.0", "miners": 2, "epoch": 5})):
            with patch("status_server.save_state"):
                poll_all()
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "nodes" in data
        assert "overall" in data
        assert data["overall"] == "operational"
        assert data["nodes_up"] == 4
        assert data["nodes_impostor"] == 0

    def test_status_degraded(self, client):
        node_status["node-1"] = {"up": False, "state": "down", "name": "Node 1"}
        node_status["node-2"] = {"up": True, "state": "up", "name": "Node 2"}
        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert data["overall"] == "degraded"

    def test_status_impostor_overall(self, client):
        """An impostor node must be visibly distinct from up in the API."""
        node_status["node-1"] = {"up": False, "state": "impostor", "name": "Node 1",
                                 "error": "HTTP 200 with Content-Type text/html"}
        node_status["node-2"] = {"up": True, "state": "up", "name": "Node 2"}
        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert data["overall"] == "impostor"
        assert data["nodes_impostor"] == 1
        assert data["nodes_up"] == 1
        node1 = next(n for n in data["nodes"] if n["name"] == "Node 1")
        assert node1["state"] == "impostor"
        assert node1["up"] is False

    def test_history_endpoint(self, client):
        history["node-1"] = [{"t": "2026-03-24T12:00:00Z", "up": True, "ms": 50}]
        resp = client.get("/api/history/node-1")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data) == 1

    def test_incidents_endpoint(self, client):
        incidents.append({"node": "Node 1", "event": "down", "time": "2026-03-24T12:00:00Z"})
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data) == 1

    def test_uptime_endpoint(self, client):
        history["node-1"] = [
            {"t": "2026-03-24T12:00:00Z", "up": True, "ms": 50},
            {"t": "2026-03-24T12:01:00Z", "up": True, "ms": 45},
            {"t": "2026-03-24T12:02:00Z", "up": False, "ms": 0},
        ]
        resp = client.get("/api/uptime")
        data = json.loads(resp.data)
        assert "node-1" in data
        assert data["node-1"]["uptime_pct"] == pytest.approx(66.67, abs=0.1)

    def test_rss_feed(self, client):
        incidents.append({"node": "Node 1", "event": "down", "time": "2026-03-24T12:00:00Z"})
        resp = client.get("/feed.xml")
        assert resp.status_code == 200
        assert b"<rss" in resp.data
        assert b"Node 1" in resp.data

    def test_rss_feed_escapes_incident_fields(self, client):
        incidents.append({
            "node": 'Node <1>',
            "event": 'down </title><item><title>POISON</title></item>',
            "detail": 'detail & "quotes" </description><item><title>POISON</title></item>',
            "time": "2026-03-24T12:00:00Z",
        })

        resp = client.get("/feed.xml")

        assert resp.status_code == 200
        assert b"</title><item><title>POISON</title></item>" not in resp.data
        assert b"</description><item><title>POISON</title></item>" not in resp.data
        assert b"Node &lt;1&gt;" in resp.data
        assert b"detail &amp; &quot;quotes&quot;" in resp.data

    def test_index_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_page_escapes_dynamic_status_fields(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")

        # escapeHtml helper still present for legacy callers
        assert "function escapeHtml(value)" in html
        # Class-name whitelist helper to prevent attribute breakout
        assert "function safeClass(value" in html
        assert "ALLOWED_STATUS_CLASSES" in html
        # No raw template interpolation of untrusted fields into innerHTML
        assert "${node.name}" not in html
        assert "${i.detail?' · '+i.detail:''}" not in html
        # Nodes must be built via safe DOM construction, not innerHTML
        assert "card.innerHTML" not in html
        assert "nameSpan.textContent = node.name" in html
        assert "badge.textContent = badgeText" in html
        # impostor must be a whitelisted, rendered badge state (issue #17180)
        assert "'impostor'" in html
        assert "IMPOSTOR" in html
        # Incident rows must be built with createElement/textContent
        assert "evt.textContent = " in html
        assert "incEl.innerHTML" not in html
        # Uptime bar must use safeClass, not direct interpolation
        assert "tick ${safeClass(s)}" in html


class TestStaticDashboardFiles:
    """Static-file checks for the GitHub Pages health dashboard surface.

    These files are not served by the Flask app at runtime but are published
    from the repository itself, so any unsafe interpolation in them is a
    shipped XSS sink on the public status page.
    """

    @staticmethod
    def _read(rel_path):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, rel_path), "r", encoding="utf-8") as fh:
            return fh.read()

    def test_status_index_html_escapes_node_and_incident_fields(self):
        html = self._read("index.html")

        # Class-name whitelist helper to prevent attribute breakout
        assert "function safeClass(value" in html
        assert 'STATUS_WHITELIST' in html
        # No innerHTML assignments that interpolate untrusted node fields.
        assert "${result.node.name}" not in html
        assert "${result.node.location}" not in html
        assert "${result.node.origin}" not in html
        # Untrusted fields must flow through textContent / className.
        assert 'title.textContent = result.node.name' in html
        assert 'loc.textContent = result.node.location' in html
        assert 'originSpan.textContent = result.node.origin' in html
        assert 'strong.textContent = result.node.name' in html
        # No `result.node.X` interpolated into a class attribute.
        assert 'class="${result.node.' not in html

    def test_network_status_html_escapes_base_and_message(self):
        # website/static/ is the canonical copy; docs/ mirrors it.
        for rel_path in (
            "../website/static/network-status.html",
            "../docs/network-status.html",
        ):
            html = self._read(rel_path)

            # No template-string innerHTML that interpolates the URL base
            assert '<div class="font-mono text-xs break-all">${base}</div>' not in html
            assert 'row.innerHTML = `' not in html
            # base must be assigned through textContent
            assert 'urlSpan.textContent = base' in html
            assert 'upVal.textContent = uptimePct(base)' in html


class TestHistoryTrimming:
    """Test that history is properly trimmed to 24 hours."""

    def test_old_entries_removed(self):
        from datetime import datetime, timedelta
        old_time = (datetime.utcnow() - timedelta(hours=25)).isoformat() + "Z"
        new_time = datetime.utcnow().isoformat() + "Z"
        history["node-1"] = [
            {"t": old_time, "up": True, "ms": 50},
            {"t": new_time, "up": True, "ms": 45},
        ]
        with patch("status_server.probe_health", return_value=_up_probe()):
            with patch("status_server.save_state"):
                poll_all()
        # Old entry should be trimmed
        old_entries = [h for h in history["node-1"] if h["t"] == old_time]
        assert len(old_entries) == 0
