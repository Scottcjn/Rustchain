import importlib.util
from pathlib import Path


def load_server_proxy():
    module_path = Path(__file__).resolve().parents[1] / "node" / "server_proxy.py"
    spec = importlib.util.spec_from_file_location("server_proxy_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_api_url_rejects_dot_segments():
    proxy = load_server_proxy()

    assert proxy._build_local_api_url("../health") is None
    assert proxy._build_local_api_url("foo/../../health") is None
    assert proxy._build_local_api_url("./stats") is None


def test_local_api_url_quotes_path_segments():
    proxy = load_server_proxy()

    assert (
        proxy._build_local_api_url("wallet balance/miner 1")
        == "http://localhost:8088/api/wallet%20balance/miner%201"
    )


def test_proxy_rejects_encoded_parent_segment(monkeypatch):
    proxy = load_server_proxy()
    called = False

    def fake_get(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("requests.get should not be called")

    monkeypatch.setattr(proxy.requests, "get", fake_get)

    response = proxy.app.test_client().get("/api/%2e%2e/health")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid API path"
    assert called is False


def test_proxy_keeps_safe_requests_under_api(monkeypatch):
    proxy = load_server_proxy()
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "ok"
        headers = {"Content-Type": "text/plain"}

    def fake_get(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(proxy.requests, "get", fake_get)

    response = proxy.app.test_client().get("/api/stats")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"
    assert captured == {"url": "http://localhost:8088/api/stats", "timeout": 10}
