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


@pytest.mark.parametrize(
    "github_username",
    [
        "../octocat",
        "alice/bob",
        "alice?tab=repositories",
        "-alice",
        "alice-",
    ],
)
def test_airdrop_eligibility_rejects_invalid_github_username(tmp_path, github_username):
    client, _db_path = _make_client(tmp_path)

    response = client.post(
        "/api/airdrop/eligibility",
        json={
            "github_username": github_username,
            "wallet_address": "wallet-1",
            "chain": "base",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "github_username must be a valid GitHub username",
    }


def test_airdrop_eligibility_rejects_overlong_github_username(tmp_path):
    client, _db_path = _make_client(tmp_path)

    response = client.post(
        "/api/airdrop/eligibility",
        json={
            "github_username": "a" * 40,
            "wallet_address": "wallet-1",
            "chain": "base",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "github_username_too_long"}


def test_airdrop_claim_rejects_invalid_github_username_before_network(tmp_path):
    client, _db_path = _make_client(tmp_path)

    response = client.post(
        "/api/airdrop/claim",
        json={
            "github_username": "alice/bob",
            "wallet_address": "wallet-1",
            "chain": "base",
            "tier": "contributor",
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "github_username must be a valid GitHub username",
    }


def test_airdrop_service_rejects_invalid_github_username_without_api_calls(tmp_path, monkeypatch):
    airdrop = AirdropV2(str(tmp_path / "airdrop.db"))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("GitHub API should not be called for malformed usernames")

    monkeypatch.setattr(airdrop, "_check_github_account", fail_if_called)

    result = airdrop.check_eligibility("../octocat", "wallet-1", "base")

    assert result.eligible is False
    assert result.reason == "Invalid GitHub username"


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


@pytest.mark.parametrize(
    ("amount_wrtc", "message"),
    [
        (0, "amount_wrtc must be positive"),
        (-1, "amount_wrtc must be positive"),
        (1e100, "amount_wrtc exceeds maximum bridge lock"),
        (30000.000001, "amount_wrtc exceeds maximum bridge lock"),
    ],
)
def test_bridge_lock_rejects_out_of_range_amounts(tmp_path, amount_wrtc, message):
    client, _db_path = _make_client(tmp_path)

    response = client.post(
        "/api/bridge/lock",
        json={
            "from_address": "solana-source",
            "to_address": "base-destination",
            "from_chain": "solana",
            "to_chain": "base",
            "amount_wrtc": amount_wrtc,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": message}


def test_airdrop_service_rejects_oversized_bridge_lock(tmp_path):
    airdrop = AirdropV2(str(tmp_path / "airdrop.db"))

    success, message, lock = airdrop.create_bridge_lock(
        "solana-source",
        "base-destination",
        "solana",
        "base",
        30_000 * 1_000_000 + 1,
    )

    assert success is False
    assert message == "Amount exceeds maximum bridge lock"
    assert lock is None


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


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("from_address", "from_address_too_long"),
        ("to_address", "to_address_too_long"),
    ],
)
def test_bridge_lock_rejects_overlong_addresses(tmp_path, field, error):
    client, _db_path = _make_client(tmp_path)
    payload = {
        "from_address": "solana-source",
        "to_address": "base-destination",
        "from_chain": "solana",
        "to_chain": "base",
        "amount_wrtc": 1,
    }
    payload[field] = "x" * 129

    response = client.post("/api/bridge/lock", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": error}


@pytest.mark.parametrize(
    ("path", "payload", "error"),
    [
        (
            "/api/bridge/lock/test-lock/confirm",
            {"source_tx": "x" * 257},
            "source_tx_too_long",
        ),
        (
            "/api/bridge/lock/test-lock/release",
            {"dest_tx": "x" * 257},
            "dest_tx_too_long",
        ),
    ],
)
def test_bridge_admin_routes_reject_overlong_tx_ids(
    tmp_path, monkeypatch, path, payload, error
):
    client, _db_path = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")

    response = client.post(
        path,
        headers={"X-Admin-Key": "expected-admin"},
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": error}


@pytest.mark.parametrize(
    ("from_address", "to_address", "message"),
    [
        ("x" * 129, "base-destination", "Source address too long"),
        ("solana-source", "x" * 129, "Destination address too long"),
    ],
)
def test_airdrop_service_rejects_overlong_bridge_addresses(
    tmp_path, from_address, to_address, message
):
    _client, db_path = _make_client(tmp_path)
    airdrop = AirdropV2(str(db_path))

    success, actual_message, lock = airdrop.create_bridge_lock(
        from_address,
        to_address,
        "solana",
        "base",
        1_000_000,
    )

    assert success is False
    assert actual_message == message
    assert lock is None


@pytest.mark.parametrize(
    ("method", "message"),
    [
        ("confirm_bridge_lock", "Source transaction too long"),
        ("release_bridge_lock", "Destination transaction too long"),
    ],
)
def test_airdrop_service_rejects_overlong_bridge_tx_ids(tmp_path, method, message):
    _client, db_path = _make_client(tmp_path)
    airdrop = AirdropV2(str(db_path))

    success, actual_message = getattr(airdrop, method)("lock-id", "x" * 257)

    assert success is False
    assert actual_message == message
