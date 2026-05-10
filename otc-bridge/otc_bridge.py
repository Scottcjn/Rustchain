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
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUSTCHAIN_NODE = os.environ.get("RUSTCHAIN_NODE", "https://50.28.86.131")
DB_PATH = os.environ.get("OTC_DB_PATH", "otc_bridge.db")

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

RC_ADMIN_KEY = os.environ.get("RC_ADMIN_KEY", "").strip()
ESCROW_WALLET = "otc_bridge_escrow"
ORDER_TTL_DEFAULT = 7 * 86400       # 7 days
ORDER_TTL_MAX = 30 * 86400          # 30 days
HTLC_TIMEOUT = 24 * 3600            # 24h for HTLC expiry
MIN_ORDER_RTC = 0.1                 # Minimum 0.1 RTC
MAX_ORDER_RTC = 100000              # Maximum 100k RTC
RATE_LIMIT_WINDOW = 60              # 1 minute
RATE_LIMIT_MAX = 10                 # 10 requests per minute per IP
RTC_REFERENCE_RATE = 0.10           # $0.10 USD reference

SUPPORTED_PAIRS = {
    "RTC/ETH": {"quote": "ETH", "decimals": 18},
    "RTC/USDC": {"quote": "USDC", "decimals": 6},
    "RTC/ERG": {"quote": "ERG", "decimals": 9},
}

log = logging.getLogger("otc_bridge")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder="static")
CORS(app)


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
                amount_rtc REAL NOT NULL,
                price_per_rtc REAL NOT NULL,
                total_quote REAL NOT NULL,
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
                amount_rtc REAL NOT NULL,
                price_per_rtc REAL NOT NULL,
                total_quote REAL NOT NULL,
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


_MINER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def is_valid_wallet_id(wallet_id):
    wallet_id = str(wallet_id or "").strip()
    return bool(_MINER_ID_RE.fullmatch(wallet_id))


def send_bridge_alert(level, message, fields):
    """Best-effort alert hook for payout failures and manual recovery events."""
    webhook = os.environ.get("RC_SOPHIACHECK_WEBHOOK", "").strip()
    if not webhook:
        return

    colors = {
        "warning": 16776960,
        "critical": 16711680,
        "info": 3447003,
    }
    embed = {
        "title": f"OTC Bridge {level.upper()}",
        "description": message,
        "color": colors.get(level, 3447003),
        "fields": [
            {"name": str(k), "value": str(v), "inline": True}
            for k, v in (fields or {}).items()
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        requests.post(webhook, json={"embeds": [embed]}, timeout=5)
    except Exception as exc:
        log.warning(f"Bridge alert delivery failed: {exc}")


def rtc_transfer_from_worker(recipient_wallet, amount_rtc, order_id):
    """Queue admin payout from the bridge worker to the actual OTC recipient."""
    last_error = "unknown payout error"
    last_payload = {}
    retry_delays = (0, 1, 2, 4)

    for attempt, delay_seconds in enumerate(retry_delays, start=1):
        if delay_seconds:
            time.sleep(delay_seconds)

        try:
            transfer_r = requests.post(
                f"{RUSTCHAIN_NODE}/wallet/transfer",
                headers={"X-Admin-Key": RC_ADMIN_KEY},
                json={
                    "from_miner": "otc_bridge_worker",
                    "to_miner": recipient_wallet,
                    "amount_rtc": amount_rtc,
                    "reason": f"otc_payout:{order_id}",
                },
                verify=TLS_VERIFY, timeout=15
            )
        except Exception as exc:
            last_error = str(exc)
            if attempt < len(retry_delays):
                log.warning(
                    f"Worker payout attempt {attempt}/{len(retry_delays)} failed for "
                    f"{order_id}: {last_error}"
                )
                continue
            return {"ok": False, "error": last_error, "details": last_payload}

        try:
            last_payload = transfer_r.json()
        except ValueError:
            last_payload = {}

        if transfer_r.ok:
            last_payload.setdefault("phase", "pending")
            return {"ok": True, "details": last_payload}

        last_error = last_payload.get("error") or transfer_r.text.strip() or f"HTTP {transfer_r.status_code}"
        should_retry = (
            transfer_r.status_code >= 500
            or "insufficient available balance" in last_error.lower()
        )
        if should_retry and attempt < len(retry_delays):
            log.warning(
                f"Worker payout attempt {attempt}/{len(retry_delays)} for {order_id} "
                f"failed, retrying: {last_error}"
            )
            continue

        break

    return {"ok": False, "error": last_error, "details": last_payload}


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
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    side = str(data.get("side", "")).strip().lower()
    pair = str(data.get("pair", "RTC/USDC")).strip().upper()
    maker_wallet = str(data.get("wallet", "")).strip()
    amount_rtc = data.get("amount_rtc", 0)
    price_per_rtc = data.get("price_per_rtc", 0)
    maker_eth_address = str(data.get("eth_address", "")).strip()
    ttl = int(data.get("ttl_seconds", ORDER_TTL_DEFAULT))

    # Validation
    if side not in ("buy", "sell"):
        return jsonify({"error": "side must be 'buy' or 'sell'"}), 400
    if pair not in SUPPORTED_PAIRS:
        return jsonify({"error": f"Unsupported pair. Supported: {list(SUPPORTED_PAIRS.keys())}"}), 400
    if not maker_wallet or len(maker_wallet) < 3:
        return jsonify({"error": "wallet required (RTC wallet ID)"}), 400

    try:
        amount_rtc = float(amount_rtc)
        price_per_rtc = float(price_per_rtc)
    except (TypeError, ValueError):
        return jsonify({"error": "amount_rtc and price_per_rtc must be numbers"}), 400

    if amount_rtc < MIN_ORDER_RTC:
        return jsonify({"error": f"Minimum order: {MIN_ORDER_RTC} RTC"}), 400
    if amount_rtc > MAX_ORDER_RTC:
        return jsonify({"error": f"Maximum order: {MAX_ORDER_RTC} RTC"}), 400
    if price_per_rtc <= 0:
        return jsonify({"error": "price_per_rtc must be positive"}), 400
    if price_per_rtc > 1000:
        return jsonify({"error": "price_per_rtc too high (max $1000)"}), 400

    ttl = min(max(ttl, 3600), ORDER_TTL_MAX)
    total_quote = round(amount_rtc * price_per_rtc, 8)
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

    # Generate HTLC secret (seller generates, buyer reveals on match)
    htlc_secret, htlc_hash = generate_htlc_secret()

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO orders
            (order_id, side, pair, maker_wallet, amount_rtc, price_per_rtc,
             total_quote, status, escrow_job_id, htlc_hash, htlc_secret,
             maker_eth_address, created_at, expires_at, ip_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)
        """, (order_id, side, pair, maker_wallet, amount_rtc, price_per_rtc,
              total_quote, escrow_job_id, htlc_hash, htlc_secret,
              maker_eth_address, now, now + ttl, hash_ip(get_client_ip())))
        conn.commit()

        response = {
            "ok": True,
            "order_id": order_id,
            "side": side,
            "pair": pair,
            "amount_rtc": amount_rtc,
            "price_per_rtc": price_per_rtc,
            "total_quote": total_quote,
            "quote_currency": pair.split("/")[1],
            "status": "open",
            "expires_at": now + ttl,
            "expires_in_hours": round(ttl / 3600, 1),
        }
        if escrow_job_id:
            response["escrow_job_id"] = escrow_job_id
            response["escrow_status"] = "locked"
        if side == "sell":
            response["htlc_hash"] = htlc_hash
            response["message"] = f"Sell order created. {amount_rtc} RTC locked in escrow. HTLC hash published for buyer verification."
        else:
            response["message"] = f"Buy order created. Waiting for a seller to match."

        return jsonify(response), 201

    except Exception as e:
        conn.rollback()
        # If we created an escrow job but DB insert failed, cancel it
        if escrow_job_id:
            rtc_cancel_escrow(escrow_job_id, maker_wallet)
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/orders", methods=["GET"])
def list_orders():
    """List open orders with optional filters."""
    pair = request.args.get("pair", "").strip().upper()
    side = request.args.get("side", "").strip().lower()
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)

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
            SELECT order_id, side, pair, maker_wallet, amount_rtc,
                   price_per_rtc, total_quote, status, htlc_hash,
                   created_at, expires_at, escrow_job_id
            FROM orders
            WHERE {' AND '.join(where)}
            ORDER BY
                CASE side WHEN 'sell' THEN price_per_rtc END ASC,
                CASE side WHEN 'buy' THEN price_per_rtc END DESC,
                created_at ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        orders = [dict(r) for r in c.execute(query, params).fetchall()]

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

        order = dict(row)
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

        order = dict(row)

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

        # Update order
        c.execute("""
            UPDATE orders
            SET status = 'matched', taker_wallet = ?, taker_eth_address = ?,
                matched_at = ?, escrow_job_id = COALESCE(?, escrow_job_id)
            WHERE order_id = ? AND status = 'open'
        """, (taker_wallet, taker_eth_address, now,
              escrow_job_id if order["side"] == "buy" else None, order_id))

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
            "htlc_hash": order["htlc_hash"],
        }

        quote_currency = order["pair"].split("/")[1]
        if order["side"] == "sell":
            response["settlement_instructions"] = {
                "step": "Send quote currency to complete the swap",
                "amount": order["total_quote"],
                "currency": quote_currency,
                "htlc_hash": order["htlc_hash"],
                "note": f"Send {order['total_quote']} {quote_currency} to the seller's address. Once confirmed, the seller reveals the HTLC secret and RTC is released from escrow."
            }
        else:
            response["settlement_instructions"] = {
                "step": "RTC is locked in escrow. Buyer sends quote currency.",
                "amount": order["total_quote"],
                "currency": quote_currency,
                "note": f"Buyer must send {order['total_quote']} {quote_currency}. Once confirmed, RTC escrow releases to buyer."
            }

        return jsonify(response)

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
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

    conn = get_db()
    try:
        c = conn.cursor()
        row = c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return jsonify({"error": "Order not found"}), 404

        order = dict(row)

        if order["status"] != "matched":
            return jsonify({"error": f"Order must be matched to confirm (current: {order['status']})"}), 409

        # Either party can confirm
        if wallet not in (order["maker_wallet"], order["taker_wallet"]):
            return jsonify({"error": "Only maker or taker can confirm"}), 403

        # Verify HTLC preimage before releasing escrow
        if not secret:
            return jsonify({"error": "HTLC secret (preimage) required to confirm settlement"}), 400

        # Validate the provided secret matches the stored hash
        computed_hash = hashlib.sha256(bytes.fromhex(secret)).hexdigest()
        if computed_hash != order["htlc_hash"]:
            return jsonify({"error": "Invalid HTLC secret (preimage hash mismatch)"}), 400

        now = int(time.time())
        rtc_recipient = order["taker_wallet"] if order["side"] == "sell" else order["maker_wallet"]
        if not is_valid_wallet_id(rtc_recipient):
            return jsonify({
                "error": "Invalid RTC recipient wallet on matched order",
                "rtc_recipient": rtc_recipient,
            }), 400

        if not RC_ADMIN_KEY:
            return jsonify({
                "error": "Bridge payout unavailable: RC_ADMIN_KEY not configured"
            }), 500

        payout_status = "not_started"
        payout_result = {}

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
                    if accept_r.ok:
                        payout_result = rtc_transfer_from_worker(
                            rtc_recipient,
                            order["amount_rtc"],
                            order_id,
                        )
                        if payout_result["ok"]:
                            payout_status = payout_result["details"].get("phase", "pending")
                        else:
                            payout_status = "manual_recovery_required"
                            log.error(
                                f"Bridge payout failed after escrow accept for {order_id}: "
                                f"{payout_result['error']}"
                            )
                            send_bridge_alert(
                                "critical",
                                "OTC payout failed after escrow accept",
                                {
                                    "order_id": order_id,
                                    "recipient": rtc_recipient,
                                    "amount_rtc": order["amount_rtc"],
                                    "error": payout_result["error"],
                                },
                            )
                    else:
                        payout_status = "escrow_accept_failed"
                        log.error(f"Escrow accept failed: {accept_r.text}")
                else:
                    payout_status = "escrow_deliver_failed"
            else:
                payout_status = "escrow_claim_failed"
        else:
            payout_status = "missing_escrow_job"

        payout_details = payout_result.get("details", {})
        payout_tx = payout_details.get("tx_hash")

        # Record trade
        trade_id = generate_trade_id(order_id, order["taker_wallet"])
        c.execute("""
            INSERT INTO trades
            (trade_id, order_id, pair, side, maker_wallet, taker_wallet,
             amount_rtc, price_per_rtc, total_quote, rtc_tx, quote_tx, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trade_id, order_id, order["pair"], order["side"],
              order["maker_wallet"], order["taker_wallet"],
              order["amount_rtc"], order["price_per_rtc"],
              order["total_quote"], payout_tx, quote_tx, now))

        # Update order
        c.execute("""
            UPDATE orders SET status = 'completed', confirmed_at = ?,
                   settlement_tx = ?
            WHERE order_id = ?
        """, (now, quote_tx, order_id))
        conn.commit()

        if payout_status == "pending":
            message = (
                f"Trade completed. {order['amount_rtc']} RTC payout to {rtc_recipient} "
                "was queued successfully. HTLC secret verified and revealed."
            )
        elif payout_status == "manual_recovery_required":
            message = (
                f"Trade completed, but payout to {rtc_recipient} failed after escrow "
                "accept. Operators were alerted for manual recovery."
            )
        elif payout_status == "escrow_accept_failed":
            message = (
                "Trade recorded, but escrow accept failed before payout could be queued. "
                "Manual review required."
            )
        else:
            message = (
                f"Trade completed with payout status '{payout_status}'. "
                "HTLC secret verified and revealed."
            )

        return jsonify({
            "ok": True,
            "order_id": order_id,
            "trade_id": trade_id,
            "status": "completed",
            "htlc_secret": secret,
            "amount_rtc": order["amount_rtc"],
            "rtc_recipient": rtc_recipient,
            "rtc_transfer_status": payout_status,
            "rtc_transfer_pending_id": payout_details.get("pending_id"),
            "rtc_transfer_tx_hash": payout_tx,
            "message": message
        })

    except Exception as e:
        conn.rollback()
        log.error(f"Confirm error: {e}")
        return jsonify({"error": str(e)}), 500
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

        order = dict(row)

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
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/trades", methods=["GET"])
def list_trades():
    """Trade history."""
    pair = request.args.get("pair", "").strip().upper()
    limit = min(int(request.args.get("limit", 50)), 200)

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
            "trades": [dict(t) for t in trades]
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
            SELECT price_per_rtc as price, SUM(amount_rtc) as total_rtc,
                   COUNT(*) as order_count
            FROM orders
            WHERE pair = ? AND side = 'sell' AND status = 'open'
            GROUP BY ROUND(price_per_rtc, 4)
            ORDER BY price ASC
            LIMIT 20
        """, (pair,)).fetchall()

        # Bids (buy orders) -- sorted by price descending (highest first)
        bids = c.execute("""
            SELECT price_per_rtc as price, SUM(amount_rtc) as total_rtc,
                   COUNT(*) as order_count
            FROM orders
            WHERE pair = ? AND side = 'buy' AND status = 'open'
            GROUP BY ROUND(price_per_rtc, 4)
            ORDER BY price DESC
            LIMIT 20
        """, (pair,)).fetchall()

        # Last trade price
        last_trade = c.execute(
            "SELECT price_per_rtc FROM trades WHERE pair = ? ORDER BY completed_at DESC LIMIT 1",
            (pair,)
        ).fetchone()

        # 24h volume
        day_ago = int(time.time()) - 86400
        vol = c.execute(
            "SELECT COALESCE(SUM(amount_rtc), 0), COUNT(*) FROM trades WHERE pair = ? AND completed_at >= ?",
            (pair, day_ago)
        ).fetchone()

        return jsonify({
            "ok": True,
            "pair": pair,
            "asks": [dict(a) for a in asks],
            "bids": [dict(b) for b in bids],
            "last_price": last_trade[0] if last_trade else None,
            "volume_24h_rtc": vol[0],
            "trades_24h": vol[1],
            "reference_rate": RTC_REFERENCE_RATE,
            "spread": round(asks[0]["price"] - bids[0]["price"], 6) if asks and bids else None
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
        total_volume = c.execute("SELECT COALESCE(SUM(amount_rtc), 0) FROM trades").fetchone()[0]
        vol_24h = c.execute(
            "SELECT COALESCE(SUM(amount_rtc), 0) FROM trades WHERE completed_at >= ?",
            (day_ago,)
        ).fetchone()[0]
        vol_7d = c.execute(
            "SELECT COALESCE(SUM(amount_rtc), 0) FROM trades WHERE completed_at >= ?",
            (week_ago,)
        ).fetchone()[0]
        open_orders = c.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'open'"
        ).fetchone()[0]
        open_sell = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_rtc), 0) FROM orders WHERE status = 'open' AND side = 'sell'"
        ).fetchone()
        open_buy = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_rtc), 0) FROM orders WHERE status = 'open' AND side = 'buy'"
        ).fetchone()

        # Price stats from recent trades
        prices = c.execute(
            "SELECT price_per_rtc FROM trades ORDER BY completed_at DESC LIMIT 100"
        ).fetchall()
        price_list = [p[0] for p in prices]

        return jsonify({
            "ok": True,
            "stats": {
                "total_trades": total_trades,
                "total_volume_rtc": round(total_volume, 2),
                "volume_24h_rtc": round(vol_24h, 2),
                "volume_7d_rtc": round(vol_7d, 2),
                "open_orders": open_orders,
                "open_sells": {"count": open_sell[0], "total_rtc": round(open_sell[1], 2)},
                "open_buys": {"count": open_buy[0], "total_rtc": round(open_buy[1], 2)},
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
