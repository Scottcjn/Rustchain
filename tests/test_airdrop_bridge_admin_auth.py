# SPDX-License-Identifier: MIT

import sqlite3

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
