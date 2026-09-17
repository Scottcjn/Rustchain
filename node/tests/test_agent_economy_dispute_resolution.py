import pytest
from node.agent_economy_dispute_resolution import (
    calculate_juror_vote_weight,
    tally_dispute_votes,
    DisputeStatus
)

def test_juror_below_min_trust_has_zero_weight():
    juror = {"wallet": "J_low", "trust_score": 65, "antiquity_multiplier": 2.0}
    weight = calculate_juror_vote_weight(juror)
    assert weight == 0.0

def test_juror_antiquity_scaling():
    juror1 = {"wallet": "J1", "trust_score": 80, "antiquity_multiplier": 1.0}
    juror2 = {"wallet": "J2", "trust_score": 80, "antiquity_multiplier": 4.0}
    w1 = calculate_juror_vote_weight(juror1)
    w2 = calculate_juror_vote_weight(juror2)
    # w1 = 8.0 * 1.0 = 8.0; w2 = 8.0 * 2.0 = 16.0
    assert w1 == 8.0
    assert w2 == 16.0

def test_dispute_parties_cannot_vote():
    dispute = {
        "job_id": "job_99",
        "poster_wallet": "P_wallet",
        "worker_wallet": "W_wallet",
        "voting_deadline": 1000
    }
    votes = [
        {"juror": {"wallet": "P_wallet", "trust_score": 90}, "vote": "poster"},
        {"juror": {"wallet": "W_wallet", "trust_score": 90}, "vote": "worker"},
        {"juror": {"wallet": "J1", "trust_score": 85}, "vote": "worker"}
    ]
    res = tally_dispute_votes(dispute, votes, current_time=500)
    assert res["total_votes"] == 1
    assert res["worker_weight"] > 0
    assert res["poster_weight"] == 0.0

def test_dispute_quorum_and_worker_win():
    dispute = {
        "job_id": "job_100",
        "poster_wallet": "P_wallet",
        "worker_wallet": "W_wallet",
        "voting_deadline": 1000
    }
    votes = [
        {"juror": {"wallet": "J1", "trust_score": 80, "antiquity_multiplier": 1.0}, "vote": "worker"},
        {"juror": {"wallet": "J2", "trust_score": 90, "antiquity_multiplier": 1.0}, "vote": "worker"},
        {"juror": {"wallet": "J3", "trust_score": 75, "antiquity_multiplier": 1.0}, "vote": "poster"}
    ]
    # Expired timestamp triggers final determination
    res = tally_dispute_votes(dispute, votes, current_time=1001)
    assert res["quorum_reached"] is True
    assert res["status"] == DisputeStatus.RESOLVED_WORKER_WIN
    assert res["winner"] == "worker"
    assert res["worker_weight"] > res["poster_weight"]
