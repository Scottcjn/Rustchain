# SPDX-License-Identifier: MIT
# Author: @xiangshangsir (大龙虾 AI)
# BCOS-Tier: L1
# Bounty: #30 - Decentralized GPU Render Protocol (Voice/LLM Extension)
"""
Voice & LLM Payment Endpoints for RustChain
Extends GPU Render Protocol with dedicated endpoints for:
- TTS (Text-to-Speech) jobs
- STT (Speech-to-Text) jobs  
- LLM Inference jobs
"""
import hashlib
import json
import math
import secrets
import sqlite3
import time
from typing import Optional, Tuple

from flask import jsonify, request


def register_voice_llm_endpoints(app, db_path, admin_key):
    """Registers voice synthesis and LLM inference payment endpoints."""

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_positive_amount(value) -> Optional[float]:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed) or parsed <= 0:
            return None
        return parsed

    def _hash_job_secret(secret: str) -> str:
        return hashlib.sha256((secret or "").encode("utf-8")).hexdigest()

    def _ensure_voice_tables(db):
        """Ensure voice/llm specific tables exist."""
        try:
            # Voice escrow table with job-specific fields
            db.execute("""
                CREATE TABLE IF NOT EXISTS voice_escrow (
                    id INTEGER PRIMARY KEY,
                    job_id TEXT UNIQUE NOT NULL,
                    job_type TEXT NOT NULL,  -- tts or stt
                    from_wallet TEXT NOT NULL,
                    to_wallet TEXT NOT NULL,
                    amount_rtc REAL NOT NULL,
                    status TEXT DEFAULT 'locked',  -- locked, released, refunded, completed
                    created_at INTEGER NOT NULL,
                    released_at INTEGER,
                    escrow_secret_hash TEXT,
                    -- TTS specific
                    text_content TEXT,
                    voice_model TEXT,
                    char_count INTEGER,
                    -- STT specific
                    audio_duration_sec REAL,
                    language TEXT,
                    -- Result
                    result_url TEXT,
                    metadata TEXT
                )
            """)
            
            # LLM escrow table
            db.execute("""
                CREATE TABLE IF NOT EXISTS llm_escrow (
                    id INTEGER PRIMARY KEY,
                    job_id TEXT UNIQUE NOT NULL,
                    from_wallet TEXT NOT NULL,
                    to_wallet TEXT NOT NULL,
                    amount_rtc REAL NOT NULL,
                    status TEXT DEFAULT 'locked',
                    created_at INTEGER NOT NULL,
                    released_at INTEGER,
                    escrow_secret_hash TEXT,
                    -- Job details
                    model_name TEXT,
                    prompt_text TEXT,
                    max_tokens INTEGER,
                    temperature REAL,
                    -- Result
                    completion_text TEXT,
                    tokens_used INTEGER,
                    tokens_input INTEGER,
                    tokens_output INTEGER,
                    metadata TEXT
                )
            """)
            
            # Pricing oracle table
            db.execute("""
                CREATE TABLE IF NOT EXISTS pricing_oracle (
                    id INTEGER PRIMARY KEY,
                    job_type TEXT NOT NULL,  -- render, tts, stt, llm
                    model_name TEXT,
                    provider_wallet TEXT,
                    price_per_unit REAL NOT NULL,
                    unit_type TEXT NOT NULL,  -- minute, 1k_chars, 1k_tokens
                    quality_score REAL DEFAULT 1.0,
                    total_jobs INTEGER DEFAULT 0,
                    avg_rating REAL DEFAULT 5.0,
                    last_updated INTEGER NOT NULL,
                    UNIQUE(job_type, model_name, provider_wallet)
                )
            """)
            
            # Job history for analytics
            db.execute("""
                CREATE TABLE IF NOT EXISTS job_history (
                    id INTEGER PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    provider_wallet TEXT NOT NULL,
                    amount_rtc REAL NOT NULL,
                    duration_sec REAL,
                    quality_rating INTEGER,
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER
                )
            """)
            
            db.commit()
        except sqlite3.Error as e:
            app.logger.error(f"Failed to create voice/llm tables: {e}")

    # ==================== TTS/STT Endpoints ====================

    @app.route("/api/voice/escrow", methods=["POST"])
    def voice_escrow():
        """
        Lock RTC for TTS/STT job.
        
        Request:
        {
            "job_type": "tts" | "stt",
            "from_wallet": "wallet_address",
            "to_wallet": "provider_wallet",
            "amount_rtc": 10.5,
            "escrow_secret": "optional_secret",
            # TTS fields
            "text_content": "text to synthesize",
            "voice_model": "xtts-v2",
            "char_count": 1000,
            # STT fields
            "audio_duration_sec": 60.5,
            "language": "en"
        }
        """
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id") or f"voice_{secrets.token_hex(8)}"
        job_type = data.get("job_type")
        from_wallet = data.get("from_wallet")
        to_wallet = data.get("to_wallet")
        amount = _parse_positive_amount(data.get("amount_rtc"))

        if not job_type or job_type not in ("tts", "stt"):
            return jsonify({"error": "job_type must be 'tts' or 'stt'"}), 400
        if not all([from_wallet, to_wallet]):
            return jsonify({"error": "from_wallet and to_wallet required"}), 400
        if amount is None:
            return jsonify({"error": "amount_rtc must be a finite number > 0"}), 400

        escrow_secret = data.get("escrow_secret") or secrets.token_hex(16)

        db = get_db()
        try:
            _ensure_voice_tables(db)

            # Check balance
            res = db.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (from_wallet,)).fetchone()
            if not res or res[0] < amount:
                return jsonify({"error": "Insufficient balance for escrow"}), 400

            # Lock funds
            db.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?", (amount, from_wallet))

            db.execute("""
                INSERT INTO voice_escrow (
                    job_id, job_type, from_wallet, to_wallet, amount_rtc, status, created_at,
                    escrow_secret_hash, text_content, voice_model, char_count,
                    audio_duration_sec, language
                ) VALUES (?, ?, ?, ?, ?, 'locked', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id, job_type, from_wallet, to_wallet, amount, int(time.time()),
                    _hash_job_secret(escrow_secret),
                    data.get("text_content"),
                    data.get("voice_model"),
                    data.get("char_count"),
                    data.get("audio_duration_sec"),
                    data.get("language"),
                ),
            )

            db.commit()
            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": "locked",
                "escrow_secret": escrow_secret,
                "pricing": {
                    "type": job_type,
                    "rate": f"{amount:.4f} RTC",
                }
            })
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/voice/release", methods=["POST"])
    def voice_release():
        """
        Release escrow to voice provider on job completion.
        Only payer (from_wallet) can release.
        
        Request:
        {
            "job_id": "voice_xxx",
            "actor_wallet": "from_wallet",
            "escrow_secret": "secret_from_escrow_creation",
            "result_url": "https://.../audio.wav",  # optional
            "metadata": {"duration": 60.5, "model": "xtts-v2"}  # optional
        }
        """
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        actor_wallet = data.get("actor_wallet")
        escrow_secret = data.get("escrow_secret")

        if not all([job_id, actor_wallet, escrow_secret]):
            return jsonify({"error": "job_id, actor_wallet, escrow_secret required"}), 400

        db = get_db()
        try:
            job = db.execute("SELECT * FROM voice_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job["status"] != "locked":
                return jsonify({"error": "Job not in locked state"}), 409
            if actor_wallet != job["from_wallet"]:
                return jsonify({"error": "only payer can release escrow"}), 403
            if _hash_job_secret(escrow_secret) != (job["escrow_secret_hash"] or ""):
                return jsonify({"error": "invalid escrow_secret"}), 403

            # Atomic state transition
            moved = db.execute(
                "UPDATE voice_escrow SET status = 'released', released_at = ?, result_url = ?, metadata = ? WHERE job_id = ? AND status = 'locked'",
                (int(time.time()), data.get("result_url"), json.dumps(data.get("metadata") or {}), job_id),
            )
            if moved.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Job was already processed"}), 409

            # Transfer to provider
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["to_wallet"]))
            
            # Record job history
            db.execute("""
                INSERT INTO job_history (job_id, job_type, provider_wallet, amount_rtc, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, job["job_type"], job["to_wallet"], job["amount_rtc"], job["created_at"], int(time.time())),
            )
            
            db.commit()
            return jsonify({"ok": True, "status": "released", "amount": job["amount_rtc"]})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/voice/refund", methods=["POST"])
    def voice_refund():
        """
        Refund escrow to payer if job fails.
        Only provider (to_wallet) can request refund.
        """
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        actor_wallet = data.get("actor_wallet")
        escrow_secret = data.get("escrow_secret")

        if not all([job_id, actor_wallet, escrow_secret]):
            return jsonify({"error": "job_id, actor_wallet, escrow_secret required"}), 400

        db = get_db()
        try:
            job = db.execute("SELECT * FROM voice_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job["status"] != "locked":
                return jsonify({"error": "Job not in locked state"}), 409
            if actor_wallet != job["to_wallet"]:
                return jsonify({"error": "only provider can request refund"}), 403
            if _hash_job_secret(escrow_secret) != (job["escrow_secret_hash"] or ""):
                return jsonify({"error": "invalid escrow_secret"}), 403

            moved = db.execute(
                "UPDATE voice_escrow SET status = 'refunded', released_at = ? WHERE job_id = ? AND status = 'locked'",
                (int(time.time()), job_id),
            )
            if moved.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Job was already processed"}), 409

            # Refund to payer
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["from_wallet"]))
            db.commit()
            return jsonify({"ok": True, "status": "refunded", "amount": job["amount_rtc"]})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/voice/status/<job_id>", methods=["GET"])
    def voice_status(job_id):
        """Get voice job status and details."""
        db = get_db()
        try:
            job = db.execute("SELECT * FROM voice_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            
            # Hide sensitive data
            result = dict(job)
            result.pop("escrow_secret_hash", None)
            return jsonify({"ok": True, "job": result})
        finally:
            db.close()

    # ==================== LLM Inference Endpoints ====================

    @app.route("/api/llm/escrow", methods=["POST"])
    def llm_escrow():
        """
        Lock RTC for LLM inference job.
        
        Request:
        {
            "from_wallet": "wallet_address",
            "to_wallet": "provider_wallet",
            "amount_rtc": 5.0,
            "model_name": "llama-3-8b",
            "prompt_text": "Explain quantum computing...",
            "max_tokens": 1000,
            "temperature": 0.7,
            "escrow_secret": "optional"
        }
        """
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id") or f"llm_{secrets.token_hex(8)}"
        from_wallet = data.get("from_wallet")
        to_wallet = data.get("to_wallet")
        amount = _parse_positive_amount(data.get("amount_rtc"))

        if not all([from_wallet, to_wallet]):
            return jsonify({"error": "from_wallet and to_wallet required"}), 400
        if amount is None:
            return jsonify({"error": "amount_rtc must be a finite number > 0"}), 400

        escrow_secret = data.get("escrow_secret") or secrets.token_hex(16)

        db = get_db()
        try:
            _ensure_voice_tables(db)

            # Check balance
            res = db.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (from_wallet,)).fetchone()
            if not res or res[0] < amount:
                return jsonify({"error": "Insufficient balance for escrow"}), 400

            # Lock funds
            db.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?", (amount, from_wallet))

            db.execute("""
                INSERT INTO llm_escrow (
                    job_id, from_wallet, to_wallet, amount_rtc, status, created_at,
                    escrow_secret_hash, model_name, prompt_text, max_tokens, temperature
                ) VALUES (?, ?, ?, ?, 'locked', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id, from_wallet, to_wallet, amount, int(time.time()),
                    _hash_job_secret(escrow_secret),
                    data.get("model_name", "unknown"),
                    data.get("prompt_text", ""),
                    data.get("max_tokens", 1024),
                    data.get("temperature", 0.7),
                ),
            )

            db.commit()
            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": "locked",
                "escrow_secret": escrow_secret,
                "model": data.get("model_name", "unknown"),
            })
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/llm/release", methods=["POST"])
    def llm_release():
        """
        Release escrow to LLM provider on completion.
        
        Request:
        {
            "job_id": "llm_xxx",
            "actor_wallet": "from_wallet",
            "escrow_secret": "secret",
            "completion_text": "LLM response...",
            "tokens_used": 512,
            "tokens_input": 128,
            "tokens_output": 384,
            "metadata": {"model": "llama-3-8b", "latency_ms": 1200}
        }
        """
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        actor_wallet = data.get("actor_wallet")
        escrow_secret = data.get("escrow_secret")

        if not all([job_id, actor_wallet, escrow_secret]):
            return jsonify({"error": "job_id, actor_wallet, escrow_secret required"}), 400

        db = get_db()
        try:
            job = db.execute("SELECT * FROM llm_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job["status"] != "locked":
                return jsonify({"error": "Job not in locked state"}), 409
            if actor_wallet != job["from_wallet"]:
                return jsonify({"error": "only payer can release escrow"}), 403
            if _hash_job_secret(escrow_secret) != (job["escrow_secret_hash"] or ""):
                return jsonify({"error": "invalid escrow_secret"}), 403

            tokens_used = data.get("tokens_used", 0)
            tokens_input = data.get("tokens_input", 0)
            tokens_output = data.get("tokens_output", 0)

            moved = db.execute(
                "UPDATE llm_escrow SET status = 'released', released_at = ?, completion_text = ?, tokens_used = ?, tokens_input = ?, tokens_output = ?, metadata = ? WHERE job_id = ? AND status = 'locked'",
                (
                    int(time.time()),
                    data.get("completion_text", ""),
                    tokens_used,
                    tokens_input,
                    tokens_output,
                    json.dumps(data.get("metadata") or {}),
                    job_id,
                ),
            )
            if moved.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Job was already processed"}), 409

            # Transfer to provider
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["to_wallet"]))
            
            # Record job history
            db.execute("""
                INSERT INTO job_history (job_id, job_type, provider_wallet, amount_rtc, created_at, completed_at)
                VALUES (?, 'llm', ?, ?, ?, ?)
                """,
                (job_id, job["to_wallet"], job["amount_rtc"], job["created_at"], int(time.time())),
            )
            
            db.commit()
            return jsonify({
                "ok": True,
                "status": "released",
                "amount": job["amount_rtc"],
                "tokens": {
                    "used": tokens_used,
                    "input": tokens_input,
                    "output": tokens_output,
                }
            })
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/llm/refund", methods=["POST"])
    def llm_refund():
        """Refund LLM escrow to payer if job fails."""
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        actor_wallet = data.get("actor_wallet")
        escrow_secret = data.get("escrow_secret")

        if not all([job_id, actor_wallet, escrow_secret]):
            return jsonify({"error": "job_id, actor_wallet, escrow_secret required"}), 400

        db = get_db()
        try:
            job = db.execute("SELECT * FROM llm_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job["status"] != "locked":
                return jsonify({"error": "Job not in locked state"}), 409
            if actor_wallet != job["to_wallet"]:
                return jsonify({"error": "only provider can request refund"}), 403
            if _hash_job_secret(escrow_secret) != (job["escrow_secret_hash"] or ""):
                return jsonify({"error": "invalid escrow_secret"}), 403

            moved = db.execute(
                "UPDATE llm_escrow SET status = 'refunded', released_at = ? WHERE job_id = ? AND status = 'locked'",
                (int(time.time()), job_id),
            )
            if moved.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Job was already processed"}), 409

            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["from_wallet"]))
            db.commit()
            return jsonify({"ok": True, "status": "refunded", "amount": job["amount_rtc"]})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/llm/status/<job_id>", methods=["GET"])
    def llm_status(job_id):
        """Get LLM job status and details."""
        db = get_db()
        try:
            job = db.execute("SELECT * FROM llm_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            
            result = dict(job)
            result.pop("escrow_secret_hash", None)
            return jsonify({"ok": True, "job": result})
        finally:
            db.close()

    # ==================== Pricing Oracle Endpoints ====================

    @app.route("/api/pricing/update", methods=["POST"])
    def pricing_update():
        """
        Update pricing for a provider/model combination.
        Called by providers to publish their rates.
        
        Request:
        {
            "provider_wallet": "wallet",
            "job_type": "tts" | "stt" | "llm" | "render",
            "model_name": "xtts-v2",
            "price_per_unit": 0.05,
            "unit_type": "1k_chars" | "minute" | "1k_tokens",
            "quality_score": 1.0
        }
        """
        data = request.get_json(silent=True) or {}
        provider_wallet = data.get("provider_wallet")
        job_type = data.get("job_type")
        model_name = data.get("model_name")
        price = _parse_positive_amount(data.get("price_per_unit"))

        if not all([provider_wallet, job_type, price]):
            return jsonify({"error": "provider_wallet, job_type, price_per_unit required"}), 400

        db = get_db()
        try:
            _ensure_voice_tables(db)
            
            db.execute("""
                INSERT OR REPLACE INTO pricing_oracle (
                    job_type, model_name, provider_wallet, price_per_unit, unit_type,
                    quality_score, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_type,
                    model_name or "default",
                    provider_wallet,
                    price,
                    data.get("unit_type", "unit"),
                    data.get("quality_score", 1.0),
                    int(time.time()),
                ),
            )
            db.commit()
            return jsonify({"ok": True, "message": "Pricing updated"})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    @app.route("/api/pricing/query", methods=["GET"])
    def pricing_query():
        """
        Query fair market rates for a job type.
        Returns aggregated pricing from all providers.
        
        Query params:
        - job_type: tts | stt | llm | render
        - model_name: optional filter
        """
        job_type = request.args.get("job_type")
        model_name = request.args.get("model_name")

        if not job_type:
            return jsonify({"error": "job_type required"}), 400

        db = get_db()
        try:
            if model_name:
                rows = db.execute("""
                    SELECT provider_wallet, model_name, price_per_unit, unit_type, quality_score, total_jobs, avg_rating
                    FROM pricing_oracle
                    WHERE job_type = ? AND model_name = ?
                    ORDER BY price_per_unit ASC
                """, (job_type, model_name)).fetchall()
            else:
                rows = db.execute("""
                    SELECT provider_wallet, model_name, price_per_unit, unit_type, quality_score, total_jobs, avg_rating
                    FROM pricing_oracle
                    WHERE job_type = ?
                    ORDER BY price_per_unit ASC
                """, (job_type,)).fetchall()

            if not rows:
                return jsonify({"ok": True, "pricing": [], "market_avg": None})

            prices = [row["price_per_unit"] for row in rows]
            avg_price = sum(prices) / len(prices)
            
            # Filter to fair market range (within 50% of average)
            fair_min = avg_price * 0.5
            fair_max = avg_price * 1.5
            fair_providers = [dict(row) for row in rows if fair_min <= row["price_per_unit"] <= fair_max]

            return jsonify({
                "ok": True,
                "pricing": [dict(row) for row in rows],
                "fair_providers": fair_providers,
                "market_avg": avg_price,
                "market_range": {"min": min(prices), "max": max(prices)},
            })
        finally:
            db.close()

    @app.route("/api/pricing/stats", methods=["GET"])
    def pricing_stats():
        """Get market statistics across all job types."""
        db = get_db()
        try:
            _ensure_voice_tables(db)
            
            stats = db.execute("""
                SELECT 
                    job_type,
                    COUNT(*) as provider_count,
                    AVG(price_per_unit) as avg_price,
                    MIN(price_per_unit) as min_price,
                    MAX(price_per_unit) as max_price,
                    AVG(quality_score) as avg_quality,
                    SUM(total_jobs) as total_jobs
                FROM pricing_oracle
                GROUP BY job_type
            """).fetchall()

            return jsonify({
                "ok": True,
                "stats": [dict(row) for row in stats],
            })
        finally:
            db.close()

    # ==================== Analytics Endpoints ====================

    @app.route("/api/job/history", methods=["GET"])
    def job_history():
        """Get job history with optional filters."""
        job_type = request.args.get("job_type")
        provider_wallet = request.args.get("provider_wallet")
        limit = min(int(request.args.get("limit", 100)), 1000)

        db = get_db()
        try:
            query = "SELECT * FROM job_history WHERE 1=1"
            params = []
            
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
            if provider_wallet:
                query += " AND provider_wallet = ?"
                params.append(provider_wallet)
            
            query += " ORDER BY completed_at DESC LIMIT ?"
            params.append(limit)

            rows = db.execute(query, params).fetchall()
            return jsonify({"ok": True, "jobs": [dict(row) for row in rows], "count": len(rows)})
        finally:
            db.close()

    print("[Voice/LLM] Payment endpoints registered")
