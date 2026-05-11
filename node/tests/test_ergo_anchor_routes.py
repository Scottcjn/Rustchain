#!/usr/bin/env python3
"""Route tests for RustChain Ergo anchor API pagination."""

import sqlite3
import sys
import tempfile
import types
from pathlib import Path

from flask import Flask

mock_crypto = types.ModuleType("rustchain_crypto")
mock_crypto.blake2b256_hex = lambda data: "00" * 32
mock_crypto.canonical_json = lambda data: "{}"
mock_crypto.MerkleTree = object
sys.modules["rustchain_crypto"] = mock_crypto

from node.rustchain_ergo_anchor import create_anchor_api_routes


class _DummyErgo:
    def get_height(self):
        return 0


class _DummyAnchorService:
    interval_blocks = 144
    ergo = _DummyErgo()

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)

    def get_last_anchor(self):
        return None

    def get_anchor_proof(self, height: int):
        return None


def _seed_anchor_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE ergo_anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rustchain_height INTEGER NOT NULL,
                rustchain_hash TEXT NOT NULL,
                commitment_hash TEXT NOT NULL,
                ergo_tx_id TEXT NOT NULL,
                ergo_height INTEGER,
                confirmations INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL
            )
            """
        )
        for height in range(3):
            conn.execute(
                """
                INSERT INTO ergo_anchors (
                    rustchain_height, rustchain_hash, commitment_hash,
                    ergo_tx_id, ergo_height, confirmations, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    height,
                    f"hash-{height}",
                    f"commitment-{height}",
                    f"ergo-{height}",
                    height + 100,
                    6,
                    "confirmed",
                    height + 1000,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _client(db_path: Path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    create_anchor_api_routes(app, _DummyAnchorService(db_path))
    return app.test_client()


def test_anchor_list_rejects_negative_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "anchors.db"
        _seed_anchor_db(db_path)
        response = _client(db_path).get("/anchor/list?limit=-1")

    assert response.status_code == 400
    assert response.get_json() == {"error": "limit_must_be_at_least_1"}


def test_anchor_list_rejects_invalid_offset():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "anchors.db"
        _seed_anchor_db(db_path)
        response = _client(db_path).get("/anchor/list?offset=abc")

    assert response.status_code == 400
    assert response.get_json() == {"error": "offset_must_be_integer"}


def test_anchor_list_keeps_valid_pagination():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "anchors.db"
        _seed_anchor_db(db_path)
        response = _client(db_path).get("/anchor/list?limit=2&offset=1")

    body = response.get_json()
    assert response.status_code == 200
    assert body["count"] == 2
    assert [anchor["rustchain_height"] for anchor in body["anchors"]] == [1, 0]


def test_anchor_list_clamps_oversized_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "anchors.db"
        _seed_anchor_db(db_path)
        response = _client(db_path).get("/anchor/list?limit=500")

    assert response.status_code == 200
    assert response.get_json()["count"] == 3
