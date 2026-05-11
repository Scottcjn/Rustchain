import importlib.util
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


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
