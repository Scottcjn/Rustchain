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
        conn.execute(
            """
            CREATE TABLE relay_agents (
                agent_id TEXT PRIMARY KEY,
                pubkey_hex TEXT NOT NULL,
                name TEXT,
                status TEXT DEFAULT 'active',
                coinbase_address TEXT DEFAULT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            )
            """
        )
        conn.execute(
            """INSERT INTO relay_agents
               (agent_id, pubkey_hex, name, coinbase_address, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "relay-1",
                "00" * 32,
                "Relay One",
                "0x1234567890123456789012345678901234567890",
                1,
                1,
            ),
        )

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


def test_set_agent_wallet_rejects_non_hex_base_address(client):
    response = client.post(
        "/api/agents/agent-1/wallet",
        json={"coinbase_address": "0xZZ34567890123456789012345678901234567890"},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid Base address"


def test_set_agent_wallet_preserves_valid_address(client):
    response = client.post(
        "/api/agents/agent-1/wallet",
        json={"coinbase_address": " 0x1234567890123456789012345678901234567890 "},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 200
    assert response.get_json()["coinbase_address"] == "0x1234567890123456789012345678901234567890"

def test_get_agent_wallet_returns_relay_wallet(client):
    response = client.get("/api/agents/relay-1/wallet")

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "relay"
    assert body["coinbase_address"] == "0x1234567890123456789012345678901234567890"
