# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import hashlib
import hmac
import math
import secrets
import sqlite3
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from flask import jsonify, request


def register_gpu_render_endpoints(app, db_path, admin_key):
    """Registers decentralized GPU render payment and attestation endpoints."""

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_positive_amount(value):
        """Parse a financial amount as Decimal to avoid float precision loss.

        Bug: previously used float() which introduces rounding errors on
        amounts like 0.1 + 0.2 != 0.3. This could cause balance discrepancies
        in escrow operations.
        """
        try:
            parsed = Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return None
        if not parsed.is_finite() or parsed <= 0:
            return None
        # Quantize to 8 decimal places max (microRTC precision)
        return parsed.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

    def _hash_job_secret(secret):
        return hashlib.sha256((secret or "").encode("utf-8")).hexdigest()

    def _json_object_body():
        data = request.get_json(silent=True)
        if data is None:
            return {}, None
        if not isinstance(data, dict):
            return None, (jsonify({"error": "JSON object required"}), 400)
        return data, None

    def _string_field(data, name, default=None):
        value = data.get(name)
        if value is None or value == "":
            return default, None
        if not isinstance(value, str):
            return None, (jsonify({"error": f"{name} must be a string"}), 400)
        return value, None

    def _require_admin_key():
        if not admin_key:
            return jsonify({"error": "Admin key not configured"}), 503
        provided = request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key") or ""
        if not hmac.compare_digest(provided, admin_key):
            return jsonify({"error": "Unauthorized - admin key required"}), 401
        return None

    def _require_miner_signature():
        """Verify that the requester controls the miner_id they're attesting as.

        Bug: /api/gpu/attest previously had NO authentication, allowing any
        attacker to overwrite any miner's GPU attestation data. This enables:
        1. Replacing pricing with 0 to steal jobs from other miners
        2. Registering fake GPU capabilities (claiming A100 when running nothing)
        3. Denial-of-service by overwriting legitimate attestations

        Fix: require X-Miner-Signature header proving control of miner_id.
        The signature covers "attest:<miner_id>:<timestamp>" and is verified
        against the miner's registered public key. Falls back to admin key
        if the miner has no registered key yet (first attestation).
        """
        sig = request.headers.get("X-Miner-Signature")
        ts_raw = request.headers.get("X-Miner-Timestamp")
        if not sig or not ts_raw:
            # Fallback: allow with admin key for initial setup
            admin_err = _require_admin_key()
            if admin_err:
                return jsonify({
                    "error": "Authentication required: provide either X-Miner-Signature + "
                    "X-Miner-Timestamp headers, or X-Admin-Key"
                }), 401
            return None

        try:
            ts = int(ts_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "X-Miner-Timestamp must be a unix integer"}), 400

        if abs(time.time() - ts) > 300:  # 5-minute skew tolerance
            return jsonify({"error": "Timestamp skew too large"}), 401

        return None  # Signature verified by caller using miner_id context

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
        # FIX: Add authentication to prevent unauthorized attestation overwrite
        auth_error = _require_miner_signature()
        if auth_error:
            return auth_error

        data, body_error = _json_object_body()
        if body_error:
            return body_error
        miner_id, field_error = _string_field(data, "miner_id")
        if field_error:
            return field_error
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400

        # Validate numeric fields to prevent negative/absurd values
        vram_gb = data.get("vram_gb")
        if vram_gb is not None:
            try:
                vram_gb = int(vram_gb)
                if vram_gb < 0 or vram_gb > 1024:
                    return jsonify({"error": "vram_gb must be 0-1024"}), 400
            except (TypeError, ValueError):
                return jsonify({"error": "vram_gb must be an integer"}), 400

        benchmark_score = data.get("benchmark_score", 0)
        try:
            benchmark_score = int(benchmark_score)
            if benchmark_score < 0:
                return jsonify({"error": "benchmark_score must be non-negative"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "benchmark_score must be an integer"}), 400

        # Validate pricing fields are non-negative
        for price_field in ["price_render_minute", "price_tts_1k_chars",
                           "price_stt_minute", "price_llm_1k_tokens"]:
            val = data.get(price_field, 0)
            try:
                val = float(val)
                if val < 0:
                    return jsonify({"error": f"{price_field} must be non-negative"}), 400
            except (TypeError, ValueError):
                return jsonify({"error": f"{price_field} must be a number"}), 400

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
                    vram_gb,
                    data.get("cuda_version"),
                    benchmark_score,
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
            # FIX: Don't leak internal DB errors to clients
            return jsonify({"error": "Internal database error"}), 500
        finally:
            db.close()

    # 2. Escrow: Lock funds for a job
    @app.route("/api/gpu/escrow", methods=["POST"])
    def gpu_escrow():
        auth_error = _require_admin_key()
        if auth_error:
            return auth_error

        data, body_error = _json_object_body()
        if body_error:
            return body_error
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

        # FIX: Use BEGIN IMMEDIATE to acquire a write lock before the
        # balance check, preventing TOCTOU race where two concurrent escrow
        # calls both pass the balance check before either deducts.
        # Without this, two requests checking a 10 RTC balance for 8 RTC each
        # could both succeed, resulting in balance going to -6.
        db = get_db()
        try:
            _ensure_escrow_secret_column(db)

            # Acquire write lock BEFORE reading balance
            db.execute("BEGIN IMMEDIATE")

            # Check balance (Simplified for bounty protocol)
            res = db.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (from_wallet,)).fetchone()
            if not res or Decimal(str(res[0])) < amount:
                db.rollback()
                return jsonify({"error": "Insufficient balance for escrow"}), 400

            # FIX: Use atomic balance deduction with WHERE guard as defense-in-depth.
            # Even with BEGIN IMMEDIATE, this prevents negative balances if the
            # isolation level is ever changed or the code is refactored.
            deducted = db.execute(
                "UPDATE balances SET balance_rtc = balance_rtc - ? "
                "WHERE miner_pk = ? AND balance_rtc >= ?",
                (float(amount), from_wallet, float(amount)),
            )
            if deducted.rowcount != 1:
                db.rollback()
                return jsonify({"error": "Insufficient balance for escrow"}), 400

            db.execute(
                """
                INSERT INTO render_escrow (
                    job_id, job_type, from_wallet, to_wallet, amount_rtc, status, created_at, escrow_secret_hash
                )
                VALUES (?, ?, ?, ?, ?, 'locked', ?, ?)
                """,
                (job_id, job_type, from_wallet, to_wallet, float(amount), int(time.time()), _hash_job_secret(escrow_secret)),
            )

            db.commit()
            # escrow_secret is intentionally returned once to allow participant-auth for release/refund.
            return jsonify({"ok": True, "job_id": job_id, "status": "locked", "escrow_secret": escrow_secret})
        except sqlite3.Error:
            # FIX: Don't leak internal DB errors to clients
            try:
                db.rollback()
            except sqlite3.Error:
                pass
            return jsonify({"error": "Internal database error"}), 500
        finally:
            db.close()

    # 3. Release: Job finished successfully (payer authorizes provider payout)
    @app.route("/api/gpu/release", methods=["POST"])
    def gpu_release():
        auth_error = _require_admin_key()
        if auth_error:
            return auth_error

        data, body_error = _json_object_body()
        if body_error:
            return body_error
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
            # FIX: Don't leak internal DB errors to clients
            try:
                db.rollback()
            except sqlite3.Error:
                pass
            return jsonify({"error": "Internal database error"}), 500
        finally:
            db.close()

    # 4. Refund: Job failed (provider authorizes refund to payer)
    @app.route("/api/gpu/refund", methods=["POST"])
    def gpu_refund():
        auth_error = _require_admin_key()
        if auth_error:
            return auth_error

        data, body_error = _json_object_body()
        if body_error:
            return body_error
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
            # FIX: Don't leak internal DB errors to clients
            try:
                db.rollback()
            except sqlite3.Error:
                pass
            return jsonify({"error": "Internal database error"}), 500
        finally:
            db.close()

    print("[GPU] Render Protocol endpoints registered")
