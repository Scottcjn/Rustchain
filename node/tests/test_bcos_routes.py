# SPDX-License-Identifier: MIT

import json
import os
import sqlite3
import sys
from hashlib import blake2b

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bcos_routes import init_bcos_table, register_bcos_routes


def _with_commitment(report):
    report = dict(report)
    commitment_report = {
        k: v for k, v in report.items()
        if k not in ("cert_id", "commitment")
    }
    canonical = json.dumps(commitment_report, sort_keys=True, separators=(",", ":"))
    report["commitment"] = blake2b(canonical.encode(), digest_size=32).hexdigest()
    return report


def test_bcos_attest_rejects_non_object_json(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    app = Flask(__name__)
    register_bcos_routes(app, str(tmp_path / "bcos.db"))
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object required"


def test_bcos_attest_rejects_non_object_report(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    app = Flask(__name__)
    register_bcos_routes(app, str(tmp_path / "bcos.db"))
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json={"report": ["not", "an", "object"]},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "report must be an object"


def test_bcos_attest_rejects_mismatched_commitment(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    app = Flask(__name__)
    register_bcos_routes(app, str(tmp_path / "bcos.db"))
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json={
            "cert_id": "BCOS-mismatch",
            "commitment": "0" * 64,
            "repo": "Scottcjn/Rustchain",
            "commit_sha": "abcdef1234567890",
            "tier": "L1",
            "trust_score": 75,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_commitment",
        "message": "commitment does not match report payload",
    }


def test_bcos_attest_stores_matching_commitment(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    db_path = tmp_path / "bcos.db"
    with sqlite3.connect(db_path) as conn:
        init_bcos_table(conn)
    app = Flask(__name__)
    register_bcos_routes(app, str(db_path))
    app.config["TESTING"] = True

    report = _with_commitment({
        "cert_id": "BCOS-valid",
        "repo": "Scottcjn/Rustchain",
        "commit_sha": "abcdef1234567890",
        "tier": "L1",
        "trust_score": 75,
        "reviewer": "codex-reviewer",
    })

    response = app.test_client().post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json=report,
    )

    assert response.status_code == 200

    verify_response = app.test_client().get("/bcos/verify/BCOS-valid")
    assert verify_response.status_code == 200
    assert verify_response.get_json()["commitment_valid"] is True
