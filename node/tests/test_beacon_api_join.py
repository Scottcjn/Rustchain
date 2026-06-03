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
