# SPDX-License-Identifier: MIT
import sqlite3
import threading
from pathlib import Path

from flask import Flask

import rip302_agent_economy


def _make_client(tmp_path: Path):
    db_path = tmp_path / "agent_jobs.db"
    app = Flask(__name__)
    rip302_agent_economy.register_agent_economy(app, str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("poster", 2_000_000),
        )
    return app, db_path


def _balance(db_path: Path, wallet: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)
        ).fetchone()
    return row[0] if row else 0


def _create_delivered_job(client):
    post = client.post(
        "/agent/jobs",
        json={
            "poster_wallet": "poster",
            "title": "Race condition audit",
            "description": "Find and fix a reproducible escrow race condition.",
            "category": "code",
            "reward_rtc": 1,
        },
    )
    assert post.status_code == 201
    job_id = post.get_json()["job_id"]
    assert client.post(
        f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker"}
    ).status_code == 200
    assert client.post(
        f"/agent/jobs/{job_id}/deliver",
        json={"worker_wallet": "worker", "result_summary": "done"},
    ).status_code == 200
    return job_id


def test_dispute_cannot_overwrite_completed_job_and_unlock_second_refund(
    tmp_path, monkeypatch
):
    app, db_path = _make_client(tmp_path)
    client = app.test_client()
    job_id = _create_delivered_job(client)

    real_connect = sqlite3.connect
    dispute_about_to_write = threading.Event()
    accept_finished = threading.Event()

    class DelayedCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split())
            if normalized.startswith("UPDATE agent_jobs SET status = 'disputed'"):
                dispute_about_to_write.set()
                assert accept_finished.wait(timeout=5)
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
        if threading.current_thread().name == "stale-dispute":
            return DelayedConnection(conn)
        return conn

    monkeypatch.setattr(rip302_agent_economy.sqlite3, "connect", delayed_connect)

    dispute_response = {}

    def dispute_with_stale_read():
        with app.test_client() as stale_client:
            dispute_response["response"] = stale_client.post(
                f"/agent/jobs/{job_id}/dispute",
                json={"poster_wallet": "poster", "reason": "not accepted"},
            )

    dispute_thread = threading.Thread(
        target=dispute_with_stale_read, name="stale-dispute"
    )
    dispute_thread.start()

    assert dispute_about_to_write.wait(timeout=5)
    accept = client.post(f"/agent/jobs/{job_id}/accept", json={"poster_wallet": "poster"})
    assert accept.status_code == 200
    accept_finished.set()
    dispute_thread.join(timeout=5)
    assert not dispute_thread.is_alive()

    assert dispute_response["response"].status_code == 409

    cancel = client.post(f"/agent/jobs/{job_id}/cancel", json={"poster_wallet": "poster"})
    assert cancel.status_code == 409

    assert _balance(db_path, "agent_escrow") == 0
    assert _balance(db_path, "worker") == 1_000_000
    assert _balance(db_path, "founder_community") == 50_000
    assert _balance(db_path, "poster") == 950_000
