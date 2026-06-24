# SPDX-License-Identifier: MIT
import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_websocket_feed_module():
    module_path = REPO_ROOT / "node" / "websocket_feed.py"
    spec = importlib.util.spec_from_file_location(
        "test_node_websocket_feed_env_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_websocket_feed_invalid_numeric_env_falls_back(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_PORT", "not-a-port")
    monkeypatch.setenv("WS_POLL_INTERVAL", "not-a-float")
    monkeypatch.setenv("WS_MAX_EVENTS", "not-an-int")

    module = load_websocket_feed_module()

    assert module.WS_PORT == 8765
    assert module.POLL_INTERVAL == 3.0
    assert module.MAX_EVENTS == 100
    assert "*" not in module.WEBSOCKET_CORS_ORIGINS

    feed = module.WebSocketFeed()
    assert feed.block_history.maxlen == 100
    assert feed.attestation_history.maxlen == 100


def test_websocket_feed_valid_numeric_env_is_preserved(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_PORT", "9001")
    monkeypatch.setenv("WS_POLL_INTERVAL", "0.25")
    monkeypatch.setenv("WS_MAX_EVENTS", "7")

    module = load_websocket_feed_module()

    assert module.WS_PORT == 9001
    assert module.POLL_INTERVAL == 0.25
    assert module.MAX_EVENTS == 7


def test_websocket_feed_default_cors_origins_are_allowlisted(monkeypatch):
    monkeypatch.delenv("WEBSOCKET_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("WEBSOCKET_PORT", "9001")

    module = load_websocket_feed_module()

    assert module.WEBSOCKET_CORS_ORIGINS == [
        "https://rustchain.org",
        "https://www.rustchain.org",
        "http://localhost:9001",
        "http://127.0.0.1:9001",
    ]


def test_websocket_feed_cors_origins_parse_explicit_allowlist(monkeypatch):
    monkeypatch.setenv(
        "WEBSOCKET_CORS_ORIGINS",
        "https://dash.rustchain.org, https://ops.rustchain.org, https://dash.rustchain.org",
    )

    module = load_websocket_feed_module()

    assert module.WEBSOCKET_CORS_ORIGINS == [
        "https://dash.rustchain.org",
        "https://ops.rustchain.org",
    ]


def test_websocket_feed_cors_origins_reject_wildcard(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_CORS_ORIGINS", "https://dash.rustchain.org,*")

    with pytest.raises(ValueError, match="must not include"):
        load_websocket_feed_module()


def test_websocket_feed_passes_allowlist_to_socketio(monkeypatch):
    socketio_module = types.ModuleType("flask_socketio")
    instances = []

    class SocketIO:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            instances.append(self)

        def on(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def emit(self, *args, **kwargs):
            pass

    socketio_module.SocketIO = SocketIO
    socketio_module.emit = lambda *args, **kwargs: None
    socketio_module.join_room = lambda *args, **kwargs: None
    socketio_module.leave_room = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_socketio", socketio_module)
    monkeypatch.setenv("WEBSOCKET_CORS_ORIGINS", "https://dash.rustchain.org")

    module = load_websocket_feed_module()
    feed = module.WebSocketFeed()
    feed.init_app(module.Flask("test-websocket-feed"))

    assert instances[0].kwargs["cors_allowed_origins"] == ["https://dash.rustchain.org"]
