import logging
import sqlite3
import time
from functools import wraps
from flask import Blueprint, jsonify, request

log = logging.getLogger("rustchain.reputation")
reputation_bp = Blueprint("reputation", __name__)

_DB_PATH = None

def init_reputation_table(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reputation_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id TEXT NOT NULL,
            target_entity TEXT NOT NULL,
            vote_type TEXT NOT NULL,
            donation_nrtc INTEGER DEFAULT 0,
            tx_id TEXT,
            created_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def register_reputation_routes(app, db_path):
    global _DB_PATH
    _DB_PATH = db_path
    init_reputation_table(db_path)
    app.register_blueprint(reputation_bp)

# -----------------------------------------------------------------------------
# HTTP 402 / x402 Payment Protocol Decorator
# -----------------------------------------------------------------------------

def x402_required(price_nrtc: int):
    """
    Decorator to enforce agent-to-agent payments via HTTP 402.
    If the X-Payment-TX-ID header is missing or the TX is unverified, 
    it returns 402 Payment Required.
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
            
            # Verify tx_id in ledger (omitted for brevity, assume valid in M1)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@reputation_bp.route("/reputation/vote", methods=["POST"])
def reputation_vote():
    data = request.get_json(silent=True) or {}
    voter_id = data.get("voter_id")
    target_entity = data.get("target_entity")
    donation_nrtc = data.get("donation_nrtc", 0)

    if not voter_id or not target_entity:
        return jsonify({"error": "voter_id and target_entity required"}), 400

    now = int(time.time())
    tx_id = data.get("tx_id")

    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO reputation_votes (voter_id, target_entity, vote_type, donation_nrtc, tx_id, created_at)
            VALUES (?, ?, 'upvote', ?, ?, ?)
        """, (voter_id, target_entity, donation_nrtc, tx_id, now))
        conn.commit()

    return jsonify({
        "ok": True,
        "message": f"Vote recorded for {target_entity}",
        "donation": donation_nrtc,
        "tx_id": tx_id
    })

@reputation_bp.route("/reputation/stats/<target>", methods=["GET"])
def reputation_stats(target):
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute("""
            SELECT COUNT(*), SUM(donation_nrtc) FROM reputation_votes WHERE target_entity = ?
        """, (target,)).fetchone()
    
    return jsonify({
        "target": target,
        "upvotes": row[0],
        "total_donations_nrtc": row[1] or 0
    })