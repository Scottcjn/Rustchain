# SPDX-License-Identifier: MIT
"""Regression tests for the public state diff API."""

import json
import sqlite3
import sys

import pytest

integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = tmp_path / "state-diff.sqlite3"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c, db_path


def _seed_blocks(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE NOT NULL,
                state_root TEXT NOT NULL,
                body_json TEXT NOT NULL
            )
            """
        )
        blocks = [
            (
                10,
                "hash10",
                "state10",
                {
                    "transactions": [
                        {
                            "tx_hash": "tx1",
                            "from_addr": "alice",
                            "to_addr": "bob",
                            "amount_urtc": 2_500_000,
                        }
                    ]
                },
            ),
            (
                11,
                "hash11",
                "state11",
                {
                    "transactions": [
                        {
                            "tx_hash": "tx2",
                            "from_addr": "bob",
                            "to_addr": "carol",
                            "amount_i64": 500_000,
                            "storage_diff": {"key": "memo", "after": "ok"},
                        }
                    ]
                },
            ),
        ]
        for height, block_hash, state_root, body in blocks:
            conn.execute(
                """
                INSERT INTO blocks (height, block_hash, state_root, body_json)
                VALUES (?, ?, ?, ?)
                """,
                (height, block_hash, state_root, json.dumps(body)),
            )


def test_state_diff_returns_block_range_balance_and_storage_diffs(client):
    flask_client, db_path = client
    _seed_blocks(db_path)

    response = flask_client.get("/api/state/diff?start=10&end=11")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["start_height"] == 10
    assert body["end_height"] == 11
    assert body["block_count"] == 2
    assert body["missing_blocks"] == []
    assert body["state_roots"] == [
        {"height": 10, "block_hash": "hash10", "state_root": "state10"},
        {"height": 11, "block_hash": "hash11", "state_root": "state11"},
    ]
    assert body["balance_diffs"] == [
        {"wallet": "alice", "delta_i64": -2_500_000, "delta_rtc": -2.5},
        {"wallet": "bob", "delta_i64": 2_000_000, "delta_rtc": 2.0},
        {"wallet": "carol", "delta_i64": 500_000, "delta_rtc": 0.5},
    ]
    assert body["state_changes"][0] == {
        "block_height": 10,
        "tx_index": 0,
        "tx_hash": "tx1",
        "wallet": "alice",
        "delta_i64": -2_500_000,
        "direction": "debit",
    }
    assert body["storage_diffs"] == [{"key": "memo", "after": "ok"}]
    assert body["storage_diff_status"] == "tracked"


@pytest.mark.parametrize(
    "query,error",
    (
        ("end=11", "start is required"),
        ("start=ten&end=11", "start must be an integer"),
        ("start=-1&end=11", "start must be non-negative"),
        ("start=12&end=11", "end must be greater than or equal to start"),
    ),
)
def test_state_diff_rejects_invalid_ranges(client, query, error):
    flask_client, _ = client

    response = flask_client.get(f"/api/state/diff?{query}")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": error}


def test_state_diff_reports_missing_boundary_block(client):
    flask_client, db_path = client
    _seed_blocks(db_path)

    response = flask_client.get("/api/state/diff?start=9&end=11")

    assert response.status_code == 404
    assert response.get_json() == {
        "ok": False,
        "error": "block_range_boundary_missing",
        "missing_blocks": [9],
    }


def test_state_diff_reports_partial_diff_for_missing_interior_block(client):
    flask_client, db_path = client
    _seed_blocks(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM blocks WHERE height = ?", (11,))
        conn.execute(
            """
            INSERT INTO blocks (height, block_hash, state_root, body_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                12,
                "hash12",
                "state12",
                json.dumps({"transactions": []}),
            ),
        )

    response = flask_client.get("/api/state/diff?start=10&end=12")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["block_count"] == 2
    assert body["missing_blocks"] == [11]
