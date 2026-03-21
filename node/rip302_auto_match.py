"""
RIP-302 Auto-Matching Engine — Scores and ranks workers for job matching based on reputation,
category expertise, and completion rate.

Endpoints:
  GET /agent/match/<job_id>         — Ranked worker suggestions for a job
  POST /agent/match/<job_id>/view   — Record a worker viewing a job
  GET /agent/match/suggest          — Best-fit open jobs for a worker wallet
  GET /agent/match/leaderboard     — Top workers per category
  GET /agent/match/stats           — Auto-match engine health stats

Author: kuanglaodi2-sudo
Date:  2026-03-20
Bounty: #683 Tier 3 — Auto-matching (75 RTC)
"""

import hashlib
import json
import sqlite3
import time
from flask import Flask, jsonify, request

log = __import__("logging").getLogger("rip302_auto_match")


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────────────────────

CATEGORY_WEIGHTS = {
    "research":       1.0,
    "code":           1.2,   # Higher weight — harder to fake competency
    "video":          0.9,
    "audio":          0.9,
    "writing":        0.85,
    "translation":    0.85,
    "data":           1.0,
    "design":         1.0,
    "testing":        1.1,
    "other":          0.8,
}

RECENCY_WINDOW_SECS = 14 * 86400    # 14 days — beyond this, scores decay
MIN_JOBS_FOR_CATEGORY_SCORE = 3     # Need ≥3 category jobs before trusting category expert


def init_auto_match_tables(db_path: str):
    """Create auto-match tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # Per-category performance per worker
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_category_stats (
                wallet_id   TEXT NOT NULL,
                category    TEXT NOT NULL,
                jobs_in_cat INTEGER DEFAULT 0,
                completed   INTEGER DEFAULT 0,
                disputed    INTEGER DEFAULT 0,
                expired     INTEGER DEFAULT 0,
                total_earned REAL DEFAULT 0,
                avg_rating  REAL DEFAULT 0,
                updated_at  INTEGER,
                PRIMARY KEY (wallet_id, category)
            )
        """)

        # Match suggestion cache (rate-limited per job)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_match_cache (
                job_id     TEXT NOT NULL,
                cached_at  INTEGER NOT NULL,
                results_json TEXT NOT NULL,
                PRIMARY KEY (job_id)
            )
        """)

        # Worker views — track who might be interested in a job
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_job_views (
                wallet_id  TEXT NOT NULL,
                job_id     TEXT NOT NULL,
                viewed_at  INTEGER NOT NULL,
                PRIMARY KEY (wallet_id, job_id)
            )
        """)

        # Indices for fast lookups
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_cat_stats_category
            ON agent_category_stats (category, completed DESC)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_cat_stats_score
            ON agent_category_stats (wallet_id, updated_at)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_views_job
            ON agent_job_views (job_id)
        """)

        conn.commit()

    log.info("RIP-302 Auto-match tables initialized")


def register_auto_match(app: Flask, db_path: str):
    """Register all auto-matching routes."""

    init_auto_match_tables(db_path)

    # ─── Helper: sync category stats from job history ───────────────────────────────────
    def _sync_category_stats(c: sqlite3.Cursor, wallet_id: str):
        """Rebuild per-category stats for a wallet from job history."""
        now = int(time.time())
        cutoff = now - RECENCY_WINDOW_SECS

        for cat in ("research", "code", "video", "audio", "writing",
                    "translation", "data", "design", "testing", "other"):
            rows = c.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'disputed' THEN 1 ELSE 0 END) AS disputed,
                    SUM(CASE WHEN status = 'expired'  THEN 1 ELSE 0 END) AS expired,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN reward_rtc ELSE 0 END), 0) AS earned
                FROM agent_jobs
                WHERE category = ?
                  AND worker_wallet = ?
                  AND status IN ('completed','disputed','expired')
                  AND completed_at > ?
            """, (cat, wallet_id, cutoff)).fetchone()

            total, completed, disputed, expired, earned = rows
            if total and total > 0:
                avg_r = c.execute("""
                    SELECT AVG(rating) FROM agent_ratings
                    WHERE ratee_wallet = ? AND role = 'poster_rates_worker'
                    """, (wallet_id,)).fetchone()[0] or 0.0

                c.execute("""
                    INSERT OR REPLACE INTO agent_category_stats
                    (wallet_id, category, jobs_in_cat, completed, disputed,
                     expired, total_earned, avg_rating, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (wallet_id, cat, total, completed, disputed,
                      expired, earned, avg_r, now))

    # ─── Helper: compute match score for a worker on a job ────────────────────────────
    def _compute_match_score(c: sqlite3.Cursor, wallet_id: str,
                              job_category: str, job_reward: float) -> dict:
        """
        Compute a 0–100 match score for wallet vs job.
        Returns dict with score + breakdown.
        """
        now = int(time.time())

        # Global reputation
        rep = c.execute(
            "SELECT * FROM agent_reputation WHERE wallet_id = ?",
            (wallet_id,)
        ).fetchone()

        if not rep:
            rep_cols = ["wallet_id","jobs_posted","jobs_completed_as_poster","jobs_completed_as_worker",
                        "jobs_disputed","jobs_expired","total_rtc_paid","total_rtc_earned","avg_rating",
                        "rating_count","first_seen","last_active"]
            rep = dict(zip(rep_cols,
                           [wallet_id,0,0,0,0,0,0,0,None,None,None,None]))

        r = dict(rep)

        # ── Trust Score (0–40 points) ──────────────────────────────────────────────
        total_jobs = (r.get("jobs_completed_as_worker", 0) +
                      r.get("jobs_completed_as_poster", 0) +
                      r.get("jobs_disputed", 0) +
                      r.get("jobs_expired", 0))
        if total_jobs == 0:
            trust_pts = 10  # New agent gets benefit of the doubt
        else:
            success_rate = r.get("jobs_completed_as_worker", 0) / total_jobs
            rating_contribution = (r.get("avg_rating", 0) / 5 * 0.2) if r.get("rating_count", 0) > 0 else 0.1
            trust_pts = min(40, int((success_rate * 0.8 + rating_contribution) * 40))

        # ── Category Expertise Score (0–35 points) ──────────────────────────────────
        cat_row = c.execute("""
            SELECT * FROM agent_category_stats
            WHERE wallet_id = ? AND category = ?
        """, (wallet_id, job_category)).fetchone()

        if cat_row and cat_row[2] >= MIN_JOBS_FOR_CATEGORY_SCORE:
            cat_total = cat_row[2]
            cat_completed = cat_row[3]
            cat_success = cat_completed / cat_total if cat_total > 0 else 0
            cat_weight = CATEGORY_WEIGHTS.get(job_category, 1.0)
            cat_pts = min(35, int(cat_success * 35 * cat_weight))
            cat_experience = cat_completed
        else:
            # Fallback: overall completion rate in this category as proxy
            global_cat = c.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                FROM agent_jobs WHERE category = ? AND worker_wallet = ?
                """, (job_category, wallet_id)).fetchone()
            if global_cat and global_cat[0] >= MIN_JOBS_FOR_CATEGORY_SCORE:
                cat_success = global_cat[1] / global_cat[0] if global_cat[0] > 0 else 0
                cat_pts = min(35, int(cat_success * 35 * CATEGORY_WEIGHTS.get(job_category, 1.0)))
                cat_experience = global_cat[1]
            else:
                cat_pts = 0
                cat_experience = 0

        # ── Reward Fitness Score (0–15 points) ─────────────────────────────────────
        # Workers who consistently handle similar reward tiers get credit
        reward_tier = "micro" if job_reward < 1 else \
                      "small" if job_reward < 10 else \
                      "medium" if job_reward < 100 else "large"
        tier_row = c.execute("""
            SELECT COUNT(*), AVG(reward_rtc)
            FROM agent_jobs
            WHERE worker_wallet = ? AND status = 'completed'
            AND completed_at > ?
        """, (wallet_id, now - RECENCY_WINDOW_SECS)).fetchone()
        if tier_row and tier_row[0] > 0:
            avg_r = tier_row[1] or 0
            tier_fit = 1.0 - min(abs(job_reward - avg_r) / max(job_reward, avg_r, 1), 1) * 0.3
            reward_pts = min(15, int(tier_fit * 15))
        else:
            reward_pts = 5  # Neutral for new workers

        # ── Recency Bonus (0–10 points) ───────────────────────────────────────────
        last_active = r.get("last_active")
        if last_active and (now - last_active) < RECENCY_WINDOW_SECS:
            recency_ratio = 1 - (now - last_active) / RECENCY_WINDOW_SECS
            recency_pts = int(recency_ratio * 10)
        else:
            recency_pts = 0

        total_score = min(100, trust_pts + cat_pts + reward_pts + recency_pts)

        return {
            "wallet_id":          wallet_id,
            "total_score":        total_score,
            "trust_score":        trust_pts,
            "category_score":     cat_pts,
            "reward_fit":         reward_pts,
            "recency_bonus":      recency_pts,
            "category":           job_category,
            "total_jobs":         total_jobs,
            "category_jobs":      cat_experience,
            "avg_rating":         round(r.get("avg_rating", 0) or 0, 2),
        }

    # ─── GET /agent/match/<job_id> ──── Ranked worker suggestions for a job ────────────
    @app.route("/agent/match/<job_id>", methods=["GET"])
    def agent_match_job(job_id: str):
        """Return ranked list of workers best suited for a specific job."""
        limit = min(int(request.args.get("limit", 10)), 50)
        force_refresh = request.args.get("refresh", "false").lower() == "true"

        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get job
            job = c.execute(
                "SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404

            j = dict(job)
            job_category = j["category"]
            job_reward = j["reward_rtc"]

            # Check cache (rate-limited: 1 update per hour per job)
            now = int(time.time())
            if not force_refresh:
                cached = c.execute(
                    "SELECT cached_at, results_json FROM agent_match_cache WHERE job_id = ?",
                    (job_id,)
                ).fetchone()
                if cached and (now - cached["cached_at"]) < 3600:
                    results = json.loads(cached["results_json"])
                    return jsonify({
                        "ok": True,
                        "job_id": job_id,
                        "cached": True,
                        "cached_at": cached["cached_at"],
                        "workers": results[:limit],
                        "total": len(results)
                    })

            # Get eligible workers: those who viewed the job OR
            # workers who have ANY completed jobs in the job's category
            # (exclude the poster and already-claimed workers)
            potential_workers = c.execute("""
                SELECT DISTINCT aw.wallet_id
                FROM agent_job_views awv
                JOIN agent_reputation aw ON awv.wallet_id = aw.wallet_id
                WHERE awv.job_id = ? AND awv.wallet_id != ?
                UNION
                SELECT DISTINCT worker_wallet
                FROM agent_jobs
                WHERE category = ? AND status = 'completed'
                  AND worker_wallet != ?
                  AND completed_at > ?
            """, (job_id, j["poster_wallet"], job_category,
                  j["poster_wallet"], now - RECENCY_WINDOW_SECS)).fetchall()

            # If no views and no category workers, use globally active workers
            if not potential_workers:
                potential_workers = c.execute("""
                    SELECT DISTINCT worker_wallet
                    FROM agent_jobs
                    WHERE status = 'completed'
                      AND worker_wallet != ?
                      AND worker_wallet IS NOT NULL
                      AND last_active > ?
                    LIMIT 100
                """, (j["poster_wallet"], now - RECENCY_WINDOW_SECS)).fetchall()

            # Score each worker
            scored = []
            for row in potential_workers:
                wallet = row[0]
                if not wallet:
                    continue
                score_info = _compute_match_score(c, wallet, job_category, job_reward)
                scored.append(score_info)

            # Sort by total_score descending
            scored.sort(key=lambda x: x["total_score"], reverse=True)

            # Cache results
            c.execute("""
                INSERT OR REPLACE INTO agent_match_cache
                (job_id, cached_at, results_json)
                VALUES (?, ?, ?)
            """, (job_id, now, json.dumps(scored)))
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "job_title": j["title"],
                "category": job_category,
                "reward_rtc": job_reward,
                "cached": False,
                "workers": scored[:limit],
                "total_candidates": len(scored)
            })

        except Exception as e:
            log.error(f"agent_match_job error: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # ─── POST /agent/match/<job_id>/view ──── Record a worker viewing a job ─────────────
    @app.route("/agent/match/<job_id>/view", methods=["POST"])
    def agent_match_view(job_id: str):
        """Record that a worker viewed a job (helps improve match quality)."""
        data = request.get_json(silent=True) or {}
        wallet = str(data.get("worker_wallet", "")).strip()
        if not wallet:
            return jsonify({"error": "worker_wallet required"}), 400

        now = int(time.time())
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            job = c.execute(
                "SELECT poster_wallet FROM agent_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job[0] == wallet:
                return jsonify({"error": "Posters cannot record views for own job"}), 400

            c.execute("""
                INSERT OR REPLACE INTO agent_job_views (wallet_id, job_id, viewed_at)
                VALUES (?, ?, ?)
            """, (wallet, job_id, now))
            conn.commit()

        return jsonify({"ok": True, "job_id": job_id, "wallet_id": wallet})

    # ─── GET /agent/match/suggest ──── Best-fit open jobs for a worker ─────────────────
    @app.route("/agent/match/suggest", methods=["GET"])
    def agent_match_suggest():
        """Suggest best-fit open jobs for a given worker wallet."""
        wallet = request.args.get("wallet", "").strip()
        limit = min(int(request.args.get("limit", 10)), 50)

        if not wallet:
            return jsonify({"error": "wallet required (query param: ?wallet=...)"}), 400

        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Sync category stats for this worker
            _sync_category_stats(c, wallet)

            # Get all open jobs
            now = int(time.time())
            open_jobs = c.execute("""
                SELECT job_id, poster_wallet, title, category, reward_rtc,
                       expires_at, created_at, tags
                FROM agent_jobs
                WHERE status = 'open' AND expires_at > ?
                ORDER BY reward_rtc DESC
            """, (now,)).fetchall()

            # Score each job for this worker
            scored = []
            for row in open_jobs:
                j = dict(row)
                score_info = _compute_match_score(
                    c, wallet, j["category"], j["reward_rtc"]
                )
                score_info["job_id"] = j["job_id"]
                score_info["job_title"] = j["title"]
                score_info["job_reward"] = j["reward_rtc"]
                score_info["expires_at"] = j["expires_at"]
                score_info["days_left"] = max(0, round((j["expires_at"] - now) / 86400, 1))
                # Remove redundant keys
                for k in ["wallet_id", "category", "total_jobs", "category_jobs"]:
                    score_info.pop(k, None)
                scored.append(score_info)

            # Sort by total_score descending
            scored.sort(key=lambda x: x["total_score"], reverse=True)

            return jsonify({
                "ok": True,
                "wallet_id": wallet,
                "suggestions": scored[:limit],
                "total_open_jobs": len(open_jobs)
            })

        except Exception as e:
            log.error(f"agent_match_suggest error: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # ─── GET /agent/match/leaderboard ──── Top workers per category ────────────────────
    @app.route("/agent/match/leaderboard", methods=["GET"])
    def agent_match_leaderboard():
        """Return top-ranked workers per category."""
        category = request.args.get("category", "").strip().lower()
        limit = min(int(request.args.get("limit", 20)), 100)
        period_days = min(int(request.args.get("days", 30)), 365)

        if category and category not in ("research", "code", "video", "audio",
                                         "writing", "translation", "data",
                                         "design", "testing", "other"):
            return jsonify({"error": "Invalid category"}), 400

        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            now = int(time.time())
            cutoff = now - (period_days * 86400)

            if category:
                # Sync category stats for all workers
                wallets = [r[0] for r in c.execute(
                    "SELECT DISTINCT wallet_id FROM agent_category_stats WHERE category = ?",
                    (category,)).fetchall()]
                for w in wallets:
                    _sync_category_stats(c, w)

                rows = c.execute("""
                    SELECT acs.*,
                           COALESCE(ar.avg_rating, 0) AS global_avg_rating
                    FROM agent_category_stats acs
                    LEFT JOIN agent_reputation ar ON ar.wallet_id = acs.wallet_id
                    WHERE acs.category = ?
                      AND acs.updated_at > ?
                    ORDER BY
                        (acs.completed * 1.0 / NULLIF(acs.jobs_in_cat, 0)) DESC,
                        acs.avg_rating DESC
                    LIMIT ?
                """, (category, cutoff, limit)).fetchall()

                results = []
                for rank, row in enumerate(rows, 1):
                    r = dict(row)
                    total = r["jobs_in_cat"]
                    completed = r["completed"]
                    if total == 0:
                        cat_score = 50
                    else:
                        success = completed / total
                        cat_score = min(100, int(success * 100 * CATEGORY_WEIGHTS.get(category, 1.0)))
                    results.append({
                        "rank": rank,
                        "wallet_id": r["wallet_id"],
                        "category": r["category"],
                        "category_score": cat_score,
                        "jobs_in_category": total,
                        "completed_in_category": completed,
                        "disputed_in_category": r["disputed"],
                        "total_earned_in_category": round(r["total_earned"], 4),
                        "avg_rating": round(r["avg_rating"] or 0, 2),
                        "global_avg_rating": round(r["global_avg_rating"] or 0, 2),
                    })
            else:
                # Global leaderboard across all categories
                rows = c.execute("""
                    SELECT ar.*,
                           COALESCE(SUM(acs.completed), 0) AS total_cat_completed
                    FROM agent_reputation ar
                    LEFT JOIN agent_category_stats acs ON ar.wallet_id = acs.wallet_id
                    WHERE ar.last_active > ?
                    GROUP BY ar.wallet_id
                    ORDER BY ar.avg_rating DESC,
                             ar.jobs_completed_as_worker DESC
                    LIMIT ?
                """, (cutoff, limit)).fetchall()

                results = []
                for rank, row in enumerate(rows, 1):
                    r = dict(row)
                    total = (r.get("jobs_completed_as_worker", 0) +
                              r.get("jobs_completed_as_poster", 0) +
                              r.get("jobs_disputed", 0) +
                              r.get("jobs_expired", 0))
                    success_rate = r.get("jobs_completed_as_worker", 0) / total if total > 0 else 0
                    trust_score = min(100, int(success_rate * 100))
                    results.append({
                        "rank": rank,
                        "wallet_id": r["wallet_id"],
                        "trust_score": trust_score,
                        "jobs_completed": r["jobs_completed_as_worker"],
                        "jobs_disputed": r.get("jobs_disputed", 0),
                        "total_earned": round(r.get("total_rtc_earned", 0), 4),
                        "avg_rating": round(r.get("avg_rating", 0) or 0, 2),
                        "last_active": r["last_active"],
                    })

            return jsonify({
                "ok": True,
                "category": category or "global",
                "period_days": period_days,
                "leaderboard": results
            })

        except Exception as e:
            log.error(f"agent_match_leaderboard error: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # ─── GET /agent/match/stats ──── Auto-match engine health stats ────────────────────
    @app.route("/agent/match/stats", methods=["GET"])
    def agent_match_stats():
        """Return auto-match engine health and cache stats."""
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            now = int(time.time())
            stats = {}
            stats["total_cached_jobs"] = c.execute(
                "SELECT COUNT(*) FROM agent_match_cache"
            ).fetchone()[0]
            stats["cache_freshness"] = c.execute("""
                SELECT COUNT(*), AVG(? - cached_at)
                FROM agent_match_cache
            """, (now,)).fetchone()[1]
            stats["total_job_views"] = c.execute(
                "SELECT COUNT(*) FROM agent_job_views"
            ).fetchone()[0]
            stats["active_categorized_workers"] = c.execute(
                "SELECT COUNT(DISTINCT wallet_id) FROM agent_category_stats"
            ).fetchone()[0]
            stats["category_breakdown"] = [
                {"category": r[0], "workers": r[1]}
                for r in c.execute("""
                    SELECT category, COUNT(DISTINCT wallet_id)
                    FROM agent_category_stats
                    GROUP BY category ORDER BY workers DESC
                """).fetchall()
            ]

            return jsonify({"ok": True, "match_stats": stats})

        finally:
            conn.close()

    log.info("RIP-302 Auto-Match endpoints registered: " +
             "/agent/match/<job_id>, /agent/match/suggest, " +
             "/agent/match/leaderboard, /agent/match/stats")
