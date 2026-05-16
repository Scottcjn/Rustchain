# SPDX-License-Identifier: MIT

import importlib.util
import json
import os
import sqlite3
import sys
import types

from flask import Flask


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "node"))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_block_producer.py")


if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

crypto_mod = sys.modules.get("rustchain_crypto")
if crypto_mod is None:
    crypto_mod = types.SimpleNamespace()
    sys.modules["rustchain_crypto"] = crypto_mod
for name, value in {
    "CanonicalBlockHeader": object,
    "MerkleTree": object,
    "SignedTransaction": object,
    "Ed25519Signer": object,
    "blake2b256_hex": lambda data: "0" * 64,
    "canonical_json": lambda data: json.dumps(data, sort_keys=True).encode(),
    "address_from_public_key": lambda public_key: "addr",
}.items():
    if not hasattr(crypto_mod, name):
        setattr(crypto_mod, name, value)

spec = importlib.util.spec_from_file_location("rustchain_block_producer_batch_test", MODULE_PATH)
block_producer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = block_producer
spec.loader.exec_module(block_producer)


class DummyProducer:
    def __init__(self, db_path):
        self.db_path = db_path


class DummyCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value


def _client(tmp_path, cache=None):
    db_path = tmp_path / "blocks.db"
    app = Flask(__name__)
    if cache is not None:
        app.config["BLOCK_BATCH_REDIS"] = cache
    block_producer.create_block_api_routes(app, DummyProducer(str(db_path)), object())
    return app.test_client(), db_path


def _seed_blocks(db_path):
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
        for height in (1, 2):
            conn.execute(
                """
                INSERT INTO blocks
                (height, block_hash, prev_hash, timestamp, merkle_root, state_root,
                 attestations_hash, producer, producer_sig, tx_count, attestation_count,
                 body_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    height,
                    f"hash{height}",
                    f"prev{height - 1}",
                    100 + height,
                    f"merkle{height}",
                    f"state{height}",
                    f"attest{height}",
                    f"miner{height}",
                    f"sig{height}",
                    height,
                    0,
                    json.dumps({"height": height, "tx_count": height}),
                    200 + height,
                ),
            )


def test_batch_blocks_returns_ordered_partial_results(tmp_path):
    client, db_path = _client(tmp_path)
    _seed_blocks(db_path)

    response = client.post("/v1/blocks/batch", json={"blocks": [2, "hash1", 999, "missing"]})

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert [block["height"] for block in body["blocks"]] == [2, 1]
    assert body["blocks"][0]["body"] == {"height": 2, "tx_count": 2}
    assert body["missing"] == [999, "missing"]
    assert "timestamp" in body


def test_batch_blocks_rejects_oversized_batches(tmp_path):
    client, _ = _client(tmp_path)

    response = client.post(
        "/v1/blocks/batch",
        json={"blocks": list(range(block_producer.MAX_BATCH_BLOCKS + 1))},
    )

    assert response.status_code == 400
    assert "more than 100" in response.get_json()["error"]


def test_batch_blocks_rejects_invalid_entries(tmp_path):
    client, _ = _client(tmp_path)

    response = client.post("/v1/blocks/batch", json={"blocks": [1, -1]})

    assert response.status_code == 400
    assert "non-negative integer heights" in response.get_json()["error"]


def test_batch_blocks_treats_missing_table_as_missing_blocks(tmp_path):
    client, _ = _client(tmp_path)

    response = client.post("/v1/blocks/batch", json={"blocks": [1, "hash1"]})

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["blocks"] == []
    assert body["count"] == 0
    assert body["missing"] == [1, "hash1"]


def test_batch_blocks_surfaces_non_missing_table_database_errors(tmp_path, monkeypatch):
    class LockedCursor:
        def execute(self, *args, **kwargs):
            raise sqlite3.OperationalError("database is locked")

    class LockedConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return LockedCursor()

    monkeypatch.setattr(
        block_producer.sqlite3,
        "connect",
        lambda db_path: LockedConnection(),
    )
    client, _ = _client(tmp_path)

    response = client.post("/v1/blocks/batch", json={"blocks": [1]})

    assert response.status_code == 500
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "Block database unavailable"


def test_batch_blocks_reads_from_configured_cache(tmp_path):
    cache = DummyCache()
    client, db_path = _client(tmp_path, cache)
    _seed_blocks(db_path)

    first = client.post("/v1/blocks/batch", json={"blocks": [1]})
    assert first.status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM blocks")

    second = client.post("/v1/blocks/batch", json={"blocks": [1]})

    assert second.status_code == 200
    body = second.get_json()
    assert body["count"] == 1
    assert body["blocks"][0]["height"] == 1
