import os
import sqlite3
import tempfile
from unittest.mock import patch

from flask import Flask

import beacon_x402
import rustchain_x402


def _make_rustchain_x402_app(db_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    rustchain_x402.init_app(app, db_path)
    return app


def _make_balances_db():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    with sqlite3.connect(tmp.name) as conn:
        conn.execute(
            """
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                miner_pk TEXT,
                balance INTEGER DEFAULT 0
            )
            """
        )
    return tmp.name


def test_rustchain_x402_link_coinbase_uses_constant_time_admin_key_compare(monkeypatch):
    db_path = _make_balances_db()
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin-key")

    try:
        app = _make_rustchain_x402_app(db_path)
        client = app.test_client()

        with patch("hmac.compare_digest", return_value=False) as compare_digest:
            response = client.post(
                "/wallet/link-coinbase",
                headers={"X-Admin-Key": "wrong-admin-key"},
                json={
                    "miner_id": "alice",
                    "coinbase_address": "0x0000000000000000000000000000000000000001",
                },
            )

        assert response.status_code == 401
        compare_digest.assert_called_once_with("wrong-admin-key", "expected-admin-key")
    finally:
        os.unlink(db_path)


def test_beacon_x402_agent_wallet_uses_constant_time_admin_key_compare(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    monkeypatch.setenv("BEACON_ADMIN_KEY", "expected-beacon-admin-key")

    with patch.object(beacon_x402, "_run_migrations"):
        beacon_x402.init_app(app, lambda: None)

    client = app.test_client()
    with patch("hmac.compare_digest", return_value=False) as compare_digest:
        response = client.post(
            "/api/agents/agent-1/wallet",
            headers={"X-Admin-Key": "wrong-beacon-admin-key"},
            json={"coinbase_address": "0x0000000000000000000000000000000000000001"},
        )

    assert response.status_code == 401
    compare_digest.assert_called_once_with(
        "wrong-beacon-admin-key",
        "expected-beacon-admin-key",
    )
