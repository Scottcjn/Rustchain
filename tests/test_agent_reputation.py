import math
import threading

import pytest
from flask import Flask

import agent_reputation


class StubReputationEngine:
    def __init__(self, levels):
        self._levels = levels
        self._lock = threading.Lock()
        self._cache = {
            "veteran-agent": ({"reputation_score": 90}, 0),
            "trusted-agent": ({"reputation_score": 60}, 0),
        }

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
            "newcomer-agent": ("newcomer", 10, 5),
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


def test_level_cap_denial_uses_level_cap_reason(reputation_client):
    response = reputation_client.get(
        "/agent/reputation/check-eligibility",
        query_string={"agent_id": "newcomer-agent", "job_value": "5.01"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["eligible"] is False
    assert payload["reason"] == "newcomer level agents can only claim jobs up to 5 RTC"


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


@pytest.mark.parametrize("job_value", ["-1", "nan", "inf", "-inf"])
def test_check_eligibility_rejects_invalid_job_values(reputation_client, job_value):
    response = reputation_client.get(
        "/agent/reputation/check-eligibility",
        query_string={"agent_id": "trusted-agent", "job_value": job_value},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "job_value must be a finite non-negative number"


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_leaderboard_rejects_non_positive_limits(reputation_client, limit):
    response = reputation_client.get(
        "/agent/reputation/leaderboard",
        query_string={"limit": limit},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "limit must be between 1 and 100"


def test_refresh_stale_cache_entries_stores_recalculated_result(monkeypatch):
    engine = agent_reputation.ReputationEngine(db_path="/tmp/does-not-exist.db")
    engine._cache["agent-a"] = ({"reputation_score": 1}, 0)

    monkeypatch.setattr(
        engine,
        "calculate",
        lambda wallet: {"agent_id": wallet, "reputation_score": 99},
    )

    engine._refresh_stale_cache_entries()

    refreshed, timestamp = engine._cache["agent-a"]
    assert refreshed == {"agent_id": "agent-a", "reputation_score": 99}
    assert timestamp > 0
