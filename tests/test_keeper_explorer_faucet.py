import importlib.util
import sqlite3
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def stub_flask_cors(monkeypatch):
    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_cors", flask_cors)


def load_keeper_explorer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module_name = "test_keeper_explorer"
    module_path = REPO_ROOT / "keeper_explorer.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_faucet_drip_rejects_non_object_json(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)

    response = keeper.app.test_client().post("/api/faucet/drip", json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "JSON object required",
    }


def test_faucet_drip_rejects_non_string_address(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)

    response = keeper.app.test_client().post("/api/faucet/drip", json={"address": 123})

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Wallet address required",
    }


def test_faucet_drip_records_valid_address(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)

    response = keeper.app.test_client().post(
        "/api/faucet/drip",
        json={"address": "  rtc-test-wallet  "},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Drip successful! 0.5 RTC sent to rtc-test-wallet"
    assert len(body["tx_hash"]) == 64

    with sqlite3.connect(tmp_path / "faucet_service" / "faucet.db") as conn:
        row = conn.execute(
            "SELECT address, amount FROM faucet_claims"
        ).fetchone()
    assert row == ("rtc-test-wallet", 0.5)


def test_proxy_hides_internal_connection_errors(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    internal_error = (
        "Connection refused for http://10.0.0.5:8000/private/admin "
        "from /srv/rustchain/node.py"
    )

    def fail_request(*_args, **_kwargs):
        raise RuntimeError(internal_error)

    monkeypatch.setattr(keeper.requests, "get", fail_request)

    response = keeper.app.test_client().get("/api/proxy/headers/tip")

    assert response.status_code == 502
    body = response.get_json()
    assert body == {"error": "Node connection failed"}
    assert internal_error not in response.get_data(as_text=True)


def test_proxy_rejects_unlisted_internal_paths_before_upstream(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("blocked proxy path reached upstream")

    monkeypatch.setattr(keeper.requests, "get", fail_if_called)

    response = keeper.app.test_client().get("/api/proxy/admin/wallet-review-holds")

    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}


def test_proxy_rejects_dot_segments_before_upstream(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("blocked proxy path reached upstream")

    monkeypatch.setattr(keeper.requests, "get", fail_if_called)

    response = keeper.app.test_client().get("/api/proxy/headers/../admin")

    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}


def test_proxy_allows_safe_readonly_paths_and_strips_internal_headers(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    calls = []

    class FakeResponse:
        status_code = 200
        content = b'{"ok": true}'
        headers = {
            "Content-Type": "application/json",
            "Server": "Werkzeug/internal",
            "X-Internal-Node": "10.0.0.5",
        }

    def fake_get(url, params, timeout):
        calls.append((url, params.to_dict(), timeout))
        return FakeResponse()

    monkeypatch.setattr(keeper.requests, "get", fake_get)

    response = keeper.app.test_client().get("/api/proxy/headers/tip?limit=1")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert calls == [("http://localhost:8000/headers/tip", {"limit": "1"}, 5)]
    assert response.headers["Content-Type"] == "application/json"
    assert "Server" not in response.headers
    assert "X-Internal-Node" not in response.headers


def test_proxy_encodes_allowed_path_segments(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    calls = []

    class FakeResponse:
        status_code = 200
        content = b'{"balance": 0}'
        headers = {"Content-Type": "application/json"}

    def fake_get(url, params, timeout):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(keeper.requests, "get", fake_get)

    response = keeper.app.test_client().get("/api/proxy/balance/rtc wallet")

    assert response.status_code == 200
    assert calls == ["http://localhost:8000/balance/rtc%20wallet"]
