# SPDX-License-Identifier: MIT

import sqlite3

import pytest
from flask import Flask

from node.gpu_render_endpoints import register_gpu_render_endpoints


ADMIN_KEY = "test-admin-key"


def _create_app(db_path, admin_key=ADMIN_KEY):
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_gpu_render_endpoints(app, str(db_path), admin_key)
    return app


def _init_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE balances (
                miner_pk TEXT PRIMARY KEY,
                balance_rtc REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE render_escrow (
                job_id TEXT PRIMARY KEY,
                job_type TEXT,
                from_wallet TEXT,
                to_wallet TEXT,
                amount_rtc REAL,
                status TEXT,
                created_at INTEGER,
                released_at INTEGER,
                escrow_secret_hash TEXT
            )
            """
        )
        conn.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)", ("victim", 25.0))
        conn.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)", ("attacker", 0.0))


def _balance(db_path, wallet):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (wallet,)).fetchone()[0]


def _escrow_payload():
    return {
        "job_id": "job-1",
        "job_type": "render",
        "from_wallet": "victim",
        "to_wallet": "attacker",
        "amount_rtc": 5,
    }


@pytest.mark.parametrize(
    "path",
    ["/api/gpu/attest", "/api/gpu/escrow", "/api/gpu/release", "/api/gpu/refund"],
)
def test_gpu_endpoints_reject_non_object_json(tmp_path, path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    response = client.post(path, json=["not", "an", "object"], headers={"X-Admin-Key": ADMIN_KEY})

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}
    assert _balance(db_path, "victim") == 25.0
    assert _balance(db_path, "attacker") == 0.0


def test_gpu_escrow_rejects_structured_string_fields(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()
    payload = _escrow_payload()
    payload["job_id"] = {"structured": "job"}

    response = client.post("/api/gpu/escrow", json=payload, headers={"X-Admin-Key": ADMIN_KEY})

    assert response.status_code == 400
    assert response.get_json() == {"error": "job_id must be a string"}
    assert _balance(db_path, "victim") == 25.0
    assert _balance(db_path, "attacker") == 0.0


def test_gpu_escrow_rejects_whitespace_required_string_fields(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()
    payload = _escrow_payload()
    payload["from_wallet"] = "   "

    response = client.post("/api/gpu/escrow", json=payload, headers={"X-Admin-Key": ADMIN_KEY})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing required escrow fields"}
    assert _balance(db_path, "victim") == 25.0
    assert _balance(db_path, "attacker") == 0.0


def test_gpu_release_rejects_structured_escrow_secret(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()
    created = client.post("/api/gpu/escrow", json=_escrow_payload(), headers={"X-Admin-Key": ADMIN_KEY})
    assert created.status_code == 200

    response = client.post(
        "/api/gpu/release",
        json={"job_id": "job-1", "actor_wallet": "victim", "escrow_secret": ["not", "text"]},
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "escrow_secret must be a string"}
    assert _balance(db_path, "victim") == 20.0
    assert _balance(db_path, "attacker") == 0.0


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/gpu/attest", {"miner_id": "gpu-miner"}),
        ("/api/gpu/escrow", _escrow_payload()),
        ("/api/gpu/release", {"job_id": "job-1", "actor_wallet": "victim", "escrow_secret": "secret"}),
        ("/api/gpu/refund", {"job_id": "job-1", "actor_wallet": "attacker", "escrow_secret": "secret"}),
    ],
)
def test_gpu_database_errors_do_not_expose_schema_details(tmp_path, path, payload):
    db_path = tmp_path / "missing-schema.db"
    client = _create_app(db_path).test_client()

    response = client.post(path, json=payload, headers={"X-Admin-Key": ADMIN_KEY})

    assert response.status_code == 500
    data = response.get_json()
    assert data == {"error": "GPU render database unavailable"}
    response_text = response.get_data(as_text=True)
    assert "no such table" not in response_text
    assert "gpu_attestations" not in response_text
    assert "render_escrow" not in response_text
    assert "balances" not in response_text


def test_gpu_escrow_rejects_unauthenticated_wallet_lock(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    response = client.post("/api/gpu/escrow", json=_escrow_payload())

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized - admin key required"}
    assert _balance(db_path, "victim") == 25.0
    assert _balance(db_path, "attacker") == 0.0


def test_gpu_settlement_rejects_unauthenticated_secret_replay(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    created = client.post(
        "/api/gpu/escrow",
        json=_escrow_payload(),
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    assert created.status_code == 200
    escrow_secret = created.get_json()["escrow_secret"]

    release = client.post(
        "/api/gpu/release",
        json={"job_id": "job-1", "actor_wallet": "victim", "escrow_secret": escrow_secret},
    )

    assert release.status_code == 401
    assert release.get_json() == {"error": "Unauthorized - admin key required"}
    assert _balance(db_path, "victim") == 20.0
    assert _balance(db_path, "attacker") == 0.0


def test_gpu_admin_can_create_and_release_escrow(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    created = client.post(
        "/api/gpu/escrow",
        json=_escrow_payload(),
        headers={"X-API-Key": ADMIN_KEY},
    )
    assert created.status_code == 200
    escrow_secret = created.get_json()["escrow_secret"]

    released = client.post(
        "/api/gpu/release",
        json={"job_id": "job-1", "actor_wallet": "victim", "escrow_secret": escrow_secret},
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert released.status_code == 200
    assert released.get_json() == {"ok": True, "status": "released"}
    assert _balance(db_path, "victim") == 20.0
    assert _balance(db_path, "attacker") == 5.0


def test_gpu_admin_endpoints_fail_closed_without_configured_key(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path, admin_key="").test_client()

    response = client.post(
        "/api/gpu/escrow",
        json=_escrow_payload(),
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "Admin key not configured"}
    assert _balance(db_path, "victim") == 25.0
