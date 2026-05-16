"""
wRTC Solana Bridge Dashboard API
Real-time data endpoints for the bridge monitoring dashboard

Extends bridge_api.py with dashboard-specific endpoints:
- GET /bridge/dashboard/metrics - Aggregated metrics for dashboard
- GET /bridge/dashboard/health - Bridge health status
- GET /bridge/dashboard/transactions - Recent transactions with filtering
- GET /bridge/dashboard/price - wRTC price data from Raydium/DexScreener
- GET /bridge/dashboard/chart - Historical price chart data

Part of Bounty #2303: wRTC Solana Bridge Dashboard
"""

import os
import json
import time
from flask import Blueprint, jsonify, request

# Import from main bridge API
from bridge.bridge_api import get_db, _amount_from_base, STATE_COMPLETE

# ─── Config ──────────────────────────────────────────────────────────────────
DASHBOARD_DB_PATH = os.environ.get("DASHBOARD_DB_PATH", "bridge_ledger.db")
SOLANA_RPC_URL = os.environ.get(
    "SOLANA_RPC_URL",
    "https://api.mainnet-beta.solana.com"
)
RAYDIUM_API_URL = os.environ.get("RAYDIUM_API_URL", "https://api.raydium.io")
DEXSCREENER_API_URL = os.environ.get("DEXSCREENER_API_URL", "https://api.dexscreener.com")
WRTC_MINT_ADDRESS = os.environ.get("WRTC_MINT_ADDRESS", "")

# Cache configuration (in-memory for simplicity)
CACHE_TTL = 30  # seconds
_price_cache = {"data": None, "timestamp": 0}

# ─── Blueprint ────────────────────────────────────────────────────────────────
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/bridge/dashboard")


# ─── API Endpoints ────────────────────────────────────────────────────────────

@dashboard_bp.route("/metrics", methods=["GET"])
def get_dashboard_metrics():
    """
    Get aggregated metrics for the dashboard.

    Returns:
    {
        "total_locked_rtc": float,
        "wrtc_circulating": float,
        "fee_revenue": float,
        "locked_change_24h": float,
        "circulating_change_24h": float,
        "total_transactions": int,
        "last_updated": int
    }
    """
    now = int(time.time())
    day_ago = now - 86400

    with get_db() as conn:
        # Total locked (all-time)
        total_row = conn.execute(
            "SELECT COALESCE(SUM(amount_rtc), 0) FROM bridge_locks WHERE state = ?",
            (STATE_COMPLETE,)
        ).fetchone()
        total_locked = _amount_from_base(total_row[0]) if total_row else 0

        # Locked 24h ago
        locked_24h_row = conn.execute(
            """
            SELECT COALESCE(SUM(amount_rtc), 0) FROM bridge_locks
            WHERE state = ? AND created_at < ?
            """,
            (STATE_COMPLETE, day_ago)
        ).fetchone()
        locked_24h = _amount_from_base(locked_24h_row[0]) if locked_24h_row else 0

        # wRTC circulating (Solana only, completed)
        wrtc_row = conn.execute(
            """
            SELECT COALESCE(SUM(amount_rtc), 0) FROM bridge_locks
            WHERE target_chain = 'solana' AND state = ?
            """,
            (STATE_COMPLETE,)
        ).fetchone()
        wrtc_circulating = _amount_from_base(wrtc_row[0]) if wrtc_row else 0

        # Fee revenue (0.1% of total bridged)
        fee_revenue = total_locked * 0.001

        # Total transactions
        total_txs = conn.execute(
            "SELECT COUNT(*) FROM bridge_locks WHERE state = ?",
            (STATE_COMPLETE,)
        ).fetchone()[0]

    # Calculate percentage changes
    locked_change_24h = ((total_locked - locked_24h) / locked_24h * 100) if locked_24h > 0 else 0
    circulating_change_24h = locked_change_24h  # Same as locked for simplicity

    return jsonify({
        "total_locked_rtc": total_locked,
        "wrtc_circulating": wrtc_circulating,
        "fee_revenue": fee_revenue,
        "locked_change_24h": round(locked_change_24h, 2),
        "circulating_change_24h": round(circulating_change_24h, 2),
        "total_transactions": total_txs,
        "last_updated": now,
    })


@dashboard_bp.route("/health", methods=["GET"])
def get_bridge_health():
    """
    Get comprehensive bridge health status.

    Checks:
    - RustChain node health
    - Solana RPC connectivity
    - Bridge API status
    - wRTC mint account status

    Returns:
    {
        "overall": "healthy" | "degraded" | "offline",
        "components": {
            "rustchain": true,
            "solana_rpc": true,
            "bridge_api": true,
            "wrtc_mint": true
        },
        "details": {...},
        "last_checked": int
    }
    """
    import urllib.request
    import urllib.error
    
    health = {
        "rustchain": False,
        "solana_rpc": False,
        "bridge_api": False,
        "wrtc_mint": False,
    }
    details = {}

    # Check RustChain node (self-check)
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        health["rustchain"] = True
        details["rustchain"] = "Database accessible"
    except Exception as e:
        details["rustchain"] = f"Database error: {str(e)}"

    # Check Solana RPC (sync version)
    try:
        req = urllib.request.Request(
            SOLANA_RPC_URL,
            data=json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getHealth"
            }).encode('utf-8'),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result and "result" in result:
                health["solana_rpc"] = True
                details["solana_rpc"] = "RPC responsive"
            else:
                details["solana_rpc"] = "RPC returned unexpected response"
    except Exception as e:
        details["solana_rpc"] = f"RPC error: {str(e)}"

    # Bridge API is healthy if we got here
    health["bridge_api"] = True
    details["bridge_api"] = "API operational"

    # Check wRTC mint account (if configured, sync version)
    if WRTC_MINT_ADDRESS:
        try:
            req = urllib.request.Request(
                SOLANA_RPC_URL,
                data=json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAccountInfo",
                    "params": [WRTC_MINT_ADDRESS, {"encoding": "jsonParsed"}]
                }).encode('utf-8'),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result and result.get("result", {}).get("value"):
                    health["wrtc_mint"] = True
                    details["wrtc_mint"] = "Mint account exists"
                else:
                    details["wrtc_mint"] = "Mint account not found"
        except Exception as e:
            details["wrtc_mint"] = f"Mint check error: {str(e)}"
    else:
        health["wrtc_mint"] = True  # Skip if not configured
        details["wrtc_mint"] = "Mint address not configured"

    # Determine overall health
    healthy_count = sum(1 for v in health.values() if v)
    if healthy_count == len(health):
        overall = "healthy"
    elif healthy_count > 0:
        overall = "degraded"
    else:
        overall = "offline"

    return jsonify({
        "overall": overall,
        "components": health,
        "details": details,
        "last_checked": int(time.time()),
    })


@dashboard_bp.route("/transactions", methods=["GET"])
def get_dashboard_transactions():
    """
    Get recent transactions for dashboard display.

    Query params:
    - type: 'wrap' | 'unwrap' | 'all' (default: 'all')
    - limit: max results (default: 50, max: 200)
    - state: filter by state (optional)

    Returns:
    {
        "transactions": [...],
        "wrap_count": int,
        "unwrap_count": int,
        "total_volume_24h": float
    }
    """
    tx_type = request.args.get("type", "all").lower()
    if tx_type not in ("all", "wrap", "unwrap"):
        return jsonify({"error": "type must be one of: all, wrap, unwrap"}), 400

    state_filter = request.args.get("state", "").strip() or None
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    limit = max(1, min(limit, 200))

    now = int(time.time())
    day_ago = now - 86400

    with get_db() as conn:
        # Build query
        where_clauses = []
        params = []

        if state_filter:
            where_clauses.append("state = ?")
            params.append(state_filter)
        if tx_type == "wrap":
            where_clauses.append("target_chain = ?")
            params.append("solana")
        elif tx_type == "unwrap":
            where_clauses.append("target_chain = ?")
            params.append("base")

        # Calculate 24h volume
        volume_row = conn.execute(
            """
            SELECT COALESCE(SUM(amount_rtc), 0) FROM bridge_locks
            WHERE state = ? AND created_at > ?
            """,
            (STATE_COMPLETE, day_ago)
        ).fetchone()
        total_volume_24h = _amount_from_base(volume_row[0]) if volume_row else 0

        # Get transactions
        query = """
        SELECT lock_id, sender_wallet, amount_rtc, target_chain, target_wallet,
               state, tx_hash, release_tx, created_at, updated_at
        FROM bridge_locks
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

        # Count wraps and unwraps
        wrap_count = conn.execute(
            "SELECT COUNT(*) FROM bridge_locks WHERE target_chain = 'solana'"
        ).fetchone()[0]
        unwrap_count = conn.execute(
            "SELECT COUNT(*) FROM bridge_locks WHERE target_chain = 'base'"
        ).fetchone()[0]

    transactions = [
        {
            "lock_id": r["lock_id"],
            "sender_wallet": r["sender_wallet"],
            "amount_rtc": _amount_from_base(r["amount_rtc"]),
            "target_chain": r["target_chain"],
            "target_wallet": r["target_wallet"],
            "state": r["state"],
            "tx_hash": r["tx_hash"],
            "release_tx": r["release_tx"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "type": "wrap" if r["target_chain"] == "solana" else "unwrap",
        }
        for r in rows
    ]

    return jsonify({
        "transactions": transactions,
        "wrap_count": wrap_count,
        "unwrap_count": unwrap_count,
        "total_volume_24h": round(total_volume_24h, 2),
    })


@dashboard_bp.route("/price", methods=["GET"])
def get_wrtc_price():
    """
    Get wRTC price data from Raydium or DexScreener.

    Returns:
    {
        "price_usd": float,
        "price_sol": float,
        "change_24h": float,
        "volume_24h": float,
        "liquidity": float,
        "source": "raydium" | "dexscreener",
        "last_updated": int
    }
    """
    import urllib.request
    import urllib.error
    
    if not WRTC_MINT_ADDRESS:
        return jsonify({
            "error": "WRTC_MINT_ADDRESS not configured",
            "price_usd": 0,
            "source": "none",
        }), 503

    # Try Raydium first
    if RAYDIUM_API_URL:
        raydium_url = f"{RAYDIUM_API_URL}/v2/ammV3/pools?address={WRTC_MINT_ADDRESS}"
        try:
            req = urllib.request.Request(raydium_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result and result.get("data"):
                    pool_data = result["data"][0] if result.get("data") else None
                    if pool_data:
                        price = float(pool_data.get("price", 0))
                        price_change = float(pool_data.get("priceChange", {}).get("percent24h", 0))
                        volume = float(pool_data.get("volume", {}).get("quote24h", 0))
                        liquidity = float(pool_data.get("liquidity", {}).get("quote", 0))

                        return jsonify({
                            "price_usd": price,
                            "price_sol": price,
                            "change_24h": round(price_change, 2),
                            "volume_24h": round(volume, 2),
                            "liquidity": round(liquidity, 2),
                            "source": "raydium",
                            "last_updated": int(time.time()),
                        })
        except Exception as e:
            print(f"[dashboard] Raydium fetch error: {e}")

    # Fallback to DexScreener
    if DEXSCREENER_API_URL:
        dex_url = f"{DEXSCREENER_API_URL}/latest/dex/tokens/{WRTC_MINT_ADDRESS}"
        try:
            req = urllib.request.Request(dex_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result and result.get("pairs"):
                    pair = result["pairs"][0]
                    price = float(pair.get("priceUsd", 0))
                    price_change = float(pair.get("priceChange", {}).get("h24", 0))
                    volume = float(pair.get("volume", {}).get("h24", 0))
                    liquidity = float(pair.get("liquidity", {}).get("usd", 0))

                    return jsonify({
                        "price_usd": price,
                        "price_sol": float(pair.get("priceNative", 0)),
                        "change_24h": round(price_change, 2),
                        "volume_24h": round(volume, 2),
                        "liquidity": round(liquidity, 2),
                        "source": "dexscreener",
                        "last_updated": int(time.time()),
                    })
        except Exception as e:
            print(f"[dashboard] DexScreener fetch error: {e}")

    return jsonify({
        "price_usd": 0,
        "change_24h": 0,
        "volume_24h": 0,
        "liquidity": 0,
        "source": "none",
        "last_updated": int(time.time()),
    }), 404


@dashboard_bp.route("/chart", methods=["GET"])
def get_price_chart_data():
    """
    Get historical price data for charting.

    Query params:
    - period: '1h' | '24h' | '7d' | '30d' (default: '24h')

    Returns array of {timestamp, price, volume} points.
    """
    period = request.args.get("period", "24h").lower()
    period_seconds = {
        "1h": 3600,
        "24h": 86400,
        "7d": 604800,
        "30d": 2592000,
    }.get(period, 86400)

    now = int(time.time())
    start_time = now - period_seconds

    # Generate mock chart data (in production, this would come from a price oracle)
    # For now, return simulated data points
    import random
    base_price = 0.001  # Mock base price

    points = []
    interval = period_seconds // 50  # 50 data points
    for i in range(50):
        timestamp = start_time + (i * interval)
        # Random walk with slight upward trend
        price = base_price * (1 + random.uniform(-0.05, 0.05) + (i / 50) * 0.02)
        volume = random.uniform(1000, 10000)
        points.append({
            "timestamp": timestamp,
            "price": round(price, 8),
            "volume": round(volume, 2),
        })

    return jsonify(points)


# ─── Integration ──────────────────────────────────────────────────────────────
def register_dashboard_routes(app):
    """Register dashboard blueprint with an existing Flask app."""
    app.register_blueprint(dashboard_bp)
    print("[dashboard] wRTC Bridge Dashboard endpoints registered at /bridge/dashboard/*")
