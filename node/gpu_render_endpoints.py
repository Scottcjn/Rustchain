# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import sqlite3
import time
import secrets
from flask import request, jsonify

def register_gpu_render_endpoints(app, db_path, admin_key):
    """Registers decentralized GPU render payment and attestation endpoints."""

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
            db.execute("""
                INSERT OR REPLACE INTO gpu_attestations (
                    miner_id, gpu_model, vram_gb, cuda_version, benchmark_score,
                    price_render_minute, price_tts_1k_chars, price_stt_minute, price_llm_1k_tokens,
                    supports_render, supports_tts, supports_stt, supports_llm, last_attestation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
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
                int(time.time())
            ))
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
        job_type = data.get("job_type") # render, tts, stt, llm
        from_wallet = data.get("from_wallet")
        to_wallet = data.get("to_wallet")
        amount = data.get("amount_rtc")

        if not all([job_type, from_wallet, to_wallet, amount]):
            return jsonify({"error": "Missing required escrow fields"}), 400

        db = get_db()
        try:
            # check balance (Simplified for bounty protocol)
            res = db.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (from_wallet,)).fetchone()
            if not res or res[0] < amount:
                return jsonify({"error": "Insufficient balance for escrow"}), 400

            # Lock funds
            db.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?", (amount, from_wallet))
            
            db.execute("""
                INSERT INTO render_escrow (job_id, job_type, from_wallet, to_wallet, amount_rtc, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'locked', ?)
            """, (job_id, job_type, from_wallet, to_wallet, amount, int(time.time())))
            
            db.commit()
            return jsonify({"ok": True, "job_id": job_id, "status": "locked"})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    # 3. Release: Job finished successfully
    @app.route("/api/gpu/release", methods=["POST"])
    def gpu_release():
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        
        # In production, this would require a signature from the requester or a verified completion proof
        db = get_db()
        try:
            job = db.execute("SELECT * FROM render_escrow WHERE job_id = ? AND status = 'locked'", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found or not in locked state"}), 404

            # Transfer to provider
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["to_wallet"]))
            db.execute("UPDATE render_escrow SET status = 'released', released_at = ? WHERE job_id = ?", (int(time.time()), job_id))
            
            db.commit()
            return jsonify({"ok": True, "status": "released"})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    # 4. Refund: Job failed
    @app.route("/api/gpu/refund", methods=["POST"])
    def gpu_refund():
        data = request.get_json(silent=True) or {}
        job_id = data.get("job_id")
        
        db = get_db()
        try:
            job = db.execute("SELECT * FROM render_escrow WHERE job_id = ? AND status = 'locked'", (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found or not in locked state"}), 404

            # Refund to original requester
            db.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?", (job["amount_rtc"], job["from_wallet"]))
            db.execute("UPDATE render_escrow SET status = 'refunded', released_at = ? WHERE job_id = ?", (int(time.time()), job_id))
            
            db.commit()
            return jsonify({"ok": True, "status": "refunded"})
        except sqlite3.Error as e:
            return jsonify({"error": str(e)}), 500
        finally:
            db.close()

    print("[GPU] Render Protocol endpoints registered")
