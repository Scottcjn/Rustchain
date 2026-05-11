from pathlib import Path

from flask import Flask

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
