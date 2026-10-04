# SPDX-License-Identifier: MIT
"""RIP-305 airdrop / bridge-lock routes after retirement.

The wRTC airdrop has ended and the wRTC bridge is disabled. The public write
routes (and public stats) answer 410 Gone with a JSON notice and never touch
the database; the admin claim lookup and the lock status lookup stay as
read-only record views. The AirdropV2 service methods are kept for history and
are still covered directly below.
"""

import sqlite3

import pytest
from flask import Flask

from node.airdrop_v2 import AirdropV2, init_airdrop_routes

ADMIN = "expected-admin"

RETIRED_ROUTES = [
    # (method, path, json body, expected notice code)
    (
        "post",
        "/api/airdrop/eligibility",
        {"github_username": "alice", "wallet_address": "wallet-1", "chain": "base"},
        "AIRDROP_ENDED",
    ),
    (
        "post",
        "/api/airdrop/claim",
        {
            "github_username": "alice",
            "wallet_address": "0x" + "a" * 40,
            "chain": "base",
            "tier": "contributor",
        },
        "AIRDROP_ENDED",
    ),
    ("get", "/api/airdrop/stats", None, "AIRDROP_ENDED"),
    (
        "post",
        "/api/bridge/lock",
        {
            "from_address": "solana-source",
            "to_address": "base-destination",
            "from_chain": "solana",
            "to_chain": "base",
            "amount_wrtc": 1,
        },
        "WRTC_BRIDGE_DISABLED",
    ),
    ("post", "/api/bridge/lock/LOCK_ID/confirm", {"source_tx": "real-source-tx"}, "WRTC_BRIDGE_DISABLED"),
    ("post", "/api/bridge/lock/LOCK_ID/release", {"dest_tx": "real-dest-tx"}, "WRTC_BRIDGE_DISABLED"),
]


def _make_client(tmp_path):
    db_path = tmp_path / "airdrop.db"
    airdrop = AirdropV2(str(db_path))
    app = Flask(__name__)
    app.config["TESTING"] = True
    init_airdrop_routes(app, airdrop, str(db_path))
    return app.test_client(), db_path, airdrop


def _create_pending_lock(airdrop):
    ok, message, lock = airdrop.create_bridge_lock(
        "solana-source", "base-destination", "solana", "base", 1_000_000
    )
    assert ok, message
    return lock.lock_id


def _seed_claim(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO airdrop_claims (claim_id, github_username, wallet_address,"
            " chain, tier, amount_uwrtc, timestamp, status)"
            " VALUES ('claim_hist', 'alice', 'wallet-1', 'base', 'contributor',"
            " 50000000, 1700000000, 'pending')"
        )


def _db_snapshot(db_path):
    with sqlite3.connect(db_path) as conn:
        return {
            table: conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()  # nosec B608
            for table in ("airdrop_claims", "airdrop_allocation", "bridge_locks", "sybil_cache")
        }


def _send(client, method, path, body, headers):
    if method == "get":
        return client.get(path, headers=headers)
    return client.post(path, headers=headers, json=body)


@pytest.mark.parametrize(("method", "path", "body", "code"), RETIRED_ROUTES)
@pytest.mark.parametrize("with_admin_key", [False, True])
def test_retired_routes_return_410_and_write_nothing(
    tmp_path, monkeypatch, method, path, body, code, with_admin_key
):
    client, db_path, airdrop = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN)
    lock_id = _create_pending_lock(airdrop)
    _seed_claim(db_path)
    path = path.replace("LOCK_ID", lock_id)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("retired routes must not reach the airdrop service")

    for name in (
        "check_eligibility",
        "claim_airdrop",
        "get_stats",
        "create_bridge_lock",
        "confirm_bridge_lock",
        "release_bridge_lock",
    ):
        monkeypatch.setattr(airdrop, name, fail_if_called)

    before = _db_snapshot(db_path)
    headers = {"X-Admin-Key": ADMIN} if with_admin_key else {}

    response = _send(client, method, path, body, headers)

    assert response.status_code == 410
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"] == "gone"
    assert payload["code"] == code
    assert "there is no off-ramp" in payload["message"]
    assert payload["docs"].endswith("/docs/EARN_AND_SPEND.md")
    assert _db_snapshot(db_path) == before


@pytest.mark.parametrize(("method", "path", "_body", "code"), RETIRED_ROUTES)
@pytest.mark.parametrize("bad_body", [None, [{"unexpected": "array"}], "text"])
def test_retired_routes_answer_410_before_body_parsing(
    tmp_path, monkeypatch, method, path, _body, code, bad_body
):
    client, _db_path, _airdrop = _make_client(tmp_path)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    path = path.replace("LOCK_ID", "no-such-lock")

    response = _send(client, method, path, bad_body, {})

    assert response.status_code == 410
    assert response.get_json()["code"] == code


def test_retired_notices_carry_no_dex_or_contract_details(tmp_path):
    client, _db_path, _airdrop = _make_client(tmp_path)
    for method, path, body, _code in RETIRED_ROUTES:
        text = _send(client, method, path.replace("LOCK_ID", "x"), body, {}).get_data(as_text=True).lower()
        for term in ("raydium", "aerodrome", "dexscreener", "swap", "0x5683c105", "remaining_wrtc"):
            assert term not in text, (path, term)


def test_admin_claim_lookup_stays_readonly_and_admin_gated(tmp_path, monkeypatch):
    client, db_path, _airdrop = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN)
    _seed_claim(db_path)
    before = _db_snapshot(db_path)

    unauthenticated = client.get("/api/airdrop/claim/claim_hist")
    wrong_key = client.get("/api/airdrop/claim/claim_hist", headers={"X-Admin-Key": "nope"})
    found = client.get("/api/airdrop/claim/claim_hist", headers={"X-Admin-Key": ADMIN})
    missing = client.get("/api/airdrop/claim/claim_missing", headers={"X-Admin-Key": ADMIN})

    assert unauthenticated.status_code == 401
    assert wrong_key.status_code == 401
    assert found.status_code == 200
    claim = found.get_json()["claim"]
    assert claim["claim_id"] == "claim_hist"
    assert claim["github_username"] == "alice"
    assert claim["status"] == "pending"
    assert missing.status_code == 404
    assert _db_snapshot(db_path) == before


def test_admin_claim_lookup_fails_closed_without_configured_key(tmp_path, monkeypatch):
    client, db_path, _airdrop = _make_client(tmp_path)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)
    _seed_claim(db_path)

    response = client.get("/api/airdrop/claim/claim_hist", headers={"X-Admin-Key": ""})

    assert response.status_code == 503
    assert response.get_json()["error"] == "admin_key_not_configured"


def test_bridge_lock_status_public_redacts_addresses_and_tx_ids(tmp_path, monkeypatch):
    client, _db_path, airdrop = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN)
    lock_id = _create_pending_lock(airdrop)
    assert airdrop.confirm_bridge_lock(lock_id, "real-source-tx")[0]

    response = client.get(f"/api/bridge/lock/{lock_id}")

    assert response.status_code == 200
    lock = response.get_json()["lock"]
    assert lock["lock_id"] == lock_id
    assert lock["status"] == "locked"
    assert lock["from_chain"] == "solana"
    assert lock["to_chain"] == "base"
    assert lock["amount_uwrtc"] == 1_000_000
    assert "timestamp_iso" in lock
    assert "from_address" not in lock
    assert "to_address" not in lock
    assert "source_tx" not in lock
    assert "dest_tx" not in lock


def test_bridge_lock_status_admin_includes_full_lock_fields(tmp_path, monkeypatch):
    client, _db_path, airdrop = _make_client(tmp_path)
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN)
    lock_id = _create_pending_lock(airdrop)
    assert airdrop.confirm_bridge_lock(lock_id, "real-source-tx")[0]

    response = client.get(f"/api/bridge/lock/{lock_id}", headers={"X-Admin-Key": ADMIN})

    assert response.status_code == 200
    lock = response.get_json()["lock"]
    assert lock["from_address"] == "solana-source"
    assert lock["to_address"] == "base-destination"
    assert lock["source_tx"] == "real-source-tx"
    assert lock["dest_tx"] is None


def test_bridge_lock_status_unknown_lock_is_404(tmp_path):
    client, _db_path, _airdrop = _make_client(tmp_path)

    response = client.get("/api/bridge/lock/no-such-lock")

    assert response.status_code == 404
    assert response.get_json()["error"] == "lock_not_found"


# --- AirdropV2 service methods (kept for the historical record) -------------


def test_airdrop_service_rejects_invalid_github_username_without_api_calls(tmp_path, monkeypatch):
    airdrop = AirdropV2(str(tmp_path / "airdrop.db"))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("GitHub API should not be called for malformed usernames")

    monkeypatch.setattr(airdrop, "_check_github_account", fail_if_called)

    result = airdrop.check_eligibility("../octocat", "wallet-1", "base")

    assert result.eligible is False
    assert result.reason == "Invalid GitHub username"


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
    _client, db_path, _airdrop = _make_client(tmp_path)
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
    _client, db_path, _airdrop = _make_client(tmp_path)
    airdrop = AirdropV2(str(db_path))

    success, actual_message = getattr(airdrop, method)("lock-id", "x" * 257)

    assert success is False
    assert actual_message == message
