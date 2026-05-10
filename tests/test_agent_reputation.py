import math

import pytest
from flask import Flask

import agent_reputation


class StubReputationEngine:
    def __init__(self, levels):
        self._levels = levels

    def get(self, agent_id):
        level, score, max_value = self._levels[agent_id]
        return {
            "agent_id": agent_id,
            "reputation_score": score,
            "level": level,
            "max_job_value_rtc": max_value,
        }


@pytest.fixture
def reputation_client(monkeypatch):
    engine = StubReputationEngine(
        {
            "trusted-agent": ("trusted", 60, math.inf),
            "veteran-agent": ("veteran", 90, math.inf),
        }
    )
    monkeypatch.setattr(agent_reputation, "_engine", engine)

    app = Flask(__name__)
    app.register_blueprint(agent_reputation.reputation_bp)
    return app.test_client()


def test_trusted_agent_can_claim_jobs_at_high_value_threshold(reputation_client):
    response = reputation_client.get(
        "/agent/reputation/check-eligibility",
        query_string={"agent_id": "trusted-agent", "job_value": "50"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["eligible"] is True
    assert payload["can_post_high_value"] is False
    assert payload["reason"] is None


def test_trusted_agent_cannot_claim_jobs_above_high_value_threshold(reputation_client):
    response = reputation_client.get(
        "/agent/reputation/check-eligibility",
        query_string={"agent_id": "trusted-agent", "job_value": "50.01"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["eligible"] is False
    assert payload["can_post_high_value"] is False
    assert "trusted level agents cannot claim high-value jobs" in payload["reason"]


def test_veteran_agent_can_claim_high_value_jobs(reputation_client):
    response = reputation_client.get(
        "/agent/reputation/check-eligibility",
        query_string={"agent_id": "veteran-agent", "job_value": "10000"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["eligible"] is True
    assert payload["can_post_high_value"] is True
    assert payload["reason"] is None
