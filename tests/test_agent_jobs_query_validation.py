import sqlite3
import time
from pathlib import Path

import pytest
from flask import Flask

from rip302_agent_economy import register_agent_economy


def make_client(tmp_path: Path):
    app = Flask(__name__)
    register_agent_economy(app, str(tmp_path / "agent_jobs.db"))
    return app.test_client()


def make_funded_client(tmp_path: Path):
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
    return app.test_client(), db_path


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


def test_claimed_expired_job_is_refunded_and_removed_from_claimed_listing(tmp_path):
    client, db_path = make_funded_client(tmp_path)

    post = client.post("/agent/jobs", json=_valid_job_payload(ttl_seconds=3600))
    assert post.status_code == 201
    job_id = post.get_json()["job_id"]
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker-1"}
    ).status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_jobs SET expires_at = ? WHERE job_id = ?",
            (int(time.time()) - 1, job_id),
        )

    response = client.get("/agent/jobs?status=claimed")

    assert response.status_code == 200
    assert response.get_json()["jobs"] == []
    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute(
            "SELECT miner_id, amount_i64 FROM balances"
        ).fetchall())
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert balances["agent_escrow"] == 0
    assert balances["poster-1"] == 2_000_000


def test_claimed_expired_job_detail_refunds_and_returns_expired(tmp_path):
    client, db_path = make_funded_client(tmp_path)

    post = client.post("/agent/jobs", json=_valid_job_payload(ttl_seconds=3600))
    assert post.status_code == 201
    job_id = post.get_json()["job_id"]
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker-1"}
    ).status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_jobs SET expires_at = ? WHERE job_id = ?",
            (int(time.time()) - 1, job_id),
        )

    response = client.get(f"/agent/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["job"]["status"] == "expired"
    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute(
            "SELECT miner_id, amount_i64 FROM balances"
        ).fetchall())
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert balances["agent_escrow"] == 0
    assert balances["poster-1"] == 2_000_000


def test_cancel_on_expired_claimed_job_refunds_instead_of_locking(tmp_path):
    client, db_path = make_funded_client(tmp_path)

    post = client.post("/agent/jobs", json=_valid_job_payload(ttl_seconds=3600))
    assert post.status_code == 201
    job_id = post.get_json()["job_id"]
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker-1"}
    ).status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_jobs SET expires_at = ? WHERE job_id = ?",
            (int(time.time()) - 1, job_id),
        )

    response = client.post(
        f"/agent/jobs/{job_id}/cancel", json={"poster_wallet": "poster-1"}
    )

    assert response.status_code == 410
    assert response.get_json() == {
        "error": "Job has expired",
        "status": "expired",
        "refunded_rtc": 1.05,
    }
    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute(
            "SELECT miner_id, amount_i64 FROM balances"
        ).fetchall())
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert balances["agent_escrow"] == 0
    assert balances["poster-1"] == 2_000_000


def test_worker_cannot_deliver_after_claimed_job_expires(tmp_path):
    client, db_path = make_funded_client(tmp_path)

    post = client.post("/agent/jobs", json=_valid_job_payload(ttl_seconds=3600))
    assert post.status_code == 201
    job_id = post.get_json()["job_id"]
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker-1"}
    ).status_code == 200

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_jobs SET expires_at = ? WHERE job_id = ?",
            (int(time.time()) - 1, job_id),
        )

    response = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker-1", "result_summary": "late delivery"},
    )

    assert response.status_code == 410
    assert response.get_json() == {"error": "Job has expired"}
    with sqlite3.connect(db_path) as conn:
        balances = dict(conn.execute(
            "SELECT miner_id, amount_i64 FROM balances"
        ).fetchall())
        status = conn.execute(
            "SELECT status FROM agent_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
    assert status == "expired"
    assert balances["agent_escrow"] == 0
    assert balances["poster-1"] == 2_000_000
