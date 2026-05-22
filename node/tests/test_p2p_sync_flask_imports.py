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


def test_p2p_blocks_reads_canonical_block_schema(tmp_path):
    """The P2P blocks endpoint should work against the node block table."""
    db_path = tmp_path / "rustchain.db"
    peer_manager = rustchain_p2p_sync.PeerManager(str(db_path), "127.0.0.1")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE NOT NULL,
                prev_hash TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                merkle_root TEXT NOT NULL,
                state_root TEXT NOT NULL,
                attestations_hash TEXT NOT NULL,
                producer TEXT NOT NULL,
                producer_sig TEXT NOT NULL,
                tx_count INTEGER NOT NULL,
                attestation_count INTEGER NOT NULL,
                body_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO blocks (
                height, block_hash, prev_hash, timestamp, merkle_root, state_root,
                attestations_hash, producer, producer_sig, tx_count, attestation_count,
                body_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "canonical-hash",
                "parent-hash",
                1234567890,
                "merkle-root",
                "state-root",
                "attestations-hash",
                "miner-1",
                "sig-1",
                3,
                4,
                '{"transactions": ["tx-1"]}',
                1234567899,
            ),
        )
        conn.commit()

    app = Flask(__name__)
    rustchain_p2p_sync.add_p2p_endpoints(app, peer_manager, None, None)
    client = app.test_client()

    response = client.get("/api/blocks?start=2&limit=1")

    assert response.status_code == 200
    assert response.get_json()["blocks"] == [
        {
            "height": 2,
            "hash": "canonical-hash",
            "data": {
                "header": {
                    "prev_hash": "parent-hash",
                    "timestamp": 1234567890,
                    "merkle_root": "merkle-root",
                    "state_root": "state-root",
                    "attestations_hash": "attestations-hash",
                    "producer": "miner-1",
                    "producer_sig": "sig-1",
                },
                "body": {
                    "tx_count": 3,
                    "attestation_count": 4,
                    "transactions": ["tx-1"],
                },
            },
        }
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
