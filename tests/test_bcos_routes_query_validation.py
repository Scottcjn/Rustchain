import json
import sqlite3
from hashlib import blake2b

import pytest
from flask import Flask

from bcos_routes import init_bcos_table, register_bcos_routes


def _with_commitment(report):
    report = dict(report)
    commitment_report = {
        k: v for k, v in report.items()
        if k not in ("cert_id", "commitment")
    }
    if "trust_score" in commitment_report and not isinstance(commitment_report["trust_score"], bool):
        commitment_report["trust_score"] = int(commitment_report["trust_score"])
    canonical = json.dumps(commitment_report, sort_keys=True, separators=(",", ":"))
    report["commitment"] = blake2b(canonical.encode(), digest_size=32).hexdigest()
    return report


@pytest.fixture
def bcos_client(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
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
    report = _with_commitment({
        "cert_id": "cert-good-score",
        "repo": "Scottcjn/Rustchain",
        "commit_sha": "abcdef1234567890",
        "tier": "L1",
        "trust_score": "81",
    })

    response = bcos_client.post(
        "/bcos/attest",
        headers={"X-Admin-Key": "0" * 32},
        json=report,
    )

    assert response.status_code == 200
    assert response.get_json()["trust_score"] == 81

    verify_response = bcos_client.get("/bcos/verify/cert-good-score")
    assert verify_response.status_code == 200
    assert verify_response.get_json()["trust_score"] == 81


def test_bcos_public_urls_default_to_certificate_valid_host(bcos_client):
    verify_response = bcos_client.get("/bcos/verify/cert-1")
    assert verify_response.status_code == 200
    verify_body = verify_response.get_json()
    assert verify_body["badge_url"] == "https://rustchain.org/bcos/badge/cert-1.svg"
    assert verify_body["pdf_url"] == "https://rustchain.org/bcos/cert/cert-1.pdf"

    directory_response = bcos_client.get("/bcos/directory")
    assert directory_response.status_code == 200
    cert = directory_response.get_json()["certificates"][0]
    assert cert["verify_url"] == "https://rustchain.org/bcos/verify/cert-1"
    assert cert["badge_url"] == "https://rustchain.org/bcos/badge/cert-1.svg"


def test_bcos_attest_uses_configured_public_url(monkeypatch, bcos_client):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    monkeypatch.setenv("RUSTCHAIN_BCOS_PUBLIC_BASE_URL", "https://bcos.example/")
    report = _with_commitment({
        "cert_id": "cert-custom-host",
        "repo": "Scottcjn/Rustchain",
        "commit_sha": "abcdef1234567890",
        "tier": "L1",
        "trust_score": 82,
    })

    response = bcos_client.post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json=report,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["verify_url"] == "https://bcos.example/bcos/verify/cert-custom-host"
    assert body["badge_url"] == "https://bcos.example/bcos/badge/cert-custom-host.svg"
