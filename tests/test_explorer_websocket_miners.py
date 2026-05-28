# SPDX-License-Identifier: MIT

import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_websocket_module(monkeypatch):
    socketio_module = types.ModuleType("flask_socketio")

    class SocketIO:
        def __init__(self, *args, **kwargs):
            pass

        def on(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    socketio_module.SocketIO = SocketIO
    socketio_module.emit = lambda *args, **kwargs: None
    socketio_module.join_room = lambda *args, **kwargs: None
    socketio_module.leave_room = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_socketio", socketio_module)

    module_path = REPO_ROOT / "explorer" / "explorer_websocket_server.py"
    spec = importlib.util.spec_from_file_location(
        "test_explorer_websocket_server_miners",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_websocket_state_tracks_current_api_miner_rows(monkeypatch):
    module = load_websocket_module(monkeypatch)
    state = module.ExplorerState()
    events = []
    state.subscribe(events.append)

    state.process_miners([
        {
            "miner": "RTCabc",
            "device_arch": "x86_64",
            "last_attest": 100,
            "antiquity_multiplier": 1.25,
        }
    ])
    state.process_miners([
        {
            "miner": "RTCabc",
            "device_arch": "x86_64",
            "last_attest": 200,
            "antiquity_multiplier": 1.25,
        }
    ])

    assert state.miners["RTCabc"][0] == 200
    assert events[-1]["type"] == "attestation"
    assert events[-1]["data"]["miner"] == "RTCabc"
    assert events[-1]["data"]["miner_id"] == "RTCabc"
    assert events[-1]["data"]["arch"] == "x86_64"
    assert events[-1]["data"]["multiplier"] == 1.25
