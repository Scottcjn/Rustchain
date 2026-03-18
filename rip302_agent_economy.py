"""
RIP-302: Agent-to-Agent RTC Economy
====================================
Transforms RTC from mining reward token into native currency for
autonomous agent-to-agent job marketplace.

Phases:
  1. Agent Wallets & Job Posting      (this file)
  2. Escrow & Delivery                (this file)
  3. Reputation & Discovery           (this file)
  4. Autonomous Pipelines             (future)

Economics:
  - 5% platform fee on job payments → founder_community
  - Jobs are escrowed: poster locks RTC when posting
  - Escrow released to worker on delivery acceptance
  - Timeout: escrow returns to poster after TTL (default 7 days)
  - Disputes: admin can void/refund

Author: Elyan Labs / Scott Boudreaux
Date: 2026-03-05
"""

import hashlib
import json
import logging
import sqlite3
import time
from flask import Flask, request, jsonify

log = logging.getLogger("rip302")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLATFORM_FEE_RATE = 0.05        # 5% platform fee
PLATFORM_FEE_WALLET = "founder_community"
JOB_TTL_DEFAULT = 7 * 86400    # 7 days default TTL
JOB_TTL_MAX = 30 * 86400       # 30 days max TTL
MAX_ACTIVE_JOBS_PER_AGENT = 20  # prevent spam
ESCROW_WALLET = "agent_escrow"  # internal escrow holding wallet

# Job statuses
STATUS_OPEN = "open"            # Posted, accepting claims
STATUS_CLAIMED = "claimed"      # Worker assigned
STATUS_DELIVERED = "delivered"   # Worker submitted result
STATUS_COMPLETED = "completed"  # Poster accepted delivery
STATUS_DISPUTED = "disputed"    # Poster rejected delivery
STATUS_EXPIRED = "expired"      # TTL passed without completion
STATUS_CANCELLED = "cancelled"  # Poster cancelled before claim

VALID_CATEGORIES = [
    "research", "code", "video", "audio", "writing",
    "translation", "data", "design", "testing", "other"
]


# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

def init_agent_economy_tables(db_path: str):
    """Create agent economy tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # Jobs marketplace
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_jobs (
                job_id TEXT PRIMARY KEY,
                poster_wallet TEXT NOT NULL,
                worker_wallet TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT DEFAULT 'other',
                reward_rtc REAL NOT NULL,
                reward_i64 INTEGER NOT NULL,
                escrow_i64 INTEGER NOT NULL,
                platform_fee_i64 INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                deliverable_url TEXT,
                deliverable_hash TEXT,
                result_summary TEXT,
                rejection_reason TEXT,
                created_at INTEGER NOT NULL,
                claimed_at INTEGER,
                delivered_at INTEGER,
                completed_at INTEGER,
                expires_at INTEGER NOT NULL,
                tags TEXT DEFAULT '[]'
            )
        """)

        # Agent reputation scores
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_reputation (
                wallet_id TEXT PRIMARY KEY,
                jobs_posted INTEGER DEFAULT 0,
                jobs_completed_as_poster INTEGER DEFAULT 0,
                jobs_completed_as_worker INTEGER DEFAULT 0,
                jobs_disputed INTEGER DEFAULT 0,
                jobs_expired INTEGER DEFAULT 0,
                total_rtc_paid REAL DEFAULT 0,
                total_rtc_earned REAL DEFAULT 0,
                avg_rating REAL DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                first_seen INTEGER,
                last_active INTEGER
            )
        """)

        # Job ratings (poster rates worker, worker rates poster)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                rater_wallet TEXT NOT NULL,
                ratee_wallet TEXT NOT NULL,
                role TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at INTEGER NOT NULL,
                UNIQUE(job_id, rater_wallet)
            )
        """)

        # Job activity log
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_job_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_wallet TEXT,
                details TEXT,
                created_at INTEGER NOT NULL
            )
        """)

        conn.commit()
    log.info("RIP-302 Agent Economy tables initialized")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_job_id(poster: str, title: str) -> str:
    """Deterministic job ID from poster + title + timestamp."""
    seed = f"{poster}:{title}:{time.time()}:{id(poster)}"
    return "job_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def _get_balance_i64(c: sqlite3.Cursor, wallet_id: str) -> int:
    """Get wallet balance in micro-units."""
    try:
        row = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?",
                        (wallet_id,)).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    # Legacy fallback
    for col, key in (("balance_rtc", "miner_pk"), ("balance_rtc", "miner_id")):
        try:
            row = c.execute(f"SELECT {col} FROM balances WHERE {key} = ?",
                            (wallet_id,)).fetchone()
            if row and row[0] is not None:
                return int(round(float(row[0]) * 1000000))
        except Exception:
            continue
    return 0


def _adjust_balance(c: sqlite3.Cursor, wallet_id: str, delta_i64: int):
    """Adjust wallet balance by delta (positive = credit, negative = debit)."""
    current = _get_balance_i64(c, wallet_id)
    new_balance = current + delta_i64
    c.execute("""
        INSERT INTO balances (miner_id, amount_i64)
        VALUES (?, ?)
        ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = ?
    """, (wallet_id, new_balance, new_balance))


def _log_job_action(c: sqlite3.Cursor, job_id: str, action: str,
                    actor: str = None, details: str = None):
    """Record job activity."""
    c.execute("""
        INSERT INTO agent_job_log (job_id, action, actor_wallet, details, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, action, actor, details, int(time.time())))


def _update_reputation(c: sqlite3.Cursor, wallet_id: str, field: str,
                       increment: int = 1):
    """Increment a reputation field for an agent."""
    now = int(time.time())
    c.execute("""
        INSERT INTO agent_reputation (wallet_id, first_seen, last_active)
        VALUES (?, ?, ?)
        ON CONFLICT(wallet_id) DO UPDATE SET last_active = ?
    """, (wallet_id, now, now, now))
    c.execute(f"""
        UPDATE agent_reputation SET {field} = {field} + ? WHERE wallet_id = ?
    """, (increment, wallet_id))


def _get_client_ip():
    """Get real client IP (trust nginx X-Real-IP only)."""
    return request.headers.get("X-Real-IP", request.remote_addr)


# ---------------------------------------------------------------------------
# Route Registration
# ---------------------------------------------------------------------------

def register_agent_economy(app: Flask, db_path: str):
    """Register all RIP-302 Agent Economy routes."""

    init_agent_economy_tables(db_path)

    # -----------------------------------------------------------------------
    # POST /agent/jobs — Create a new job (locks escrow)
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs", methods=["POST"])
    def agent_post_job():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        poster = str(data.get("poster_wallet", "")).strip()
        title = str(data.get("title", "")).strip()
        description = str(data.get("description", "")).strip()
        category = str(data.get("category", "other")).strip().lower()
        reward_rtc = data.get("reward_rtc", 0)
        ttl_seconds = int(data.get("ttl_seconds", JOB_TTL_DEFAULT))
        tags = data.get("tags", [])

        # Validation
        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400
        if not title or len(title) < 5:
            return jsonify({"error": "title must be at least 5 characters"}), 400
        if not description or len(description) < 20:
            return jsonify({"error": "description must be at least 20 characters"}), 400
        if category not in VALID_CATEGORIES:
            return jsonify({"error": f"category must be one of: {VALID_CATEGORIES}"}), 400

        try:
            reward_rtc = float(reward_rtc)
        except (TypeError, ValueError):
            return jsonify({"error": "reward_rtc must be a number"}), 400

        if reward_rtc < 0.01:
            return jsonify({"error": "Minimum reward is 0.01 RTC"}), 400
        if reward_rtc > 10000:
            return jsonify({"error": "Maximum reward is 10,000 RTC"}), 400

        ttl_seconds = min(max(ttl_seconds, 3600), JOB_TTL_MAX)  # 1h to 30d

        reward_i64 = int(reward_rtc * 1000000)
        platform_fee_i64 = int(reward_i64 * PLATFORM_FEE_RATE)
        escrow_i64 = reward_i64 + platform_fee_i64  # poster pays reward + fee

        now = int(time.time())
        job_id = _generate_job_id(poster, title)

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()

            # Check poster balance
            poster_balance = _get_balance_i64(c, poster)
            if poster_balance < escrow_i64:
                return jsonify({
                    "error": "Insufficient balance for escrow",
                    "balance_rtc": poster_balance / 1000000,
                    "escrow_required_rtc": escrow_i64 / 1000000,
                    "reward_rtc": reward_rtc,
                    "platform_fee_rtc": platform_fee_i64 / 1000000,
                    "hint": "Total escrow = reward + 5% platform fee"
                }), 400

            # Check active job limit
            active_count = c.execute("""
                SELECT COUNT(*) FROM agent_jobs
                WHERE poster_wallet = ? AND status IN ('open', 'claimed', 'delivered')
            """, (poster,)).fetchone()[0]

            if active_count >= MAX_ACTIVE_JOBS_PER_AGENT:
                return jsonify({
                    "error": f"Maximum {MAX_ACTIVE_JOBS_PER_AGENT} active jobs per agent",
                    "active_jobs": active_count
                }), 429

            # Lock escrow: debit poster, credit escrow wallet
            _adjust_balance(c, poster, -escrow_i64)
            _adjust_balance(c, ESCROW_WALLET, escrow_i64)

            # Create job
            c.execute("""
                INSERT INTO agent_jobs
                (job_id, poster_wallet, title, description, category,
                 reward_rtc, reward_i64, escrow_i64, platform_fee_i64,
                 status, created_at, expires_at, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
            """, (job_id, poster, title, description, category,
                  reward_rtc, reward_i64, escrow_i64, platform_fee_i64,
                  now, now + ttl_seconds, json.dumps(tags)))

            _log_job_action(c, job_id, "posted", poster,
                           f"reward={reward_rtc} RTC, escrow={escrow_i64/1000000} RTC")
            _update_reputation(c, poster, "jobs_posted")

            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_OPEN,
                "poster_wallet": poster,
                "reward_rtc": reward_rtc,
                "platform_fee_rtc": platform_fee_i64 / 1000000,
                "escrow_total_rtc": escrow_i64 / 1000000,
                "expires_at": now + ttl_seconds,
                "expires_in_hours": ttl_seconds / 3600,
                "message": f"Job posted! {escrow_i64/1000000} RTC locked in escrow."
            }), 201

        except Exception as e:
            conn.rollback()
            log.error(f"agent_post_job error: {e}")
            return jsonify({"error": "Internal error", "details": str(e)}), 500
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/claim — Claim a job
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/claim", methods=["POST"])
    def agent_claim_job(job_id):
        data = request.get_json(silent=True) or {}
        worker = str(data.get("worker_wallet", "")).strip()

        if not worker:
            return jsonify({"error": "worker_wallet required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()

            job = c.execute("SELECT * FROM agent_jobs WHERE job_id = ?",
                           (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404

            # Map columns
            cols = [d[0] for d in c.description]
            j = dict(zip(cols, job))

            if j["status"] != STATUS_OPEN:
                return jsonify({
                    "error": f"Job is not open (status: {j['status']})"
                }), 409

            if j["poster_wallet"] == worker:
                return jsonify({"error": "Cannot claim your own job"}), 400

            now = int(time.time())
            if now > j["expires_at"]:
                # Auto-expire
                c.execute("UPDATE agent_jobs SET status = 'expired' WHERE job_id = ?",
                         (job_id,))
                _refund_escrow(c, j)
                conn.commit()
                return jsonify({"error": "Job has expired"}), 410

            # Claim it
            c.execute("""
                UPDATE agent_jobs
                SET worker_wallet = ?, status = 'claimed', claimed_at = ?
                WHERE job_id = ? AND status = 'open'
            """, (worker, now, job_id))

            if c.execute("SELECT changes()").fetchone()[0] == 0:
                return jsonify({"error": "Job was claimed by another worker"}), 409

            _log_job_action(c, job_id, "claimed", worker)
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_CLAIMED,
                "worker_wallet": worker,
                "reward_rtc": j["reward_rtc"],
                "expires_at": j["expires_at"],
                "message": "Job claimed! Submit your deliverable when ready."
            })

        except Exception as e:
            conn.rollback()
            log.error(f"agent_claim_job error: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/deliver — Submit deliverable
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/deliver", methods=["POST"])
    def agent_deliver_job(job_id):
        data = request.get_json(silent=True) or {}
        worker = str(data.get("worker_wallet", "")).strip()
        deliverable_url = str(data.get("deliverable_url", "")).strip()
        deliverable_hash = str(data.get("deliverable_hash", "")).strip()
        result_summary = str(data.get("result_summary", "")).strip()

        if not worker:
            return jsonify({"error": "worker_wallet required"}), 400
        if not deliverable_url and not result_summary:
            return jsonify({"error": "deliverable_url or result_summary required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["status"] != STATUS_CLAIMED:
                return jsonify({"error": f"Job must be in 'claimed' status (current: {j['status']})"}), 409

            if j["worker_wallet"] != worker:
                return jsonify({"error": "Only the assigned worker can deliver"}), 403

            now = int(time.time())
            c.execute("""
                UPDATE agent_jobs
                SET status = 'delivered', deliverable_url = ?,
                    deliverable_hash = ?, result_summary = ?, delivered_at = ?
                WHERE job_id = ?
            """, (deliverable_url, deliverable_hash, result_summary, now, job_id))

            _log_job_action(c, job_id, "delivered", worker,
                           f"url={deliverable_url}")
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_DELIVERED,
                "message": "Deliverable submitted! Waiting for poster to accept."
            })

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/accept — Accept delivery (releases escrow)
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/accept", methods=["POST"])
    def agent_accept_delivery(job_id):
        data = request.get_json(silent=True) or {}
        poster = str(data.get("poster_wallet", "")).strip()
        rating = data.get("rating")  # 1-5 optional

        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["status"] != STATUS_DELIVERED:
                return jsonify({"error": f"Job must be in 'delivered' status (current: {j['status']})"}), 409

            if j["poster_wallet"] != poster:
                return jsonify({"error": "Only the poster can accept delivery"}), 403

            now = int(time.time())
            worker = j["worker_wallet"]
            reward_i64 = j["reward_i64"]
            fee_i64 = j["platform_fee_i64"]
            escrow_i64 = j["escrow_i64"]

            # Release escrow: pay worker + platform fee
            _adjust_balance(c, ESCROW_WALLET, -escrow_i64)
            _adjust_balance(c, worker, reward_i64)
            _adjust_balance(c, PLATFORM_FEE_WALLET, fee_i64)

            c.execute("""
                UPDATE agent_jobs
                SET status = 'completed', completed_at = ?
                WHERE job_id = ?
            """, (now, job_id))

            # Update reputation
            _update_reputation(c, poster, "jobs_completed_as_poster")
            _update_reputation(c, worker, "jobs_completed_as_worker")
            c.execute("""
                UPDATE agent_reputation
                SET total_rtc_paid = total_rtc_paid + ?
                WHERE wallet_id = ?
            """, (j["reward_rtc"], poster))
            c.execute("""
                UPDATE agent_reputation
                SET total_rtc_earned = total_rtc_earned + ?
                WHERE wallet_id = ?
            """, (j["reward_rtc"], worker))

            # Optional rating
            if rating is not None:
                try:
                    rating = max(1, min(5, int(rating)))
                    c.execute("""
                        INSERT INTO agent_ratings
                        (job_id, rater_wallet, ratee_wallet, role, rating, created_at)
                        VALUES (?, ?, ?, 'poster_rates_worker', ?, ?)
                    """, (job_id, poster, worker, rating, now))
                    # Update average
                    avg = c.execute("""
                        SELECT AVG(rating), COUNT(*) FROM agent_ratings
                        WHERE ratee_wallet = ?
                    """, (worker,)).fetchone()
                    if avg[0]:
                        c.execute("""
                            UPDATE agent_reputation
                            SET avg_rating = ?, rating_count = ?
                            WHERE wallet_id = ?
                        """, (round(avg[0], 2), avg[1], worker))
                except (TypeError, ValueError):
                    pass  # Skip bad rating silently

            _log_job_action(c, job_id, "completed", poster,
                           f"worker={worker}, reward={j['reward_rtc']} RTC, fee={fee_i64/1000000} RTC")
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_COMPLETED,
                "worker_wallet": worker,
                "reward_paid_rtc": reward_i64 / 1000000,
                "platform_fee_rtc": fee_i64 / 1000000,
                "message": f"Job complete! {reward_i64/1000000} RTC paid to {worker}."
            })

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/dispute — Reject delivery
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/dispute", methods=["POST"])
    def agent_dispute_job(job_id):
        data = request.get_json(silent=True) or {}
        poster = str(data.get("poster_wallet", "")).strip()
        reason = str(data.get("reason", "")).strip()

        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400
        if not reason:
            return jsonify({"error": "reason required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["status"] != STATUS_DELIVERED:
                return jsonify({"error": f"Can only dispute delivered jobs (current: {j['status']})"}), 409

            if j["poster_wallet"] != poster:
                return jsonify({"error": "Only the poster can dispute"}), 403

            now = int(time.time())
            c.execute("""
                UPDATE agent_jobs
                SET status = 'disputed', rejection_reason = ?
                WHERE job_id = ?
            """, (reason[:500], job_id))

            _update_reputation(c, j["worker_wallet"], "jobs_disputed")
            _log_job_action(c, job_id, "disputed", poster, reason[:200])
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_DISPUTED,
                "message": "Job disputed. Escrow held pending resolution. Worker can re-deliver or admin can refund."
            })

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/cancel — Cancel open job (refund escrow)
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/cancel", methods=["POST"])
    def agent_cancel_job(job_id):
        data = request.get_json(silent=True) or {}
        poster = str(data.get("poster_wallet", "")).strip()

        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["poster_wallet"] != poster:
                return jsonify({"error": "Only the poster can cancel"}), 403

            if j["status"] not in (STATUS_OPEN, STATUS_DISPUTED):
                return jsonify({
                    "error": f"Can only cancel open or disputed jobs (current: {j['status']})"
                }), 409

            # Refund escrow to poster
            _refund_escrow(c, j)

            c.execute("UPDATE agent_jobs SET status = 'cancelled' WHERE job_id = ?",
                     (job_id,))
            _log_job_action(c, job_id, "cancelled", poster)
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_CANCELLED,
                "refunded_rtc": j["escrow_i64"] / 1000000,
                "message": "Job cancelled. Escrow refunded."
            })

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # GET /agent/jobs — Browse open jobs
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs", methods=["GET"])
    def agent_list_jobs():
        category = request.args.get("category", "").strip().lower()
        status_filter = request.args.get("status", STATUS_OPEN).strip().lower()
        limit = min(int(request.args.get("limit", 50)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
        min_reward = float(request.args.get("min_reward", 0))

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Expire old jobs first
            now = int(time.time())
            expired = c.execute("""
                SELECT job_id, poster_wallet, escrow_i64, platform_fee_i64, reward_i64
                FROM agent_jobs
                WHERE status = 'open' AND expires_at < ?
            """, (now,)).fetchall()
            for ej in expired:
                _adjust_balance(c, ESCROW_WALLET, -ej["escrow_i64"])
                _adjust_balance(c, ej["poster_wallet"], ej["escrow_i64"])
                c.execute("UPDATE agent_jobs SET status = 'expired' WHERE job_id = ?",
                         (ej["job_id"],))
                _update_reputation(c, ej["poster_wallet"], "jobs_expired")
            if expired:
                conn.commit()

            # Build query
            where = ["status = ?", "reward_rtc >= ?"]
            params = [status_filter, min_reward]

            if category and category in VALID_CATEGORIES:
                where.append("category = ?")
                params.append(category)

            query = f"""
                SELECT job_id, poster_wallet, title, description, category,
                       reward_rtc, status, created_at, expires_at, tags,
                       worker_wallet
                FROM agent_jobs
                WHERE {' AND '.join(where)}
                ORDER BY reward_rtc DESC, created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            jobs = [dict(row) for row in c.execute(query, params).fetchall()]

            # Get total count
            count_query = f"SELECT COUNT(*) FROM agent_jobs WHERE {' AND '.join(where)}"
            total = c.execute(count_query, params[:-2]).fetchone()[0]

            return jsonify({
                "ok": True,
                "jobs": jobs,
                "total": total,
                "limit": limit,
                "offset": offset,
                "categories": VALID_CATEGORIES
            })

    # -----------------------------------------------------------------------
    # GET /agent/jobs/<job_id> — Job details
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>", methods=["GET"])
    def agent_get_job(job_id):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            job = c.execute("SELECT * FROM agent_jobs WHERE job_id = ?",
                           (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404

            j = dict(job)

            # Get activity log
            log_rows = c.execute("""
                SELECT action, actor_wallet, details, created_at
                FROM agent_job_log WHERE job_id = ?
                ORDER BY created_at ASC
            """, (job_id,)).fetchall()
            j["activity_log"] = [dict(r) for r in log_rows]

            # Get ratings
            ratings = c.execute("""
                SELECT rater_wallet, ratee_wallet, role, rating, comment, created_at
                FROM agent_ratings WHERE job_id = ?
            """, (job_id,)).fetchall()
            j["ratings"] = [dict(r) for r in ratings]

            return jsonify({"ok": True, "job": j})

    # -----------------------------------------------------------------------
    # GET /agent/reputation/<wallet_id> — Agent reputation
    # -----------------------------------------------------------------------
    @app.route("/agent/reputation/<wallet_id>", methods=["GET"])
    def agent_reputation(wallet_id):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            rep = c.execute("SELECT * FROM agent_reputation WHERE wallet_id = ?",
                           (wallet_id,)).fetchone()
            if not rep:
                return jsonify({
                    "ok": True,
                    "wallet_id": wallet_id,
                    "reputation": None,
                    "message": "No reputation history"
                })

            r = dict(rep)

            # Compute trust score (0-100)
            completed = r["jobs_completed_as_worker"] + r["jobs_completed_as_poster"]
            disputed = r["jobs_disputed"]
            expired = r["jobs_expired"]
            total = completed + disputed + expired

            if total == 0:
                trust_score = 50  # Neutral for new agents
            else:
                success_rate = completed / total
                trust_score = int(min(100, max(0,
                    success_rate * 80 +
                    min(r["avg_rating"] / 5 * 20, 20) if r["rating_count"] > 0 else 10
                )))

            r["trust_score"] = trust_score
            r["trust_level"] = (
                "legendary" if trust_score >= 90 else
                "trusted" if trust_score >= 70 else
                "neutral" if trust_score >= 40 else
                "risky"
            )

            return jsonify({"ok": True, "wallet_id": wallet_id, "reputation": r})

    # -----------------------------------------------------------------------
    # GET /agent/stats — Marketplace stats
    # -----------------------------------------------------------------------
    @app.route("/agent/stats", methods=["GET"])
    def agent_stats():
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()

            stats = {}
            stats["total_jobs"] = c.execute("SELECT COUNT(*) FROM agent_jobs").fetchone()[0]
            stats["open_jobs"] = c.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE status = 'open'").fetchone()[0]
            stats["completed_jobs"] = c.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE status = 'completed'").fetchone()[0]
            stats["total_rtc_volume"] = c.execute(
                "SELECT COALESCE(SUM(reward_rtc), 0) FROM agent_jobs WHERE status = 'completed'"
            ).fetchone()[0]
            stats["total_fees_collected"] = c.execute(
                "SELECT COALESCE(SUM(platform_fee_i64), 0) FROM agent_jobs WHERE status = 'completed'"
            ).fetchone()[0] / 1000000
            stats["active_agents"] = c.execute(
                "SELECT COUNT(*) FROM agent_reputation WHERE last_active > ?",
                (int(time.time()) - 7 * 86400,)).fetchone()[0]
            stats["platform_fee_rate"] = f"{PLATFORM_FEE_RATE * 100}%"
            stats["escrow_wallet"] = ESCROW_WALLET
            stats["escrow_balance_rtc"] = _get_balance_i64(c, ESCROW_WALLET) / 1000000

            # Top categories
            cats = c.execute("""
                SELECT category, COUNT(*) as cnt, SUM(reward_rtc) as total_rtc
                FROM agent_jobs GROUP BY category ORDER BY cnt DESC
            """).fetchall()
            stats["categories"] = [
                {"category": r[0], "jobs": r[1], "total_rtc": r[2]} for r in cats
            ]

            return jsonify({"ok": True, "stats": stats})

    # -----------------------------------------------------------------------
    # Internal: Refund escrow to poster
    # -----------------------------------------------------------------------
    def _refund_escrow(c: sqlite3.Cursor, job: dict):
        """Return escrowed funds to the poster."""
        escrow_i64 = job["escrow_i64"]
        poster = job["poster_wallet"]
        _adjust_balance(c, ESCROW_WALLET, -escrow_i64)
        _adjust_balance(c, poster, escrow_i64)
        _log_job_action(c, job["job_id"], "escrow_refunded", poster,
                       f"refunded {escrow_i64/1000000} RTC")

    log.info("RIP-302 Agent Economy endpoints registered: "
             "/agent/jobs, /agent/reputation, /agent/stats")

    # ── RIP-302 Multi-Step Pipeline Extension ──────────────────────────
    # Bounty: #683 Tier 3 (100 RTC)
    # Author: kuanglaodi2-sudo (OpenClaw Agent)

    import hashlib, json as _json

    _PFR = 0.05
    _PFW = "founder_community"
    _EW  = "agent_escrow"

    def _pg_bal(c, w):
        try:
            r = c.execute("SELECT amount_i64 FROM balances WHERE miner_id=?",(w,)).fetchone()
            if r and r[0] is not None: return int(r[0])
        except: pass
        for col,key in [("balance_rtc","miner_pk"),("balance_rtc","miner_id")]:
            try:
                r = c.execute(f"SELECT {col} FROM balances WHERE {key}=?",(w,)).fetchone()
                if r and r[0] is not None: return int(round(float(r[0])*1000000))
            except: continue
        return 0

    def _pg_adj(c, w, d):
        n = _pg_bal(c,w) + d
        c.execute("INSERT INTO balances(miner_id,amount_i64) VALUES(?,?) ON CONFLICT(miner_id) DO UPDATE SET amount_i64=? WHERE miner_id=?",(w,n,n,w))

    def _pg_log(c, jid, act, act2="", det=""):
        c.execute("INSERT INTO agent_job_log(job_id,action,actor_wallet,details,created_at) VALUES(?,?,?,?,?)",(jid,act,act2,det,int(__import__('time').time())))

    def _init_pg(db):
        c = db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS agent_pipelines(
            pipeline_id TEXT PRIMARY KEY, poster_wallet TEXT NOT NULL,
            title TEXT NOT NULL, description TEXT, status TEXT DEFAULT 'active',
            total_reward_rtc REAL NOT NULL, total_reward_i64 INTEGER NOT NULL,
            total_fee_i64 INTEGER NOT NULL, total_escrow_i64 INTEGER NOT NULL,
            escrow_funded INTEGER DEFAULT 0, created_at INTEGER NOT NULL,
            completed_at INTEGER, completed_step_index INTEGER DEFAULT -1)""")
        c.execute("""CREATE TABLE IF NOT EXISTS agent_pipeline_steps(
            id INTEGER PRIMARY KEY AUTOINCREMENT, pipeline_id TEXT NOT NULL,
            step_index INTEGER NOT NULL, job_id TEXT, title TEXT NOT NULL,
            description TEXT, category TEXT DEFAULT 'other',
            reward_rtc REAL NOT NULL, reward_i64 INTEGER NOT NULL,
            fee_i64 INTEGER NOT NULL, escrow_i64 INTEGER NOT NULL,
            status TEXT DEFAULT 'pending', worker_wallet TEXT,
            deliverable_url TEXT, result_summary TEXT,
            created_at INTEGER NOT NULL, claimed_at INTEGER,
            delivered_at INTEGER, completed_at INTEGER,
            UNIQUE(pipeline_id,step_index))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pg_s ON agent_pipeline_steps(pipeline_id,step_index)")
        db.commit()

    _init_pg(sqlite3.connect(db_path))

    @app.route("/agent/pipelines",methods=["POST"])
    def agent_create_pipeline():
        d=request.get_json(silent=True) or {}
        p=str(d.get("poster_wallet","")).strip()
        t=str(d.get("title","")).strip()
        desc=str(d.get("description","")).strip()
        steps=d.get("steps",[])
        if not p: return jsonify({"error":"poster_wallet required"}),400
        if not t or len(t)<5: return jsonify({"error":"title must be at least 5 chars"}),400
        if not isinstance(steps,list) or len(steps)<2: return jsonify({"error":"At least 2 steps required"}),400
        now=int(__import__('time').time())
        pid="pipe_"+hashlib.sha256(f"{p}:{t}:{now}".encode()).hexdigest()[:16]
        tot=0; sout=[]
        for i,s in enumerate(steps):
            try: r=float(s.get("reward_rtc",0))
            except: return jsonify({"error":f"Step {i} bad reward"}),400
            if r<0.01: return jsonify({"error":f"Step {i} min 0.01 RTC"}),400
            ri=int(r*1000000); fi=int(ri*_PFR); ei=ri+fi; tot+=ri
            sout.append({"title":str(s.get("title","")).strip(),"desc":str(s.get("description","")).strip(),"cat":str(s.get("category","other")).strip().lower(),"r":r,"ri":ri,"fi":fi,"ei":ei})
        tfi=int(tot*_PFR); tei=tot+tfi
        conn=sqlite3.connect(db_path)
        try:
            c=conn.cursor()
            bal=_pg_bal(c,p)
            if bal<tei: return jsonify({"error":"Insufficient balance","balance_rtc":bal/1000000,"required_rtc":tei/1000000}),400
            _pg_adj(c,p,-tei); _pg_adj(c,_EW,tei)
            c.execute("INSERT INTO agent_pipelines(pipeline_id,poster_wallet,title,description,total_reward_rtc,total_reward_i64,total_fee_i64,total_escrow_i64,escrow_funded,created_at) VALUES(?,?,?,?,?,?,?,?,1,?)",(pid,p,t,desc,tot/1000000,tot,tfi,tei,now))
            for i,s in enumerate(sout):
                c.execute("INSERT INTO agent_pipeline_steps(pipeline_id,step_index,title,description,category,reward_rtc,reward_i64,fee_i64,escrow_i64,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'pending',?)",(pid,i,s["title"],s["desc"],s["cat"],s["r"],s["ri"],s["fi"],s["ei"],now))
            conn.commit()
            return jsonify({"ok":True,"pipeline_id":pid,"status":"active","poster_wallet":p,"total_reward_rtc":tot/1000000,"total_fee_rtc":tfi/1000000,"total_escrow_rtc":tei/1000000,"step_count":len(sout),"message":f"Pipeline created! {len(sout)} steps, {tei/1000000} RTC locked."}),201
        except Exception as e:
            conn.rollback(); return jsonify({"error":str(e)}),500
        finally:
            conn.close()

    @app.route("/agent/pipelines",methods=["GET"])
    def agent_list_pipelines():
        sf=request.args.get("status","active").strip()
        pt=request.args.get("poster","").strip()
        lm=min(int(request.args.get("limit",50)),100)
        conn=sqlite3.connect(db_path)
        try:
            conn.row_factory=sqlite3.Row; c=conn.cursor()
            wh=["status=?"]; pr=[sf]
            if pt: wh.append("poster_wallet=?"); pr.append(pt)
            rows=c.execute(f"""SELECT p.pipeline_id,p.poster_wallet,p.title,p.description,p.total_reward_rtc,p.status,p.created_at,p.completed_step_index,
                (SELECT COUNT(*) FROM agent_pipeline_steps WHERE pipeline_id=p.pipeline_id) AS sc,
                (SELECT COUNT(*) FROM agent_pipeline_steps WHERE pipeline_id=p.pipeline_id AND status='completed') AS cc
                FROM agent_pipelines p WHERE {' AND '.join(wh)} ORDER BY p.created_at DESC LIMIT ?""",[*pr,lm]).fetchall()
            return jsonify({"ok":True,"pipelines":[dict(r) for r in rows],"count":len(rows)})
        finally:
            conn.close()

    @app.route("/agent/pipelines/<pid>",methods=["GET"])
    def agent_get_pipeline(pid):
        conn=sqlite3.connect(db_path)
        try:
            conn.row_factory=sqlite3.Row; c=conn.cursor()
            p=c.execute("SELECT * FROM agent_pipelines WHERE pipeline_id=?",(pid,)).fetchone()
            if not p: return jsonify({"error":"Pipeline not found"}),404
            steps=c.execute("SELECT * FROM agent_pipeline_steps WHERE pipeline_id=? ORDER BY step_index ASC",(pid,)).fetchall()
            return jsonify({"ok":True,"pipeline":dict(p),"steps":[dict(s) for s in steps]})
        finally:
            conn.close()

    @app.route("/agent/pipelines/<pid>/advance",methods=["POST"])
    def agent_pipeline_advance(pid):
        conn=sqlite3.connect(db_path)
        try:
            c=conn.cursor()
            p=c.execute("SELECT * FROM agent_pipelines WHERE pipeline_id=?",(pid,)).fetchone()
            if not p: return jsonify({"error":"Pipeline not found"}),404
            p=dict(p)
            if p["status"]!="active": return jsonify({"error":f"Not active ({p['status']})"}),409
            ns=c.execute("SELECT * FROM agent_pipeline_steps WHERE pipeline_id=? AND status='pending' ORDER BY step_index ASC LIMIT 1",(pid,)).fetchone()
            if not ns:
                c.execute("UPDATE agent_pipelines SET status='completed',completed_at=? WHERE pipeline_id=?",(int(__import__('time').time()),pid))
                conn.commit(); return jsonify({"ok":True,"pipeline_id":pid,"status":"completed","message":"All steps done!"})
            ns=dict(ns); si=ns["step_index"]; now=int(__import__('time').time())
            jid="pipejob_"+hashlib.sha256(f"{pid}:{si}:{now}".encode()).hexdigest()[:16]
            jt=f"[PIPELINE:{pid[:12]}] Step {si+1}: {ns['title']}"
            jd=f"{ns.get('description',ns['title'])}\n\n[PIPELINE] Step {si+1} of {p['title']} ({pid}). Complete to trigger next phase."
            ei=ns["escrow_i64"]
            _pg_adj(c,_EW,-ei); _pg_adj(c,_EW+"_step",ei)
            c.execute("INSERT INTO agent_jobs(job_id,poster_wallet,title,description,category,reward_rtc,reward_i64,escrow_i64,platform_fee_i64,status,created_at,expires_at,tags) VALUES(?,?,?,?,?,?,?,?,?,'open',?,?,?)",(jid,p["poster_wallet"],jt,jd,ns.get("category","other"),ns["reward_rtc"],ns["reward_i64"],ei,ns["fee_i64"],now,now+7*86400,_json.dumps(["pipeline",f"pipeline_id:{pid}",f"pipeline_step:{si}"])))
            c.execute("UPDATE agent_pipeline_steps SET job_id=?,status='posted' WHERE pipeline_id=? AND step_index=?",(jid,pid,si))
            _pg_log(c,jid,"pipeline_advance",p["poster_wallet"],f"pipeline={pid}, step={si}")
            conn.commit()
            return jsonify({"ok":True,"pipeline_id":pid,"step_index":si,"step_title":ns["title"],"job_id":jid,"job_title":jt,"reward_rtc":ns["reward_rtc"],"status":"posted","message":f"Step {si+1} posted as job {jid}"}),201
        except Exception as e:
            conn.rollback(); return jsonify({"error":str(e)}),500
        finally:
            conn.close()

    @app.route("/agent/pipelines/<pid>/trigger",methods=["POST"])
    def agent_pipeline_trigger(pid):
        d=request.get_json(silent=True) or {}; cji=str(d.get("job_id","")).strip(); csi=d.get("step_index"); wk=str(d.get("worker_wallet","")).strip()
        conn=sqlite3.connect(db_path)
        try:
            c=conn.cursor()
            p=c.execute("SELECT * FROM agent_pipelines WHERE pipeline_id=?",(pid,)).fetchone()
            if not p: return jsonify({"error":"Pipeline not found"}),404
            p=dict(p)
            if csi is None and cji:
                r=c.execute("SELECT step_index FROM agent_pipeline_steps WHERE pipeline_id=? AND job_id=?",(pid,cji)).fetchone()
                if r: csi=r[0]
            if csi is None: return jsonify({"error":"Could not determine completed step"}),400
            csi=int(csi)
            sr=c.execute("SELECT * FROM agent_pipeline_steps WHERE pipeline_id=? AND step_index=?",(pid,csi)).fetchone()
            if not sr: return jsonify({"error":"Step not found"}),404
            sc=[d[0] for d in c.description]; s=dict(zip(sc,sr))
            if wk: _pg_adj(c,_EW+"_step",-s["escrow_i64"]); _pg_adj(c,wk,s["reward_i64"]); _pg_adj(c,_PFW,s["fee_i64"])
            now=int(__import__('time').time())
            c.execute("UPDATE agent_pipeline_steps SET status='completed',completed_at=?,deliverable_url=?,result_summary=? WHERE pipeline_id=? AND step_index=?",(now,s.get("deliverable_url","") or "",s.get("result_summary","") or "",pid,csi))
            c.execute("UPDATE agent_pipelines SET completed_step_index=? WHERE pipeline_id=?",(csi,pid))
            nr=c.execute("SELECT step_index,title FROM agent_pipeline_steps WHERE pipeline_id=? AND status='pending' ORDER BY step_index ASC LIMIT 1",(pid,)).fetchone()
            if nr:
                conn.commit(); return jsonify({"ok":True,"pipeline_id":pid,"completed_step":csi,"next_step":nr[0],"next_step_title":nr[1],"message":f"Step {csi} done. POST /agent/pipelines/{pid}/advance for step {nr[0]}"})
            used=c.execute("SELECT COALESCE(SUM(escrow_i64),0) FROM agent_pipeline_steps WHERE pipeline_id=? AND status='completed'",(pid,)).fetchone()[0] or 0
            rem=p["total_escrow_i64"]-int(used)
            if rem>0: _pg_adj(c,_EW,-rem); _pg_adj(c,p["poster_wallet"],rem)
            c.execute("UPDATE agent_pipelines SET status='completed',completed_at=? WHERE pipeline_id=?",(now,pid))
            conn.commit(); return jsonify({"ok":True,"pipeline_id":pid,"status":"completed","completed_step":csi,"refunded_rtc":rem/1000000,"message":"All steps done! Escrow refunded."})
        except Exception as e:
            conn.rollback(); return jsonify({"error":str(e)}),500
        finally:
            conn.close()

    @app.route("/agent/pipelines/<pid>",methods=["DELETE"])
    def agent_cancel_pipeline(pid):
        d=request.get_json(silent=True) or {}; p=str(d.get("poster_wallet","")).strip()
        if not p: return jsonify({"error":"poster_wallet required"}),400
        conn=sqlite3.connect(db_path)
        try:
            c=conn.cursor()
            pr=c.execute("SELECT * FROM agent_pipelines WHERE pipeline_id=?",(pid,)).fetchone()
            if not pr: return jsonify({"error":"Pipeline not found"}),404
            pr=dict(pr)
            if pr["poster_wallet"]!=p: return jsonify({"error":"Only poster can cancel"}),403
            if pr["status"]!="active": return jsonify({"error":"Not active"}),409
            rem=pr["total_escrow_i64"]
            c.execute("UPDATE agent_pipelines SET status='cancelled' WHERE pipeline_id=?",(pid,))
            if rem>0: _pg_adj(c,_EW,-rem); _pg_adj(c,p,rem)
            conn.commit(); return jsonify({"ok":True,"pipeline_id":pid,"status":"cancelled","refunded_rtc":rem/1000000,"message":"Pipeline cancelled. Escrow refunded."})
        except Exception as e:
            conn.rollback(); return jsonify({"error":str(e)}),500
        finally:
            conn.close()

    log.info("RIP-302 Pipeline endpoints registered: /agent/pipelines, /agent/pipelines/<id>, /agent/pipelines/<id>/advance, /agent/pipelines/<id>/trigger, /agent/pipelines/<id> [DELETE]")