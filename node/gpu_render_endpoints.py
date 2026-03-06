# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import hashlib
import math
import secrets
import sqlite3
import time

from flask import jsonify, request


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
        data = request.get_json(silent=True) or {}
        miner_id = data.get("miner_id")
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
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    # 2. Escrow: Lock funds for a job
    @app.route("/api/gpu/escrow", methods=["POST"])
    def gpu_escrow():
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id") or f"job_{secrets.token_hex(8)}"
        job_type = data.get("job_type")  # render, tts, stt, llm
        from_wallet = data.get("from_wallet")
        to_wallet = data.get("to_wallet")
        amount = _parse_positive_amount(data.get("amount_rtc"))

        if not all([job_type, from_wallet, to_wallet]):
            return jsonify({"error": "Missing required escrow fields"}), 400
        if amount is None:
            return jsonify({"error": "amount_rtc must be a finite number > 0"}), 400

        escrow_secret = data.get("escrow_secret") or secrets.token_hex(16)

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
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    # 3. Release: Job finished successfully (payer authorizes provider payout)
    @app.route("/api/gpu/release", methods=["POST"])
    def gpu_release():
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        actor_wallet = data.get("actor_wallet")
        escrow_secret = data.get("escrow_secret")

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
            if _hash_job_secret(escrow_secret) != (job["escrow_secret_hash"] or ""):
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
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    # 4. Refund: Job failed (provider authorizes refund to payer)
    @app.route("/api/gpu/refund", methods=["POST"])
    def gpu_refund():
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        actor_wallet = data.get("actor_wallet")
        escrow_secret = data.get("escrow_secret")

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
            if _hash_job_secret(escrow_secret) != (job["escrow_secret_hash"] or ""):
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
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    print("[GPU] Render Protocol endpoints registered")
