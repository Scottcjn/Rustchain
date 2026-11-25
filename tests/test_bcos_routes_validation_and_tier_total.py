# SPDX-License-Identifier: MIT
"""Regression tests for BCOS route body validation, admin auth, and tier totals."""

import sqlite3

import pytest
from flask import Flask

from bcos_routes import init_bcos_table, register_bcos_routes


@pytest.fixture()
def bcos_client(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
    db_path = tmp_path / "bcos.sqlite"
    with sqlite3.connect(db_path) as conn:
        init_bcos_table(conn)
        conn.executemany(
            """
            INSERT INTO bcos_attestations (
                cert_id, commitment, repo, commit_sha, tier, trust_score,
                reviewer, report_json, signature, signer_pubkey, anchored_epoch, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("cert-l0", "c0", "Scottcjn/r0", "aaaa1111bbbb2222", "L0", 50, "rev", "{}", None, None, None, 10),
                ("cert-l1-a", "c1", "Scottcjn/r1", "bbbb1111cccc2222", "L1", 75, "rev", "{}", None, None, None, 20),
                ("cert-l1-b", "c2", "Scottcjn/r2", "cccc1111dddd2222", "L1", 80, "rev", "{}", None, None, None, 30),
                ("cert-l2", "c3", "Scottcjn/r3", "dddd1111eeee2222", "L2", 95, "rev", "{}", None, None, None, 40),
            ],
        )

    app = Flask(__name__)
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False
    register_bcos_routes(app, str(db_path))
    return app.test_client()


@pytest.mark.parametrize("payload", [["cert-l0"], 123, True, False, "cert-l0"])
def test_bcos_anchor_rejects_non_object_json_with_400(bcos_client, payload):
    response = bcos_client.post(
        "/api/v1/bcos/anchor",
        headers={"X-Admin-Key": "0" * 32},
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_bcos_admin_checks_reject_non_ascii_key_without_500(bcos_client):
    headers = {"X-Admin-Key": "cl\xe9-secr\xe8te"}

    attest_resp = bcos_client.post(
        "/bcos/attest",
        headers=headers,
        json={
            "cert_id": "cert-new",
            "commitment": "a" * 64,
            "repo": "Scottcjn/Rustchain",
            "commit_sha": "abcdef1234567890",
            "tier": "L1",
            "trust_score": 80,
        },
    )
    assert attest_resp.status_code == 401

    anchor_resp = bcos_client.post(
        "/api/v1/bcos/anchor",
        headers=headers,
        json={"cert_id": "cert-l0"},
    )
    assert anchor_resp.status_code == 401


def test_bcos_directory_total_matches_tier_filter(bcos_client):
    all_resp = bcos_client.get("/bcos/directory")
    assert all_resp.status_code == 200
    all_body = all_resp.get_json()
    assert all_body["total"] == 4
    assert all_body["count"] == 4

    l1_resp = bcos_client.get("/bcos/directory?tier=L1&limit=1&offset=0")
    assert l1_resp.status_code == 200
    l1_body = l1_resp.get_json()
    assert l1_body["count"] == 1
    assert l1_body["total"] == 2
    assert l1_body["certificates"][0]["tier"] == "L1"

    l2_resp = bcos_client.get("/bcos/directory?tier=L2")
    assert l2_resp.status_code == 200
    l2_body = l2_resp.get_json()
    assert l2_body["count"] == 1
    assert l2_body["total"] == 1
    assert l2_body["certificates"][0]["cert_id"] == "cert-l2"
