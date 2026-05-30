# SPDX-License-Identifier: MIT

import sqlite3
import threading

import pytest
from flask import Flask

from node import gpu_render_endpoints as gpu_module
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


def _init_gpu_attestation_table(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE gpu_attestations (
                miner_id TEXT PRIMARY KEY,
                gpu_model TEXT,
                vram_gb REAL,
                cuda_version TEXT,
                benchmark_score REAL,
                price_render_minute REAL,
                price_tts_1k_chars REAL,
                price_stt_minute REAL,
                price_llm_1k_tokens REAL,
                supports_render INTEGER,
                supports_tts INTEGER,
                supports_stt INTEGER,
                supports_llm INTEGER,
                last_attestation INTEGER
            )
            """
        )


def _balance(db_path, wallet):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (wallet,)).fetchone()[0]


def _attestation_count(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM gpu_attestations").fetchone()[0]


def _escrow_payload():
    return {
        "job_id": "job-1",
        "job_type": "render",
        "from_wallet": "victim",
        "to_wallet": "attacker",
        "amount_rtc": 5,
    }


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


def test_gpu_escrow_blocks_concurrent_overdraft(tmp_path, monkeypatch):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    app = _create_app(db_path)

    real_connect = gpu_module.sqlite3.connect
    select_barrier = threading.Barrier(2)

    class RaceCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def fetchone(self):
            row = self._cursor.fetchone()
            select_barrier.wait(timeout=5)
            return row

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class RaceConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            cursor = self._conn.execute(sql, params)
            if sql.strip().startswith("SELECT balance_rtc FROM balances"):
                return RaceCursor(cursor)
            return cursor

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def __enter__(self):
            self._conn.__enter__()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return self._conn.__exit__(exc_type, exc_value, traceback)

    def race_connect(*args, **kwargs):
        return RaceConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(gpu_module.sqlite3, "connect", race_connect)
    results = []

    def create_escrow(job_id):
        payload = _escrow_payload()
        payload["job_id"] = job_id
        payload["amount_rtc"] = 20
        client = app.test_client()
        response = client.post(
            "/api/gpu/escrow",
            json=payload,
            headers={"X-Admin-Key": ADMIN_KEY},
        )
        results.append(response.status_code)

    threads = [
        threading.Thread(target=create_escrow, args=("race-job-1",)),
        threading.Thread(target=create_escrow, args=("race-job-2",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    monkeypatch.undo()

    assert sorted(results) == [200, 400]
    assert _balance(db_path, "victim") == 5.0


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


def test_gpu_attest_requires_admin_key_before_write(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    _init_gpu_attestation_table(db_path)
    client = _create_app(db_path).test_client()

    response = client.post("/api/gpu/attest", json={"miner_id": "victim"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized - admin key required"}
    assert _attestation_count(db_path) == 0


def test_gpu_attest_accepts_configured_admin_key(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    _init_gpu_attestation_table(db_path)
    client = _create_app(db_path).test_client()

    response = client.post(
        "/api/gpu/attest",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={
            "miner_id": "miner-1",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "benchmark_score": 95,
            "price_render_minute": 0.5,
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "message": "GPU attestation recorded"}
    assert _attestation_count(db_path) == 1


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/api/gpu/attest", {}),
        ("/api/gpu/escrow", {"X-Admin-Key": ADMIN_KEY}),
        ("/api/gpu/release", {"X-Admin-Key": ADMIN_KEY}),
        ("/api/gpu/refund", {"X-Admin-Key": ADMIN_KEY}),
    ],
)
def test_gpu_routes_reject_non_object_json(tmp_path, path, headers):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    response = client.post(path, headers=headers, json=[{"unexpected": "array"}])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def test_gpu_escrow_rejects_structured_string_fields(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    payload = _escrow_payload()
    payload["job_id"] = {"structured": "job"}

    response = client.post(
        "/api/gpu/escrow",
        json=payload,
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "job_id must be a string"}
    assert _balance(db_path, "victim") == 25.0


def test_gpu_release_rejects_structured_escrow_secret(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    created = client.post(
        "/api/gpu/escrow",
        json=_escrow_payload(),
        headers={"X-Admin-Key": ADMIN_KEY},
    )
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


def test_gpu_attest_hides_sqlite_schema_errors(tmp_path):
    db_path = tmp_path / "gpu.db"
    _init_db(db_path)
    client = _create_app(db_path).test_client()

    response = client.post(
        "/api/gpu/attest",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={"miner_id": "miner-1"},
    )

    assert response.status_code == 500
    assert response.get_json() == {"error": "Database operation failed"}
