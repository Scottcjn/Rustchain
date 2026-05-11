# SPDX-License-Identifier: MIT

import sqlite3

from flask import Flask

import beacon_x402


def _make_paid_beacon_client(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(beacon_x402.X402_BEACON_SCHEMA)
        conn.execute("CREATE TABLE reputation (agent_id TEXT, score REAL)")
        conn.execute("INSERT INTO reputation VALUES (?, ?)", ("agent-victim", 99.9))

    monkeypatch.setattr(beacon_x402, "X402_CONFIG_OK", True)
    monkeypatch.setattr(beacon_x402, "PRICE_REPUTATION_EXPORT", "0.01", raising=False)
    monkeypatch.setattr(beacon_x402, "PRICE_BEACON_CONTRACT", "0.05", raising=False)
    monkeypatch.setattr(beacon_x402, "X402_NETWORK", "base-sepolia", raising=False)
    monkeypatch.setattr(
        beacon_x402,
        "FACILITATOR_URL",
        "https://facilitator.invalid",
        raising=False,
    )
    monkeypatch.setattr(
        beacon_x402,
        "BEACON_TREASURY",
        "0x1111111111111111111111111111111111111111",
        raising=False,
    )
    monkeypatch.setattr(
        beacon_x402,
        "USDC_BASE",
        "0x2222222222222222222222222222222222222222",
        raising=False,
    )
    monkeypatch.setattr(beacon_x402, "SWAP_INFO", {"network": "Base"}, raising=False)
    monkeypatch.setattr(beacon_x402, "has_cdp_credentials", lambda: True, raising=False)
    monkeypatch.setattr(
        beacon_x402,
        "is_free",
        lambda price: str(price) in ("0", "0.0", "0.00", ""),
        raising=False,
    )
    monkeypatch.setattr(beacon_x402, "_run_migrations", lambda _db_path: None)

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = Flask(__name__)
    app.config["TESTING"] = True
    beacon_x402.init_app(app, get_db)
    return app.test_client(), db_path


def test_paid_beacon_reputation_without_payment_returns_x402_challenge(tmp_path, monkeypatch):
    client, _db_path = _make_paid_beacon_client(tmp_path, monkeypatch)

    response = client.get("/api/premium/reputation")

    body = response.get_json()
    assert response.status_code == 402
    assert body["error"] == "Payment Required"
    assert body["x402"]["maxAmountRequired"] == "0.01"
    assert body["x402"]["payTo"] == "0x1111111111111111111111111111111111111111"


def test_paid_beacon_reputation_rejects_unverified_payment_header(tmp_path, monkeypatch):
    client, db_path = _make_paid_beacon_client(tmp_path, monkeypatch)

    response = client.get(
        "/api/premium/reputation",
        headers={"X-PAYMENT": "bogus-not-json-not-signed-not-facilitated"},
    )

    body = response.get_json()
    assert response.status_code == 503
    assert body["error"] == "Payment verification unavailable"
    assert "reputation" not in body

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM x402_beacon_payments").fetchone()[0]
    assert count == 0
