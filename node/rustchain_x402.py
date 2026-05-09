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


from .rustchain_x402_core import register_agent_routes, x402_required

def init_app(app, db_path):
    """Register x402 and Reputation routes on the RustChain Flask app."""

    try:
        _run_migration(db_path)
    except Exception as e:
        log.error(f"RustChain x402 migration failed: {e}")

    @app.route("/wallet/swap-info", methods=["GET"])
    def wallet_swap_info():
        return jsonify(SWAP_INFO)

    @app.route("/wallet/link-coinbase", methods=["PATCH", "POST"])
    def wallet_link_coinbase():
        # ... (implementation remains same)
        admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
        expected = os.environ.get("RC_ADMIN_KEY", "")
        if not expected: return jsonify({"error": "Admin key not configured"}), 503
        if admin_key != expected: return jsonify({"error": "Unauthorized — admin key required"}), 401
        data = request.get_json(silent=True) or {}
        miner_id = data.get("miner_id", "").strip()
        coinbase_address = data.get("coinbase_address", "").strip()
        if not miner_id: return jsonify({"error": "miner_id is required"}), 400
        if not coinbase_address or not coinbase_address.startswith("0x") or len(coinbase_address) != 42:
            return jsonify({"error": "Invalid Base address"}), 400
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT miner_id FROM balances WHERE miner_id = ?", (miner_id,)).fetchone()
        if not row: row = conn.execute("SELECT miner_id FROM balances WHERE miner_pk = ?", (miner_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": f"Miner '{miner_id}' not found"}), 404
        conn.execute("UPDATE balances SET coinbase_address = ? WHERE miner_id = ?", (coinbase_address, row[0]))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "miner_id": row[0], "coinbase_address": coinbase_address, "network": "Base"})

    # Register shared agent routes
    register_agent_routes(app, db_path)

    log.info("RustChain x402 module initialized with Agent Payments support")
