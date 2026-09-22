# SPDX-License-Identifier: MIT
"""Regression: when a CLAIMED job expires, the WORKER's reputation takes the
jobs_expired hit, not the poster's.

_expire_refundable_job() booked every expiry against poster_wallet. For a
claimed job that means the worker who took it and never delivered walks away
clean, and any worker could poison a poster's trust score just by claiming
their jobs and letting them lapse. An OPEN job nobody claimed still counts
against the poster (unchanged).
"""
import sqlite3
import time

import pytest
from flask import Flask

import rip302_agent_economy as r302
from tests.rip302_auth_helpers import rip302_authorized  # noqa: F401  (autouse)

JOB = {
    "poster_wallet": "poster",
    "title": "Write a scraper",
    "description": "Scrape the public listing page and return a CSV of rows.",
    "category": "code",
    "reward_rtc": 1,
}


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "jobs.db"
    app = Flask(__name__)
    r302.register_agent_economy(app, str(db))
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)")
        conn.execute("INSERT INTO balances VALUES (?, ?)", ("poster", 50_000_000))
    return {"client": app.test_client(), "db": db}


def _expired_count(client, wallet):
    body = client.get(f"/agent/reputation/{wallet}").get_json()
    rep = body["reputation"]
    return rep.get("jobs_expired", 0)


def _force_expiry(db, job_id):
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE agent_jobs SET expires_at = ? WHERE job_id = ?",
                     (int(time.time()) - 100, job_id))


def test_claimed_job_expiry_penalizes_worker(env):
    c = env["client"]
    r = c.post("/agent/jobs", json=JOB)
    assert r.status_code == 201, r.data
    job_id = r.get_json()["job_id"]
    r = c.post(f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker"})
    assert r.status_code == 200, r.data

    _force_expiry(env["db"], job_id)
    r = c.get(f"/agent/jobs/{job_id}")  # read path runs the expiry sweep
    assert r.status_code == 200, r.data
    assert r.get_json()["job"]["status"] == "expired"

    assert _expired_count(c, "worker") == 1, "the no-show worker must carry the expiry"
    assert _expired_count(c, "poster") == 0, "the poster must not be penalized for a worker's no-show"
    # Escrow still refunds to the poster.
    with sqlite3.connect(env["db"]) as conn:
        assert conn.execute("SELECT amount_i64 FROM balances WHERE miner_id='poster'").fetchone()[0] == 50_000_000


def test_open_job_expiry_still_counts_against_poster(env):
    c = env["client"]
    r = c.post("/agent/jobs", json=JOB)
    assert r.status_code == 201, r.data
    job_id = r.get_json()["job_id"]

    _force_expiry(env["db"], job_id)
    c.get(f"/agent/jobs/{job_id}")

    assert _expired_count(c, "poster") == 1
    assert _expired_count(c, "worker") == 0
