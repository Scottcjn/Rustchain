import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests


MODULE_PATH = Path(__file__).resolve().parents[1] / "explorer" / "explorer_server.py"
SPEC = importlib.util.spec_from_file_location("explorer_server_under_test", MODULE_PATH)
explorer_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(explorer_server)


class DummyHandler:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = explorer_server.ExplorerHandler._cache_ttl
        self.json_response = None
        self.error_response = None

    def send_json(self, data, status=200, headers=None):
        self.json_response = {
            "data": data,
            "status": status,
            "headers": headers or {},
        }

    def send_error_json(self, status, message):
        self.error_response = {
            "status": status,
            "message": message,
        }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("health", "health"),
        ("epoch", "epoch"),
        ("api/miners", "api/miners"),
        ("api/transactions", "api/transactions"),
        ("blocks", "blocks"),
        ("hall/leaderboard", "hall/leaderboard"),
    ],
)
def test_normalize_proxy_endpoint_allows_explorer_read_paths(raw, expected):
    assert explorer_server.normalize_proxy_endpoint(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "/health",
        "health/",
        "admin/status",
        "api/admin",
        "api//miners",
        "api/../admin",
        "api/%2e%2e/admin",
        "api%2Fminers",
        r"api\\miners",
    ],
)
def test_normalize_proxy_endpoint_rejects_unlisted_and_confused_paths(raw):
    assert explorer_server.normalize_proxy_endpoint(raw) is None


def test_handle_proxy_rejects_blocked_path_before_upstream_request(monkeypatch):
    def fail_get(*args, **kwargs):
        raise AssertionError("blocked proxy path should not call upstream")

    monkeypatch.setattr(explorer_server.requests, "get", fail_get)

    handler = DummyHandler()
    explorer_server.ExplorerHandler.handle_proxy(
        handler,
        "admin/status",
        SimpleNamespace(query=""),
    )

    assert handler.error_response == {
        "status": 404,
        "message": "Proxy endpoint not allowed",
    }
    assert handler.json_response is None


def test_handle_proxy_forwards_allowed_path_with_parsed_query(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"ok": True, "miners": []})

    monkeypatch.setattr(explorer_server, "API_BASE", "https://node.example")
    monkeypatch.setattr(explorer_server.requests, "get", fake_get)

    handler = DummyHandler()
    explorer_server.ExplorerHandler.handle_proxy(
        handler,
        "api/miners",
        SimpleNamespace(query="limit=10&empty="),
    )

    assert calls == [
        (
            "https://node.example/api/miners",
            {
                "params": [("limit", "10"), ("empty", "")],
                "timeout": explorer_server.API_TIMEOUT,
            },
        )
    ]
    assert handler.json_response == {
        "data": {"ok": True, "miners": []},
        "status": 200,
        "headers": {"X-Cache": "MISS"},
    }


def test_handle_proxy_cache_uses_normalized_endpoint(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"height": 1})

    monkeypatch.setattr(explorer_server, "API_BASE", "https://node.example")
    monkeypatch.setattr(explorer_server.requests, "get", fake_get)

    handler = DummyHandler()
    parsed = SimpleNamespace(query="")
    explorer_server.ExplorerHandler.handle_proxy(handler, "blocks", parsed)
    explorer_server.ExplorerHandler.handle_proxy(handler, "blocks", parsed)

    assert len(calls) == 1
    assert handler.json_response["headers"] == {"X-Cache": "HIT"}


def test_handle_proxy_does_not_leak_upstream_exception_details(monkeypatch):
    def fake_get(url, **kwargs):
        raise requests.exceptions.RequestException(
            "connect to http://internal-admin.local/secrets failed"
        )

    monkeypatch.setattr(explorer_server.requests, "get", fake_get)

    handler = DummyHandler()
    explorer_server.ExplorerHandler.handle_proxy(
        handler,
        "health",
        SimpleNamespace(query=""),
    )

    assert handler.error_response == {
        "status": 502,
        "message": "Bad Gateway",
    }
