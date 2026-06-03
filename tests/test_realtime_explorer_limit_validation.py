import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def stub_flask_socketio(monkeypatch):
    socketio_module = types.ModuleType("flask_socketio")

    class SocketIO:
        def __init__(self, *args, **kwargs):
            pass

        def init_app(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            pass

        def on(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def run(self, *args, **kwargs):
            pass

    socketio_module.SocketIO = SocketIO
    socketio_module.emit = lambda *args, **kwargs: None
    socketio_module.join_room = lambda *args, **kwargs: None
    socketio_module.leave_room = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_socketio", socketio_module)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


@pytest.fixture
def realtime_module():
    module = load_module(
        "test_realtime_server",
        REPO_ROOT / "explorer" / "realtime_server.py",
    )
    module.state.blocks = [{"height": height} for height in range(150, 0, -1)]
    module.state.transactions = [{"txid": txid} for txid in range(250, 0, -1)]
    return module


@pytest.fixture
def websocket_module():
    module = load_module(
        "test_explorer_websocket_server",
        REPO_ROOT / "explorer" / "explorer_websocket_server.py",
    )
    module.state.blocks = [{"height": height} for height in range(150, 0, -1)]
    return module


@pytest.mark.parametrize(
    "query, expected_error",
    (
        ("limit=abc", "limit_must_be_integer"),
        ("limit=0", "limit_must_be_positive"),
        ("limit=-1", "limit_must_be_positive"),
    ),
)
def test_realtime_blocks_reject_invalid_limits(realtime_module, query, expected_error):
    response = realtime_module.app.test_client().get(f"/api/blocks?{query}")

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}


def test_realtime_blocks_caps_oversized_limit(realtime_module):
    response = realtime_module.app.test_client().get("/api/blocks?limit=500")

    assert response.status_code == 200
    assert len(response.get_json()) == 100


def test_realtime_transactions_caps_oversized_limit(realtime_module):
    response = realtime_module.app.test_client().get("/api/transactions?limit=500")

    assert response.status_code == 200
    assert len(response.get_json()) == 200


@pytest.mark.parametrize(
    "query, expected_error",
    (
        ("limit=abc", "limit_must_be_integer"),
        ("limit=0", "limit_must_be_positive"),
        ("limit=-1", "limit_must_be_positive"),
    ),
)
def test_websocket_blocks_reject_invalid_limits(websocket_module, query, expected_error):
    response = websocket_module.app.test_client().get(f"/api/explorer/blocks?{query}")

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}


def test_websocket_blocks_caps_oversized_limit(websocket_module):
    response = websocket_module.app.test_client().get("/api/explorer/blocks?limit=500")

    assert response.status_code == 200
    assert len(response.get_json()) == 100
