# SPDX-License-Identifier: MIT

import sqlite3

import pytest
from flask import Flask

from node.airdrop_v2 import AirdropV2, init_airdrop_routes


def _make_client(tmp_path):
    db_path = tmp_path / "airdrop.db"
    airdrop = AirdropV2(str(db_path))
    app = Flask(__name__)
    app.config["TESTING"] = True
    init_airdrop_routes(app, airdrop, str(db_path))
    return app.test_client(), db_path


def _create_pending_lock(client):
    response = client.post(
        "/api/bridge/lock",
        json={
            "from_address": "solana-source",
            "to_address": "base-destination",
            "from_chain": "solana",
            "to_chain": "base",
            "amount_wrtc": 1,
        },
    )
    assert response.status_code == 200
    return response.get_json()["lock"]["lock_id"]


def _lock_status(db_path, lock_id):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT status, source_tx, dest_tx FROM bridge_locks WHERE lock_id = ?",
            (lock_id,),
        ).fetchone()


def test_bridge_confirm_requires_admin_key(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path)
    lock_id = _create_pending_lock(client)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

    response = client.post(
        f"/api/bridge/lock/{lock_id}/confirm",
        json={"source_tx": "attacker-source-tx"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
    assert _lock_status(db_path, lock_id) == ("pending", None, None)


def test_bridge_release_requires_admin_key(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path)
    lock_id = _create_pending_lock(client)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

    authorized = client.post(
        f"/api/bridge/lock/{lock_id}/confirm",
        headers={"X-Admin-Key": "expected-admin"},
        json={"source_tx": "real-source-tx"},
    )
    assert authorized.status_code == 200

    response = client.post(
        f"/api/bridge/lock/{lock_id}/release",
        json={"dest_tx": "attacker-dest-tx"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
    assert _lock_status(db_path, lock_id) == ("locked", "real-source-tx", None)


def test_bridge_confirm_and_release_accept_valid_admin_key(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path)
    lock_id = _create_pending_lock(client)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

    confirmed = client.post(
        f"/api/bridge/lock/{lock_id}/confirm",
        headers={"X-Admin-Key": "expected-admin"},
        json={"source_tx": "real-source-tx"},
    )
    released = client.post(
        f"/api/bridge/lock/{lock_id}/release",
        headers={"X-Admin-Key": "expected-admin"},
        json={"dest_tx": "real-dest-tx"},
    )

    assert confirmed.status_code == 200
    assert released.status_code == 200
    assert _lock_status(db_path, lock_id) == (
        "released",
        "real-source-tx",
        "real-dest-tx",
    )


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/api/airdrop/eligibility", {}),
        ("/api/airdrop/claim", {}),
        ("/api/bridge/lock", {}),
        ("/api/bridge/lock/test-lock/confirm", {"X-Admin-Key": "expected-admin"}),
        ("/api/bridge/lock/test-lock/release", {"X-Admin-Key": "expected-admin"}),
    ],
)
def test_airdrop_write_routes_reject_non_object_json(tmp_path, monkeypatch, path, headers):
    client, _db_path = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

    response = client.post(path, headers=headers, json=[{"unexpected": "array"}])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}


def test_airdrop_eligibility_rejects_structured_text_field(tmp_path):
    client, _db_path = _make_client(tmp_path)

    response = client.post(
        "/api/airdrop/eligibility",
        json={
            "github_username": {"login": "alice"},
            "wallet_address": "wallet-1",
            "chain": "base",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "github_username must be a string"}


def test_bridge_lock_rejects_structured_amount(tmp_path):
    client, _db_path = _make_client(tmp_path)

    response = client.post(
        "/api/bridge/lock",
        json={
            "from_address": "solana-source",
            "to_address": "base-destination",
            "from_chain": "solana",
            "to_chain": "base",
            "amount_wrtc": ["bad"],
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "amount_wrtc must be a finite number"}


def test_bridge_confirm_rejects_structured_source_tx(tmp_path, monkeypatch):
    client, _db_path = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

    response = client.post(
        "/api/bridge/lock/test-lock/confirm",
        headers={"X-Admin-Key": "expected-admin"},
        json={"source_tx": {"tx": "abc"}},
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "source_tx must be a string"}
