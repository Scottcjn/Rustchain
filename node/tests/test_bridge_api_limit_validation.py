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

