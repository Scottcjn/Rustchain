import importlib.util
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import Mock

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


def test_proxy_blocks_unlisted_internal_paths(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    get = Mock()
    monkeypatch.setattr(keeper.requests, "get", get)

    response = keeper.app.test_client().get("/api/proxy/wallet/transfer")

    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}
    get.assert_not_called()


def test_proxy_allows_read_only_paths_and_strips_internal_headers(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    upstream = types.SimpleNamespace(
        content=b'{"height": 7}',
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "Server": "internal-node",
            "X-Powered-By": "Flask",
        },
    )
    get = Mock(return_value=upstream)
    monkeypatch.setattr(keeper.requests, "get", get)

    response = keeper.app.test_client().get("/api/proxy/headers/tip?limit=1")

    assert response.status_code == 200
    assert response.data == b'{"height": 7}'
    assert response.headers["Content-Type"] == "application/json"
    assert "Server" not in response.headers
    assert "X-Powered-By" not in response.headers
    get.assert_called_once_with(
        "http://localhost:8000/headers/tip",
        params={"limit": ["1"]},
        timeout=5,
    )


def test_proxy_returns_generic_error_for_node_failures(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    monkeypatch.setattr(
        keeper.requests,
        "get",
        Mock(side_effect=keeper.requests.RequestException("localhost:8000 refused")),
    )

    response = keeper.app.test_client().get("/api/proxy/epoch")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Node connection error"}
