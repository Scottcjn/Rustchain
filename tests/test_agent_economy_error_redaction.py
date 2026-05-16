import sqlite3
from pathlib import Path

import pytest
from flask import Flask

import rip302_agent_economy


SECRET_ERROR = "no such table: balances at /srv/rustchain/private.db with super-secret"


def make_client(tmp_path: Path):
    app = Flask(__name__)
    rip302_agent_economy.register_agent_economy(app, str(tmp_path / "agent_jobs.db"))
    return app.test_client()


class FailingConnection:
    def cursor(self):
        raise sqlite3.OperationalError(SECRET_ERROR)

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.mark.parametrize(
    ("path", "payload"),
    (
        (
            "/agent/jobs",
            {
                "poster_wallet": "poster",
                "title": "Build integration",
                "description": "Build a complete test integration",
                "category": "other",
                "reward_rtc": 1,
            },
        ),
        ("/agent/jobs/job-1/claim", {"worker_wallet": "worker"}),
        (
            "/agent/jobs/job-1/deliver",
            {"worker_wallet": "worker", "result_summary": "done"},
        ),
        ("/agent/jobs/job-1/accept", {"poster_wallet": "poster"}),
        (
            "/agent/jobs/job-1/dispute",
            {"poster_wallet": "poster", "reason": "not accepted"},
        ),
        ("/agent/jobs/job-1/cancel", {"poster_wallet": "poster"}),
    ),
)
def test_agent_job_write_routes_hide_internal_database_errors(
    tmp_path, monkeypatch, path, payload
):
    client = make_client(tmp_path)

    monkeypatch.setattr(
        rip302_agent_economy.sqlite3,
        "connect",
        lambda *args, **kwargs: FailingConnection(),
    )

    response = client.post(path, json=payload)

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal error"}
    body = response.get_data(as_text=True)
    assert "no such table" not in body
    assert "/srv/rustchain" not in body
    assert "super-secret" not in body
