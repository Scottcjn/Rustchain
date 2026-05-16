import sqlite3
import sys
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node import rustchain_x402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "wallets.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, miner_pk TEXT)")
        conn.execute(
            "INSERT INTO balances (miner_id, miner_pk) VALUES (?, ?)",
            ("miner-1", "pk-1"),
        )
        conn.commit()

    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key")

    app = Flask(__name__)
    app.config["TESTING"] = True
    rustchain_x402.init_app(app, str(db_path))
    with app.test_client() as test_client:
        yield test_client


def test_link_coinbase_rejects_non_object_json(client):
    response = client.post(
        "/wallet/link-coinbase",
        json=["miner_id"],
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object body is required"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("miner_id", ["miner-1"]),
        ("coinbase_address", {"address": "0x1234567890123456789012345678901234567890"}),
    ],
)
def test_link_coinbase_rejects_non_string_fields(client, field, value):
    payload = {
        "miner_id": "miner-1",
        "coinbase_address": "0x1234567890123456789012345678901234567890",
    }
    payload[field] = value

    response = client.post(
        "/wallet/link-coinbase",
        json=payload,
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == f"{field} must be a string"


def test_link_coinbase_preserves_valid_request(client):
    response = client.post(
        "/wallet/link-coinbase",
        json={
            "miner_id": " miner-1 ",
            "coinbase_address": " 0x1234567890123456789012345678901234567890 ",
        },
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["miner_id"] == "miner-1"
    assert body["coinbase_address"] == "0x1234567890123456789012345678901234567890"
