# SPDX-License-Identifier: MIT

import sqlite3
from unittest.mock import patch

from flask import Flask

import beacon_x402


def _make_app(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    monkeypatch.setenv("BEACON_ADMIN_KEY", "expected-beacon-admin-key")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(beacon_x402.X402_BEACON_SCHEMA)
    conn.execute(
        """
        INSERT INTO x402_beacon_payments (
            payer_address, payer_agent_id, action, amount_usdc,
            tx_hash, contract_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "0x0000000000000000000000000000000000000001",
            "agent-1",
            "reputation_export",
            "50000",
            "tx-sensitive",
            "contract-1",
            123.0,
        ),
    )
    conn.commit()

    with patch.object(beacon_x402, "_run_migrations"):
        beacon_x402.init_app(app, lambda: conn)

    return app


def test_x402_payment_history_requires_admin_key(monkeypatch):
    client = _make_app(monkeypatch).test_client()

    response = client.get("/api/x402/payments")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized - admin key required"


def test_x402_payment_history_uses_constant_time_admin_compare(monkeypatch):
    client = _make_app(monkeypatch).test_client()

    with patch("hmac.compare_digest", return_value=False) as compare_digest:
        response = client.get(
            "/api/x402/payments",
            headers={"X-Admin-Key": "wrong-beacon-admin-key"},
        )

    assert response.status_code == 401
    compare_digest.assert_called_once_with(
        "wrong-beacon-admin-key",
        "expected-beacon-admin-key",
    )


def test_x402_payment_history_returns_rows_for_admin(monkeypatch):
    client = _make_app(monkeypatch).test_client()

    response = client.get(
        "/api/x402/payments",
        headers={"X-Admin-Key": "expected-beacon-admin-key"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    assert body["payments"][0]["tx_hash"] == "tx-sensitive"
