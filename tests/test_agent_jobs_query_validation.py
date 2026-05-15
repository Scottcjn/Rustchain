from pathlib import Path

import pytest
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
