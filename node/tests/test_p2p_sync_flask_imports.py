# SPDX-License-Identifier: MIT

import os
import sqlite3
import sys

import pytest
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

    announce = client.post("/p2p/announce", json={"peer_url": "https://node.example.com:8088"})
    assert announce.status_code == 200
    assert announce.get_json() == {"ok": True, "peers": 1}

    peers = client.get("/p2p/peers")
    assert peers.status_code == 200
    assert peers.get_json()["peers"] == ["https://node.example.com:8088"]

    blocks = client.get("/api/blocks?start=1&limit=1")
    assert blocks.status_code == 200
    assert blocks.get_json()["blocks"] == [
        {"height": 1, "hash": "block-hash", "data": {"ok": True}}
    ]


@pytest.mark.parametrize(
    "peer_url",
    [
        "http://localhost:8088",
        "http://127.0.0.1:8088",
        "http://0.0.0.0:8088",
        "http://10.0.0.2:8088",
        "http://172.17.0.1:8088",
        "http://172.31.255.255:8088",
        "http://192.168.0.10:8088",
        "http://169.254.169.254:8088",
        "http://[::1]:8088",
        "http://[fd00::1]:8088",
        "http://[fe80::1]:8088",
    ],
)
def test_p2p_announce_rejects_private_or_internal_peer_urls(tmp_path, peer_url):
    db_path = tmp_path / "rustchain.db"
    peer_manager = rustchain_p2p_sync.PeerManager(str(db_path), "127.0.0.1")

    app = Flask(__name__)
    rustchain_p2p_sync.add_p2p_endpoints(app, peer_manager, None, None)
    client = app.test_client()

    response = client.post("/p2p/announce", json={"peer_url": peer_url})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "peer_url must be a public address"}



def test_p2p_blocks_exports_canonical_node_schema(tmp_path):
    db_path = tmp_path / "rustchain.db"
    peer_manager = rustchain_p2p_sync.PeerManager(str(db_path), "127.0.0.1")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE blocks (
                height INTEGER,
                block_hash TEXT,
                prev_hash TEXT,
                timestamp REAL,
                merkle_root TEXT,
                state_root TEXT,
                attestations_hash TEXT,
                producer TEXT,
                producer_sig TEXT,
                tx_count INTEGER,
                attestation_count INTEGER,
                body_json TEXT,
                created_at REAL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO blocks (height, block_hash, body_json)
            VALUES (?, ?, ?)
            """,
            (1, "canonical-hash", '{"canonical": true}'),
        )
        conn.commit()

    app = Flask(__name__)
    rustchain_p2p_sync.add_p2p_endpoints(app, peer_manager, None, None)
    client = app.test_client()

    response = client.get("/api/blocks?start=1&limit=1")

    assert response.status_code == 200
    assert response.get_json()["blocks"] == [
        {"height": 1, "hash": "canonical-hash", "data": {"canonical": True}}
    ]

@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("start=abc", "start must be an integer"),
        ("start=10.5", "start must be an integer"),
        ("start=-1", "start must be >= 0"),
        ("limit=abc", "limit must be an integer"),
        ("limit=10.5", "limit must be an integer"),
        ("limit=0", "limit must be >= 1"),
        ("limit=-1", "limit must be >= 1"),
    ],
)
def test_p2p_blocks_rejects_invalid_pagination(tmp_path, query, message):
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
        conn.commit()

    app = Flask(__name__)
    rustchain_p2p_sync.add_p2p_endpoints(app, peer_manager, None, None)
    client = app.test_client()

    response = client.get(f"/api/blocks?{query}")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": message}


def test_p2p_blocks_caps_oversized_limit(tmp_path):
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
        conn.executemany(
            "INSERT INTO blocks (height, hash, data) VALUES (?, ?, ?)",
            [
                (height, f"block-{height}", '{"ok": true}')
                for height in range(1, 1003)
            ],
        )
        conn.commit()

    app = Flask(__name__)
    rustchain_p2p_sync.add_p2p_endpoints(app, peer_manager, None, None)
    client = app.test_client()

    response = client.get("/api/blocks?start=1&limit=5000")

    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 1000
    assert body["blocks"][0]["height"] == 1
    assert body["blocks"][-1]["height"] == 1000
