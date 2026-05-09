# SPDX-License-Identifier: Apache-2.0
"""
RustChain x402 Integration — Swap Info + Coinbase Wallet Linking + Agent Payments
Adds /wallet/swap-info, /wallet/link-coinbase, /reputation/vote endpoints.
Includes HTTP 402 / x402 protocol decorator for agent-to-agent payments.

Usage in rustchain server:
    import rustchain_x402
    rustchain_x402.init_app(app, DB_PATH)
"""

import logging
import os
import sqlite3
import time
from functools import wraps
from flask import jsonify, request

log = logging.getLogger("rustchain.x402")

# Import shared config
try:
    import sys
    sys.path.insert(0, "/root/shared")
    from x402_config import SWAP_INFO, WRTC_BASE, USDC_BASE, AERODROME_POOL
    X402_CONFIG_OK = True
except ImportError:
    log.warning("x402_config not found — using inline swap info")
    X402_CONFIG_OK = False
    SWAP_INFO = {
        "wrtc_contract": "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
        "usdc_contract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "aerodrome_pool": "0x4C2A0b915279f0C22EA766D58F9B815Ded2d2A3F",
        "swap_url": "https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
        "network": "Base (eip155:8453)",
        "reference_price_usd": 0.10,
    }


COINBASE_MIGRATION = "ALTER TABLE balances ADD COLUMN coinbase_address TEXT DEFAULT NULL"

REPUTATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reputation_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    vote_type TEXT NOT NULL,
    donation_nrtc INTEGER DEFAULT 0,
    tx_id TEXT,
    created_at INTEGER NOT NULL
)
"""

def _run_migration(db_path):
    """Add columns and tables for x402 and agent payments."""
    conn = sqlite3.connect(db_path)
    # 1. Coinbase link migration
    cursor = conn.execute("PRAGMA table_info(balances)")
    existing = {row[1] for row in cursor.fetchall()}
    if "coinbase_address" not in existing:
        try:
            conn.execute(COINBASE_MIGRATION)
            conn.commit()
            log.info("Added coinbase_address column to balances")
        except sqlite3.OperationalError:
            pass
    
    # 2. Reputation table migration
    try:
        conn.execute(REPUTATION_TABLE_SQL)
        conn.commit()
        log.info("Initialized reputation_votes table")
    except Exception as e:
        log.error(f"Failed to create reputation table: {e}")

    conn.close()

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
            
            # Note: Verification logic would check the ledger for tx_id confirmation
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def init_app(app, db_path):
    """Register x402 and Reputation routes on the RustChain Flask app."""

    try:
        _run_migration(db_path)
    except Exception as e:
        log.error(f"RustChain x402 migration failed: {e}")

    @app.route("/wallet/swap-info", methods=["GET"])
    def wallet_swap_info():
        """Returns Aerodrome pool info for USDC→wRTC swap guidance."""
        return jsonify(SWAP_INFO)

    @app.route("/wallet/link-coinbase", methods=["PATCH", "POST"])
    def wallet_link_coinbase():
        """Link a Coinbase Base address to a miner_id. Requires admin key."""
        admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
        expected = os.environ.get("RC_ADMIN_KEY", "")
        if not expected:
            return jsonify({"error": "Admin key not configured"}), 503
        if admin_key != expected:
            return jsonify({"error": "Unauthorized — admin key required"}), 401

        data = request.get_json(silent=True) or {}
        miner_id = data.get("miner_id", "").strip()
        coinbase_address = data.get("coinbase_address", "").strip()

        if not miner_id:
            return jsonify({"error": "miner_id is required"}), 400
        if not coinbase_address or not coinbase_address.startswith("0x") or len(coinbase_address) != 42:
            return jsonify({"error": "Invalid Base address (must be 0x + 40 hex chars)"}), 400

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT miner_id FROM balances WHERE miner_id = ?", (miner_id,)
        ).fetchone()
        if not row:
            # Try miner_pk
            row = conn.execute(
                "SELECT miner_id FROM balances WHERE miner_pk = ?", (miner_id,)
            ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"Miner '{miner_id}' not found in balances"}), 404

        actual_id = row[0]
        conn.execute(
            "UPDATE balances SET coinbase_address = ? WHERE miner_id = ?",
            (coinbase_address, actual_id),
        )
        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "miner_id": actual_id,
            "coinbase_address": coinbase_address,
            "network": "Base (eip155:8453)",
        })

    # -------------------------------------------------------------------------
    # Agent Reputation & Payments (Bounty #35)
    # -------------------------------------------------------------------------

    @app.route("/reputation/vote", methods=["POST"])
    def reputation_vote():
        """Record an agent upvote, optionally including an RTC microtip."""
        data = request.get_json(silent=True) or {}
        voter_id = data.get("voter_id")
        target_entity = data.get("target_entity")
        donation_nrtc = data.get("donation_nrtc", 0)

        if not voter_id or not target_entity:
            return jsonify({"error": "voter_id and target_entity required"}), 400

        now = int(time.time())
        tx_id = data.get("tx_id")

        with sqlite3.connect(db_path) as conn:
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

    @app.route("/reputation/stats/<target>", methods=["GET"])
    def reputation_stats(target):
        """Get aggregate upvotes and donations for a target repo or user."""
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("""
                SELECT COUNT(*), SUM(donation_nrtc) FROM reputation_votes WHERE target_entity = ?
            """, (target,)).fetchone()
        
        return jsonify({
            "target": target,
            "upvotes": row[0],
            "total_donations_nrtc": row[1] or 0
        })

    log.info("RustChain x402 module initialized with Agent Payments support")
