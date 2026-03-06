"""
Beacon Atlas x402 Integration Module
Adds Coinbase wallet support for beacon agents and x402 payments on contracts.

Usage in beacon_chat.py:
    import beacon_x402
    beacon_x402.init_app(app, get_db)
"""

import json
import logging
import os
import sqlite3
import time

from flask import g, jsonify, request
from functools import wraps

log = logging.getLogger("beacon.x402")

# --- Optional imports (graceful degradation) ---
try:
    import sys
    sys.path.insert(0, "/root/shared")
    from x402_config import (
        BEACON_TREASURY, FACILITATOR_URL, X402_NETWORK, USDC_BASE,
        PRICE_BEACON_CONTRACT, PRICE_RELAY_REGISTER, PRICE_REPUTATION_EXPORT,
        is_free, has_cdp_credentials, create_agentkit_wallet, SWAP_INFO,
    )
    X402_CONFIG_OK = True
except ImportError:
    log.warning("x402_config not found — x402 features disabled")
    X402_CONFIG_OK = False


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

X402_BEACON_SCHEMA = """
CREATE TABLE IF NOT EXISTS x402_beacon_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payer_address TEXT NOT NULL,
    payer_agent_id TEXT,
    action TEXT NOT NULL,
    amount_usdc TEXT NOT NULL,
    tx_hash TEXT,
    contract_id TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS beacon_wallets (
    agent_id TEXT PRIMARY KEY,
    coinbase_address TEXT,
    created_at REAL NOT NULL
);
"""

RELAY_MIGRATION_SQL = [
    "ALTER TABLE relay_agents ADD COLUMN coinbase_address TEXT DEFAULT NULL",
]


def _run_migrations(db_path):
    """Run x402 migrations on the beacon database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(X402_BEACON_SCHEMA)

    # Add coinbase_address to relay_agents if missing
    cursor = conn.execute("PRAGMA table_info(relay_agents)")
    existing_cols = {row[1] if isinstance(row, tuple) else row["name"]
                     for row in cursor.fetchall()}

    for sql in RELAY_MIGRATION_SQL:
        col_name = sql.split("ADD COLUMN ")[1].split()[0]
        if col_name not in existing_cols:
            try:
                conn.execute(sql)
                log.info(f"Migration: added column {col_name} to relay_agents")
            except sqlite3.OperationalError:
                pass
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# CORS helper (match beacon_chat.py pattern)
# ---------------------------------------------------------------------------

def _cors_json(data, status=200):
    """Return JSON response with CORS headers (matching beacon_chat.py pattern)."""
    resp = jsonify(data) if not isinstance(data, str) else data
    if hasattr(resp, 'headers'):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-PAYMENT"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    return resp, status


# ---------------------------------------------------------------------------
# x402 payment check
# ---------------------------------------------------------------------------

def _check_x402_payment(price_str, action_name):
    """
    Check for x402 payment. Returns (passed, response_or_none).
    When price is "0", always passes.
    """
    if not X402_CONFIG_OK or is_free(price_str):
        return True, None

    payment_header = request.headers.get("X-PAYMENT", "")
    if not payment_header:
        return False, _cors_json({
            "error": "Payment Required",
            "x402": {
                "version": "1",
                "network": X402_NETWORK,
                "facilitator": FACILITATOR_URL,
                "payTo": BEACON_TREASURY,
                "maxAmountRequired": price_str,
                "asset": USDC_BASE,
                "resource": request.url,
                "description": f"Beacon Atlas: {action_name}",
            }
        }, 402)

    # Log payment
    try:
        db = g.get("db")
        if db:
            db.execute(
                "INSERT INTO x402_beacon_payments (payer_address, action, amount_usdc, created_at) "
                "VALUES (?, ?, ?, ?)",
                ("unknown", action_name, price_str, time.time()),
            )
            db.commit()
    except Exception as e:
        log.debug(f"Payment logging failed: {e}")

    return True, None


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def init_app(app, get_db_func):
    """Register x402 routes on the Beacon Atlas Flask app."""

    # Determine DB path from the app's existing config
    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "beacon_atlas.db"
    )

    # Run migrations
    try:
        _run_migrations(db_path)
        log.info("Beacon x402 migrations complete")
    except Exception as e:
        log.error(f"Beacon x402 migration failed: {e}")

    # ---------------------------------------------------------------
    # Wallet Management — Native Agents
    # ---------------------------------------------------------------

    @app.route("/api/agents/<agent_id>/wallet", methods=["POST", "OPTIONS"])
    def set_agent_wallet(agent_id):
        """Set Coinbase wallet for a native beacon agent (admin only)."""
        if request.method == "OPTIONS":
            return _cors_json({"ok": True})

        # Simple admin check — require admin key in header
        admin_key = request.headers.get("X-Admin-Key", "")
        expected = os.environ.get("BEACON_ADMIN_KEY", "beacon_admin_2025")
        if admin_key != expected:
            return _cors_json({"error": "Unauthorized — admin key required"}, 401)

        data = request.get_json(silent=True) or {}
        address = data.get("coinbase_address", "").strip()
        if not address or not address.startswith("0x") or len(address) != 42:
            return _cors_json({"error": "Invalid Base address"}, 400)

        db = get_db_func()
        db.execute(
            """INSERT INTO beacon_wallets (agent_id, coinbase_address, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET coinbase_address = excluded.coinbase_address""",
            (agent_id, address, time.time()),
        )
        db.commit()

        return _cors_json({
            "ok": True,
            "agent_id": agent_id,
            "coinbase_address": address,
            "network": "Base (eip155:8453)",
        })

    @app.route("/api/agents/<agent_id>/wallet", methods=["GET", "OPTIONS"])
    def get_agent_wallet(agent_id):
        """Get a beacon agent's Coinbase wallet info."""
        if request.method == "OPTIONS":
            return _cors_json({"ok": True})

        db = get_db_func()

        # Check beacon_wallets table (native agents)
        row = db.execute(
            "SELECT coinbase_address FROM beacon_wallets WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()

        if row and row["coinbase_address"]:
            return _cors_json({
                "agent_id": agent_id,
                "coinbase_address": row["coinbase_address"],
                "source": "native",
                "network": "Base (eip155:8453)",
                "swap_info": SWAP_INFO if X402_CONFIG_OK else None,
            })

        # Check relay_agents table
        try:
            relay = db.execute(
                "SELECT coinbase_address FROM relay_agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            if relay and relay.get("coinbase_address"):
                return _cors_json({
                    "agent_id": agent_id,
                    "coinbase_address": relay["coinbase_address"],
                    "source": "relay",
                    "network": "Base (eip155:8453)",
                    "swap_info": SWAP_INFO if X402_CONFIG_OK else None,
                })
        except (sqlite3.OperationalError, KeyError):
            pass  # Column may not exist yet

        return _cors_json({
            "agent_id": agent_id,
            "coinbase_address": None,
            "hint": "POST /api/agents/<id>/wallet with admin key to set wallet",
        })

    # ---------------------------------------------------------------
    # Premium Endpoints (x402 paywalled)
    # ---------------------------------------------------------------

    @app.route("/api/premium/reputation", methods=["GET", "OPTIONS"])
    def premium_reputation():
        """Full reputation export for all agents."""
        if request.method == "OPTIONS":
            return _cors_json({"ok": True})

        passed, err_resp = _check_x402_payment(
            PRICE_REPUTATION_EXPORT if X402_CONFIG_OK else "0",
            "reputation_export",
        )
        if not passed:
            return err_resp

        db = get_db_func()
        try:
            rows = db.execute(
                "SELECT * FROM reputation ORDER BY score DESC"
            ).fetchall()
            reputation = [dict(r) for r in rows]
        except sqlite3.OperationalError:
            reputation = []

        return _cors_json({
            "total": len(reputation),
            "reputation": reputation,
            "exported_at": time.time(),
        })

    @app.route("/api/premium/contracts/export", methods=["GET", "OPTIONS"])
    def premium_contracts_export():
        """Full contracts export with payment status."""
        if request.method == "OPTIONS":
            return _cors_json({"ok": True})

        passed, err_resp = _check_x402_payment(
            PRICE_BEACON_CONTRACT if X402_CONFIG_OK else "0",
            "contracts_export",
        )
        if not passed:
            return err_resp

        db = get_db_func()
        rows = db.execute(
            "SELECT * FROM contracts ORDER BY created_at DESC"
        ).fetchall()

        contracts = []
        for r in rows:
            d = dict(r)
            # Check if contract has wallet info
            for field in ("from_agent", "to_agent"):
                agent_id = d.get(field, "")
                wallet_row = db.execute(
                    "SELECT coinbase_address FROM beacon_wallets WHERE agent_id = ?",
                    (agent_id,),
                ).fetchone()
                d[f"{field}_wallet"] = wallet_row["coinbase_address"] if wallet_row else None
            contracts.append(d)

        return _cors_json({
            "total": len(contracts),
            "contracts": contracts,
            "exported_at": time.time(),
        })

    # ---------------------------------------------------------------
    # x402 Payment History
    # ---------------------------------------------------------------

    @app.route("/api/x402/payments", methods=["GET", "OPTIONS"])
    def x402_beacon_payments():
        """View x402 payment history for beacon."""
        if request.method == "OPTIONS":
            return _cors_json({"ok": True})

        db = get_db_func()
        try:
            rows = db.execute(
                "SELECT * FROM x402_beacon_payments ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        return _cors_json({
            "payments": [dict(r) for r in rows],
            "total": len(rows),
        })

    # ---------------------------------------------------------------
    # x402 Status
    # ---------------------------------------------------------------

    @app.route("/api/x402/status", methods=["GET", "OPTIONS"])
    def x402_beacon_status():
        """Public endpoint showing x402 integration status for Beacon Atlas."""
        if request.method == "OPTIONS":
            return _cors_json({"ok": True})

        return _cors_json({
            "x402_enabled": X402_CONFIG_OK,
            "cdp_configured": has_cdp_credentials() if X402_CONFIG_OK else False,
            "network": "Base (eip155:8453)",
            "facilitator": FACILITATOR_URL if X402_CONFIG_OK else None,
            "pricing_mode": "free" if not X402_CONFIG_OK or is_free(
                PRICE_BEACON_CONTRACT if X402_CONFIG_OK else "0"
            ) else "paid",
            "swap_info": SWAP_INFO if X402_CONFIG_OK else None,
            "premium_endpoints": [
                "/api/premium/reputation",
                "/api/premium/contracts/export",
            ],
        })

    log.info("Beacon Atlas x402 module initialized")
