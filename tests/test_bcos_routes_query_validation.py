import sqlite3

import pytest
from flask import Flask

from bcos_routes import init_bcos_table, register_bcos_routes


@pytest.fixture
def bcos_client(tmp_path):
    db_path = tmp_path / "bcos.sqlite"
    with sqlite3.connect(db_path) as conn:
        init_bcos_table(conn)
        conn.execute(
            """
            INSERT INTO bcos_attestations (
                cert_id, commitment, repo, commit_sha, tier, trust_score,
                reviewer, report_json, signature, signer_pubkey, anchored_epoch, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cert-1",
                "commitment",
                "Scottcjn/Rustchain",
                "abcdef1234567890",
                "L1",
                80,
                "reviewer",
                "{}",
                None,
                None,
                1,
                1234567890,
            ),
        )

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_bcos_routes(app, str(db_path))
    return app.test_client()


@pytest.mark.parametrize(
    "query,message",
    [
        ("limit=abc", "limit must be an integer"),
        ("offset=abc", "offset must be an integer"),
        ("limit=-1", "limit must be non-negative"),
        ("offset=-1", "offset must be non-negative"),
    ],
)
def test_bcos_directory_rejects_invalid_pagination(bcos_client, query, message):
    response = bcos_client.get(f"/bcos/directory?{query}")

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "invalid_pagination"
    assert body["message"] == message


def test_bcos_directory_clamps_large_limit(bcos_client):
    response = bcos_client.get("/bcos/directory?limit=999999")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 1


@pytest.mark.parametrize(
    "trust_score,message",
    [
        ("high", "trust_score must be a number"),
        (None, "trust_score must be a number"),
        (True, "trust_score must be a number"),
        (-1, "trust_score must be between 0 and 100"),
        (101, "trust_score must be between 0 and 100"),
    ],
)
def test_bcos_attest_rejects_invalid_trust_score(bcos_client, trust_score, message):
    response = bcos_client.post(
        "/bcos/attest",
        headers={"X-Admin-Key": "0" * 32},
        json={
            "cert_id": "cert-bad-score",
            "commitment": "commitment",
            "repo": "Scottcjn/Rustchain",
            "commit_sha": "abcdef1234567890",
            "tier": "L1",
            "trust_score": trust_score,
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "invalid_trust_score"
    assert body["message"] == message


def test_bcos_attest_stores_numeric_trust_score(bcos_client):
    response = bcos_client.post(
        "/bcos/attest",
        headers={"X-Admin-Key": "0" * 32},
        json={
            "cert_id": "cert-good-score",
            "commitment": "commitment",
            "repo": "Scottcjn/Rustchain",
            "commit_sha": "abcdef1234567890",
            "tier": "L1",
            "trust_score": "81",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["trust_score"] == 81

    verify_response = bcos_client.get("/bcos/verify/cert-good-score")
    assert verify_response.status_code == 200
    assert verify_response.get_json()["trust_score"] == 81
