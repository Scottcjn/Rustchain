import sqlite3
import sys
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))

from bcos_routes import init_bcos_table, register_bcos_routes


def _app_with_bcos_db(tmp_path):
    db_path = tmp_path / "bcos.db"
    with sqlite3.connect(db_path) as conn:
        init_bcos_table(conn)
        conn.execute(
            """
            INSERT INTO bcos_attestations
            (cert_id, commitment, repo, commit_sha, tier, trust_score,
             reviewer, report_json, signature, signer_pubkey,
             anchored_epoch, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BCOS-test",
                "abc123",
                "Scottcjn/Rustchain",
                "deadbeefcafebabe",
                "L1",
                80,
                "tester",
                "{}",
                None,
                None,
                42,
                123456,
            ),
        )

    app = Flask(__name__)
    register_bcos_routes(app, str(db_path))
    return app


def test_bcos_directory_rejects_non_integer_limit(tmp_path):
    client = _app_with_bcos_db(tmp_path).test_client()

    response = client.get("/bcos/directory?limit=abc")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_pagination",
        "message": "limit must be an integer",
    }


def test_bcos_directory_rejects_negative_offset(tmp_path):
    client = _app_with_bcos_db(tmp_path).test_client()

    response = client.get("/bcos/directory?offset=-1")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_pagination",
        "message": "offset must be non-negative",
    }


def test_bcos_directory_clamps_large_limit(tmp_path):
    client = _app_with_bcos_db(tmp_path).test_client()

    response = client.get("/bcos/directory?limit=999")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert body["certificates"][0]["cert_id"] == "BCOS-test"
