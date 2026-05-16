# SPDX-License-Identifier: MIT

import os
import sqlite3
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rustchain_p2p_sync


def test_p2p_sync_flask_routes_use_flask_request_and_jsonify(tmp_path):
    """P2P route handlers should not crash on missing Flask globals."""
    db_path = tmp_path / "rustchain.db"
    peer_manager = rustchain_p2p_sync.PeerManager(str(db_path), "127.0.0.1")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE blocks (
                height INTEGER,
                hash TEXT,
                data TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO blocks (height, hash, data) VALUES (?, ?, ?)",
            (1, "block-hash", '{"ok": true}'),
        )
        conn.commit()

    app = Flask(__name__)
    rustchain_p2p_sync.add_p2p_endpoints(app, peer_manager, None, None)
    client = app.test_client()

    announce = client.post("/p2p/announce", json={"peer_url": "http://10.0.0.2:8088"})
    assert announce.status_code == 200
    assert announce.get_json() == {"ok": True, "peers": 1}

    peers = client.get("/p2p/peers")
    assert peers.status_code == 200
    assert peers.get_json()["peers"] == ["http://10.0.0.2:8088"]

    blocks = client.get("/api/blocks?start=1&limit=1")
    assert blocks.status_code == 200
    assert blocks.get_json()["blocks"] == [
        {"height": 1, "hash": "block-hash", "data": {"ok": True}}
    ]
