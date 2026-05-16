"""
RustChain x402 Integration — Swap Info + Coinbase Wallet Linking
Adds /wallet/swap-info and /wallet/link-coinbase endpoints.

Usage in rustchain server:
    import rustchain_x402
    rustchain_x402.init_app(app, DB_PATH)
"""

import hmac
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


def _json_object_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON object body is required"}), 400)
    return data, None


def _json_string_field(data, field_name, default=""):
    value = data.get(field_name, default)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


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
        expected = os.environ.get("RC_ADMIN_KEY", "")
        if not expected:
            return jsonify({"error": "Admin key not configured"}), 503
        if not hmac.compare_digest(admin_key, expected):
            return jsonify({"error": "Unauthorized — admin key required"}), 401

        data, error_response = _json_object_body()
        if error_response:
            return error_response
        try:
            miner_id = _json_string_field(data, "miner_id")
            coinbase_address = _json_string_field(data, "coinbase_address")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

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
