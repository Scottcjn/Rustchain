# SPDX-License-Identifier: MIT

import json
import os
import sqlite3
import sys
import types
from types import SimpleNamespace

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


crypto_stub = types.ModuleType("rustchain_crypto")
crypto_stub.CanonicalBlockHeader = object
crypto_stub.Ed25519Signer = object
crypto_stub.SignedTransaction = object
crypto_stub.blake2b256_hex = lambda payload: "0" * 64
crypto_stub.canonical_json = lambda payload: json.dumps(payload, sort_keys=True).encode("utf-8")


class _MerkleTree:
    root_hex = "0" * 64

    def add_leaf_hash(self, _tx_hash):
        return None


crypto_stub.MerkleTree = _MerkleTree
sys.modules.setdefault("rustchain_crypto", crypto_stub)

tx_handler_stub = types.ModuleType("rustchain_tx_handler")
tx_handler_stub.TransactionPool = object
sys.modules.setdefault("rustchain_tx_handler", tx_handler_stub)

from randomness_beacon import (  # noqa: E402
    GENESIS_RANDOMNESS,
    build_randomness_record,
    verify_randomness_record,
)
from rustchain_block_producer import (  # noqa: E402
    BlockProducer,
    BlockValidator,
    create_block_api_routes,
)


class EmptyPool:
    def confirm_transaction(self, *_args, **_kwargs):
        raise AssertionError("empty blocks should not confirm transactions")


class StubBody:
    transactions = []
    attestations = []

    def to_dict(self):
        return {
            "transactions": [],
            "attestations": [],
            "merkle_root": "a" * 64,
            "attestations_hash": "b" * 64,
            "tx_count": 0,
            "attestation_count": 0,
        }


def _block(height, block_hash, prev_hash="0" * 64, timestamp=123456789):
    return SimpleNamespace(
        height=height,
        hash=block_hash,
        header=SimpleNamespace(
            prev_hash=prev_hash,
            timestamp=timestamp,
            merkle_root="a" * 64,
            state_root="c" * 64,
            attestations_hash="b" * 64,
            producer="RTC-test-producer",
            producer_sig="d" * 128,
        ),
        body=StubBody(),
    )


def test_randomness_record_is_verifiable_and_chain_bound():
    first = build_randomness_record(
        height=1,
        block_hash="1" * 64,
        prev_hash="0" * 64,
        prev_randomness=GENESIS_RANDOMNESS,
        merkle_root="a" * 64,
        attestations_hash="b" * 64,
        producer="RTC-test-producer",
        timestamp=123,
    )
    second = build_randomness_record(
        height=2,
        block_hash="2" * 64,
        prev_hash="1" * 64,
        prev_randomness=first["randomness"],
        merkle_root="a" * 64,
        attestations_hash="b" * 64,
        producer="RTC-test-producer",
        timestamp=124,
    )

    assert verify_randomness_record(first["randomness"], first["proof"])
    assert verify_randomness_record(second["randomness"], second["proof"])
    assert first["randomness"] != second["randomness"]
    assert second["proof"]["prev_randomness"] == first["randomness"]


def test_save_block_adds_randomness_columns_to_existing_blocks_table(tmp_path):
    db_path = tmp_path / "rustchain.db"
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

    producer = BlockProducer(str(db_path), EmptyPool())
    assert producer.save_block(_block(0, "1" * 64))

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT randomness_beacon, randomness_proof_json FROM blocks WHERE height = 0"
        ).fetchone()

    proof = json.loads(row[1])
    assert proof["prev_randomness"] == GENESIS_RANDOMNESS
    assert verify_randomness_record(row[0], proof)


def test_randomness_routes_return_verified_latest_and_height(tmp_path):
    db_path = tmp_path / "rustchain.db"
    producer = BlockProducer(str(db_path), EmptyPool())
    first = _block(0, "1" * 64)
    second = _block(1, "2" * 64, prev_hash="1" * 64, timestamp=123456790)

    assert producer.save_block(first)
    assert producer.save_block(second)

    app = Flask(__name__)
    create_block_api_routes(app, producer, BlockValidator(str(db_path)))
    client = app.test_client()

    latest = client.get("/api/randomness/latest")
    by_height = client.get("/api/randomness/0")

    assert latest.status_code == 200
    latest_body = latest.get_json()
    assert latest_body["height"] == 1
    assert latest_body["verified"] is True

    assert by_height.status_code == 200
    height_body = by_height.get_json()
    assert height_body["height"] == 0
    assert height_body["verified"] is True
    assert latest_body["proof"]["prev_randomness"] == height_body["randomness"]


def test_randomness_route_handles_corrupt_stored_proof(tmp_path):
    db_path = tmp_path / "rustchain.db"
    producer = BlockProducer(str(db_path), EmptyPool())

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
                randomness_beacon TEXT,
                randomness_proof_json TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO blocks (
                height, block_hash, prev_hash, timestamp, merkle_root, state_root,
                attestations_hash, producer, producer_sig, tx_count,
                attestation_count, body_json, randomness_beacon,
                randomness_proof_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                0,
                "1" * 64,
                "0" * 64,
                123456789,
                "a" * 64,
                "c" * 64,
                "b" * 64,
                "RTC-test-producer",
                "d" * 128,
                0,
                0,
                "{}",
                "e" * 64,
                "{not-json",
                123456789,
            ),
        )

    app = Flask(__name__)
    create_block_api_routes(app, producer, BlockValidator(str(db_path)))
    response = app.test_client().get("/api/randomness/latest")

    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "error": "Stored randomness proof is invalid",
    }
