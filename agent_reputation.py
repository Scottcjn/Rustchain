"""
agent_reputation.py — RustChain Agent Reputation Scoring Engine
Bounty #754: Agent Reputation Score — On-Chain Trust for Agent Economy

Integration:
    from agent_reputation import reputation_bp, ReputationEngine
    engine = ReputationEngine(db_path="rustchain.db", node_url="https://rustchain.org")
    engine.start_cache_refresh()
    app.register_blueprint(reputation_bp)

Standalone test:
    python3 agent_reputation.py --agent noxventures_rtc

Author: noxventures_rtc
Wallet: noxventures_rtc
"""

import time
import math
import threading
import sqlite3
import os
import json
import urllib.request
from flask import Blueprint, jsonify, request
from node.tls_config import get_ssl_context

# ─── Config ─────────────────────────────────────────────────────────────────── #
DB_PATH       = os.environ.get("RUSTCHAIN_DB_PATH", "rustchain.db")
NODE_URL      = os.environ.get("RUSTCHAIN_NODE_URL", "https://rustchain.org")
CACHE_TTL_S   = 3600       # Refresh reputation cache every epoch (~1hr)
DECAY_DAYS    = 30         # Lose 1 point per 30 days inactive

CTX = get_ssl_context()

# ─── Reputation Levels ───────────────────────────────────────────────────────── #
LEVELS = [
    (81, "veteran",    "Can post high-value jobs (50+ RTC), priority in disputes"),
    (51, "trusted",    "Can claim any job, can post jobs"),
    (21, "known",      "Can claim jobs up to 25 RTC"),
    ( 0, "newcomer",   "Can claim jobs up to 5 RTC"),
]

MAX_JOB_VALUE = {
    "newcomer": 5,
    "known":    25,
    "trusted":  float("inf"),
    "veteran":  float("inf"),
}

CAN_POST_JOBS       = {"trusted", "veteran"}
CAN_POST_HIGH_VALUE = {"veteran"}
HIGH_VALUE_THRESHOLD = 50  # RTC — jobs above this require veteran level


def score_to_level(score):
    for threshold, level, desc in LEVELS:
        if score >= threshold:
            return level, desc
    return "newcomer", LEVELS[-1][2]


# ─── ReputationEngine ────────────────────────────────────────────────────────── #
class ReputationEngine:
    def __init__(self, db_path=DB_PATH, node_url=NODE_URL):
        self.db_path  = db_path
        self.node_url = node_url
        self._cache   = {}          # wallet -> (score_dict, timestamp)
        self._lock    = threading.Lock()

    # ── DB helpers ──────────────────────────────────────────────────────────── #
    def _query(self, sql, params=()):
        """Run a read query against the SQLite DB. Returns list of Row dicts."""
        if not os.path.exists(self.db_path):
            return []
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ── Node API fetch ──────────────────────────────────────────────────────── #
    def _fetch(self, path):
        url = f"{self.node_url.rstrip('/')}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rustchain-reputation/1.0"})
            with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    # ── Reputation Calculation ──────────────────────────────────────────────── #
    def calculate(self, wallet: str) -> dict:
        """
        Compute reputation score for a wallet from on-chain data.
        Falls back to API if DB not available locally.
        """
        now = time.time()

        # ── Jobs data (from DB or API) ───────────────────────────────────────── #
        jobs_completed = 0
        jobs_accepted  = 0
        jobs_disputed  = 0
        total_earned   = 0.0
        delivery_hours = []
        first_job_ts   = None

        # Try DB first
        job_rows = self._query(
            """SELECT status, reward_rtc, claimed_at, completed_at, rejection_reason
               FROM agent_jobs
               WHERE worker_wallet = ?""",
            (wallet,)
        )

        if job_rows:
            for row in job_rows:
                status = row.get("status", "")
                reward = float(row.get("reward_rtc", 0) or 0)
                claimed_at   = row.get("claimed_at")
                completed_at = row.get("completed_at")

                if status in ("delivered", "accepted", "completed"):
                    jobs_completed += 1
                    total_earned   += reward
                    if claimed_at and completed_at:
                        hours = (float(completed_at) - float(claimed_at)) / 3600
                        delivery_hours.append(max(0.1, hours))
                    if first_job_ts is None or (claimed_at and float(claimed_at) < first_job_ts):
                        first_job_ts = float(claimed_at) if claimed_at else None

                if status == "accepted":
                    jobs_accepted += 1

                if status in ("rejected", "disputed") or row.get("rejection_reason"):
                    jobs_disputed += 1
        else:
            # Fallback: use API
            api_data = self._fetch(f"/agent/jobs?worker_wallet={wallet}&limit=200")
            if api_data and isinstance(api_data, dict):
                for job in api_data.get("jobs", []):
                    status = job.get("status", "")
                    reward = float(job.get("reward_rtc", 0) or 0)
                    claimed_at   = job.get("claimed_at")
                    completed_at = job.get("completed_at")

                    if status in ("delivered", "accepted", "completed"):
                        jobs_completed += 1
                        total_earned   += reward
                        if claimed_at and completed_at:
                            hours = (float(completed_at) - float(claimed_at)) / 3600
                            delivery_hours.append(max(0.1, hours))
                        if first_job_ts is None or (claimed_at and float(claimed_at) < first_job_ts):
                            first_job_ts = float(claimed_at) if claimed_at else None

                    if status == "accepted":
                        jobs_accepted += 1
                    if status in ("rejected", "disputed"):
                        jobs_disputed += 1

        # ── Hardware attestation ─────────────────────────────────────────────── #
        hardware_verified = False
        attest_rows = self._query(
            "SELECT wallet_name, created_at FROM miner_attest_recent WHERE wallet_name = ? LIMIT 1",
            (wallet,)
        )
        if attest_rows:
            hardware_verified = True
        else:
            # Try via API /api/miners
            miners_data = self._fetch("/api/miners")
            if miners_data:
                miners = miners_data if isinstance(miners_data, list) else miners_data.get("miners", [])
                for m in miners:
                    if m.get("wallet_name") == wallet or m.get("wallet") == wallet:
                        hardware_verified = True
                        break

        # ── Account age ──────────────────────────────────────────────────────── #
        account_age_days = 0
        if first_job_ts:
            account_age_days = (now - first_job_ts) / 86400

        # Also check miner table for earlier activity
        miner_rows = self._query(
            "SELECT MIN(created_at) as first_seen FROM miner_attest_recent WHERE wallet_name = ?",
            (wallet,)
        )
        if miner_rows and miner_rows[0].get("first_seen"):
            miner_age = (now - float(miner_rows[0]["first_seen"])) / 86400
            account_age_days = max(account_age_days, miner_age)

        # ── Last activity (for decay) ─────────────────────────────────────────── #
        last_activity_ts = first_job_ts or now
        all_activity = self._query(
            "SELECT MAX(completed_at) as last FROM agent_jobs WHERE worker_wallet = ?",
            (wallet,)
        )
        if all_activity and all_activity[0].get("last"):
            last_activity_ts = float(all_activity[0]["last"])

        days_inactive = max(0, (now - last_activity_ts) / 86400)

        # ── Score Calculation ────────────────────────────────────────────────── #
        score = 0.0

        # Jobs
        score += jobs_completed * 10
        score += jobs_accepted  * 5
        score -= jobs_disputed  * 15

        # Delivery speed bonus (faster = more points, max +5)
        if delivery_hours:
            avg_hours = sum(delivery_hours) / len(delivery_hours)
            if avg_hours < 1:
                score += 5
            elif avg_hours < 4:
                score += 4
            elif avg_hours < 12:
                score += 3
            elif avg_hours < 24:
                score += 2
            elif avg_hours < 72:
                score += 1

        # Total RTC earned: +1 per 10 RTC
        score += math.floor(total_earned / 10)

        # Account age: +1 per 30 days
        score += math.floor(account_age_days / 30)

        # Hardware attestation bonus
        if hardware_verified:
            score += 10

        # ── Decay ────────────────────────────────────────────────────────────── #
        decay = math.floor(days_inactive / DECAY_DAYS)
        score = max(0, score - decay)

        # ── Level ────────────────────────────────────────────────────────────── #
        score = int(score)
        level, level_desc = score_to_level(score)

        result = {
            "agent_id": wallet,
            "reputation_score": score,
            "level": level,
            "level_description": level_desc,
            "max_job_value_rtc": MAX_JOB_VALUE[level],
            "can_post_jobs": level in CAN_POST_JOBS,
            "can_post_high_value": level in CAN_POST_HIGH_VALUE,
            "jobs_completed": jobs_completed,
            "jobs_accepted": jobs_accepted,
            "jobs_disputed": jobs_disputed,
            "avg_delivery_hours": round(sum(delivery_hours) / len(delivery_hours), 2) if delivery_hours else None,
            "total_earned_rtc": round(total_earned, 4),
            "account_age_days": round(account_age_days, 1),
            "days_inactive": round(days_inactive, 1),
            "decay_applied": decay,
            "hardware_verified": hardware_verified,
            "calculated_at": now,
        }

        return result

    # ── Cache layer ──────────────────────────────────────────────────────────── #
    def get(self, wallet: str) -> dict:
        with self._lock:
            if wallet in self._cache:
                data, ts = self._cache[wallet]
                if time.time() - ts < CACHE_TTL_S:
                    return {**data, "cached": True}
        result = self.calculate(wallet)
        with self._lock:
            self._cache[wallet] = (result, time.time())
        return result

    def invalidate(self, wallet: str = None):
        with self._lock:
            if wallet:
                self._cache.pop(wallet, None)
            else:
                self._cache.clear()

    def _refresh_loop(self):
        while True:
            time.sleep(CACHE_TTL_S)
            with self._lock:
                stale = [w for w, (_, ts) in self._cache.items()
                         if time.time() - ts > CACHE_TTL_S]
            for w in stale:
                self.calculate(w)
                with self._lock:
                    if w in self._cache:
                        self._cache[w] = (self._cache[w][0], time.time())

    def start_cache_refresh(self):
        t = threading.Thread(target=self._refresh_loop, daemon=True)
        t.start()


# ─── Global engine instance (override in app init) ──────────────────────────── #
_engine = ReputationEngine()


# ─── Flask Blueprint ─────────────────────────────────────────────────────────── #
reputation_bp = Blueprint("reputation", __name__)


@reputation_bp.route("/agent/reputation")
def get_reputation():
    """
    GET /agent/reputation?agent_id=my-wallet
    Returns reputation score and level for a wallet.
    """
    agent_id = request.args.get("agent_id", "").strip()
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400

    result = _engine.get(agent_id)
    return jsonify(result)


@reputation_bp.route("/agent/reputation/check-eligibility")
def check_eligibility():
    """
    GET /agent/reputation/check-eligibility?agent_id=wallet&job_value=20
    Returns whether an agent is eligible to claim a job of given value.
    """
    agent_id  = request.args.get("agent_id", "").strip()
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400

    try:
        job_value = float(request.args.get("job_value", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "job_value must be a number"}), 400
    if not math.isfinite(job_value) or job_value < 0:
        return jsonify({"error": "job_value must be a finite non-negative number"}), 400

    rep = _engine.get(agent_id)
    max_val = rep["max_job_value_rtc"]
    level = rep["level"]
    eligible = job_value <= max_val

    # High-value job gate: jobs above HIGH_VALUE_THRESHOLD require veteran level
    if eligible and job_value > HIGH_VALUE_THRESHOLD:
        if level not in CAN_POST_HIGH_VALUE:
            eligible = False

    return jsonify({
        "agent_id": agent_id,
        "job_value_rtc": job_value,
        "eligible": eligible,
        "reputation_score": rep["reputation_score"],
        "level": level,
        "can_post_high_value": level in CAN_POST_HIGH_VALUE,
        "max_job_value_rtc": max_val,
        "reason": None if eligible else f"{level} level agents cannot claim high-value jobs (>{HIGH_VALUE_THRESHOLD} RTC)",
    })


@reputation_bp.route("/agent/reputation/leaderboard")
def leaderboard():
    """
    GET /agent/reputation/leaderboard?limit=20
    Returns top agents by reputation (from cache).
    """
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer"}), 400
    if limit < 1:
        return jsonify({"error": "limit must be between 1 and 100"}), 400
    with _engine._lock:
        entries = [(w, d["reputation_score"]) for w, (d, _) in _engine._cache.items()]
    entries.sort(key=lambda x: x[1], reverse=True)
    return jsonify({
        "leaderboard": [
            {"rank": i + 1, "agent_id": w, "score": s}
            for i, (w, s) in enumerate(entries[:limit])
        ],
        "total_agents_tracked": len(entries),
    })


# ─── CLI / standalone ─────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Agent Reputation Engine")
    parser.add_argument("--agent", required=True, help="Wallet name to check")
    parser.add_argument("--db", default=DB_PATH, help="Path to rustchain.db")
    parser.add_argument("--node", default=NODE_URL, help="Node URL")
    args = parser.parse_args()

    engine = ReputationEngine(db_path=args.db, node_url=args.node)
    result = engine.calculate(args.agent)

    print(f"\n{'='*50}")
    print(f"Agent Reputation: {result['agent_id']}")
    print(f"{'='*50}")
    print(f"  Score:          {result['reputation_score']} pts")
    print(f"  Level:          {result['level'].upper()} — {result['level_description']}")
    print(f"  Max Job Value:  {result['max_job_value_rtc']} RTC")
    print(f"  Can Post Jobs:  {'✓' if result['can_post_jobs'] else '✗'}")
    print(f"")
    print(f"  Jobs Completed: {result['jobs_completed']}")
    print(f"  Jobs Accepted:  {result['jobs_accepted']}")
    print(f"  Jobs Disputed:  {result['jobs_disputed']}")
    if result['avg_delivery_hours']:
        print(f"  Avg Delivery:   {result['avg_delivery_hours']}h")
    print(f"  Total Earned:   {result['total_earned_rtc']} RTC")
    print(f"  Account Age:    {result['account_age_days']} days")
    print(f"  Days Inactive:  {result['days_inactive']} days")
    print(f"  Decay Applied:  -{result['decay_applied']} pts")
    print(f"  HW Verified:    {'✓' if result['hardware_verified'] else '✗'}")
    print()
