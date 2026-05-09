# SPDX-License-Identifier: Apache-2.0
import logging
import sqlite3
import time
from functools import wraps
from flask import jsonify, request

log = logging.getLogger("rustchain.x402_core")

def x402_required(db_path, price_nrtc: int):
    """
    Decorator to enforce agent-to-agent payments via HTTP 402.
    Verifies the X-Payment-TX-ID header against the ledger.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            tx_id = request.headers.get("X-Payment-TX-ID")
            if not tx_id:
                return jsonify({
                    "error": "Payment Required",
                    "price_nrtc": price_nrtc,
                    "payment_protocol": "x402",
                    "hint": f"Submit a signed transaction for {price_nrtc} nRTC to the network first."
                }), 402
            
            # Implementation of ledger verification
            try:
                with sqlite3.connect(db_path) as conn:
                    # Check if TX exists and is either pending or confirmed
                    row = conn.execute("SELECT status FROM pending_ledger WHERE tx_hash = ?", (tx_id,)).fetchone()
                    if not row:
                        return jsonify({"error": "Transaction not found on ledger"}), 402
                    
                    status = row[0]
                    if status == 'voided':
                        return jsonify({"error": "Transaction was voided"}), 402
            except Exception as e:
                log.error(f"Ledger verification failed: {e}")
                return jsonify({"error": "Ledger verification failed"}), 500

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def register_agent_routes(app_or_bp, db_path):
    """Register reputation and agent payment routes."""
    
    @app_or_bp.route("/reputation/vote", methods=["POST"])
    def reputation_vote():
        """Record an agent upvote, optionally including an RTC microtip."""
        data = request.get_json(silent=True) or {}
        voter_id = data.get("voter_id")
        target_entity = data.get("target_entity")
        donation_nrtc = data.get("donation_nrtc", 0)

        # Finding 4: Length validation
        if voter_id and len(voter_id) > 64:
            return jsonify({"error": "voter_id too long (max 64)"}), 400
        if target_entity and len(target_entity) > 256:
            return jsonify({"error": "target_entity too long (max 256)"}), 400

        if not voter_id or not target_entity:
            return jsonify({"error": "voter_id and target_entity required"}), 400

        # Finding 3: Simple Rate Limiting (check recent votes by this voter)
        now = int(time.time())
        try:
            with sqlite3.connect(db_path) as conn:
                # Limit to 10 votes per hour per voter
                hour_ago = now - 3600
                count = conn.execute("SELECT COUNT(*) FROM reputation_votes WHERE voter_id = ? AND created_at > ?", (voter_id, hour_ago)).fetchone()[0]
                if count >= 10:
                    return jsonify({"error": "Rate limit exceeded (max 10 votes/hour)"}), 429

                tx_id = data.get("tx_id")
                conn.execute("""
                    INSERT INTO reputation_votes (voter_id, target_entity, vote_type, donation_nrtc, tx_id, created_at)
                    VALUES (?, ?, 'upvote', ?, ?, ?)
                """, (voter_id, target_entity, donation_nrtc, tx_id, now))
                conn.commit()
        except Exception as e:
            log.error(f"Database error in reputation_vote: {e}")
            return jsonify({"error": "Database error"}), 500

        return jsonify({
            "ok": True,
            "message": f"Vote recorded for {target_entity}",
            "donation": donation_nrtc,
            "tx_id": tx_id
        })

    @app_or_bp.route("/reputation/stats/<target>", methods=["GET"])
    def reputation_stats(target):
        """Get aggregate upvotes and donations for a target repo or user."""
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("""
                    SELECT COUNT(*), SUM(donation_nrtc) FROM reputation_votes WHERE target_entity = ?
                """, (target,)).fetchone()
            
            return jsonify({
                "target": target,
                "upvotes": row[0],
                "total_donations_nrtc": row[1] or 0
            })
        except Exception as e:
            log.error(f"Database error in reputation_stats: {e}")
            return jsonify({"error": "Database error"}), 500
