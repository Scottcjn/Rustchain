import pytest
from node.agent_economy_automatching import calculate_worker_match_score, rank_workers_for_job

def test_overloaded_worker_yields_zero_score():
    job = {"category": "code", "reward_rtc": 10}
    worker = {
        "wallet": "RTC_busy",
        "trust_score": 95,
        "active_jobs": 3,
        "max_concurrent_jobs": 3
    }
    score = calculate_worker_match_score(job, worker)
    assert score == 0.0

def test_high_reputation_and_category_match():
    job = {"category": "code", "reward_rtc": 10}
    worker = {
        "wallet": "RTC_expert",
        "trust_score": 90,
        "category_history": {"code": 10},
        "dispute_count": 0,
        "jobs_completed": 20,
        "active_jobs": 0,
        "max_concurrent_jobs": 3,
        "antiquity_multiplier": 2.0
    }
    score = calculate_worker_match_score(job, worker)
    # 90*0.4 (36) + 30 + 20 + 10 = 96.0
    assert score >= 90.0

def test_dispute_penalty_application():
    job = {"category": "data"}
    worker_clean = {
        "wallet": "RTC_clean",
        "trust_score": 80,
        "jobs_completed": 10,
        "dispute_count": 0,
        "active_jobs": 0
    }
    worker_disputed = {
        "wallet": "RTC_disputed",
        "trust_score": 80,
        "jobs_completed": 10,
        "dispute_count": 5,
        "active_jobs": 0
    }
    score_clean = calculate_worker_match_score(job, worker_clean)
    score_disputed = calculate_worker_match_score(job, worker_disputed)
    assert score_disputed < score_clean
    assert (score_clean - score_disputed) >= 20.0

def test_ranking_candidates_order():
    job = {"category": "research"}
    workers = [
        {"wallet": "W1", "trust_score": 50, "active_jobs": 0},
        {"wallet": "W2", "trust_score": 95, "category_history": {"research": 5}, "active_jobs": 0},
        {"wallet": "W3", "trust_score": 70, "active_jobs": 2, "max_concurrent_jobs": 2}
    ]
    ranked = rank_workers_for_job(job, workers, min_score=20.0)
    assert len(ranked) == 2
    assert ranked[0]["worker_wallet"] == "W2"
    assert ranked[1]["worker_wallet"] == "W1"
