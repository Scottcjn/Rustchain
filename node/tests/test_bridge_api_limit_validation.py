import os
import sqlite3
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_client(tmp_path):
    import bridge_api

    db_path = str(tmp_path / "bridge.db")
    bridge_api.DB_PATH = db_path
    with sqlite3.connect(db_path) as conn:
        bridge_api.init_bridge_schema(conn.cursor())
        conn.commit()

    app = Flask(__name__)
    app.config["TESTING"] = True
    bridge_api.register_bridge_routes(app)
    return app.test_client()


def test_bridge_list_rejects_non_integer_limit(tmp_path):
    client = _make_client(tmp_path)

    resp = client.get("/api/bridge/list?limit=abc")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "limit must be an integer"


def test_bridge_list_rejects_negative_limit(tmp_path):
    client = _make_client(tmp_path)

    resp = client.get("/api/bridge/list?limit=-1")

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "limit must be non-negative"


def test_bridge_list_accepts_empty_limit_default(tmp_path):
    client = _make_client(tmp_path)

    resp = client.get("/api/bridge/list?limit=")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["count"] == 0


def test_bridge_void_rejects_structured_tx_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    client = _make_client(tmp_path)

    resp = client.post(
        "/api/bridge/void",
        headers={"X-Admin-Key": "test-admin"},
        json={"tx_hash": ["not", "a", "hash"]},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "tx_hash must be a string"


def test_bridge_void_rejects_structured_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    client = _make_client(tmp_path)

    resp = client.post(
        "/api/bridge/void",
        headers={"X-Admin-Key": "test-admin"},
        json={"tx_hash": "missing-transfer", "reason": {"why": "bad input"}},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "reason must be a string"


def test_bridge_update_external_rejects_structured_hash_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_BRIDGE_API_KEY", "bridge-api-key")
    client = _make_client(tmp_path)

    resp = client.post(
        "/api/bridge/update-external",
        headers={"X-API-Key": "bridge-api-key"},
        json={
            "tx_hash": {"hash": "abc"},
            "external_tx_hash": "external-1",
            "confirmations": 1,
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "tx_hash must be a string"


def test_bridge_update_external_rejects_malformed_confirmations(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_BRIDGE_API_KEY", "bridge-api-key")
    client = _make_client(tmp_path)

    resp = client.post(
        "/api/bridge/update-external",
        headers={"X-API-Key": "bridge-api-key"},
        json={
            "tx_hash": "missing-transfer",
            "external_tx_hash": "external-1",
            "confirmations": ["one"],
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "confirmations must be an integer"
