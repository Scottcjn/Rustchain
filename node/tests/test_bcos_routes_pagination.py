"""Regression tests for BCOS public pagination validation."""

import gc
import os
import sqlite3
import sys
import tempfile
import time

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bcos_routes import register_bcos_routes


def _unlink_temp_db(db_path):
    gc.collect()
    for _ in range(5):
        try:
            os.unlink(db_path)
            return
        except PermissionError:
            time.sleep(0.05)
    # Windows can keep Flask/SQLite test handles alive until process teardown.


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE bcos_attestations (
                cert_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                tier TEXT NOT NULL,
                trust_score INTEGER NOT NULL,
                reviewer TEXT NOT NULL,
                anchored_epoch INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO bcos_attestations (
                cert_id, repo, commit_sha, tier, trust_score,
                reviewer, anchored_epoch, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("BCOS-ONE", "owner/repo-one", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "L1", 80, "alice", 1, "2026-05-01T00:00:00Z"),
                ("BCOS-TWO", "owner/repo-two", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "L2", 95, "bob", 2, "2026-05-02T00:00:00Z"),
            ],
        )

    yield db_path
    _unlink_temp_db(db_path)


@pytest.fixture
def client(tmp_db):
    app = Flask(__name__)
    register_bcos_routes(app, tmp_db)
    app.config["TESTING"] = True
    return app.test_client()


def test_bcos_directory_rejects_non_integer_pagination(client):
    limit_response = client.get("/bcos/directory?limit=not-an-int")
    assert limit_response.status_code == 400
    assert limit_response.get_json() == {"error": "invalid_pagination", "message": "limit must be an integer"}

    offset_response = client.get("/bcos/directory?offset=not-an-int")
    assert offset_response.status_code == 400
    assert offset_response.get_json() == {"error": "invalid_pagination", "message": "offset must be an integer"}


def test_bcos_directory_rejects_negative_pagination(client):
    response = client.get("/bcos/directory?limit=-10&offset=-20")
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_pagination", "message": "limit must be non-negative"}
