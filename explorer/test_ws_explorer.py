# SPDX-License-Identifier: MIT
"""Unit tests for RustChain Explorer WebSocket Feed (Bounty #2295)."""

import importlib.util
import json
import sys
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from ws_explorer_server import app, socketio, state, fetch_api, poll_and_broadcast


MODULE_PATH = Path(__file__).with_name("ws_explorer_server.py")


class _NoopThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


def load_ws_explorer_module(monkeypatch):
    module_name = "test_ws_explorer_server_env_module"
    monkeypatch.setattr(threading, "Thread", _NoopThread)
    sys.path.insert(0, str(MODULE_PATH.parent))
    try:
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(module_name, None)
    finally:
        try:
            sys.path.remove(str(MODULE_PATH.parent))
        except ValueError:
            pass
    return module


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def socket_client():
    app.config["TESTING"] = True
    client = socketio.test_client(app)
    yield client
    client.disconnect()


@pytest.fixture(autouse=True)
def reset_state():
    state["last_epoch"] = None
    state["last_miner_count"] = None
    state["last_block_hash"] = None
    state["connected_clients"] = 0
    state["total_updates"] = 0


class TestFetchAPI:
    def test_successful_fetch(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"epoch": 42}
        with patch("ws_explorer_server.requests.get", return_value=mock_resp):
            result = fetch_api("/epoch")
        assert result == {"epoch": 42}

    def test_failed_fetch_returns_none(self):
        with patch("ws_explorer_server.requests.get", side_effect=Exception("timeout")):
            result = fetch_api("/epoch")
        assert result is None

    def test_non_200_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("ws_explorer_server.requests.get", return_value=mock_resp):
            result = fetch_api("/health")
        assert result is None


class TestNumericEnv:
    def test_malformed_numeric_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("API_TIMEOUT", "not-a-timeout")
        monkeypatch.setenv("WS_POLL_INTERVAL", "not-an-interval")
        monkeypatch.setenv("WS_EXPLORER_PORT", "not-a-port")

        module = load_ws_explorer_module(monkeypatch)

        assert module.API_TIMEOUT == 8.0
        assert module.POLL_INTERVAL == 10.0
        assert module.PORT == 8060

    def test_valid_numeric_env_is_preserved(self, monkeypatch):
        monkeypatch.setenv("API_TIMEOUT", "2.5")
        monkeypatch.setenv("WS_POLL_INTERVAL", "0.75")
        monkeypatch.setenv("WS_EXPLORER_PORT", "9002")

        module = load_ws_explorer_module(monkeypatch)

        assert module.API_TIMEOUT == 2.5
        assert module.POLL_INTERVAL == 0.75
        assert module.PORT == 9002


class TestHTTPRoutes:
    def test_index_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_ws_status_endpoint(self, client):
        state["connected_clients"] = 3
        state["total_updates"] = 42
        resp = client.get("/api/ws-status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["connected_clients"] == 3
        assert data["total_updates"] == 42


class TestWebSocket:
    def test_connect_increments_clients(self, socket_client):
        assert state["connected_clients"] == 1

    def test_welcome_message(self, socket_client):
        received = socket_client.get_received()
        welcome_msgs = [m for m in received if m["name"] == "welcome"]
        assert len(welcome_msgs) >= 1
        assert "connected_clients" in welcome_msgs[0]["args"][0]

    def test_request_snapshot(self, socket_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"epoch": 100, "miners": []}
        with patch("ws_explorer_server.requests.get", return_value=mock_resp):
            socket_client.emit("request_snapshot")
        received = socket_client.get_received()
        snapshot_msgs = [m for m in received if m["name"] == "snapshot"]
        assert len(snapshot_msgs) >= 1

    def test_disconnect_decrements_clients(self):
        app.config["TESTING"] = True
        client = socketio.test_client(app)
        assert state["connected_clients"] == 1
        client.disconnect()
        assert state["connected_clients"] == 0


class TestStateTracking:
    def test_initial_state(self):
        assert state["last_epoch"] is None
        assert state["last_miner_count"] is None
        assert state["connected_clients"] == 0
        assert state["total_updates"] == 0

    def test_started_at_set(self):
        assert state["started_at"] is not None
        assert "Z" in state["started_at"]


class TestPolling:
    def test_poll_and_broadcast_handles_bare_miner_array(self):
        emitted = []

        def fake_fetch(path):
            if path == "/api/miners":
                return [{"miner_id": "miner-a", "hardware": "gpu", "multiplier": 1.5}]
            return None

        def fake_emit(event, payload, namespace="/"):
            emitted.append((event, payload, namespace))

        with (
            patch("ws_explorer_server.fetch_api", side_effect=fake_fetch),
            patch("ws_explorer_server.socketio.emit", side_effect=fake_emit),
            patch("ws_explorer_server.time.sleep", side_effect=KeyboardInterrupt),
        ):
            with pytest.raises(KeyboardInterrupt):
                poll_and_broadcast()

        assert emitted == [
            (
                "explorer_update",
                {
                    "miners": {
                        "count": 1,
                        "miners": [
                            {
                                "miner_id": "miner-a",
                                "hardware": "gpu",
                                "multiplier": 1.5,
                            }
                        ],
                    },
                    "server_time": emitted[0][1]["server_time"],
                },
                "/",
            )
        ]
