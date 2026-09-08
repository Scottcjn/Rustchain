# SPDX-License-Identifier: MIT
"""RIP-302: a disputed job must remain workable by the assigned worker.

`POST /agent/jobs/<id>/dispute` answers the client with "the assigned worker can
re-deliver", but `/deliver` used to accept only `claimed` jobs and no route ever
moved a job back out of `disputed`. That left the worker unable to act on the
rejection reason while the escrow stayed locked (a disputed job is also outside
the TTL expiry sweep), so the only reachable exit was the poster cancelling and
taking the full escrow back — after the deliverable was already readable on the
public job endpoint.
"""
import sqlite3
from pathlib import Path

from flask import Flask

import rip302_agent_economy


def _make_app(tmp_path: Path, poster_balance: int = 5_000_000):
    db_path = tmp_path / "agent_jobs.db"
    app = Flask(__name__)
    rip302_agent_economy.register_agent_economy(app, str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("poster", poster_balance),
        )
    return app, db_path


def _balance(db_path: Path, wallet: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)
        ).fetchone()
    return row[0] if row else 0


def _job_row(db_path: Path, job_id: str) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return dict(
            conn.execute(
                "SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        )


def _post_job(client, reward_rtc: int = 1) -> str:
    resp = client.post(
        "/agent/jobs",
        json={
            "poster_wallet": "poster",
            "title": "Write a scraper",
            "description": "Scrape the public listing page and return a CSV of rows.",
            "category": "code",
            "reward_rtc": reward_rtc,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["job_id"]


def _disputed_job(client) -> str:
    job_id = _post_job(client)
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker"}
    ).status_code == 200
    assert client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={
            "worker_wallet": "worker",
            "result_summary": "first attempt",
            "deliverable_url": "https://example.com/v1.csv",
        },
    ).status_code == 200
    assert client.post(
        f"/agent/jobs/{job_id}/dispute",
        json={"poster_wallet": "poster", "reason": "missing the price column"},
    ).status_code == 200
    return job_id


def test_assigned_worker_can_redeliver_a_disputed_job_and_get_paid(tmp_path):
    app, db_path = _make_app(tmp_path)
    client = app.test_client()
    job_id = _disputed_job(client)

    resp = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={
            "worker_wallet": "worker",
            "result_summary": "added the price column",
            "deliverable_url": "https://example.com/v2.csv",
        },
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "delivered"

    job = _job_row(db_path, job_id)
    assert job["status"] == "delivered"
    assert job["deliverable_url"] == "https://example.com/v2.csv"
    assert job["result_summary"] == "added the price column"

    # The escrow can now actually reach the worker instead of only going back.
    accept = client.post(
        f"/agent/jobs/{job_id}/accept", json={"poster_wallet": "poster"}
    )
    assert accept.status_code == 200, accept.get_json()
    assert _balance(db_path, "worker") == 1_000_000
    assert _balance(db_path, "agent_escrow") == 0


def test_redelivery_clears_the_stale_rejection_reason(tmp_path):
    app, db_path = _make_app(tmp_path)
    client = app.test_client()
    job_id = _disputed_job(client)
    assert _job_row(db_path, job_id)["rejection_reason"] == "missing the price column"

    assert client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker", "result_summary": "fixed"},
    ).status_code == 200

    assert _job_row(db_path, job_id)["rejection_reason"] == ""


def test_redelivery_is_recorded_distinctly_in_the_activity_log(tmp_path):
    app, db_path = _make_app(tmp_path)
    client = app.test_client()
    job_id = _disputed_job(client)
    assert client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker", "result_summary": "fixed"},
    ).status_code == 200

    actions = [
        entry["action"]
        for entry in client.get(f"/agent/jobs/{job_id}").get_json()["job"]["activity_log"]
    ]
    assert actions.count("delivered") == 1
    assert "redelivered" in actions


def test_only_the_assigned_worker_can_redeliver_a_disputed_job(tmp_path):
    app, db_path = _make_app(tmp_path)
    client = app.test_client()
    job_id = _disputed_job(client)

    resp = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "someone_else", "result_summary": "let me in"},
    )
    assert resp.status_code == 403
    assert _job_row(db_path, job_id)["status"] == "disputed"


def test_redelivery_still_works_after_the_original_ttl_elapsed(tmp_path):
    """A disputed job is outside the expiry sweep, so its TTL must not gate
    re-delivery — otherwise the fix would silently expire for any dispute that
    outlives the original deadline."""
    app, db_path = _make_app(tmp_path)
    client = app.test_client()
    job_id = _disputed_job(client)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE agent_jobs SET expires_at = 1 WHERE job_id = ?", (job_id,))

    resp = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker", "result_summary": "late but done"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert _job_row(db_path, job_id)["status"] == "delivered"


def test_open_and_completed_jobs_are_still_not_deliverable(tmp_path):
    app, db_path = _make_app(tmp_path)
    client = app.test_client()

    open_job = _post_job(client)
    resp = client.post(
        f"/agent/jobs/{open_job}/deliver",
        json={"worker_wallet": "worker", "result_summary": "unclaimed"},
    )
    assert resp.status_code == 409
    assert _job_row(db_path, open_job)["status"] == "open"

    done_job = _post_job(client)
    assert client.post(
        f"/agent/jobs/{done_job}/claim", json={"worker_wallet": "worker"}
    ).status_code == 200
    assert client.post(
        f"/agent/jobs/{done_job}/deliver",
        json={"worker_wallet": "worker", "result_summary": "done"},
    ).status_code == 200
    assert client.post(
        f"/agent/jobs/{done_job}/accept", json={"poster_wallet": "poster"}
    ).status_code == 200

    resp = client.post(
        f"/agent/jobs/{done_job}/deliver",
        json={"worker_wallet": "worker", "result_summary": "again"},
    )
    assert resp.status_code == 409
    assert _job_row(db_path, done_job)["status"] == "completed"


def test_claimed_job_past_ttl_still_expires_and_refunds_on_deliver(tmp_path):
    """Regression guard: skipping the TTL gate must apply only to re-delivery."""
    app, db_path = _make_app(tmp_path)
    client = app.test_client()
    job_id = _post_job(client)
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker"}
    ).status_code == 200
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE agent_jobs SET expires_at = 1 WHERE job_id = ?", (job_id,))

    resp = client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker", "result_summary": "too late"},
    )
    assert resp.status_code == 410
    assert _job_row(db_path, job_id)["status"] == "expired"
    assert _balance(db_path, "agent_escrow") == 0
    assert _balance(db_path, "poster") == 5_000_000


def test_dispute_response_only_names_routes_that_exist(tmp_path):
    app, _ = _make_app(tmp_path)
    client = app.test_client()
    job_id = _post_job(client)
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker"}
    ).status_code == 200
    assert client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker", "result_summary": "done"},
    ).status_code == 200

    message = client.post(
        f"/agent/jobs/{job_id}/dispute",
        json={"poster_wallet": "poster", "reason": "not what I asked for"},
    ).get_json()["message"]

    # The old text promised an admin refund; no admin route is registered.
    rules = {str(rule.rule) for rule in app.url_map.iter_rules()}
    assert "admin" not in message.lower()
    assert "/agent/jobs/<job_id>/deliver" in rules
    assert "/agent/jobs/<job_id>/cancel" in rules
