import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def load_socketio_cors():
    return load_module(
        "test_socketio_cors_helper",
        REPO_ROOT / "explorer" / "socketio_cors.py",
    )


@pytest.fixture
def socketio_stub(monkeypatch):
    socketio_module = types.ModuleType("flask_socketio")
    instances = []

    class SocketIO:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            instances.append(self)

        def init_app(self, *args, **kwargs):
            self.init_args = args
            self.init_kwargs = kwargs

        def on(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def emit(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            pass

    socketio_module.SocketIO = SocketIO
    socketio_module.emit = lambda *args, **kwargs: None
    socketio_module.join_room = lambda *args, **kwargs: None
    socketio_module.leave_room = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_socketio", socketio_module)
    return instances


def test_default_explorer_socketio_origins_are_allowlisted(monkeypatch):
    monkeypatch.delenv("EXPLORER_SOCKETIO_CORS_ORIGINS", raising=False)
    socketio_cors = load_socketio_cors()

    origins = socketio_cors.parse_socketio_cors_origins(local_port=8080)

    assert "*" not in origins
    assert "https://rustchain.org" in origins
    assert "https://www.rustchain.org" in origins
    assert "http://localhost:8080" in origins
    assert "http://127.0.0.1:8080" in origins


def test_explorer_socketio_origins_parse_explicit_allowlist(monkeypatch):
    monkeypatch.setenv(
        "EXPLORER_SOCKETIO_CORS_ORIGINS",
        "https://dash.rustchain.org, https://ops.rustchain.org, https://dash.rustchain.org",
    )
    socketio_cors = load_socketio_cors()

    assert socketio_cors.parse_socketio_cors_origins(local_port=8080) == [
        "https://dash.rustchain.org",
        "https://ops.rustchain.org",
    ]


def test_explorer_socketio_origins_reject_wildcard(monkeypatch):
    monkeypatch.setenv("EXPLORER_SOCKETIO_CORS_ORIGINS", "https://rustchain.org,*")
    socketio_cors = load_socketio_cors()

    with pytest.raises(ValueError, match="must not include"):
        socketio_cors.parse_socketio_cors_origins(local_port=8080)


def test_realtime_server_passes_allowlist_to_socketio(monkeypatch, socketio_stub):
    monkeypatch.setenv("EXPLORER_SOCKETIO_CORS_ORIGINS", "https://dash.rustchain.org")

    module = load_module(
        "test_realtime_server_cors",
        REPO_ROOT / "explorer" / "realtime_server.py",
    )

    assert module.SOCKETIO_CORS_ORIGINS == ["https://dash.rustchain.org"]
    assert socketio_stub[0].kwargs["cors_allowed_origins"] == ["https://dash.rustchain.org"]


def test_websocket_server_passes_allowlist_to_socketio(monkeypatch, socketio_stub):
    monkeypatch.setenv("EXPLORER_SOCKETIO_CORS_ORIGINS", "https://dash.rustchain.org")

    module = load_module(
        "test_explorer_websocket_server_cors",
        REPO_ROOT / "explorer" / "explorer_websocket_server.py",
    )

    assert module.SOCKETIO_CORS_ORIGINS == ["https://dash.rustchain.org"]
    assert socketio_stub[0].kwargs["cors_allowed_origins"] == ["https://dash.rustchain.org"]


def test_explorer_runtime_sources_no_longer_use_socketio_wildcard():
    for rel_path in (
        "explorer/ws_explorer_server.py",
        "explorer/realtime_server.py",
        "explorer/explorer_websocket_server.py",
    ):
        source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert 'cors_allowed_origins="*"' not in source
        assert "cors_allowed_origins='*'" not in source
