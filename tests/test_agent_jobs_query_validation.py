from pathlib import Path
import sqlite3
import threading

import pytest
from flask import Flask

import rip302_agent_economy
from rip302_agent_economy import register_agent_economy


def make_client(tmp_path: Path):
    app = Flask(__name__)
    register_agent_economy(app, str(tmp_path / "agent_jobs.db"))
    return app.test_client()


def test_agent_jobs_rejects_malformed_query_numbers(tmp_path):
    client = make_client(tmp_path)

    for query in (
        "/agent/jobs?limit=abc",
        "/agent/jobs?offset=abc",
        "/agent/jobs?min_reward=abc",
        "/agent/jobs?min_reward=nan",
    ):
        response = client.get(query)
        assert response.status_code == 400
        assert "error" in response.get_json()


def test_agent_jobs_rejects_negative_query_numbers(tmp_path):
    client = make_client(tmp_path)

    for query in (
        "/agent/jobs?limit=-1",
        "/agent/jobs?offset=-1",
        "/agent/jobs?min_reward=-0.1",
    ):
        response = client.get(query)
        assert response.status_code == 400
        assert "error" in response.get_json()


def test_agent_jobs_clamps_large_limit_and_preserves_empty_listing(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/agent/jobs?limit=500&offset=0&min_reward=0")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["jobs"] == []
    assert payload["limit"] == 100
    assert payload["offset"] == 0


@pytest.mark.parametrize(
    "path",
    (
        "/agent/jobs",
        "/agent/jobs/job-1/claim",
        "/agent/jobs/job-1/deliver",
        "/agent/jobs/job-1/accept",
        "/agent/jobs/job-1/dispute",
        "/agent/jobs/job-1/cancel",
    ),
)
def test_agent_job_post_routes_reject_non_object_json(tmp_path, path):
    client = make_client(tmp_path)

    response = client.post(path, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


def _valid_job_payload(**overrides):
    payload = {
        "poster_wallet": "poster-1",
        "title": "Build integration",
        "description": "Build a complete test integration",
        "category": "other",
        "reward_rtc": 1,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("reward", ["nan", "inf", True, "not-a-number"])
def test_agent_job_post_rejects_invalid_reward_values(tmp_path, reward):
    client = make_client(tmp_path)

    response = client.post("/agent/jobs", json=_valid_job_payload(reward_rtc=reward))

    assert response.status_code == 400
    assert response.get_json() == {"error": "reward_rtc must be a finite number"}


@pytest.mark.parametrize("ttl", ["soon", True, None])
def test_agent_job_post_rejects_invalid_ttl_values(tmp_path, ttl):
    client = make_client(tmp_path)

    response = client.post("/agent/jobs", json=_valid_job_payload(ttl_seconds=ttl))

    assert response.status_code == 400
    assert response.get_json() == {"error": "ttl_seconds must be an integer"}


def _make_funded_client(tmp_path: Path):
    db_path = tmp_path / "agent_jobs.db"
    app = Flask(__name__)
    register_agent_economy(app, str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("poster-1", 2_000_000),
        )
    return app, db_path


def _balance(db_path: Path, wallet: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)
        ).fetchone()
    return row[0] if row else 0


def _balance_with_connect(connect, db_path: Path, wallet: str) -> int:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)
        ).fetchone()
    return row[0] if row else 0


def _create_claimed_job(client):
    post = client.post(
        "/agent/jobs",
        json=_valid_job_payload(
            title="Build expiry refund",
            description="Build a complete expiry refund regression test.",
            ttl_seconds=3600,
        ),
    )
    assert post.status_code == 201
    job_id = post.get_json()["job_id"]
    claim = client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker-1"}
    )
    assert claim.status_code == 200
    return job_id


def _create_open_job(client):
    post = client.post(
        "/agent/jobs",
        json=_valid_job_payload(
            title="Build open expiry refund",
            description="Build a complete open expiry refund regression test.",
            ttl_seconds=3600,
        ),
    )
    assert post.status_code == 201
    return post.get_json()["job_id"]


def _expire_job(db_path: Path, job_id: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_jobs SET expires_at = ? WHERE job_id = ?",
            (1, job_id),
        )


def test_claimed_expired_job_is_refunded_and_removed_from_claimed_listing(tmp_path):
    app, db_path = _make_funded_client(tmp_path)
    client = app.test_client()
    job_id = _create_claimed_job(client)
    _expire_job(db_path, job_id)

    response = client.get("/agent/jobs?status=claimed")

    assert response.status_code == 200
    assert response.get_json()["jobs"] == []
    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert _balance(db_path, "poster-1") == 2_000_000
    assert _balance(db_path, "agent_escrow") == 0


def test_detail_and_cancel_refund_expired_claimed_job_once(tmp_path):
    app, db_path = _make_funded_client(tmp_path)
    client = app.test_client()
    job_id = _create_claimed_job(client)
    _expire_job(db_path, job_id)

    detail = client.get(f"/agent/jobs/{job_id}")
    cancel = client.post(
        f"/agent/jobs/{job_id}/cancel", json={"poster_wallet": "poster-1"}
    )

    assert detail.status_code == 200
    assert detail.get_json()["job"]["status"] == "expired"
    assert cancel.status_code == 409
    assert _balance(db_path, "poster-1") == 2_000_000
    assert _balance(db_path, "agent_escrow") == 0


def test_worker_cannot_deliver_after_claimed_job_expires(tmp_path):
    app, db_path = _make_funded_client(tmp_path)
    client = app.test_client()
    job_id = _create_claimed_job(client)
    _expire_job(db_path, job_id)

    response = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker-1", "result_summary": "late work"},
    )

    assert response.status_code == 410
    assert response.get_json() == {"error": "Job has expired"}
    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert _balance(db_path, "poster-1") == 2_000_000
    assert _balance(db_path, "worker-1") == 0
    assert _balance(db_path, "founder_community") == 0
    assert _balance(db_path, "agent_escrow") == 0


def test_claim_returns_state_race_if_expiry_refund_loses_status_race(
    tmp_path, monkeypatch
):
    app, db_path = _make_funded_client(tmp_path)
    client = app.test_client()
    job_id = _create_open_job(client)
    _expire_job(db_path, job_id)

    real_connect = sqlite3.connect

    class RacingCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("UPDATE agent_jobs SET status = ?"):
                with real_connect(db_path) as conn:
                    conn.execute(
                        "UPDATE agent_jobs SET status = ? WHERE job_id = ?",
                        ("cancelled", job_id),
                    )
            return self._cursor.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class RacingConnection:
        def __init__(self, conn):
            self._conn = conn

        def cursor(self, *args, **kwargs):
            return RacingCursor(self._conn.cursor(*args, **kwargs))

        def __getattr__(self, name):
            return getattr(self._conn, name)

    def racing_connect(*args, **kwargs):
        return RacingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(rip302_agent_economy.sqlite3, "connect", racing_connect)

    response = client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker-1"}
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "STATE_RACE"
    assert _balance_with_connect(real_connect, db_path, "poster-1") == 950_000
    assert _balance_with_connect(real_connect, db_path, "agent_escrow") == 1_050_000


def test_deliver_returns_state_race_if_expiry_refund_loses_status_race(
    tmp_path, monkeypatch
):
    app, db_path = _make_funded_client(tmp_path)
    client = app.test_client()
    job_id = _create_claimed_job(client)
    _expire_job(db_path, job_id)

    real_connect = sqlite3.connect

    class RacingCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("UPDATE agent_jobs SET status = ?"):
                with real_connect(db_path) as conn:
                    conn.execute(
                        "UPDATE agent_jobs SET status = ? WHERE job_id = ?",
                        ("delivered", job_id),
                    )
            return self._cursor.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class RacingConnection:
        def __init__(self, conn):
            self._conn = conn

        def cursor(self, *args, **kwargs):
            return RacingCursor(self._conn.cursor(*args, **kwargs))

        def __getattr__(self, name):
            return getattr(self._conn, name)

    def racing_connect(*args, **kwargs):
        return RacingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(rip302_agent_economy.sqlite3, "connect", racing_connect)

    response = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker-1", "result_summary": "late work"},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "STATE_RACE"
    assert _balance_with_connect(real_connect, db_path, "poster-1") == 950_000
    assert _balance_with_connect(real_connect, db_path, "worker-1") == 0
    assert _balance_with_connect(real_connect, db_path, "founder_community") == 0
    assert _balance_with_connect(real_connect, db_path, "agent_escrow") == 1_050_000


def test_stale_deliver_cannot_resurrect_refunded_expired_job(
    tmp_path, monkeypatch
):
    app, db_path = _make_funded_client(tmp_path)
    client = app.test_client()
    job_id = _create_claimed_job(client)

    real_connect = sqlite3.connect
    deliver_about_to_write = threading.Event()
    listing_finished = threading.Event()

    class DelayedCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("UPDATE agent_jobs SET status = 'delivered'"):
                deliver_about_to_write.set()
                assert listing_finished.wait(timeout=5)
            return self._cursor.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class DelayedConnection:
        def __init__(self, conn):
            self._conn = conn

        def cursor(self, *args, **kwargs):
            return DelayedCursor(self._conn.cursor(*args, **kwargs))

        def __getattr__(self, name):
            return getattr(self._conn, name)

    def delayed_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        if threading.current_thread().name == "stale-deliver":
            return DelayedConnection(conn)
        return conn

    monkeypatch.setattr(rip302_agent_economy.sqlite3, "connect", delayed_connect)

    deliver_response = {}

    def deliver_with_stale_read():
        with app.test_client() as stale_client:
            deliver_response["response"] = stale_client.post(
                f"/agent/jobs/{job_id}/deliver",
                json={"worker_wallet": "worker-1", "result_summary": "late work"},
            )

    deliver_thread = threading.Thread(
        target=deliver_with_stale_read, name="stale-deliver"
    )
    deliver_thread.start()

    assert deliver_about_to_write.wait(timeout=5)
    _expire_job(db_path, job_id)
    listing = client.get("/agent/jobs?status=claimed")
    assert listing.status_code == 200
    listing_finished.set()
    deliver_thread.join(timeout=5)
    assert not deliver_thread.is_alive()

    assert deliver_response["response"].status_code == 409
    assert deliver_response["response"].get_json()["code"] == "STATE_RACE"

    accept = client.post(
        f"/agent/jobs/{job_id}/accept", json={"poster_wallet": "poster-1"}
    )
    assert accept.status_code == 409

    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert _balance(db_path, "poster-1") == 2_000_000
    assert _balance(db_path, "worker-1") == 0
    assert _balance(db_path, "founder_community") == 0
    assert _balance(db_path, "agent_escrow") == 0
