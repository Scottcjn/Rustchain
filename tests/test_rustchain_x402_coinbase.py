# SPDX-License-Identifier: MIT

import sqlite3

from flask import Flask

from node import rustchain_x402


ADMIN_KEY = "test-admin-key"
BASE_ADDRESS = "0x1234567890123456789012345678901234567890"


def _client(db_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    app = Flask(__name__)
    app.config["TESTING"] = True
    rustchain_x402.init_app(app, str(db_path))
    return app.test_client()


def test_link_coinbase_updates_miner_id_balance_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "x402.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, balance_rtc REAL)")
        conn.execute("INSERT INTO balances (miner_id, balance_rtc) VALUES (?, ?)", ("miner-1", 1.0))

    response = _client(db_path, monkeypatch).post(
        "/wallet/link-coinbase",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={"miner_id": "miner-1", "coinbase_address": BASE_ADDRESS},
    )

    assert response.status_code == 200
    assert response.get_json()["miner_id"] == "miner-1"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT coinbase_address FROM balances WHERE miner_id = ?", ("miner-1",)).fetchone()
    assert row == (BASE_ADDRESS,)


def test_link_coinbase_updates_miner_pk_balance_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "x402.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL)")
        conn.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)", ("miner-pk-1", 1.0))

    response = _client(db_path, monkeypatch).post(
        "/wallet/link-coinbase",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={"miner_id": "miner-pk-1", "coinbase_address": BASE_ADDRESS},
    )

    assert response.status_code == 200
    assert response.get_json()["miner_id"] == "miner-pk-1"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT coinbase_address FROM balances WHERE miner_pk = ?", ("miner-pk-1",)).fetchone()
    assert row == (BASE_ADDRESS,)
