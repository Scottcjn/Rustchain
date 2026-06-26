import sqlite3
import sys

import pytest

integrated_node = sys.modules["integrated_node"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "wallets.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
        )
        db.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("still_worthy", 809610),
        )
        db.commit()

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path), raising=False)
    monkeypatch.setitem(
        integrated_node.api_wallet_balance.__globals__,
        "DB_PATH",
        str(db_path),
    )
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client


def test_wallet_balance_rejects_whitespace_wrapped_miner_id(client):
    response = client.get("/wallet/balance?miner_id=%20still_worthy")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid miner_id"}


def test_wallet_balance_rejects_wildcard_miner_id(client):
    response = client.get("/wallet/balance?miner_id=*")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid miner_id"}


def test_wallet_balance_keeps_canonical_identifier_unchanged(client):
    response = client.get("/wallet/balance?miner_id=still_worthy")

    assert response.status_code == 200
    assert response.get_json() == {
        "miner_id": "still_worthy",
        "amount_i64": 809610,
        "amount_rtc": 0.80961,
    }
