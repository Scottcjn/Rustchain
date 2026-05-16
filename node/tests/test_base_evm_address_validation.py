import importlib.util
import sqlite3
from pathlib import Path

from flask import Flask


NODE_DIR = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


beacon_x402 = _load_module("beacon_x402_under_test", NODE_DIR / "beacon_x402.py")
rustchain_x402 = _load_module("rustchain_x402_under_test", NODE_DIR / "rustchain_x402.py")


INVALID_BASE_ADDRESSES = [
    "0x1234",
    "0x" + ("g" * 40),
]


def test_rustchain_x402_rejects_short_and_non_hex_coinbase_addresses(tmp_path, monkeypatch):
    db_path = tmp_path / "balances.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, miner_pk TEXT)")
    conn.execute("INSERT INTO balances (miner_id, miner_pk) VALUES (?, ?)", ("miner-1", "pk-1"))
    conn.commit()
    conn.close()

    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")
    app = Flask(__name__)
    rustchain_x402.init_app(app, str(db_path))
    client = app.test_client()

    for address in INVALID_BASE_ADDRESSES:
        response = client.post(
            "/wallet/link-coinbase",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"miner_id": "miner-1", "coinbase_address": address},
        )

        assert response.status_code == 400
        assert "Invalid Base address" in response.get_json()["error"]


def test_beacon_x402_rejects_short_and_non_hex_agent_wallets(monkeypatch):
    monkeypatch.setenv("BEACON_ADMIN_KEY", "test-admin-key")
    monkeypatch.setattr(beacon_x402, "_run_migrations", lambda db_path: None)

    def get_db():
        raise AssertionError("invalid wallet requests should not touch the database")

    app = Flask(__name__)
    beacon_x402.init_app(app, get_db)
    client = app.test_client()

    for address in INVALID_BASE_ADDRESSES:
        response = client.post(
            "/api/agents/beacon-1/wallet",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"coinbase_address": address},
        )

        assert response.status_code == 400
        assert "Invalid Base address" in response.get_json()["error"]
