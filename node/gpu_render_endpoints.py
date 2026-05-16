# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import hashlib
import hmac
import logging
import math
import secrets
import sqlite3
import time

from flask import jsonify, request


logger = logging.getLogger(__name__)


def register_gpu_render_endpoints(app, db_path, admin_key):
    """Registers decentralized GPU render payment and attestation endpoints."""

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_positive_amount(value):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed) or parsed <= 0:
            return None
        return parsed

    def _hash_job_secret(secret):
        return hashlib.sha256((secret or "").encode("utf-8")).hexdigest()

    def _request_json_object():
        data = request.get_json(silent=True)
        if data is None:
            return {}, None
        if not isinstance(data, dict):
            return None, (jsonify({"error": "JSON object required"}), 400)
        return data, None

    def _string_field(data, name, default=None):
        value = data.get(name)
        if value is None:
            return default, None
        if not isinstance(value, str):
            return None, (jsonify({"error": f"{name} must be a string"}), 400)
        value = value.strip()
        if not value:
            return default, None
        return value, None

    def _database_error(endpoint_name):
        logger.exception("GPU render endpoint %s database failure", endpoint_name)
        return jsonify({"error": "GPU render database unavailable"}), 500

    def _require_admin_key():
        if not admin_key:
            return jsonify({"error": "Admin key not configured"}), 503
        provided = request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key") or ""
        if not hmac.compare_digest(provided, admin_key):
            return jsonify({"error": "Unauthorized - admin key required"}), 401
        return None

    def _ensure_escrow_secret_column(db):
        """Best-effort migration for older DBs."""
        try:
            cols = {row[1] for row in db.execute("PRAGMA table_info(render_escrow)").fetchall()}
            if "escrow_secret_hash" not in cols:
                db.execute("ALTER TABLE render_escrow ADD COLUMN escrow_secret_hash TEXT")
                db.commit()
        except sqlite3.Error:
            pass

    # 1. GPU Node Attestation (Extension)
    @app.route("/api/gpu/attest", methods=["POST"])
    def gpu_attest():
        data, json_error = _request_json_object()
        if json_error:
            return json_error
        miner_id, field_error = _string_field(data, "miner_id")
        if field_error:
            return field_error
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400

        # In a real node, we'd verify the signed hardware fingerprint here.
        # For the bounty, we implement the protocol storage and API.
        db = get_db()
        try:
            db.execute(
                """
                INSERT OR REPLACE INTO gpu_attestations (
                    miner_id, gpu_model, vram_gb, cuda_version, benchmark_score,
                    price_render_minute, price_tts_1k_chars, price_stt_minute, price_llm_1k_tokens,
                    supports_render, supports_tts, supports_stt, supports_llm, last_attestation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    miner_id,
                    data.get("gpu_model"),
                    data.get("vram_gb"),
                    data.get("cuda_version"),
                    data.get("benchmark_score", 0),
                    data.get("price_render_minute", 0.1),
                    data.get("price_tts_1k_chars", 0.05),
                    data.get("price_stt_minute", 0.1),
                    data.get("price_llm_1k_tokens", 0.02),
                    1 if data.get("supports_render") else 0,
                    1 if data.get("supports_tts") else 0,
                    1 if data.get("supports_stt") else 0,
                    1 if data.get("supports_llm") else 0,
                    int(time.time()),
                ),
            )
            db.commit()
            return jsonify({"ok": True, "message": "GPU attestation recorded"})
        except sqlite3.Error:
            return _database_error("attest")
        finally:
            db.close()

    # 2. Escrow: Lock funds for a job
    @app.route("/api/gpu/escrow", methods=["POST"])
    def gpu_escrow():
        auth_error = _require_admin_key()
        if auth_error:
            return auth_error

        data, json_error = _request_json_object()
        if json_error:
            return json_error
        job_id, field_error = _string_field(data, "job_id", default=f"job_{secrets.token_hex(8)}")
        if field_error:
            return field_error
        job_type, field_error = _string_field(data, "job_type")  # render, tts, stt, llm
        if field_error:
            return field_error
        from_wallet, field_error = _string_field(data, "from_wallet")
        if field_error:
            return field_error
        to_wallet, field_error = _string_field(data, "to_wallet")
        if field_error:
            return field_error
        amount = _parse_positive_amount(data.get("amount_rtc"))

        if not all([job_type, from_wallet, to_wallet]):
            return jsonify({"error": "Missing required escrow fields"}), 400
        if amount is None:
            return jsonify({"error": "amount_rtc must be a finite number > 0"}), 400

        escrow_secret, field_error = _string_field(data, "escrow_secret", default=secrets.token_hex(16))
        if field_error:
            return field_error

        db = get_db()
        try:
            _ensure_escrow_secret_column(db)

            # check balance (Simplified for bounty protocol)
            res = db.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (from_wallet,)).fetchone()
            if not res or res[0] < amount:
                return jsonify({"error": "Insufficient balance for escrow"}), 400

            # Lock funds
            db.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?", (amount, from_wallet))

            db.execute(
                """
                INSERT INTO render_escrow (
                    job_id, job_type, from_wallet, to_wallet, amount_rtc, status, created_at, escrow_secret_hash
                )
                VALUES (?, ?, ?, ?, ?, 'locked', ?, ?)
                """,
                (job_id, job_type, from_wallet, to_wallet, amount, int(time.time()), _hash_job_secret(escrow_secret)),
            )

            db.commit()
            # escrow_secret is intentionally returned once to allow participant-auth for release/refund.
            return jsonify({"ok": True, "job_id": job_id, "status": "locked", "escrow_secret": escrow_secret})
        except sqlite3.Error:
            db.rollback()
            return _database_error("escrow")
        finally:
            db.close()

    # 3. Release: Job finished successfully (payer authorizes provider payout)
    @app.route("/api/gpu/release", methods=["POST"])
    def gpu_release():
        auth_error = _require_admin_key()
        if auth_error:
            return auth_error

        data, json_error = _request_json_object()
        if json_error:
            return json_error
        job_id, field_error = _string_field(data, "job_id")
        if field_error:
            return field_error
        actor_wallet, field_error = _string_field(data, "actor_wallet")
        if field_error:
            return field_error
        escrow_secret, field_error = _string_field(data, "escrow_secret")
        if field_error:
            return field_error

        if not all([job_id, actor_wallet, escrow_secret]):
            return jsonify({"error": "job_id, actor_wallet, escrow_secret are required"}), 400

        db = get_db()
        try:
            _ensure_escrow_secret_column(db)
            job = db.execute("SELECT * FROM render_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job["status"] != "locked":
                return jsonify({"error": "Job not in locked state"}), 409
            if actor_wallet not in {job["from_wallet"], job["to_wallet"]}:
                return jsonify({"error": "actor_wallet must be escrow participant"}), 403
            if actor_wallet != job["from_wallet"]:
                return jsonify({"error": "only payer can release escrow"}), 403
            # Security fix: use hmac.compare_digest() to prevent timing
            # side-channel attacks that could leak the escrow secret hash.
            if not hmac.compare_digest(_hash_job_secret(escrow_secret), job["escrow_secret_hash"] or ""):
                return jsonify({"error": "invalid escrow_secret"}), 403

            # Atomic state transition first to prevent races/double-processing.
            moved = db.execute(
                "UPDATE render_escrow SET status = 'released', released_at = ? WHERE job_id = ? AND status = 'locked'",
                (int(time.time()), job_id),
            )
            if moved.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Job was already processed"}), 409

            # Transfer to provider
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["to_wallet"]))
            db.commit()
            return jsonify({"ok": True, "status": "released"})
        except sqlite3.Error:
            db.rollback()
            return _database_error("release")
        finally:
            db.close()

    # 4. Refund: Job failed (provider authorizes refund to payer)
    @app.route("/api/gpu/refund", methods=["POST"])
    def gpu_refund():
        auth_error = _require_admin_key()
        if auth_error:
            return auth_error

        data, json_error = _request_json_object()
        if json_error:
            return json_error
        job_id, field_error = _string_field(data, "job_id")
        if field_error:
            return field_error
        actor_wallet, field_error = _string_field(data, "actor_wallet")
        if field_error:
            return field_error
        escrow_secret, field_error = _string_field(data, "escrow_secret")
        if field_error:
            return field_error

        if not all([job_id, actor_wallet, escrow_secret]):
            return jsonify({"error": "job_id, actor_wallet, escrow_secret are required"}), 400

        db = get_db()
        try:
            _ensure_escrow_secret_column(db)
            job = db.execute("SELECT * FROM render_escrow WHERE job_id = ?", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job["status"] != "locked":
                return jsonify({"error": "Job not in locked state"}), 409
            if actor_wallet not in {job["from_wallet"], job["to_wallet"]}:
                return jsonify({"error": "actor_wallet must be escrow participant"}), 403
            if actor_wallet != job["to_wallet"]:
                return jsonify({"error": "only provider can request refund"}), 403
            # Security fix: use hmac.compare_digest() to prevent timing
            # side-channel attacks that could leak the escrow secret hash.
            if not hmac.compare_digest(_hash_job_secret(escrow_secret), job["escrow_secret_hash"] or ""):
                return jsonify({"error": "invalid escrow_secret"}), 403

            # Atomic state transition first to prevent races/double-processing.
            moved = db.execute(
                "UPDATE render_escrow SET status = 'refunded', released_at = ? WHERE job_id = ? AND status = 'locked'",
                (int(time.time()), job_id),
            )
            if moved.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Job was already processed"}), 409

            # Refund to original requester
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["from_wallet"]))
            db.commit()
            return jsonify({"ok": True, "status": "refunded"})
        except sqlite3.Error:
            db.rollback()
            return _database_error("refund")
        finally:
            db.close()

    print("[GPU] Render Protocol endpoints registered")
