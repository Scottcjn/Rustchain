# SPDX-License-Identifier: MIT
import sqlite3
import random

from flask import Flask

from node import beacon_api as beacon_module


def _make_client(tmp_path, monkeypatch):
    db_path = tmp_path / "beacon_chat.db"
    monkeypatch.setattr(beacon_module, "DB_PATH", str(db_path))
    beacon_module.init_beacon_tables(str(db_path))

    app = Flask(__name__)
    app.register_blueprint(beacon_module.beacon_api)
    return app.test_client(), db_path


def test_chat_endpoint_escapes_user_message_before_storage(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch)
    payload = '<img src=x onerror="alert(1)"><script>alert(2)</script>'

    response = client.post(
        "/api/chat",
        json={"agent_id": "bcn_xss_test", "message": payload},
    )

    assert response.status_code == 200
    with sqlite3.connect(db_path) as conn:
        stored = conn.execute(
            """
            SELECT content
            FROM beacon_chat
            WHERE agent_id = ? AND role = ?
            ORDER BY id
            LIMIT 1
            """,
            ("bcn_xss_test", "user"),
        ).fetchone()[0]

    assert stored == (
        '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'
        '&lt;script&gt;alert(2)&lt;/script&gt;'
    )
    assert "<script>" not in stored
    assert 'onerror="' not in stored


def test_chat_endpoint_escapes_agent_id_in_response(tmp_path, monkeypatch):
    client, db_path = _make_client(tmp_path, monkeypatch)
    payload = '<img src=x onerror="alert(1)">'
    monkeypatch.setattr(random, "choice", lambda responses: responses[0])

    response = client.post(
        "/api/chat",
        json={"agent_id": payload, "message": "hello"},
    )

    assert response.status_code == 200
    body = response.get_json()

    assert body["agent"] == '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'
    assert body["agent"] in body["response"]
    assert "<img" not in body["agent"]
    assert "<img" not in body["response"]
    assert 'onerror="' not in body["agent"]
    assert 'onerror="' not in body["response"]

    with sqlite3.connect(db_path) as conn:
        stored = conn.execute(
            """
            SELECT content
            FROM beacon_chat
            WHERE agent_id = ? AND role = ?
            ORDER BY id
            LIMIT 1
            """,
            (payload, "assistant"),
        ).fetchone()[0]

    assert body["agent"] in stored
    assert "<img" not in stored
