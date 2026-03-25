# SPDX-License-Identifier: MIT
"""Unit tests for RustChain Multi-Node Health Dashboard."""

import json
import pytest
from unittest.mock import patch, MagicMock
from status_server import app, check_node, poll_all, NODES, node_status, history, incidents


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
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "version": "1.2.3",
            "uptime_seconds": 86400,
            "active_miners": 5,
            "current_epoch": 42,
        }
        with patch("status_server.requests.get", return_value=mock_resp):
            result = check_node(NODES[0])
        assert result["up"] is True
        assert result["version"] == "1.2.3"
        assert result["active_miners"] == 5
        assert result["current_epoch"] == 42
        assert "response_ms" in result
        assert "checked_at" in result

    def test_down_node_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("status_server.requests.get", return_value=mock_resp):
            result = check_node(NODES[0])
        assert result["up"] is False
        assert result["status_code"] == 500

    def test_down_node_connection_error(self):
        with patch("status_server.requests.get", side_effect=Exception("Connection refused")):
            result = check_node(NODES[0])
        assert result["up"] is False
        assert "Connection refused" in result["error"]

    def test_down_node_timeout(self):
        import requests as req
        with patch("status_server.requests.get", side_effect=req.Timeout("timed out")):
            result = check_node(NODES[0])
        assert result["up"] is False


class TestPollAll:
    """Tests for the polling cycle."""

    def test_poll_all_healthy(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "1.0", "miners": 3, "epoch": 10}
        with patch("status_server.requests.get", return_value=mock_resp):
            with patch("status_server.save_state"):
                poll_all()
        assert len(node_status) == 4
        for nid, status in node_status.items():
            assert status["up"] is True

    def test_incident_logged_on_down(self):
        # First poll: all up
        mock_up = MagicMock()
        mock_up.status_code = 200
        mock_up.json.return_value = {"version": "1.0"}
        with patch("status_server.requests.get", return_value=mock_up):
            with patch("status_server.save_state"):
                poll_all()
        assert len(incidents) == 0

        # Second poll: node-1 down
        def side_effect(url, **kwargs):
            if "50.28.86.131" in url:
                raise Exception("Connection refused")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"version": "1.0"}
            return resp

        with patch("status_server.requests.get", side_effect=side_effect):
            with patch("status_server.save_state"):
                poll_all()
        assert len(incidents) >= 1
        assert incidents[0]["event"] == "down"
        assert "Node 1" in incidents[0]["node"]

    def test_incident_recovery(self):
        # Setup: node-1 is down
        node_status["node-1"] = {"up": False, "name": "Node 1"}
        mock_up = MagicMock()
        mock_up.status_code = 200
        mock_up.json.return_value = {"version": "1.0"}
        with patch("status_server.requests.get", return_value=mock_up):
            with patch("status_server.save_state"):
                poll_all()
        recovery = [i for i in incidents if i["event"] == "recovered" and "Node 1" in i["node"]]
        assert len(recovery) >= 1


class TestAPI:
    """Tests for API endpoints."""

    def test_status_endpoint(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "1.0", "miners": 2, "epoch": 5}
        with patch("status_server.requests.get", return_value=mock_resp):
            with patch("status_server.save_state"):
                poll_all()
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "nodes" in data
        assert "overall" in data
        assert data["overall"] == "operational"

    def test_status_degraded(self, client):
        node_status["node-1"] = {"up": False, "name": "Node 1"}
        node_status["node-2"] = {"up": True, "name": "Node 2"}
        resp = client.get("/api/status")
        data = json.loads(resp.data)
        assert data["overall"] == "degraded"

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

    def test_index_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


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
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "1.0"}
        with patch("status_server.requests.get", return_value=mock_resp):
            with patch("status_server.save_state"):
                poll_all()
        # Old entry should be trimmed
        old_entries = [h for h in history["node-1"] if h["t"] == old_time]
        assert len(old_entries) == 0
