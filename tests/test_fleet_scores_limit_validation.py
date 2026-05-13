import sqlite3
import sys
from pathlib import Path

import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rips" / "python"))

from rustchain.fleet_immune_system import ensure_schema, register_fleet_endpoints


@pytest.fixture
def fleet_db(tmp_path):
    db_path = tmp_path / "fleet.db"
    with sqlite3.connect(db_path) as db:
        ensure_schema(db)
        db.executemany(
            """
            INSERT INTO fleet_scores (
                miner, epoch, fleet_score, ip_signal, timing_signal,
                fingerprint_signal, effective_multiplier
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("miner-a", 1, 0.9, 0.8, 0.7, 0.6, 0.64),
                ("miner-b", 1, 0.7, 0.6, 0.5, 0.4, 0.72),
                ("miner-c", 1, 0.5, 0.4, 0.3, 0.2, 0.80),
            ],
        )
    return db_path


@pytest.fixture
def client(monkeypatch, fleet_db):
    monkeypatch.setenv("RC_ADMIN_KEY", "secret")
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_fleet_endpoints(app, str(fleet_db))
    return app.test_client()


def authed_get(client, query):
    return client.get(
        f"/admin/fleet/scores?{query}",
        headers={"X-Admin-Key": "secret"},
    )


@pytest.mark.parametrize(
    "query, expected_error",
    (
        ("limit=abc", "limit must be an integer"),
        ("limit=0", "limit must be positive"),
        ("limit=-1", "limit must be positive"),
    ),
)
def test_fleet_scores_rejects_invalid_limits(client, query, expected_error):
    response = authed_get(client, query)

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}


def test_fleet_scores_caps_oversized_limit(client):
    response = authed_get(client, "limit=5000")

    assert response.status_code == 200
    assert len(response.get_json()["scores"]) == 3


def test_fleet_scores_respects_valid_limit(client):
    response = authed_get(client, "limit=2")

    assert response.status_code == 200
    assert [row["miner"] for row in response.get_json()["scores"]] == ["miner-a", "miner-b"]
