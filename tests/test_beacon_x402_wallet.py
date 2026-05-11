import sqlite3
import sys
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node import beacon_x402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(beacon_x402.X402_BEACON_SCHEMA)

    monkeypatch.setenv("BEACON_ADMIN_KEY", "test-admin-key")
    monkeypatch.setattr(beacon_x402, "_run_migrations", lambda _db_path: None)

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = Flask(__name__)
    app.config["TESTING"] = True
    beacon_x402.init_app(app, get_db)
    with app.test_client() as test_client:
        yield test_client


def test_set_agent_wallet_rejects_non_object_json(client):
    response = client.post(
        "/api/agents/agent-1/wallet",
        json=["coinbase_address"],
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object body is required"


def test_set_agent_wallet_rejects_non_string_coinbase_address(client):
    response = client.post(
        "/api/agents/agent-1/wallet",
        json={"coinbase_address": {"address": "0x1234567890123456789012345678901234567890"}},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "coinbase_address must be a string"


def test_set_agent_wallet_preserves_valid_address(client):
    response = client.post(
        "/api/agents/agent-1/wallet",
        json={"coinbase_address": " 0x1234567890123456789012345678901234567890 "},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 200
    assert response.get_json()["coinbase_address"] == "0x1234567890123456789012345678901234567890"
