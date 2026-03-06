"""
RustChain x402 Integration — Swap Info + Coinbase Wallet Linking
Adds /wallet/swap-info and /wallet/link-coinbase endpoints.

Usage in rustchain server:
    import rustchain_x402
    rustchain_x402.init_app(app, DB_PATH)
"""

import logging
import os
import sqlite3
import time

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


def _run_migration(db_path):
    """Add coinbase_address column to balances if missing."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(balances)")
    existing = {row[1] for row in cursor.fetchall()}
    if "coinbase_address" not in existing:
        try:
            conn.execute(COINBASE_MIGRATION)
            conn.commit()
            log.info("Added coinbase_address column to balances")
        except sqlite3.OperationalError:
            pass
    conn.close()


def init_app(app, db_path):
    """Register x402 routes on the RustChain Flask app."""

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
        expected = os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64")
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

    log.info("RustChain x402 module initialized")
