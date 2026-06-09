import importlib.util
import sys
from pathlib import Path
from types import MethodType
from urllib.parse import urlparse

import pytest
import requests


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_explorer_server():
    module_name = "explorer_server_under_test"
    module_path = REPO_ROOT / "explorer" / "explorer_server.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    module.ExplorerHandler._cache.clear()
    return module


def make_handler(module):
    handler = module.ExplorerHandler.__new__(module.ExplorerHandler)
    handler.sent = None

    def capture_json(self, data, status=200, headers=None):
        self.sent = {
            "data": data,
            "status": status,
            "headers": headers or {},
        }

    handler.send_json = MethodType(capture_json, handler)
    return handler


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "admin/status",
        "api/admin",
        "api/miners/latest",
        "../health",
        "%2e%2e/health",
        "api%2fminers",
    ],
)
def test_proxy_rejects_unlisted_or_confused_paths_without_upstream_request(
    endpoint,
    monkeypatch,
):
    explorer_server = load_explorer_server()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("blocked proxy path should not contact upstream")

    monkeypatch.setattr(explorer_server.requests, "get", fail_if_called)
    handler = make_handler(explorer_server)

    handler.handle_proxy(endpoint, urlparse(f"/api/proxy/{endpoint}"))

    assert handler.sent["status"] == 404
    assert handler.sent["data"]["message"] == "Not Found"


def test_proxy_forwards_allowlisted_endpoint_with_query_params(monkeypatch):
    explorer_server = load_explorer_server()
    monkeypatch.setattr(explorer_server, "API_BASE", "https://node.example/base/")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"miners": []}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(explorer_server.requests, "get", fake_get)
    handler = make_handler(explorer_server)
    parsed = urlparse("/api/proxy/api/miners?limit=10&tag=&tag=vintage")

    handler.handle_proxy("api/miners", parsed)

    assert captured == {
        "url": "https://node.example/base/api/miners",
        "params": {"limit": ["10"], "tag": ["", "vintage"]},
        "timeout": explorer_server.API_TIMEOUT,
    }
    assert handler.sent["status"] == 200
    assert handler.sent["data"] == {"miners": []}
    assert handler.sent["headers"] == {"X-Cache": "MISS"}


def test_proxy_allows_hall_leaderboard_query(monkeypatch):
    explorer_server = load_explorer_server()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"leaderboard": []}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr(explorer_server.requests, "get", fake_get)
    handler = make_handler(explorer_server)
    parsed = urlparse("/api/proxy/hall/leaderboard?limit=10")

    handler.handle_proxy("hall/leaderboard", parsed)

    assert captured["url"].endswith("/hall/leaderboard")
    assert captured["params"] == {"limit": ["10"]}
    assert handler.sent["data"] == {"leaderboard": []}


def test_proxy_uses_normalized_cache_key_for_encoded_allowed_path(monkeypatch):
    explorer_server = load_explorer_server()
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok"}

    def fake_get(*_args, **_kwargs):
        calls["count"] += 1
        return FakeResponse()

    monkeypatch.setattr(explorer_server.requests, "get", fake_get)
    first_handler = make_handler(explorer_server)
    second_handler = make_handler(explorer_server)

    first_handler.handle_proxy("%68ealth", urlparse("/api/proxy/%68ealth"))
    second_handler.handle_proxy("health", urlparse("/api/proxy/health"))

    assert calls["count"] == 1
    assert first_handler.sent["headers"] == {"X-Cache": "MISS"}
    assert second_handler.sent["headers"] == {"X-Cache": "HIT"}


def test_proxy_hides_upstream_exception_details(monkeypatch):
    explorer_server = load_explorer_server()
    sensitive = "http://10.0.0.8:8000/admin?token=secret /srv/rustchain/node.py"

    def fake_get(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError(sensitive)

    monkeypatch.setattr(explorer_server.requests, "get", fake_get)
    handler = make_handler(explorer_server)

    handler.handle_proxy("health", urlparse("/api/proxy/health"))

    assert handler.sent["status"] == 502
    assert handler.sent["data"]["message"] == "Bad Gateway"
    assert sensitive not in str(handler.sent["data"])
