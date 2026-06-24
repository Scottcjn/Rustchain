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
    assert body["status"] == "claim_recorded"
    assert body["settlement_status"] == "recorded_only"
    assert body["amount"] == 0.5
    assert body["address"] == "rtc-test-wallet"
    assert body["message"] == (
        "Faucet claim recorded for rtc-test-wallet; no on-chain transfer "
        "was submitted by this explorer"
    )
    assert len(body["receipt_id"]) == 64
    assert body["tx_hash"] is None

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

    # Issue #4904: paths outside the allowlist short-circuit with 403 and
    # never call requests.get, so no internal connection error can leak.
    response = keeper.app.test_client().get("/api/proxy/blocks/latest")
    assert response.status_code == 403
    assert response.get_json() == {"error": "Proxy path not allowed"}
    assert internal_error not in response.get_data(as_text=True)

    # An allowlisted path that does reach requests.get returns the sanitized
    # 502 response and does not surface the internal connection detail.
    response = keeper.app.test_client().get("/api/proxy/blocks")
    assert response.status_code == 502
    body = response.get_json()
    assert body == {"error": "Node connection failed"}
    assert internal_error not in response.get_data(as_text=True)
