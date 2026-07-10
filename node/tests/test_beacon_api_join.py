import sqlite3

from flask import Flask

import beacon_api


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


def _join(client, agent_id, pubkey_hex="22" * 32, name=None):
    body = {"agent_id": agent_id, "pubkey_hex": pubkey_hex}
    if name is not None:
        body["name"] = name
    return client.post("/beacon/join", json=body)


def test_beacon_join_does_not_unban_banned_agent(tmp_path, monkeypatch):
    """A rejoin must not lift an administrative ban (issue #14589)."""
    client = _client(tmp_path, monkeypatch)

    assert _join(client, "banned-agent").status_code == 200
    # Admin bars the agent out of band.
    _set_status("banned-agent", "banned")

    # Attacker rejoins with the same (immutable) pubkey to self-unban.
    response = _join(client, "banned-agent", name="renamed")

    assert response.status_code == 200
    assert response.get_json()["status"] == "banned"
    assert _db_status("banned-agent") == "banned"


def test_beacon_join_keeps_suspended_and_revoked_status(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    for agent_id, status in (("susp-agent", "suspended"), ("rev-agent", "revoked")):
        assert _join(client, agent_id).status_code == 200
        _set_status(agent_id, status)

        response = _join(client, agent_id)

        assert response.get_json()["status"] == status
        assert _db_status(agent_id) == status


def test_beacon_join_reactivates_inactive_agent(tmp_path, monkeypatch):
    """Non-protected statuses (e.g. inactive) still come back online on rejoin."""
    client = _client(tmp_path, monkeypatch)

    assert _join(client, "idle-agent").status_code == 200
    _set_status("idle-agent", "inactive")

    response = _join(client, "idle-agent")

    assert response.get_json()["status"] == "active"
    assert _db_status("idle-agent") == "active"
