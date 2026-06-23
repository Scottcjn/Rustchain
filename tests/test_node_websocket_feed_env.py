# SPDX-License-Identifier: MIT
import importlib.util
import sys
from pathlib import Path


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
