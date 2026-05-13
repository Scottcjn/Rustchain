# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "node" / "server_proxy.py"


def load_server_proxy():
    spec = importlib.util.spec_from_file_location("server_proxy_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


class FakeResponse:
    def __init__(self, payload, status_code=200, content_type="application/json"):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.text = "text-response"

    def json(self):
        return self._payload


def test_proxy_blocks_unlisted_admin_path_before_upstream(monkeypatch):
    module = load_server_proxy()

    def fail_post(*args, **kwargs):
        raise AssertionError("blocked admin path should not reach upstream")

    monkeypatch.setattr(module.requests, "post", fail_post)

    client = module.app.test_client()
    response = client.post("/api/admin/delete", json={"danger": True})

    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}


def test_proxy_blocks_path_traversal_before_upstream(monkeypatch):
    module = load_server_proxy()

    def fail_get(*args, **kwargs):
        raise AssertionError("path traversal should not reach upstream")

    monkeypatch.setattr(module.requests, "get", fail_get)

    client = module.app.test_client()
    response = client.get("/api/stats/../admin")

    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}


def test_proxy_allows_public_stats_get_with_query(monkeypatch):
    module = load_server_proxy()
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return FakeResponse({"ok": True})

    monkeypatch.setattr(module.requests, "get", fake_get)

    client = module.app.test_client()
    response = client.get("/api/stats?miner_id=demo")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert calls == [
        {
            "url": "http://localhost:8088/api/stats",
            "params": {"miner_id": "demo"},
            "timeout": 10,
        }
    ]


def test_proxy_allows_public_mine_post_json(monkeypatch):
    module = load_server_proxy()
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse({"accepted": True}, status_code=201)

    monkeypatch.setattr(module.requests, "post", fake_post)

    client = module.app.test_client()
    response = client.post("/api/mine", json={"wallet": "RTCdemo"})

    assert response.status_code == 201
    assert response.get_json() == {"accepted": True}
    assert calls == [
        {
            "url": "http://localhost:8088/api/mine",
            "json": {"wallet": "RTCdemo"},
            "headers": {"Content-Type": "application/json"},
            "timeout": 10,
        }
    ]


def test_proxy_rejects_missing_json_for_allowed_post(monkeypatch):
    module = load_server_proxy()

    def fail_post(*args, **kwargs):
        raise AssertionError("missing JSON should not reach upstream")

    monkeypatch.setattr(module.requests, "post", fail_post)

    client = module.app.test_client()
    response = client.post("/api/register", data="not-json", content_type="text/plain")

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}
