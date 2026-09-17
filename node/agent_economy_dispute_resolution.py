"""
RustChain RIP-302 Agent Economy Dispute Resolution Engine
Voting-based dispute settlement by reputation holders:
1. When a job is disputed, a dispute round opens with a voting deadline.
2. Only agents with trust_score >= MIN_JUROR_TRUST (default 70) can cast juror votes.
3. Juror vote weight is proportional to their trust score and hardware antiquity multiplier.
4. Quorum and majority rules determine whether escrow is released to the worker or refunded to the poster.
5. Slashing & reward rules: Jurors voting with the majority earn dispute settlement fees; bad-faith posters or fraudulent workers suffer trust score penalties.
"""

from typing import List, Dict, Any, Optional
import time

MIN_JUROR_TRUST = 70.0
QUORUM_MIN_VOTES = 3

class DisputeStatus:
    PENDING = "pending"
    RESOLVED_WORKER_WIN = "resolved_worker_win"
    RESOLVED_POSTER_WIN = "resolved_poster_win"
    NO_QUORUM_REFUND = "no_quorum_refund"

def calculate_juror_vote_weight(juror: Dict[str, Any]) -> float:
    """
    Juror vote weight is based on verified trust score (>=70) and antiquity multiplier.
    Weight = (trust_score / 10.0) * sqrt(antiquity_multiplier)
    """
    trust = float(juror.get("trust_score", 0.0))
    if trust < MIN_JUROR_TRUST:
        return 0.0

    multiplier = max(float(juror.get("antiquity_multiplier", 1.0)), 1.0)
    base_weight = trust / 10.0
    antiquity_factor = multiplier ** 0.5
    return round(base_weight * antiquity_factor, 3)

def tally_dispute_votes(
    dispute: Dict[str, Any],
    votes: List[Dict[str, Any]],
    current_time: Optional[int] = None
) -> Dict[str, Any]:
    """
    Tallies juror votes for a disputed job.
    Vote payload: {"juror": {...}, "vote": "worker" | "poster"}
    """
    if current_time is None:
        current_time = int(time.time())

    deadline = dispute.get("voting_deadline", 0)
    is_expired = current_time >= deadline

    valid_votes = []
    worker_weight = 0.0
    poster_weight = 0.0

    seen_jurors = set()

    for entry in votes:
        juror = entry.get("juror", {})
        wallet = juror.get("wallet")
        if not wallet or wallet in seen_jurors:
            continue
        # Poster and worker cannot vote on their own dispute
        if wallet in [dispute.get("poster_wallet"), dispute.get("worker_wallet")]:
            continue

        weight = calculate_juror_vote_weight(juror)
        if weight <= 0.0:
            continue

        seen_jurors.add(wallet)
        choice = entry.get("vote")
        if choice == "worker":
            worker_weight += weight
            valid_votes.append({"wallet": wallet, "vote": "worker", "weight": weight})
        elif choice == "poster":
            poster_weight += weight
            valid_votes.append({"wallet": wallet, "vote": "poster", "weight": weight})

    total_votes_count = len(valid_votes)
    total_weight = worker_weight + poster_weight

    status = DisputeStatus.PENDING
    winner = None

    if is_expired or total_votes_count >= 5:
        if total_votes_count < QUORUM_MIN_VOTES:
            status = DisputeStatus.NO_QUORUM_REFUND
            winner = "split"
        elif worker_weight > poster_weight:
            status = DisputeStatus.RESOLVED_WORKER_WIN
            winner = "worker"
        else:
            status = DisputeStatus.RESOLVED_POSTER_WIN
            winner = "poster"

    return {
        "job_id": dispute.get("job_id"),
        "status": status,
        "winner": winner,
        "total_votes": total_votes_count,
        "worker_weight": round(worker_weight, 3),
        "poster_weight": round(poster_weight, 3),
        "quorum_reached": total_votes_count >= QUORUM_MIN_VOTES,
        "is_expired": is_expired
    }
