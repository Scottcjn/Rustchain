import hashlib
import json
import sqlite3
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask

import beacon_api


def _sign_headers(agent_id, private_key, body_bytes, timestamp=None, nonce=None):
    if timestamp is None:
        timestamp = int(time.time())
    if nonce is None:
        nonce = f"nonce-{time.time_ns()}"

    body_hash = hashlib.sha256(body_bytes or b"").hexdigest()
    message = "\n".join([
        "POST",
        "/beacon/join",
        body_hash,
        str(timestamp),
        str(nonce),
        str(agent_id),
    ]).encode("utf-8")

    sig_hex = private_key.sign(message).hex()
    return {
        "X-Agent-Id": agent_id,
        "X-Agent-Timestamp": str(timestamp),
        "X-Agent-Nonce": nonce,
        "X-Agent-Signature": sig_hex,
    }


def _client(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon.db"
    monkeypatch.setattr(beacon_api, "DB_PATH", str(db_path))
    beacon_api.init_beacon_tables(str(db_path))

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(beacon_api.beacon_api)
    return app.test_client()


def _db_status(agent_id):
    conn = sqlite3.connect(beacon_api.DB_PATH)
    try:
        row = conn.execute(
            "SELECT status FROM relay_agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _set_status(agent_id, status):
    conn = sqlite3.connect(beacon_api.DB_PATH)
    try:
        conn.execute(
            "UPDATE relay_agents SET status = ? WHERE agent_id = ?",
            (status, agent_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_beacon_join_rejects_non_ed25519_pubkey_length(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/beacon/join",
        json={
            "agent_id": "short-key-agent",
            "pubkey_hex": "00",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid pubkey_hex: must be 32 bytes"


def test_beacon_join_accepts_32_byte_ed25519_pubkey(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/beacon/join",
        json={
            "agent_id": "valid-key-agent",
            "pubkey_hex": "11" * 32,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def _join(client, agent_id, pubkey_hex="22" * 32, name=None, priv_key=None):
    body = {"agent_id": agent_id, "pubkey_hex": pubkey_hex}
    if name is not None:
        body["name"] = name
    body_bytes = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if priv_key is not None:
        headers.update(_sign_headers(agent_id, priv_key, body_bytes))
    return client.post("/beacon/join", data=body_bytes, headers=headers)


def test_beacon_join_rejects_unsigned_rename_and_does_not_unban(tmp_path, monkeypatch):
    """A rejoin must not lift an administrative ban (issue #14589) and unsigned rename is rejected (issue #8514)."""
    client = _client(tmp_path, monkeypatch)
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()

    assert _join(client, "banned-agent", pubkey_hex=pub_hex).status_code == 200
    # Admin bars the agent out of band.
    _set_status("banned-agent", "banned")

    # Attacker rejoins with same pubkey to rename/unban unsigned -> 401
    unsigned_res = _join(client, "banned-agent", pubkey_hex=pub_hex, name="renamed")
    assert unsigned_res.status_code == 401
    assert "Missing Beacon signature headers" in unsigned_res.get_json()["error"]

    # Even with a valid signature, banned status remains banned
    signed_res = _join(client, "banned-agent", pubkey_hex=pub_hex, name="renamed", priv_key=priv)
    assert signed_res.status_code == 200
    assert signed_res.get_json()["status"] == "banned"
    assert _db_status("banned-agent") == "banned"


def test_beacon_join_keeps_suspended_and_revoked_status_when_signed(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    for agent_id, status in (("susp-agent", "suspended"), ("rev-agent", "revoked")):
        priv = Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes_raw().hex()

        assert _join(client, agent_id, pubkey_hex=pub_hex).status_code == 200
        _set_status(agent_id, status)

        # Unsigned rejoin -> 401
        assert _join(client, agent_id, pubkey_hex=pub_hex).status_code == 401

        # Signed rejoin keeps status
        response = _join(client, agent_id, pubkey_hex=pub_hex, priv_key=priv)
        assert response.status_code == 200
        assert response.get_json()["status"] == status
        assert _db_status(agent_id) == status


def test_beacon_join_reactivates_inactive_agent_only_when_signed(tmp_path, monkeypatch):
    """Non-protected statuses (e.g. inactive) reactivate only with signature (issue #8514)."""
    client = _client(tmp_path, monkeypatch)
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()

    assert _join(client, "idle-agent", pubkey_hex=pub_hex).status_code == 200
    _set_status("idle-agent", "inactive")

    # Unsigned rejoin -> 401
    assert _join(client, "idle-agent", pubkey_hex=pub_hex).status_code == 401
    assert _db_status("idle-agent") == "inactive"

    # Signed rejoin -> 200 and reactivates to active
    response = _join(client, "idle-agent", pubkey_hex=pub_hex, priv_key=priv)
    assert response.status_code == 200
    assert response.get_json()["status"] == "active"
    assert _db_status("idle-agent") == "active"


def _fund(agent_id, amount_i64):
    conn = sqlite3.connect(beacon_api.DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (agent_id, amount_i64),
        )
        conn.commit()
    finally:
        conn.close()


def test_beacon_join_refuses_first_registration_of_prefunded_noncanonical_id(tmp_path, monkeypatch):
    """#398 Step 3: RTC credited to an unregistered legacy bcn_ name must not be
    claimable by whoever registers that name first."""
    client = _client(tmp_path, monkeypatch)
    _fund("bcn_legacy_demo", 35_000_000)
    response = client.post(
        "/beacon/join",
        json={"agent_id": "bcn_legacy_demo", "pubkey_hex": "11" * 32},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "PREFUNDED_ID_REQUIRES_MIGRATION"
    assert _db_status("bcn_legacy_demo") is None


def test_beacon_join_still_accepts_unfunded_noncanonical_id(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _fund("bcn_other_name", 5_000_000)  # balances table exists, but not for this id
    response = client.post(
        "/beacon/join",
        json={"agent_id": "bcn_legacy_fresh", "pubkey_hex": "22" * 32},
    )
    assert response.status_code in (200, 201)
    assert _db_status("bcn_legacy_fresh") == "active"


def test_beacon_join_without_balances_table_is_unaffected(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/beacon/join",
        json={"agent_id": "bcn_legacy_nodb", "pubkey_hex": "33" * 32},
    )
    assert response.status_code in (200, 201)
