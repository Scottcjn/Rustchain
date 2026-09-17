"""
RustChain RIP-302 Agent Economy Auto-Matching Engine
Algorithm that matches open jobs to the best-reputation workers based on:
1. Category track record & historical task success rate.
2. Trust score (0-100) and dispute frequency penalty.
3. Worker capacity and concurrent active claims.
4. Response latency and stake / antiquity weight.
"""

from typing import List, Dict, Any, Optional
import math
import time

def calculate_worker_match_score(
    job: Dict[str, Any],
    worker: Dict[str, Any]
) -> float:
    """
    Computes a deterministic match score (0.0 to 100.0) between a job and a candidate worker.
    """
    # 1. Base reputation trust score (0 - 100, weight: 40%)
    trust_score = float(worker.get("trust_score", 0.0))
    trust_component = min(max(trust_score, 0.0), 100.0) * 0.40

    # 2. Category expertise match (weight: 30%)
    job_category = job.get("category", "other")
    worker_categories = worker.get("category_history", {})
    cat_completed = worker_categories.get(job_category, 0)
    # Diminishing returns scaling: 10 completed jobs yields max category score
    category_score = min(cat_completed / 10.0, 1.0) * 100.0
    category_component = category_score * 0.30

    # 3. Dispute penalty (negative impact up to -25 points)
    dispute_count = int(worker.get("dispute_count", 0))
    total_completed = max(int(worker.get("jobs_completed", 0)), 1)
    dispute_ratio = dispute_count / total_completed
    dispute_penalty = min(dispute_ratio * 50.0, 25.0)

    # 4. Concurrency & load capacity penalty (weight: 20%)
    active_jobs = int(worker.get("active_jobs", 0))
    max_concurrent = max(int(worker.get("max_concurrent_jobs", 3)), 1)
    if active_jobs >= max_concurrent:
        # Overloaded worker
        return 0.0
    capacity_ratio = 1.0 - (active_jobs / max_concurrent)
    capacity_component = (capacity_ratio * 100.0) * 0.20

    # 5. Antiquity / hardware backing bonus (weight: 10%)
    multiplier = float(worker.get("antiquity_multiplier", 1.0))
    # Normalized: 1.0x -> 50%, 2.0x+ -> 100%
    antiquity_score = min(multiplier / 2.0, 1.0) * 100.0
    antiquity_component = antiquity_score * 0.10

    total_score = trust_component + category_component + capacity_component + antiquity_component - dispute_penalty
    return max(round(total_score, 2), 0.0)


def rank_workers_for_job(
    job: Dict[str, Any],
    candidate_workers: List[Dict[str, Any]],
    min_score: float = 30.0,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Ranks eligible worker agents for a given open job.
    Returns ranked candidates with their match scores.
    """
    ranked = []
    for worker in candidate_workers:
        score = calculate_worker_match_score(job, worker)
        if score >= min_score:
            ranked.append({
                "worker_wallet": worker.get("wallet"),
                "match_score": score,
                "trust_score": worker.get("trust_score", 0),
                "category": job.get("category"),
                "active_jobs": worker.get("active_jobs", 0),
                "matched_at": int(time.time())
            })

    ranked.sort(key=lambda x: x["match_score"], reverse=True)
    return ranked[:limit]
