import importlib.util
import sqlite3
import sys
import types
from concurrent.futures import ThreadPoolExecutor
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
    monkeypatch.setattr(keeper.secrets, "token_hex", lambda n: "a" * (n * 2))

    response = keeper.app.test_client().post(
        "/api/faucet/drip",
        json={"address": "  RTC1TestWalletAddress1234567890  "},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Drip successful! 0.5 RTC sent to RTC1TestWalletAddress1234567890"
    assert body["tx_hash"] == "a" * 64

    with sqlite3.connect(tmp_path / "faucet_service" / "faucet.db") as conn:
        row = conn.execute(
            "SELECT address, amount FROM faucet_claims"
        ).fetchone()
    assert row == ("RTC1TestWalletAddress1234567890", 0.5)


def test_faucet_drip_rejects_invalid_wallet_string(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)

    response = keeper.app.test_client().post(
        "/api/faucet/drip",
        json={"address": "not-a-wallet"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid wallet address",
    }


def test_faucet_claim_record_is_atomic(tmp_path, monkeypatch):
    keeper = load_keeper_explorer(tmp_path, monkeypatch)
    address = "RTC1RaceWalletAddress123456789"
    ip = "198.51.100.10"

    def attempt_claim(_):
        return keeper.record_faucet_claim_if_allowed(address, ip, 0.5)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(attempt_claim, range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7

    with sqlite3.connect(tmp_path / "faucet_service" / "faucet.db") as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM faucet_claims WHERE address = ? OR ip_address = ?",
            (address, ip),
        ).fetchone()[0]

    assert count == 1
