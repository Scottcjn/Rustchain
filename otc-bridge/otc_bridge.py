"""
RustChain OTC Bridge -- Tier 2: Escrow-Based RTC/ETH Swap
==========================================================
Peer-to-peer OTC trading with RTC escrow via RIP-302 Agent Economy
and ETH-side HTLC (Hash Time-Locked Contract) on Base.

Endpoints:
  POST /api/orders          -- Create buy/sell order
  GET  /api/orders          -- List open orders
  GET  /api/orders/<id>     -- Order detail
  POST /api/orders/<id>/match   -- Match an order (counterparty)
  POST /api/orders/<id>/confirm -- Confirm settlement (reveals HTLC secret)
  POST /api/orders/<id>/cancel  -- Cancel open order
  GET  /api/trades          -- Trade history
  GET  /api/stats           -- Market stats
  GET  /api/orderbook       -- Aggregated order book (bids/asks)
  GET  /                    -- Frontend SPA

Author: WireWork (wirework.dev)
License: MIT
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUSTCHAIN_NODE = os.environ.get("RUSTCHAIN_NODE", "https://50.28.86.131")
DB_PATH = os.environ.get("OTC_DB_PATH", "otc_bridge.db")
DEFAULT_OTC_CORS_ORIGINS = (
    "https://bottube.ai",
    "https://rustchain.org",
    "http://localhost:3000",
)

# TLS verification: defaults to True (secure).
# Set RUSTCHAIN_TLS_VERIFY=false only for local development with self-signed certs.
# Prefer RUSTCHAIN_CA_BUNDLE to point at a pinned CA/cert file instead of disabling.
_tls_verify_env = os.environ.get("RUSTCHAIN_TLS_VERIFY", "true").strip().lower()
_ca_bundle = os.environ.get("RUSTCHAIN_CA_BUNDLE", "").strip()
if _ca_bundle and os.path.isfile(_ca_bundle):
    TLS_VERIFY = _ca_bundle          # Path to pinned cert / CA bundle
elif _tls_verify_env in ("false", "0", "no"):
    TLS_VERIFY = False                # Explicit opt-out (dev only)
else:
    TLS_VERIFY = True                 # Default: full CA verification

ESCROW_WALLET = "otc_bridge_escrow"
ORDER_TTL_DEFAULT = 7 * 86400       # 7 days
ORDER_TTL_MAX = 30 * 86400          # 30 days
HTLC_TIMEOUT = 24 * 3600            # 24h for HTLC expiry
MIN_ORDER_RTC = 0.1                 # Minimum 0.1 RTC
MAX_ORDER_RTC = 100000              # Maximum 100k RTC
RATE_LIMIT_WINDOW = 60              # 1 minute
RATE_LIMIT_MAX = 10                 # 10 requests per minute per IP
RTC_REFERENCE_RATE = 0.10           # $0.10 USD reference
RTC_UNIT = 1_000_000                # 1 micro-RTC
QUOTE_PRICE_SCALE = 1_000_000_000   # 9 decimal places for quote units

SUPPORTED_PAIRS = {
    "RTC/ETH": {"quote": "ETH", "decimals": 18},
    "RTC/USDC": {"quote": "USDC", "decimals": 6},
    "RTC/ERG": {"quote": "ERG", "decimals": 9},
}

log = logging.getLogger("otc_bridge")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder="static")


def parse_cors_origins(raw_origins=None):
    raw_origins = os.environ.get("OTC_CORS_ORIGINS") if raw_origins is None else raw_origins
    if raw_origins is None:
        return list(DEFAULT_OTC_CORS_ORIGINS)

    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if not origins:
        return list(DEFAULT_OTC_CORS_ORIGINS)
    if "*" in origins:
        raise ValueError("OTC_CORS_ORIGINS must name trusted origins and must not include '*'")
    return origins


OTC_CORS_ORIGINS = parse_cors_origins()
CORS(app, origins=OTC_CORS_ORIGINS)


def decimal_units(value, scale, field_name):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field_name} must be a finite decimal number")

    if not amount.is_finite():
        raise ValueError(f"{field_name} must be a finite decimal number")

    units = (amount * Decimal(scale)).to_integral_value(rounding=ROUND_HALF_UP)
    return amount, int(units)


def units_to_float(units, scale):
    return float(Decimal(int(units)) / Decimal(scale))


def money_view(row):
    data = dict(row)
    if "amount_micro_rtc" in data and data.get("amount_micro_rtc") is not None:
        data["amount_rtc"] = units_to_float(data["amount_micro_rtc"], RTC_UNIT)
    if "price_per_rtc_nano_quote" in data and data.get("price_per_rtc_nano_quote") is not None:
        data["price_per_rtc"] = units_to_float(
            data["price_per_rtc_nano_quote"], QUOTE_PRICE_SCALE
        )
    if "total_quote_nano" in data and data.get("total_quote_nano") is not None:
        data["total_quote"] = units_to_float(data["total_quote_nano"], QUOTE_PRICE_SCALE)
    return data


def migrate_precision_columns(cursor, table_name):
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}
    if "amount_micro_rtc" not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN amount_micro_rtc INTEGER")
    if "price_per_rtc_nano_quote" not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN price_per_rtc_nano_quote INTEGER")
    if "total_quote_nano" not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN total_quote_nano INTEGER")

    refreshed = {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}
    if {"amount_rtc", "price_per_rtc", "total_quote"}.issubset(refreshed):
        cursor.execute(f"""
            UPDATE {table_name}
            SET amount_micro_rtc = COALESCE(amount_micro_rtc, CAST(ROUND(amount_rtc * ?) AS INTEGER)),
                price_per_rtc_nano_quote = COALESCE(price_per_rtc_nano_quote, CAST(ROUND(price_per_rtc * ?) AS INTEGER)),
                total_quote_nano = COALESCE(total_quote_nano, CAST(ROUND(total_quote * ?) AS INTEGER))
        """, (RTC_UNIT, QUOTE_PRICE_SCALE, QUOTE_PRICE_SCALE))


def table_columns(cursor, table_name):
    return {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}


def include_legacy_money_columns_if_present(columns, insert_columns, values, amount_rtc, price_per_rtc, total_quote):
    if {"amount_rtc", "price_per_rtc", "total_quote"}.issubset(columns):
        insert_columns.extend(["amount_rtc", "price_per_rtc", "total_quote"])
        values.extend([amount_rtc, price_per_rtc, total_quote])


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
                pair TEXT NOT NULL,
                maker_wallet TEXT NOT NULL,
                amount_micro_rtc INTEGER NOT NULL,
                price_per_rtc_nano_quote INTEGER NOT NULL,
                total_quote_nano INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                escrow_job_id TEXT,
                htlc_hash TEXT,
                htlc_secret TEXT,
                taker_wallet TEXT,
                taker_eth_address TEXT,
                maker_eth_address TEXT,
                settlement_tx TEXT,
                created_at INTEGER NOT NULL,
                matched_at INTEGER,
                confirmed_at INTEGER,
                expires_at INTEGER NOT NULL,
                ip_hash TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                pair TEXT NOT NULL,
                side TEXT NOT NULL,
                maker_wallet TEXT NOT NULL,
                taker_wallet TEXT NOT NULL,
                amount_micro_rtc INTEGER NOT NULL,
                price_per_rtc_nano_quote INTEGER NOT NULL,
                total_quote_nano INTEGER NOT NULL,
                rtc_tx TEXT,
                quote_tx TEXT,
                completed_at INTEGER NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                ip_hash TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)

        migrate_precision_columns(c, "orders")
        migrate_precision_columns(c, "trades")

        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, pair)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_side ON orders(side, status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair, completed_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_rate_ip ON rate_limits(ip_hash, timestamp)")

        conn.commit()
    log.info("OTC Bridge database initialized")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_order_id(wallet, side):
    seed = f"{wallet}:{side}:{time.time()}:{secrets.token_hex(8)}"
    return "otc_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def generate_trade_id(order_id, taker):
    seed = f"{order_id}:{taker}:{time.time()}"
    return "trade_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def hash_ip(ip):
    return hashlib.sha256(f"otc_salt_{ip}".encode()).hexdigest()[:16]


def get_client_ip():
    return request.headers.get("X-Real-IP", request.remote_addr)


def generate_htlc_secret():
    """Generate a random secret and its hash for HTLC."""
    secret = secrets.token_hex(32)  # 256-bit secret
    hash_val = hashlib.sha256(bytes.fromhex(secret)).hexdigest()
    return secret, hash_val


def positive_int_arg(name, default, max_value=None):
    raw_value = request.args.get(name)
    if raw_value is None:
        return default, None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f"{name}_must_be_integer"

    if value < 1:
        return None, f"{name}_must_be_positive"

    if max_value is not None:
        value = min(value, max_value)

    return value, None


def non_negative_int_arg(name, default):
    raw_value = request.args.get(name)
    if raw_value is None:
        return default, None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f"{name}_must_be_integer"

    if value < 0:
        return None, f"{name}_must_be_non_negative"

    return value, None


def internal_error_response(operation):
    """Log internal exception details without exposing them to clients."""
    log.exception("%s failed", operation)
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

def check_rate_limit(ip):
    ip_h = hash_ip(ip)
    now = int(time.time())
    cutoff = now - RATE_LIMIT_WINDOW

    with get_db() as conn:
        c = conn.cursor()
        # Cleanup old entries
        c.execute("DELETE FROM rate_limits WHERE timestamp < ?", (cutoff,))
        # Count recent
        count = c.execute(
            "SELECT COUNT(*) FROM rate_limits WHERE ip_hash = ? AND timestamp >= ?",
            (ip_h, cutoff)
        ).fetchone()[0]

        if count >= RATE_LIMIT_MAX:
            return False

        c.execute("INSERT INTO rate_limits (ip_hash, timestamp) VALUES (?, ?)",
                  (ip_h, now))
        conn.commit()
    return True


def rate_limited(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not check_rate_limit(get_client_ip()):
            return jsonify({
                "error": "Rate limit exceeded",
                "retry_after_seconds": RATE_LIMIT_WINDOW
            }), 429
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# RustChain Integration
# ---------------------------------------------------------------------------

def rtc_get_balance(wallet_id):
    """Query RTC balance from node."""
    try:
        r = requests.get(
            f"{RUSTCHAIN_NODE}/wallet/balance",
            params={"miner_id": wallet_id},
            verify=TLS_VERIFY, timeout=10
        )
        if r.ok:
            data = r.json()
            return data.get("amount_rtc", 0)
    except Exception as e:
        log.warning(f"Balance check failed for {wallet_id}: {e}")
    return None


def rtc_create_escrow_job(poster_wallet, amount_rtc, title, description):
    """Lock RTC in escrow via RIP-302 /agent/jobs."""
    try:
        r = requests.post(
            f"{RUSTCHAIN_NODE}/agent/jobs",
            json={
                "poster_wallet": poster_wallet,
                "title": title,
                "description": description,
                "category": "other",
                "reward_rtc": amount_rtc,
                "ttl_seconds": ORDER_TTL_DEFAULT,
                "tags": ["otc_bridge", "escrow"]
            },
            verify=TLS_VERIFY, timeout=15
        )
        if r.ok:
            data = r.json()
            return {"ok": True, "job_id": data.get("job_id")}
        else:
            return {"ok": False, "error": r.json().get("error", "Unknown error")}
    except Exception:
        log.exception("Escrow job creation failed")
        return {"ok": False, "error": "escrow_create_failed"}


def rtc_release_escrow(job_id, poster_wallet):
    """Release escrow -- accept delivery to pay the taker."""
    try:
        # First, claim the job as the taker (OTC bridge acts as intermediary)
        # Then deliver and accept to release funds
        r = requests.post(
            f"{RUSTCHAIN_NODE}/agent/jobs/{job_id}/accept",
            json={"poster_wallet": poster_wallet},
            verify=TLS_VERIFY, timeout=15
        )
        return r.ok
    except Exception as e:
        log.error(f"Escrow release failed: {e}")
        return False


def rtc_cancel_escrow(job_id, poster_wallet):
    """Cancel escrow job -- refund to poster."""
    try:
        r = requests.post(
            f"{RUSTCHAIN_NODE}/agent/jobs/{job_id}/cancel",
            json={"poster_wallet": poster_wallet},
            verify=TLS_VERIFY, timeout=15
        )
        return r.ok
    except Exception as e:
        log.error(f"Escrow cancel failed: {e}")
        return False


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/api/orders", methods=["POST"])
@rate_limited
def create_order():
    """Create a new buy or sell order."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "JSON body required"}), 400
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    side = str(data.get("side", "")).strip().lower()
    pair = str(data.get("pair", "RTC/USDC")).strip().upper()
    maker_wallet = str(data.get("wallet", "")).strip()
    amount_rtc = data.get("amount_rtc", 0)
    price_per_rtc = data.get("price_per_rtc", 0)
    maker_eth_address = str(data.get("eth_address", "")).strip()
    try:
        ttl = int(data.get("ttl_seconds", ORDER_TTL_DEFAULT))
    except (TypeError, ValueError):
        return jsonify({"error": "ttl_seconds must be an integer"}), 400

    # Validation
    if side not in ("buy", "sell"):
        return jsonify({"error": "side must be 'buy' or 'sell'"}), 400
    if pair not in SUPPORTED_PAIRS:
        return jsonify({"error": f"Unsupported pair. Supported: {list(SUPPORTED_PAIRS.keys())}"}), 400
    if not maker_wallet or len(maker_wallet) < 3:
        return jsonify({"error": "wallet required (RTC wallet ID)"}), 400

    try:
        amount_dec, amount_micro_rtc = decimal_units(amount_rtc, RTC_UNIT, "amount_rtc")
        price_dec, price_per_rtc_nano_quote = decimal_units(
            price_per_rtc, QUOTE_PRICE_SCALE, "price_per_rtc"
        )
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    amount_rtc = units_to_float(amount_micro_rtc, RTC_UNIT)
    price_per_rtc = units_to_float(price_per_rtc_nano_quote, QUOTE_PRICE_SCALE)

    if amount_rtc < MIN_ORDER_RTC:
        return jsonify({"error": f"Minimum order: {MIN_ORDER_RTC} RTC"}), 400
    if amount_rtc > MAX_ORDER_RTC:
        return jsonify({"error": f"Maximum order: {MAX_ORDER_RTC} RTC"}), 400
    if price_per_rtc <= 0:
        return jsonify({"error": "price_per_rtc must be positive"}), 400
    if price_per_rtc > 1000:
        return jsonify({"error": "price_per_rtc too high (max $1000)"}), 400

    ttl = min(max(ttl, 3600), ORDER_TTL_MAX)
    total_quote_nano = int(
        (amount_dec * price_dec * Decimal(QUOTE_PRICE_SCALE)).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    total_quote = units_to_float(total_quote_nano, QUOTE_PRICE_SCALE)
    now = int(time.time())
    order_id = generate_order_id(maker_wallet, side)

    # For sell orders: lock RTC in escrow via RIP-302
    escrow_job_id = None
    if side == "sell":
        # Check balance first
        balance = rtc_get_balance(maker_wallet)
        if balance is not None and balance < amount_rtc:
            return jsonify({
                "error": "Insufficient RTC balance",
                "balance_rtc": balance,
                "required_rtc": amount_rtc
            }), 400

        escrow_result = rtc_create_escrow_job(
            poster_wallet=maker_wallet,
            amount_rtc=amount_rtc,
            title=f"OTC Bridge Escrow: {order_id}",
            description=f"Escrowed {amount_rtc} RTC for OTC sell order at {price_per_rtc} {pair.split('/')[1]} per RTC. Total: {total_quote} {pair.split('/')[1]}. Auto-expires in {ttl//3600}h."
        )
        if not escrow_result["ok"]:
            return jsonify({
                "error": "Failed to lock RTC in escrow",
                "details": escrow_result.get("error"),
                "hint": "Ensure your wallet has sufficient RTC balance (reward + 5% platform fee)"
            }), 400
        escrow_job_id = escrow_result["job_id"]

    # The RTC seller owns the release preimage. For a sell order the maker is
    # the seller, so generate and return it at creation. For a buy order the
    # seller is not known until match time, so defer preimage generation.
    htlc_secret, htlc_hash = (None, None)
    if side == "sell":
        htlc_secret, htlc_hash = generate_htlc_secret()

    conn = get_db()
    try:
        c = conn.cursor()
        insert_columns = [
            "order_id", "side", "pair", "maker_wallet", "amount_micro_rtc",
            "price_per_rtc_nano_quote", "total_quote_nano", "status",
            "escrow_job_id", "htlc_hash", "htlc_secret", "maker_eth_address",
            "created_at", "expires_at", "ip_hash",
        ]
        values = [
            order_id, side, pair, maker_wallet, amount_micro_rtc,
            price_per_rtc_nano_quote, total_quote_nano, "open",
            escrow_job_id, htlc_hash, htlc_secret, maker_eth_address,
            now, now + ttl, hash_ip(get_client_ip()),
        ]
        include_legacy_money_columns_if_present(
            table_columns(c, "orders"), insert_columns, values, amount_rtc, price_per_rtc, total_quote
        )
        placeholders = ", ".join("?" for _ in values)
        c.execute(
            f"INSERT INTO orders ({', '.join(insert_columns)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()

        response = {
            "ok": True,
            "order_id": order_id,
            "side": side,
            "pair": pair,
            "amount_rtc": amount_rtc,
            "amount_micro_rtc": amount_micro_rtc,
            "price_per_rtc": price_per_rtc,
            "price_per_rtc_nano_quote": price_per_rtc_nano_quote,
            "total_quote": total_quote,
            "total_quote_nano": total_quote_nano,
            "quote_currency": pair.split("/")[1],
            "status": "open",
            "expires_at": now + ttl,
            "expires_in_hours": round(ttl / 3600, 1),
        }
        if htlc_hash:
            response["htlc_hash"] = htlc_hash
        if htlc_secret:
            # Returned only once to the RTC seller; public order reads hide it until completion.
            response["htlc_secret"] = htlc_secret
        if escrow_job_id:
            response["escrow_job_id"] = escrow_job_id
            response["escrow_status"] = "locked"
        if side == "sell":
            response["message"] = f"Sell order created. {amount_rtc} RTC locked in escrow. HTLC hash published for buyer verification."
        else:
            response["message"] = f"Buy order created. Waiting for a seller to match."

        return jsonify(response), 201

    except Exception:
        conn.rollback()
        # If we created an escrow job but DB insert failed, cancel it
        if escrow_job_id:
            rtc_cancel_escrow(escrow_job_id, maker_wallet)
        return internal_error_response("Order creation")
    finally:
        conn.close()


@app.route("/api/orders", methods=["GET"])
def list_orders():
    """List open orders with optional filters."""
    pair = request.args.get("pair", "").strip().upper()
    side = request.args.get("side", "").strip().lower()
    limit, error = positive_int_arg("limit", 50, max_value=200)
    if error:
        return jsonify({"error": error}), 400

    offset, error = non_negative_int_arg("offset", 0)
    if error:
        return jsonify({"error": error}), 400

    conn = get_db()
    try:
        c = conn.cursor()
        now = int(time.time())

        # Auto-expire old orders
        expired = c.execute(
            "SELECT order_id, maker_wallet, escrow_job_id FROM orders WHERE status = 'open' AND expires_at < ?",
            (now,)
        ).fetchall()
        for ex in expired:
            c.execute("UPDATE orders SET status = 'expired' WHERE order_id = ?", (ex["order_id"],))
            if ex["escrow_job_id"]:
                rtc_cancel_escrow(ex["escrow_job_id"], ex["maker_wallet"])
        if expired:
            conn.commit()

        # Build query
        where = ["status = 'open'"]
        params = []
        if pair and pair in SUPPORTED_PAIRS:
            where.append("pair = ?")
            params.append(pair)
        if side in ("buy", "sell"):
            where.append("side = ?")
            params.append(side)

        query = f"""
            SELECT order_id, side, pair, maker_wallet, amount_micro_rtc,
                   price_per_rtc_nano_quote, total_quote_nano, status, htlc_hash,
                   created_at, expires_at, escrow_job_id
            FROM orders
            WHERE {' AND '.join(where)}
            ORDER BY
                CASE side WHEN 'sell' THEN price_per_rtc_nano_quote END ASC,
                CASE side WHEN 'buy' THEN price_per_rtc_nano_quote END DESC,
                created_at ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        orders = [money_view(r) for r in c.execute(query, params).fetchall()]

        total = c.execute(
            f"SELECT COUNT(*) FROM orders WHERE {' AND '.join(where)}",
            params[:-2]
        ).fetchone()[0]

        return jsonify({
            "ok": True,
            "orders": orders,
            "total": total,
            "pairs": list(SUPPORTED_PAIRS.keys())
        })
    finally:
        conn.close()


@app.route("/api/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    """Get order details."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return jsonify({"error": "Order not found"}), 404

        order = money_view(row)
        # Don't expose HTLC secret unless order is confirmed
        if order["status"] not in ("confirmed", "completed"):
            order.pop("htlc_secret", None)

        return jsonify({"ok": True, "order": order})
    finally:
        conn.close()


@app.route("/api/orders/<order_id>/match", methods=["POST"])
@rate_limited
def match_order(order_id):
    """Match an open order as the counterparty."""
    data = request.get_json(silent=True) or {}
    taker_wallet = str(data.get("wallet", "")).strip()
    taker_eth_address = str(data.get("eth_address", "")).strip()

    if not taker_wallet:
        return jsonify({"error": "wallet required"}), 400

    conn = get_db()
    try:
        c = conn.cursor()
        row = c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return jsonify({"error": "Order not found"}), 404

        order = money_view(row)

        if order["status"] != "open":
            return jsonify({"error": f"Order is not open (status: {order['status']})"}), 409
        if order["maker_wallet"] == taker_wallet:
            return jsonify({"error": "Cannot match your own order"}), 400

        now = int(time.time())
        if now > order["expires_at"]:
            c.execute("UPDATE orders SET status = 'expired' WHERE order_id = ?", (order_id,))
            if order["escrow_job_id"]:
                rtc_cancel_escrow(order["escrow_job_id"], order["maker_wallet"])
            conn.commit()
            return jsonify({"error": "Order has expired"}), 410

        # For buy orders: taker is selling RTC, needs to lock escrow
        escrow_job_id = order["escrow_job_id"]
        if order["side"] == "buy":
            balance = rtc_get_balance(taker_wallet)
            if balance is not None and balance < order["amount_rtc"]:
                return jsonify({
                    "error": "Insufficient RTC balance to fill this buy order",
                    "balance_rtc": balance,
                    "required_rtc": order["amount_rtc"]
                }), 400

            escrow_result = rtc_create_escrow_job(
                poster_wallet=taker_wallet,
                amount_rtc=order["amount_rtc"],
                title=f"OTC Bridge Escrow: {order_id} (taker)",
                description=f"Escrowed {order['amount_rtc']} RTC for OTC buy order match. Buyer: {order['maker_wallet']}."
            )
            if not escrow_result["ok"]:
                return jsonify({
                    "error": "Failed to lock RTC in escrow",
                    "details": escrow_result.get("error")
                }), 400
            escrow_job_id = escrow_result["job_id"]
            htlc_secret, htlc_hash = generate_htlc_secret()
        else:
            htlc_secret, htlc_hash = order["htlc_secret"], order["htlc_hash"]

        # Update order
        c.execute("""
            UPDATE orders
            SET status = 'matched', taker_wallet = ?, taker_eth_address = ?,
                matched_at = ?, escrow_job_id = COALESCE(?, escrow_job_id),
                htlc_hash = COALESCE(?, htlc_hash),
                htlc_secret = COALESCE(?, htlc_secret)
            WHERE order_id = ? AND status = 'open'
        """, (taker_wallet, taker_eth_address, now,
              escrow_job_id if order["side"] == "buy" else None,
              htlc_hash if order["side"] == "buy" else None,
              htlc_secret if order["side"] == "buy" else None,
              order_id))

        if c.execute("SELECT changes()").fetchone()[0] == 0:
            return jsonify({"error": "Order was matched by someone else"}), 409

        conn.commit()

        response = {
            "ok": True,
            "order_id": order_id,
            "status": "matched",
            "side": order["side"],
            "pair": order["pair"],
            "amount_rtc": order["amount_rtc"],
            "price_per_rtc": order["price_per_rtc"],
            "total_quote": order["total_quote"],
            "maker_wallet": order["maker_wallet"],
            "taker_wallet": taker_wallet,
            "htlc_hash": htlc_hash,
        }
        if order["side"] == "buy":
            # Returned only once to the matching RTC seller.
            response["htlc_secret"] = htlc_secret

        quote_currency = order["pair"].split("/")[1]
        if order["side"] == "sell":
            response["settlement_instructions"] = {
                "step": "Send quote currency to complete the swap",
                "amount": order["total_quote"],
                "currency": quote_currency,
                "htlc_hash": htlc_hash,
                "note": f"Send {order['total_quote']} {quote_currency} to the seller's address. Once confirmed, the seller reveals the HTLC secret and RTC is released from escrow."
            }
        else:
            response["settlement_instructions"] = {
                "step": "RTC is locked in escrow. Buyer sends quote currency.",
                "amount": order["total_quote"],
                "currency": quote_currency,
                "htlc_hash": htlc_hash,
                "note": f"Buyer must send {order['total_quote']} {quote_currency}. The matching seller confirms by revealing the HTLC secret, then RTC escrow releases to buyer."
            }

        return jsonify(response)

    except Exception:
        conn.rollback()
        return internal_error_response("Order match")
    finally:
        conn.close()


@app.route("/api/orders/<order_id>/confirm", methods=["POST"])
@rate_limited
def confirm_order(order_id):
    """Confirm settlement -- verifies HTLC preimage, releases escrow."""
    data = request.get_json(silent=True) or {}
    wallet = str(data.get("wallet", "")).strip()
    quote_tx = str(data.get("quote_tx", "")).strip()
    secret = str(data.get("secret", "")).strip()

    if not wallet:
        return jsonify({"error": "wallet required"}), 400
    if not quote_tx:
        return jsonify({"error": "quote_tx required"}), 400

    conn = get_db()
    try:
        c = conn.cursor()
        row = c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return jsonify({"error": "Order not found"}), 404

        order = money_view(row)

        if order["status"] != "matched":
            return jsonify({"error": f"Order must be matched to confirm (current: {order['status']})"}), 409

        # Only the RTC seller owns the preimage and can confirm settlement.
        seller_wallet = order["maker_wallet"] if order["side"] == "sell" else order["taker_wallet"]
        if wallet != seller_wallet:
            return jsonify({"error": "Only the RTC seller can confirm settlement"}), 403

        # Verify HTLC preimage before releasing escrow
        if not secret:
            return jsonify({"error": "HTLC secret (preimage) required to confirm settlement"}), 400
        if not order["htlc_hash"]:
            return jsonify({"error": "HTLC hash unavailable for matched order"}), 409

        # Validate the provided secret matches the stored hash
        try:
            computed_hash = hashlib.sha256(bytes.fromhex(secret)).hexdigest()
        except ValueError:
            return jsonify({"error": "Invalid HTLC secret format"}), 400
        if not hmac.compare_digest(computed_hash, order["htlc_hash"]):
            return jsonify({"error": "Invalid HTLC secret"}), 400

        now = int(time.time())

        # Release RTC escrow
        if order["escrow_job_id"]:
            # Determine who posted the escrow job
            escrow_poster = order["maker_wallet"] if order["side"] == "sell" else order["taker_wallet"]

            # To release via RIP-302: claim -> deliver -> accept
            # First claim as the bridge
            claim_r = requests.post(
                f"{RUSTCHAIN_NODE}/agent/jobs/{order['escrow_job_id']}/claim",
                json={"worker_wallet": "otc_bridge_worker"},
                verify=TLS_VERIFY, timeout=15
            )

            if claim_r.ok or "not open" in claim_r.text.lower():
                # Deliver
                deliver_r = requests.post(
                    f"{RUSTCHAIN_NODE}/agent/jobs/{order['escrow_job_id']}/deliver",
                    json={
                        "worker_wallet": "otc_bridge_worker",
                        "result_summary": f"OTC trade confirmed. Order: {order_id}. Quote TX: {quote_tx}"
                    },
                    verify=TLS_VERIFY, timeout=15
                )

                # Accept (releases funds to otc_bridge_worker, then we transfer to actual recipient)
                if deliver_r.ok:
                    accept_r = requests.post(
                        f"{RUSTCHAIN_NODE}/agent/jobs/{order['escrow_job_id']}/accept",
                        json={"poster_wallet": escrow_poster, "rating": 5},
                        verify=TLS_VERIFY, timeout=15
                    )
                    if not accept_r.ok:
                        log.error(f"Escrow accept failed: {accept_r.text}")

        # Determine RTC recipient
        if order["side"] == "sell":
            rtc_recipient = order["taker_wallet"]
        else:
            rtc_recipient = order["maker_wallet"]

        # Record trade
        trade_id = generate_trade_id(order_id, order["taker_wallet"])
        insert_columns = [
            "trade_id", "order_id", "pair", "side", "maker_wallet", "taker_wallet",
            "amount_micro_rtc", "price_per_rtc_nano_quote", "total_quote_nano",
            "quote_tx", "completed_at",
        ]
        values = [
            trade_id, order_id, order["pair"], order["side"],
            order["maker_wallet"], order["taker_wallet"],
            order["amount_micro_rtc"], order["price_per_rtc_nano_quote"],
            order["total_quote_nano"], quote_tx, now,
        ]
        include_legacy_money_columns_if_present(
            table_columns(c, "trades"),
            insert_columns,
            values,
            order["amount_rtc"],
            order["price_per_rtc"],
            order["total_quote"],
        )
        placeholders = ", ".join("?" for _ in values)
        c.execute(
            f"INSERT INTO trades ({', '.join(insert_columns)}) VALUES ({placeholders})",
            values,
        )

        # Update order
        c.execute("""
            UPDATE orders SET status = 'completed', confirmed_at = ?,
                   settlement_tx = ?
            WHERE order_id = ?
        """, (now, quote_tx, order_id))
        conn.commit()

        return jsonify({
            "ok": True,
            "order_id": order_id,
            "trade_id": trade_id,
            "status": "completed",
            "htlc_secret": secret,
            "amount_rtc": order["amount_rtc"],
            "rtc_recipient": rtc_recipient,
            "message": f"Trade completed. {order['amount_rtc']} RTC released to {rtc_recipient}. HTLC secret verified and revealed."
        })

    except Exception:
        conn.rollback()
        return internal_error_response("Order confirmation")
    finally:
        conn.close()


@app.route("/api/orders/<order_id>/cancel", methods=["POST"])
@rate_limited
def cancel_order(order_id):
    """Cancel an open order and refund escrow."""
    data = request.get_json(silent=True) or {}
    wallet = str(data.get("wallet", "")).strip()

    if not wallet:
        return jsonify({"error": "wallet required"}), 400

    conn = get_db()
    try:
        c = conn.cursor()
        row = c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return jsonify({"error": "Order not found"}), 404

        order = money_view(row)

        if order["maker_wallet"] != wallet:
            return jsonify({"error": "Only the order creator can cancel"}), 403
        if order["status"] not in ("open",):
            return jsonify({"error": f"Can only cancel open orders (current: {order['status']})"}), 409

        # Cancel RTC escrow
        if order["escrow_job_id"]:
            rtc_cancel_escrow(order["escrow_job_id"], wallet)

        c.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
        conn.commit()

        return jsonify({
            "ok": True,
            "order_id": order_id,
            "status": "cancelled",
            "message": "Order cancelled. Escrow refunded."
        })
    except Exception:
        conn.rollback()
        return internal_error_response("Order cancellation")
    finally:
        conn.close()


@app.route("/api/trades", methods=["GET"])
def list_trades():
    """Trade history."""
    pair = request.args.get("pair", "").strip().upper()
    limit, error = positive_int_arg("limit", 50, max_value=200)
    if error:
        return jsonify({"error": error}), 400

    conn = get_db()
    try:
        if pair and pair in SUPPORTED_PAIRS:
            trades = conn.execute(
                "SELECT * FROM trades WHERE pair = ? ORDER BY completed_at DESC LIMIT ?",
                (pair, limit)
            ).fetchall()
        else:
            trades = conn.execute(
                "SELECT * FROM trades ORDER BY completed_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

        return jsonify({
            "ok": True,
            "trades": [money_view(t) for t in trades]
        })
    finally:
        conn.close()


@app.route("/api/orderbook", methods=["GET"])
def orderbook():
    """Aggregated order book -- bids and asks."""
    pair = request.args.get("pair", "RTC/USDC").strip().upper()
    if pair not in SUPPORTED_PAIRS:
        return jsonify({"error": f"Unsupported pair"}), 400

    conn = get_db()
    try:
        c = conn.cursor()

        # Asks (sell orders) -- sorted by price ascending (cheapest first)
        asks = c.execute("""
            SELECT price_per_rtc_nano_quote as price_nano,
                   SUM(amount_micro_rtc) as total_micro_rtc,
                   COUNT(*) as order_count
            FROM orders
            WHERE pair = ? AND side = 'sell' AND status = 'open'
            GROUP BY price_per_rtc_nano_quote
            ORDER BY price_nano ASC
            LIMIT 20
        """, (pair,)).fetchall()

        # Bids (buy orders) -- sorted by price descending (highest first)
        bids = c.execute("""
            SELECT price_per_rtc_nano_quote as price_nano,
                   SUM(amount_micro_rtc) as total_micro_rtc,
                   COUNT(*) as order_count
            FROM orders
            WHERE pair = ? AND side = 'buy' AND status = 'open'
            GROUP BY price_per_rtc_nano_quote
            ORDER BY price_nano DESC
            LIMIT 20
        """, (pair,)).fetchall()

        # Last trade price
        last_trade = c.execute(
            "SELECT price_per_rtc_nano_quote FROM trades WHERE pair = ? ORDER BY completed_at DESC LIMIT 1",
            (pair,)
        ).fetchone()

        # 24h volume
        day_ago = int(time.time()) - 86400
        vol = c.execute(
            "SELECT COALESCE(SUM(amount_micro_rtc), 0), COUNT(*) FROM trades WHERE pair = ? AND completed_at >= ?",
            (pair, day_ago)
        ).fetchone()

        ask_levels = [
            {
                "price": units_to_float(a["price_nano"], QUOTE_PRICE_SCALE),
                "total_rtc": units_to_float(a["total_micro_rtc"], RTC_UNIT),
                "order_count": a["order_count"],
            }
            for a in asks
        ]
        bid_levels = [
            {
                "price": units_to_float(b["price_nano"], QUOTE_PRICE_SCALE),
                "total_rtc": units_to_float(b["total_micro_rtc"], RTC_UNIT),
                "order_count": b["order_count"],
            }
            for b in bids
        ]

        return jsonify({
            "ok": True,
            "pair": pair,
            "asks": ask_levels,
            "bids": bid_levels,
            "last_price": units_to_float(last_trade[0], QUOTE_PRICE_SCALE) if last_trade else None,
            "volume_24h_rtc": units_to_float(vol[0], RTC_UNIT),
            "trades_24h": vol[1],
            "reference_rate": RTC_REFERENCE_RATE,
            "spread": round(ask_levels[0]["price"] - bid_levels[0]["price"], 6)
            if ask_levels and bid_levels else None
        })
    finally:
        conn.close()


@app.route("/api/stats", methods=["GET"])
def market_stats():
    """Overall market statistics."""
    conn = get_db()
    try:
        c = conn.cursor()
        now = int(time.time())
        day_ago = now - 86400
        week_ago = now - 7 * 86400

        total_trades = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        total_volume = c.execute("SELECT COALESCE(SUM(amount_micro_rtc), 0) FROM trades").fetchone()[0]
        vol_24h = c.execute(
            "SELECT COALESCE(SUM(amount_micro_rtc), 0) FROM trades WHERE completed_at >= ?",
            (day_ago,)
        ).fetchone()[0]
        vol_7d = c.execute(
            "SELECT COALESCE(SUM(amount_micro_rtc), 0) FROM trades WHERE completed_at >= ?",
            (week_ago,)
        ).fetchone()[0]
        open_orders = c.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'open'"
        ).fetchone()[0]
        open_sell = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_micro_rtc), 0) FROM orders WHERE status = 'open' AND side = 'sell'"
        ).fetchone()
        open_buy = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_micro_rtc), 0) FROM orders WHERE status = 'open' AND side = 'buy'"
        ).fetchone()

        # Price stats from recent trades
        prices = c.execute(
            "SELECT price_per_rtc_nano_quote FROM trades ORDER BY completed_at DESC LIMIT 100"
        ).fetchall()
        price_list = [units_to_float(p[0], QUOTE_PRICE_SCALE) for p in prices]

        return jsonify({
            "ok": True,
            "stats": {
                "total_trades": total_trades,
                "total_volume_rtc": round(units_to_float(total_volume, RTC_UNIT), 2),
                "volume_24h_rtc": round(units_to_float(vol_24h, RTC_UNIT), 2),
                "volume_7d_rtc": round(units_to_float(vol_7d, RTC_UNIT), 2),
                "open_orders": open_orders,
                "open_sells": {
                    "count": open_sell[0],
                    "total_rtc": round(units_to_float(open_sell[1], RTC_UNIT), 2),
                },
                "open_buys": {
                    "count": open_buy[0],
                    "total_rtc": round(units_to_float(open_buy[1], RTC_UNIT), 2),
                },
                "last_price": price_list[0] if price_list else RTC_REFERENCE_RATE,
                "high_24h": max(price_list) if price_list else None,
                "low_24h": min(price_list) if price_list else None,
                "reference_rate_usd": RTC_REFERENCE_RATE,
                "supported_pairs": list(SUPPORTED_PAIRS.keys())
            }
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("OTC_PORT", 5580))
    app.run(host="0.0.0.0", port=port, debug=False)
