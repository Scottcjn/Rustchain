# SPDX-License-Identifier: MIT
import json
import os
import sqlite3
import sys
from types import SimpleNamespace

from flask import Flask


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

from rustchain_p2p_sync import add_p2p_endpoints


class DummyPeerManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.peers = []

    def add_peer(self, peer_url):
        self.peers.append(peer_url)
        return True

    def get_active_peers(self):
        return list(self.peers)


def _client(tmp_path):
    db_path = tmp_path / "p2p.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE blocks (height INTEGER, hash TEXT, data TEXT)")
        conn.executemany(
            "INSERT INTO blocks (height, hash, data) VALUES (?, ?, ?)",
            [
                (1, "hash-1", json.dumps({"height": 1})),
                (2, "hash-2", json.dumps({"height": 2})),
            ],
        )
        conn.commit()

    app = Flask(__name__)
    app.config["TESTING"] = True
    add_p2p_endpoints(app, DummyPeerManager(str(db_path)), SimpleNamespace(), SimpleNamespace())
    return app.test_client()


def test_announce_rejects_non_object_json(tmp_path):
    client = _client(tmp_path)

    response = client.post("/p2p/announce", data="null", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}


def test_announce_requires_peer_url(tmp_path):
    client = _client(tmp_path)

    response = client.post("/p2p/announce", json={})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "peer_url required"}


def test_get_blocks_rejects_malformed_pagination(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/blocks?start=abc")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "start and limit must be integers"}

    response = client.get("/api/blocks?limit=abc")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "start and limit must be integers"}


def test_get_blocks_clamps_negative_pagination(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/blocks?start=-10&limit=-1")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["count"] == 1
    assert data["blocks"][0]["height"] == 1
