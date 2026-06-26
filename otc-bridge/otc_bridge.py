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
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - stripped-down deployments should fail closed
    InvalidSignature = None
    Ed25519PublicKey = None

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

# Admin key for /wallet/transfer payouts from otc_bridge_worker → real recipient.
# Required for confirm_order() to complete OTC settlement. Without it, escrow funds
# stay trapped in otc_bridge_worker.
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
RTC_UNIT = 1_000_000                # 1 micro-RTC
QUOTE_PRICE_SCALE = 1_000_000_000   # 9 decimal places for quote units
WALLET_AUTH_MAX_AGE_SECONDS = 300
RTC_WALLET_RE = re.compile(r"^RTC[0-9a-fA-F]{40}$")
CREATE_ORDER_AUTH_ID = "create_order"

SUPPORTED_PAIRS = {
    "RTC/ETH": {"quote": "ETH", "decimals": 18},
    "RTC/USDC": {"quote": "USDC", "decimals": 6},
    "RTC/ERG": {"quote": "ERG", "decimals": 9},
}

log = logging.getLogger("otc_bridge")
logging.basicConfig(level=logging.INFO)

GENERIC_INTERNAL_ERROR = "Internal server error"


def log_internal_error(context):
    log.exception("%s failed", context)

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


# SQLite cannot parameterize identifiers (PRAGMA/ALTER/UPDATE take a literal
# table name), so every table name interpolated into the DDL below MUST be
# validated against this allowlist first — never against caller-supplied text.
_KNOWN_TABLES = frozenset({"orders", "trades", "rate_limits"})
# Integer precision columns we add (also literal, never caller-supplied).
_PRECISION_COLUMNS = ("amount_micro_rtc", "price_per_rtc_nano_quote", "total_quote_nano")


def _require_known_table(table_name):
    """Guard before building DDL: refuse any table name not on the allowlist."""
    if table_name not in _KNOWN_TABLES:
        raise ValueError(f"refusing to build SQL for unknown table {table_name!r}")
    return table_name


def migrate_precision_columns(cursor, table_name):
    # Validate before interpolation so only known-safe identifiers reach the SQL.
    _require_known_table(table_name)

    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}
    for col in _PRECISION_COLUMNS:
        if col in columns:
            continue
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} INTEGER")
        except sqlite3.OperationalError as exc:
            # Idempotent under concurrent migrations: another worker may have
            # added the column between the PRAGMA read above and this ALTER.
            if "duplicate column name" not in str(exc).lower():
                raise

    refreshed = {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}
    if {"amount_rtc", "price_per_rtc", "total_quote"}.issubset(refreshed):
        # COALESCE keeps the backfill idempotent: re-runs converge to the same
        # values, so concurrent migrations are safe without a write lock.
        cursor.execute(f"""
            UPDATE {table_name}
            SET amount_micro_rtc = COALESCE(amount_micro_rtc, CAST(ROUND(amount_rtc * ?) AS INTEGER)),
                price_per_rtc_nano_quote = COALESCE(price_per_rtc_nano_quote, CAST(ROUND(price_per_rtc * ?) AS INTEGER)),
                total_quote_nano = COALESCE(total_quote_nano, CAST(ROUND(total_quote * ?) AS INTEGER))
        """, (RTC_UNIT, QUOTE_PRICE_SCALE, QUOTE_PRICE_SCALE))


def table_columns(cursor, table_name):
    _require_known_table(table_name)
    return {row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})")}


def include_legacy_money_columns_if_present(columns, insert_columns, values, amount_rtc, price_per_rtc, total_quote):
    if {"amount_rtc", "price_per_rtc", "total_quote"}.issubset(columns):
        insert_columns.extend(["amount_rtc", "price_per_rtc", "total_quote"])
        values.extend([amount_rtc, price_per_rtc, total_quote])


# ---------------------------------------------------------------------------
# OTC payout helpers (close fund-trap bug: escrow accept releases to
# otc_bridge_worker, then we must transfer from there to the real recipient)
# ---------------------------------------------------------------------------

_MINER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def is_valid_wallet_id(wallet_id):
    """Validate a wallet/miner identifier before using it as a transfer target."""
    wallet_id = str(wallet_id or "").strip()
    return bool(_MINER_ID_RE.fullmatch(wallet_id))


def _admin_transport_block_reason():
    """Return a reason string if it is UNSAFE to send the admin key to the
    configured node, else None.

    Fail-closed: the RC_ADMIN_KEY must never leave over plaintext (http://) or
    to a non-local host with TLS verification disabled (MITM credential theft).
    Loopback hosts and an explicit OTC_ALLOW_INSECURE_ADMIN opt-out are allowed
    for local development.
    """
    if os.environ.get("OTC_ALLOW_INSECURE_ADMIN", "").strip().lower() in ("1", "true", "yes"):
        return None  # explicit operator opt-out (dev only)

    parsed = urlparse(RUSTCHAIN_NODE)
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return None  # loopback dev is acceptable

    if parsed.scheme != "https":
        return (
            f"insecure scheme '{parsed.scheme or 'none'}' for admin endpoint "
            f"{RUSTCHAIN_NODE!r}: set RUSTCHAIN_NODE to https:// "
            f"(or OTC_ALLOW_INSECURE_ADMIN=1 for local dev)"
        )
    if TLS_VERIFY is False:
        return (
            "TLS verification disabled (RUSTCHAIN_TLS_VERIFY=false) for a "
            "non-local admin endpoint — MITM credential exposure; pin "
            "RUSTCHAIN_CA_BUNDLE instead of disabling verification"
        )
    return None


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
    """Queue admin payout from the bridge worker to the actual OTC recipient.

    Returns ``{"ok": True, "details": {...}}`` on success (transfer queued or
    accepted into pending pool), or ``{"ok": False, "error": str, "details": {...}}``
    on terminal failure after retries.
    """
    # Fail-closed BEFORE sending the admin key: never leak RC_ADMIN_KEY over an
    # insecure transport. Refusing strands funds in otc_bridge_worker (alerted +
    # recoverable) — strictly safer than exfiltrating the admin credential.
    block_reason = _admin_transport_block_reason()
    if block_reason:
        log.error(f"OTC payout blocked for {order_id}: {block_reason}")
        send_bridge_alert(
            "critical",
            "OTC payout blocked: insecure admin transport",
            {"order_id": order_id, "node": RUSTCHAIN_NODE, "reason": block_reason},
        )
        return {"ok": False, "error": f"insecure_admin_transport: {block_reason}", "details": {}}

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
                    # Idempotency: stable, unique-per-payout key so retries (and
                    # any double-confirm) dedup server-side in wallet_transfer_v2
                    # instead of paying twice. Derived from the immutable
                    # order_id (one worker payout per order), and kept equal to
                    # `reason` so the server's reason-consistency check passes.
                    "idempotency_key": f"otc_payout:{order_id}",
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
        # Single-row advisory lock so only one worker reconciles at a time (the
        # reconciler makes external node/refund calls; without this every gunicorn
        # worker would race them). Holder is time-boxed so a crashed holder frees
        # the lock automatically. See _acquire_reconcile_lock().
        c.execute("""
            CREATE TABLE IF NOT EXISTS reconcile_lock (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                locked_until INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("INSERT OR IGNORE INTO reconcile_lock (id, locked_until) VALUES (1, 0)")

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


def rtc_address_from_public_key(public_key_hex):
    public_key_bytes = bytes.fromhex(public_key_hex)
    return f"RTC{hashlib.sha256(public_key_bytes).hexdigest()[:40]}"


def wallet_auth_message(action, order_id, wallet, timestamp, bound_fields=None):
    payload = {
        "action": action,
        "order_id": order_id,
        "timestamp": int(timestamp),
        "wallet": wallet,
    }
    if bound_fields:
        payload.update(bound_fields)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_order_auth_fields(
    side,
    pair,
    amount_micro_rtc,
    price_per_rtc_nano_quote,
    ttl_seconds,
    eth_address,
):
    return {
        "side": side,
        "pair": pair,
        "amount_micro_rtc": int(amount_micro_rtc),
        "price_per_rtc_nano_quote": int(price_per_rtc_nano_quote),
        "ttl_seconds": int(ttl_seconds),
        "eth_address": eth_address,
    }


def require_wallet_auth(data, action, order_id, wallet, bound_fields=None):
    if Ed25519PublicKey is None:
        return "wallet_auth_unavailable"
    if not RTC_WALLET_RE.fullmatch(wallet):
        return "wallet_must_be_native_rtc_address"

    auth = data.get("wallet_auth")
    if not isinstance(auth, dict):
        return "wallet_auth_required"

    public_key = str(auth.get("public_key", "")).strip()
    signature = str(auth.get("signature", "")).strip()
    timestamp_raw = auth.get("timestamp")
    if not public_key or not signature or timestamp_raw is None:
        return "wallet_auth_public_key_signature_timestamp_required"

    try:
        timestamp = int(timestamp_raw)
        if isinstance(timestamp_raw, bool):
            return "wallet_auth_invalid_timestamp"
        if abs(int(time.time()) - timestamp) > WALLET_AUTH_MAX_AGE_SECONDS:
            return "wallet_auth_timestamp_expired"
        if rtc_address_from_public_key(public_key).lower() != wallet.lower():
            return "wallet_auth_public_key_does_not_match_wallet"

        verify_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key))
        verify_key.verify(
            bytes.fromhex(signature),
            wallet_auth_message(action, order_id, wallet, timestamp, bound_fields),
        )
    except (TypeError, ValueError):
        return "wallet_auth_invalid_encoding"
    except InvalidSignature:
        return "wallet_auth_invalid_signature"

    return None


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
        log_internal_error("Escrow job creation")
        return {"ok": False, "error": GENERIC_INTERNAL_ERROR}


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


def safe_refund_escrow(job_id, poster_wallet, alert_title, alert_fields):
    """Best-effort escrow refund used AFTER a durable status commit.

    NEVER raises: the order's terminal/intermediate state is already committed,
    so the caller's API response must not turn into a 500 just because the
    refund call (or the alert) failed. On any failure it logs + alerts and
    returns False, so stranded escrow is always surfaced for reconciliation.
    """
    try:
        if rtc_cancel_escrow(job_id, poster_wallet):
            return True
    except Exception:
        log.error(f"Exception during post-commit escrow refund of job {job_id}")
    log.error(f"Escrow refund failed for job {job_id}: {alert_title}")
    try:
        send_bridge_alert("critical", alert_title, alert_fields)
    except Exception:
        log.error("send_bridge_alert raised while reporting refund failure")
    return False


# ---------------------------------------------------------------------------
# Settlement reconciliation (crash recovery + async payout confirmation)
# ---------------------------------------------------------------------------
# The durable, recoverable states the confirm/expiry/cancel paths can leave an
# order in, and which this reconciler is responsible for driving to terminal:
#   'settling'        confirm crashed AFTER claiming but before resolving payout
#   'payout_pending'  escrow released, worker payout QUEUED but not yet confirmed
#   'refund_pending'  expiry/cancel committed but the escrow refund hasn't landed
# Reconciliation is idempotent: the worker payout is keyed otc_payout:<order_id>
# (so re-driving never double-pays) and every transition is a guarded CAS.
def _int_env(name, default):
    """Parse an int env var, falling back (never raising) on a bad value so a
    typo in config can't crash the worker at import time."""
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        log.warning("invalid %s=%r; using default %s", name, os.environ.get(name), default)
        return default


SETTLEMENT_STUCK_SECONDS = _int_env("OTC_SETTLEMENT_STUCK_SECONDS", 120)
RECONCILE_INTERVAL_SECONDS = _int_env("OTC_RECONCILE_INTERVAL_SECONDS", 60)


def _acquire_reconcile_lock(conn, ttl=300):
    """Time-boxed single-row advisory lock. True iff this process won the lock;
    a crashed holder's lock auto-expires after ``ttl`` seconds. Cheap CAS:
    UPDATE only succeeds when the current lease has expired."""
    now = int(time.time())
    c = conn.cursor()
    c.execute("UPDATE reconcile_lock SET locked_until = ? WHERE id = 1 AND locked_until < ?",
              (now + ttl, now))
    won = c.execute("SELECT changes()").fetchone()[0] == 1
    conn.commit()
    return won


def _release_reconcile_lock(conn):
    """Release the lock early (best-effort) so the next tick isn't delayed a full TTL."""
    try:
        conn.execute("UPDATE reconcile_lock SET locked_until = 0 WHERE id = 1")
        conn.commit()
    except Exception:
        log.exception("failed to release reconcile lock")


def _lookup_worker_payout_status(order_id):
    """Authoritatively derive the worker payout's status from the node by its
    stable idempotency key (otc_payout:<order_id>). Scans BOTH the pending and the
    confirmed/voided ledgers, paginated, so 'missing' means *never queued* — never
    'confirmed-but-already-swept-out-of-the-pending-window'. Returns
    'confirmed' | 'pending' | 'voided' | 'missing' | 'unknown' (network/partial
    error -> 'unknown', which the caller treats as "leave for next pass")."""
    key = f"otc_payout:{order_id}"
    headers = {"X-Admin-Key": RC_ADMIN_KEY} if RC_ADMIN_KEY else {}
    PAGE = 500
    # Query confirmed/voided first: a confirmed payout is terminal truth and must
    # win over any stale pending row. Each status is fully paginated so a large
    # backlog can't push the target row outside a single fixed window.
    for status in ("confirmed", "voided", "pending"):
        offset = 0
        while True:
            try:
                r = requests.get(
                    f"{RUSTCHAIN_NODE}/pending/list", headers=headers,
                    params={"status": status, "limit": PAGE, "offset": offset},
                    verify=TLS_VERIFY, timeout=15,
                )
                if not r.ok:
                    return "unknown"
                body = r.json()
            except Exception:
                return "unknown"
            items = body.get("pending", []) if isinstance(body, dict) else []
            if not isinstance(items, list):
                items = []
            for it in items:
                if it.get("reason") == key or it.get("idempotency_key") == key:
                    st = str(it.get("status", status)).lower()
                    if st in ("confirmed", "completed"):
                        return "confirmed"
                    if st in ("voided", "cancelled", "failed", "rejected"):
                        return "voided"
                    return "pending"
            if len(items) < PAGE:
                break  # last page for this status
            offset += PAGE
    return "missing"  # authoritatively absent across confirmed + voided + pending


def _record_completed_trade(c, order, quote_tx, now):
    """Insert the trades row for a confirmed settlement (shared by confirm + reconcile)."""
    trade_id = generate_trade_id(order["order_id"], order["taker_wallet"])
    insert_columns = [
        "trade_id", "order_id", "pair", "side", "maker_wallet", "taker_wallet",
        "amount_micro_rtc", "price_per_rtc_nano_quote", "total_quote_nano",
        "quote_tx", "completed_at",
    ]
    values = [
        trade_id, order["order_id"], order["pair"], order["side"],
        order["maker_wallet"], order["taker_wallet"],
        order["amount_micro_rtc"], order["price_per_rtc_nano_quote"],
        order["total_quote_nano"], quote_tx, now,
    ]
    include_legacy_money_columns_if_present(
        table_columns(c, "trades"), insert_columns, values,
        order["amount_rtc"], order["price_per_rtc"], order["total_quote"],
    )
    placeholders = ", ".join("?" for _ in values)
    c.execute(f"INSERT OR IGNORE INTO trades ({', '.join(insert_columns)}) VALUES ({placeholders})", values)
    return trade_id


def reconcile_settlements():
    """One reconciliation pass. Idempotent; safe to call at startup and on a timer.

    Drives every order stuck in a recoverable state to a terminal one without
    ever double-paying (payout idempotency) or revealing a preimage before its
    payout confirms (the secret is only readable once status reaches 'completed').
    Returns a small summary dict for observability / tests.
    """
    summary = {"promoted": 0, "recovered": 0, "reverted": 0, "refunded": 0, "left": 0, "skipped_locked": 0}
    now = int(time.time())
    cutoff = now - SETTLEMENT_STUCK_SECONDS
    conn = get_db()
    acquired = False
    try:
        # Leader election: only one process reconciles at a time, so concurrent
        # gunicorn workers (and the timer + /admin/reconcile + startup pass) can't
        # race the external refund/payout calls. Idempotency keeps funds safe even
        # without this; the lock keeps the work single-driver and counters honest.
        if not _acquire_reconcile_lock(conn):
            summary["skipped_locked"] = 1
            return summary
        acquired = True
        c = conn.cursor()
        rows = c.execute(
            "SELECT * FROM orders WHERE status IN "
            "('payout_pending', 'settling', 'refund_pending', 'settlement_recovery')",
            ()).fetchall()
        for row in rows:
            order = money_view(row)
            oid = order["order_id"]
            st = order["status"]

            if st == "refund_pending":
                # The escrow on a cancelled/expired order was posted by the order
                # MAKER (the order creator) — always refund to them. Do NOT derive
                # the recipient from side+taker: refund_pending is reached from OPEN
                # orders that may have no taker, so a side-based taker recipient
                # could refund to a NULL/wrong party (funds loss). This matches the
                # cancel/expiry happy paths, which both refund maker_wallet.
                poster = order["maker_wallet"]
                if order["escrow_job_id"] and safe_refund_escrow(
                        order["escrow_job_id"], poster,
                        "OTC refund retry (reconcile)", {"order_id": oid}):
                    # 'refund_pending' is produced by BOTH cancel and expiry. The
                    # happy paths set their own terminal ('cancelled'/'expired')
                    # after a successful refund; this branch only runs for crash-
                    # stranded rows, where the origin is unknown — infer it from the
                    # TTL: past expires_at => 'expired', otherwise 'cancelled'. Both
                    # are existing terminal states already out of the open book.
                    terminal = "expired" if (order.get("expires_at") or 0) <= now else "cancelled"
                    c.execute("UPDATE orders SET status = ? "
                              "WHERE order_id = ? AND status = 'refund_pending'", (terminal, oid))
                    conn.commit(); summary["refunded"] += 1
                else:
                    summary["left"] += 1
                continue

            # 'settling' that hasn't moved is only actionable once it's plausibly
            # crashed (give the live confirm handler time to finish first).
            if st == "settling" and (order.get("matched_at") or 0) > cutoff and (order.get("created_at") or 0) > cutoff:
                summary["left"] += 1
                continue

            payout = _lookup_worker_payout_status(oid)
            if payout == "confirmed":
                # Only finalize a GENUINELY-matched settlement: require the taker +
                # the quote-settlement reference. A stale or operator-set recovery
                # row that lacks these must NOT auto-complete — doing so would expose
                # the HTLC secret and record a trade with no verified quote leg.
                # Leave it for an operator (alert) instead.
                if not order.get("taker_wallet") or not order.get("settlement_tx"):
                    send_bridge_alert(
                        "warning",
                        "OTC reconcile: confirmed payout but order missing taker/settlement_tx",
                        {"order_id": oid, "status": st})
                    summary["left"] += 1
                    continue
                # Promote payout_pending / settling / settlement_recovery -> completed
                # and record the trade exactly once (INSERT OR IGNORE on the
                # deterministic trade_id). Sweeping 'settlement_recovery' here is what
                # rescues a row whose payout DID confirm after its claim was lost —
                # without it that completed trade would be permanently missing.
                quote_tx = order.get("settlement_tx")
                _record_completed_trade(c, order, quote_tx, now)
                c.execute("UPDATE orders SET status = 'completed', confirmed_at = ? "
                          "WHERE order_id = ? AND status IN "
                          "('payout_pending', 'settling', 'settlement_recovery')",
                          (now, oid))
                if c.execute("SELECT changes()").fetchone()[0]:
                    conn.commit(); summary["promoted"] += 1
                else:
                    conn.rollback(); summary["left"] += 1
            elif payout == "voided" and st in ("payout_pending", "settling"):
                c.execute("UPDATE orders SET status = 'settlement_recovery' "
                          "WHERE order_id = ? AND status IN ('payout_pending', 'settling')", (oid,))
                conn.commit()
                send_bridge_alert("critical", "OTC queued payout voided after escrow release",
                                  {"order_id": oid, "amount_rtc": order["amount_rtc"]})
                summary["recovered"] += 1
            elif payout == "missing" and st == "settling":
                # A 'settling' order with NO worker payout by its idempotency key.
                # 'missing' is AMBIGUOUS — never-queued OR confirmed-and-already-swept
                # — so we must NOT revert to a retryable 'matched': a swept-after-
                # payout order would become re-confirmable and could double-deliver
                # escrow. Route to settlement_recovery for an operator (the payout is
                # idempotent, so a re-drive is safe) and alert. (v2: this replaces the
                # unsafe missing->matched revert flagged in review.)
                c.execute("UPDATE orders SET status = 'settlement_recovery' "
                          "WHERE order_id = ? AND status = 'settling'", (oid,))
                conn.commit()
                send_bridge_alert("critical",
                                  "OTC settling order has no payout by idempotency key — needs recovery",
                                  {"order_id": oid})
                summary["recovered"] += 1
            else:
                # 'pending'/'unknown', or 'missing' for a non-settling row — leave for
                # the next pass (payout still queued, or transient node error). A
                # 'settlement_recovery' row with a non-confirmed payout stays put.
                summary["left"] += 1
        return summary
    finally:
        if acquired:
            _release_reconcile_lock(conn)
        conn.close()


def parse_order_ttl(value):
    if value is None:
        return ORDER_TTL_DEFAULT
    if isinstance(value, bool):
        raise ValueError("ttl_seconds must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("ttl_seconds must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("ttl_seconds must be an integer") from exc


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
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    side = str(data.get("side", "")).strip().lower()
    pair = str(data.get("pair", "RTC/USDC")).strip().upper()
    maker_wallet = str(data.get("wallet", "")).strip()
    amount_rtc = data.get("amount_rtc", 0)
    price_per_rtc = data.get("price_per_rtc", 0)
    maker_eth_address = str(data.get("eth_address", "")).strip()
    try:
        ttl = parse_order_ttl(data.get("ttl_seconds"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

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

    auth_error = require_wallet_auth(
        data,
        "create_order",
        CREATE_ORDER_AUTH_ID,
        maker_wallet,
        create_order_auth_fields(
            side,
            pair,
            amount_micro_rtc,
            price_per_rtc_nano_quote,
            ttl,
            maker_eth_address,
        ),
    )
    if auth_error:
        return jsonify({"error": auth_error}), 401

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

        # Auto-expire old orders in two phases so the durable 'expired'
        # transition commits BEFORE the irreversible refund (same ordering as
        # cancel): a commit failure must never leave a refunded order still
        # 'open' and matchable. Each transition is guarded with AND status='open'
        # so a stale expiry scan racing a concurrent match can't clobber/refund a
        # just-matched order.
        expired = c.execute(
            "SELECT order_id, maker_wallet, escrow_job_id FROM orders WHERE status = 'open' AND expires_at < ?",
            (now,)
        ).fetchall()
        to_refund = []
        for ex in expired:
            # Escrow orders move to the durable 'refund_pending' transient so a
            # crash before the refund leaves a reconcilable row, not a terminal
            # 'expired' with stranded escrow. Non-escrow orders expire straight
            # to terminal. Both are out of the open book (not re-matchable).
            target = "refund_pending" if ex["escrow_job_id"] else "expired"
            c.execute(
                "UPDATE orders SET status = ? WHERE order_id = ? AND status = 'open'",
                (target, ex["order_id"]))
            if c.execute("SELECT changes()").fetchone()[0] == 0:
                continue  # already matched/cancelled concurrently — leave it alone
            if ex["escrow_job_id"]:
                to_refund.append((ex["order_id"], ex["escrow_job_id"], ex["maker_wallet"]))
        if expired:
            conn.commit()
        # Expiry is durable; refund escrow best-effort (raise-proof, so a refund/
        # alert failure can't 500 this hot GET path). On success promote
        # 'refund_pending' -> terminal 'expired'; on failure the row stays
        # 'refund_pending' and reconcile_settlements() retries + alerts.
        refunded_any = False
        for order_id_x, job_id, maker in to_refund:
            if safe_refund_escrow(
                    job_id, maker, "OTC escrow refund failed on order expiry",
                    {"order_id": order_id_x, "escrow_job_id": job_id, "maker_wallet": maker}):
                c.execute("UPDATE orders SET status = 'expired' "
                          "WHERE order_id = ? AND status = 'refund_pending'", (order_id_x,))
                refunded_any = True
        if refunded_any:
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
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    taker_wallet = str(data.get("wallet", "")).strip()
    taker_eth_address = str(data.get("eth_address", "")).strip()

    if not taker_wallet:
        return jsonify({"error": "wallet required"}), 400
    auth_error = require_wallet_auth(
        data,
        "match_order",
        order_id,
        taker_wallet,
        {"eth_address": taker_eth_address},
    )
    if auth_error:
        return jsonify({"error": auth_error}), 401

    conn = get_db()
    # Escrow this request locks (buy side); released on any failure after the
    # lock but before the match commits, so it is never orphaned.
    created_escrow_job_id = None
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
            # Escrow orders → durable 'refund_pending' (reconcilable on crash);
            # non-escrow → terminal 'expired'.
            target = "refund_pending" if order["escrow_job_id"] else "expired"
            c.execute(
                "UPDATE orders SET status = ? WHERE order_id = ? AND status = 'open'",
                (target, order_id))
            won_expire = c.execute("SELECT changes()").fetchone()[0] != 0
            if won_expire:
                conn.commit()  # commit the out-of-book state BEFORE the refund
                # Only refund if THIS request expired the row (not a racing match).
                if order["escrow_job_id"]:
                    if safe_refund_escrow(
                            order["escrow_job_id"], order["maker_wallet"],
                            "OTC escrow refund failed on order expiry",
                            {"order_id": order_id, "escrow_job_id": order["escrow_job_id"],
                             "maker_wallet": order["maker_wallet"]}):
                        c.execute("UPDATE orders SET status = 'expired' "
                                  "WHERE order_id = ? AND status = 'refund_pending'", (order_id,))
                        conn.commit()
                    # else: stays 'refund_pending'; reconcile_settlements() retries it.
            else:
                conn.rollback()
            return jsonify({"error": "Order has expired"}), 410

        # For buy orders: taker is selling RTC, needs to lock escrow.
        # created_escrow_job_id (init'd above) tracks an escrow WE create this
        # request so we can release it if we then lose the atomic match CAS or
        # hit an error before committing.
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
            created_escrow_job_id = escrow_job_id
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
            # We lost the race. Release the escrow WE just locked, else the
            # loser's RTC is orphaned in a job no order row references.
            conn.rollback()
            if created_escrow_job_id:
                if not rtc_cancel_escrow(created_escrow_job_id, taker_wallet):
                    log.error(f"Failed to refund losing-taker escrow {created_escrow_job_id} for {order_id}")
                    send_bridge_alert(
                        "critical",
                        "OTC taker escrow orphaned after lost match race",
                        {"order_id": order_id, "escrow_job_id": created_escrow_job_id,
                         "taker_wallet": taker_wallet},
                    )
            return jsonify({"error": "Order was matched by someone else"}), 409

        conn.commit()
        # The escrow is now committed to a live matched order — clear the marker
        # so the exception handler below can never refund it out from under the
        # settlement if response building (or anything later) throws.
        created_escrow_job_id = None

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
        # Release escrow this request locked but never committed to an order,
        # so an unexpected failure can't strand the taker's RTC. (Cleared to None
        # right after a successful commit, so this only fires for uncommitted
        # escrow.) Alert on refund failure, same as the lost-race path.
        if created_escrow_job_id:
            refunded = False
            try:
                refunded = rtc_cancel_escrow(created_escrow_job_id, taker_wallet)
            except Exception:
                log.error(f"Exception refunding escrow {created_escrow_job_id} after match error for {order_id}")
            if not refunded:
                send_bridge_alert(
                    "critical",
                    "OTC taker escrow orphaned after match exception",
                    {"order_id": order_id, "escrow_job_id": created_escrow_job_id,
                     "taker_wallet": taker_wallet},
                )
        return internal_error_response("Order match")
    finally:
        conn.close()


@app.route("/api/orders/<order_id>/confirm", methods=["POST"])
@rate_limited
def confirm_order(order_id):
    """Confirm settlement -- verifies HTLC preimage, releases escrow."""
    data = request.get_json(silent=True)
    if data is None:
        if request.is_json and request.get_data(cache=True).strip():
            return jsonify({"error": "JSON object required"}), 400
        data = {}
    elif not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    wallet = str(data.get("wallet", "")).strip()
    quote_tx = str(data.get("quote_tx", "")).strip()
    secret = str(data.get("secret", "")).strip()

    if not wallet:
        return jsonify({"error": "wallet required"}), 400
    if not quote_tx:
        return jsonify({"error": "quote_tx required"}), 400

    conn = get_db()
    # Init before the try so the exception handler can always read it (it only
    # becomes meaningful once escrow is released, but must be bound regardless).
    escrow_released = False
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

        # Determine RTC recipient + validate BEFORE touching escrow.
        rtc_recipient = order["taker_wallet"] if order["side"] == "sell" else order["maker_wallet"]
        if not is_valid_wallet_id(rtc_recipient):
            return jsonify({
                "error": "Invalid RTC recipient wallet on matched order",
                "rtc_recipient": rtc_recipient,
            }), 400

        # Without an admin key we cannot transfer escrow proceeds from
        # otc_bridge_worker to the real recipient — refuse to release escrow
        # rather than trap funds.
        if not RC_ADMIN_KEY:
            return jsonify({
                "error": "Bridge payout unavailable: RC_ADMIN_KEY not configured"
            }), 500

        # Atomically claim this settlement BEFORE any irreversible external call.
        # The seller holds the preimage and could submit confirm twice; without
        # this, two concurrent confirms both pass the status=='matched' read and
        # both release escrow. Commit the matched->settling transition so a
        # racing confirm sees 'settling' and is rejected.
        c.execute(
            "UPDATE orders SET status = 'settling' WHERE order_id = ? AND status = 'matched'",
            (order_id,))
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            conn.rollback()
            return jsonify({"error": "Order is no longer matched (already settling or settled)"}), 409
        conn.commit()

        payout_status = "not_started"
        payout_result = {}
        # Tracks whether escrow funds have left into otc_bridge_worker. Drives
        # recovery if we crash mid-settlement: released -> settlement_recovery,
        # not-released -> safe to revert to 'matched' for retry.
        escrow_released = False

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

                # Accept releases funds to otc_bridge_worker. We then transfer
                # from worker → recipient via admin /wallet/transfer.
                if deliver_r.ok:
                    # Mark released BEFORE the call: accept is the point of no
                    # return. If it times out / disconnects the funds may have
                    # moved even though we got no ok response, so any exception
                    # from here must route recovery to 'settlement_recovery'
                    # (ambiguous), never back to a retryable 'matched'.
                    #
                    # DELIBERATE TRADE-OFF (reviewed): this also routes a purely
                    # client-side / pre-send failure (e.g. immediate ConnectionError)
                    # to settlement_recovery even though funds provably did NOT move,
                    # which costs an operator a manual re-drive on a confirm that was
                    # technically retryable. We accept that: `requests` cannot reliably
                    # distinguish "failed before the bytes left" from "failed after the
                    # node already moved funds", and on a money path we prefer
                    # operator-recovery (idempotent, fund-safe) over auto-retry that
                    # could double-move escrow. Clean, definitive failures (accept
                    # returns ok=False below) are NOT exceptions and still fall through
                    # to retryable 'matched'.
                    escrow_released = True
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

        payout_details = payout_result.get("details", {}) if isinstance(payout_result, dict) else {}
        payout_tx = payout_details.get("tx_hash") if isinstance(payout_details, dict) else None

        # Decide the real outcome — never mark 'completed' unless the payout to
        # the recipient actually succeeded:
        #   payout ok                      -> completed (+ record the trade)
        #   escrow released, payout failed -> settlement_recovery (funds left the
        #       escrow into otc_bridge_worker; payout is idempotent (#6799) so an
        #       operator can re-drive it — NOT retryable as a fresh confirm)
        #   escrow never released          -> revert to matched (safe to retry)
        # CONFIRM-BEFORE-FINALIZE. rtc_transfer_from_worker QUEUES the payout into
        # the node's pending pool (phase 'pending') — it settles later and can
        # still be voided inside the confirmation window. Revealing the HTLC
        # preimage or recording the trade on a merely-queued payout breaks
        # atomicity: the counterparty could claim the quote side off the revealed
        # preimage while the RTC payout never lands. So ONLY a CONFIRMED payout
        # finalizes (completed + preimage). A queued payout parks in the durable
        # 'payout_pending' state; reconcile_settlements() promotes it later to
        # 'completed' (on confirm) or 'settlement_recovery' (on void). The payout
        # is idempotent (key otc_payout:<order_id>, #6799), so reconciliation can
        # always re-derive its status from the node's pending pool by that key.
        payout_ok = isinstance(payout_result, dict) and bool(payout_result.get("ok"))
        payout_phase = payout_details.get("phase") if (payout_ok and isinstance(payout_details, dict)) else None
        payout_confirmed = payout_ok and payout_phase == "confirmed"
        payout_queued = payout_ok and not payout_confirmed
        trade_id = generate_trade_id(order_id, order["taker_wallet"])

        if payout_confirmed:
            final_status = "completed"
        elif payout_queued:
            final_status = "payout_pending"   # escrow released + payout queued — NOT yet atomic-final
        elif payout_status == "manual_recovery_required":
            final_status = "settlement_recovery"
        else:
            final_status = "matched"  # escrow untouched (claim/deliver/accept failed) — retryable

        # Record the trade ONLY on a CONFIRMED settlement, so trade history /
        # volume stats never count queued, failed, or pending settlements.
        if payout_confirmed:
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
            c.execute("""
                UPDATE orders SET status = 'completed', confirmed_at = ?, settlement_tx = ?
                WHERE order_id = ? AND status = 'settling'
            """, (now, quote_tx, order_id))
            if c.execute("SELECT changes()").fetchone()[0] == 0:
                # Our 'settling' claim vanished AFTER a confirmed payout. The funds
                # are gone; the order must NOT be left in a retryable state. Force
                # 'settlement_recovery' (idempotent payout means a re-drive can't
                # double-pay) and alert — never a bare 409 that leaves the row in
                # an ambiguous, re-confirmable state (the double-pay window).
                conn.rollback()
                rec = conn.cursor()
                rec.execute(
                    "UPDATE orders SET status = 'settlement_recovery', settlement_tx = ? "
                    "WHERE order_id = ? AND status NOT IN ('completed', 'settlement_recovery')",
                    (quote_tx, order_id))
                conn.commit()
                send_bridge_alert(
                    "critical",
                    "OTC settlement claim lost after confirmed payout",
                    {"order_id": order_id, "recipient": rtc_recipient,
                     "amount_rtc": order["amount_rtc"], "payout_tx": payout_tx},
                )
                return jsonify({
                    "ok": False, "status": "settlement_recovery", "order_id": order_id,
                    "error": "Settlement claim lost after confirmed payout; routed to recovery",
                }), 409
        else:
            # Queued/failed: store the quote_tx (so a later promotion can record the
            # trade) and release our 'settling' claim to its durable next state.
            # 'payout_pending' is picked up by reconcile_settlements(); 'matched' is
            # a safe retry; 'settlement_recovery' needs an operator.
            # Persist settlement_tx whenever a payout is actually out there
            # (payout_pending OR settlement_recovery), not only when queued: an
            # idempotent payout that lands later must be promotable by
            # reconcile_settlements(), which refuses to promote a confirmed
            # payout whose order has no settlement_tx (#6813 tribrain finding).
            # 'matched' means the escrow was never released, so no tx to store.
            store_tx = quote_tx if final_status in ("payout_pending", "settlement_recovery") else None
            c.execute(
                "UPDATE orders SET status = ?, settlement_tx = ? "
                "WHERE order_id = ? AND status = 'settling'",
                (final_status, store_tx, order_id))
        conn.commit()

        if final_status == "completed":
            message = (
                f"Trade completed. {order['amount_rtc']} RTC payout to {rtc_recipient} "
                "succeeded. HTLC secret verified and revealed."
            )
        elif final_status == "payout_pending":
            message = (
                f"Escrow released; {order['amount_rtc']} RTC payout to {rtc_recipient} is "
                "QUEUED and pending confirmation. The HTLC secret is withheld until the "
                f"payout confirms — poll GET /orders/{order_id} for completion."
            )
        elif final_status == "settlement_recovery":
            message = (
                f"Escrow released but payout to {rtc_recipient} failed. Operators were "
                "alerted; the payout is idempotent and will be re-driven for recovery. "
                "This order is NOT retryable as a fresh confirm."
            )
        else:  # reverted to matched
            message = (
                f"Settlement could not be completed (escrow status '{payout_status}'); "
                "no funds left escrow. Order returned to 'matched' — retry confirm."
            )

        response = {
            "ok": payout_confirmed,
            "order_id": order_id,
            "status": final_status,
            "amount_rtc": order["amount_rtc"],
            "rtc_recipient": rtc_recipient,
            "rtc_transfer_status": payout_status,
            "rtc_transfer_pending_id": payout_details.get("pending_id") if isinstance(payout_details, dict) else None,
            "rtc_transfer_tx_hash": payout_tx,
            "message": message,
        }
        if final_status == "completed":
            # Reveal the preimage + trade_id ONLY on a CONFIRMED swap. A queued
            # payout must not leak the secret (that is the atomicity break #6803
            # was holding on) — it is released by reconciliation on confirmation.
            response["trade_id"] = trade_id
            response["htlc_secret"] = secret
        # Always HTTP 200: the request was processed and the outcome is in the
        # body (ok + status). Clients here branch on `ok`, not the status code;
        # a non-2xx would break the frontend's `if (data.ok)` flow.
        return jsonify(response)

    except Exception:
        conn.rollback()
        # We may hold a committed 'settling' claim (the claim is committed before
        # the external calls). The rollback above can't undo that prior commit,
        # so an exception here would otherwise WEDGE the order in 'settling'
        # forever (unconfirmable, invisible to the open book). Move it to a
        # recoverable state: 'settlement_recovery' if escrow funds may have left
        # (operator + idempotent payout), else back to 'matched' for retry.
        try:
            recovery = "settlement_recovery" if escrow_released else "matched"
            rc = conn.cursor()
            rc.execute(
                "UPDATE orders SET status = ? WHERE order_id = ? AND status = 'settling'",
                (recovery, order_id))
            if rc.execute("SELECT changes()").fetchone()[0]:
                conn.commit()
                send_bridge_alert(
                    "critical",
                    "OTC confirm errored mid-settlement",
                    {"order_id": order_id, "recovered_to": recovery,
                     "escrow_released": escrow_released},
                )
            else:
                conn.rollback()
        except Exception:
            log.error(f"Failed to recover wedged 'settling' order {order_id} after confirm error")
        return internal_error_response("Order confirmation")
    finally:
        conn.close()


@app.route("/api/orders/<order_id>/cancel", methods=["POST"])
@rate_limited
def cancel_order(order_id):
    """Cancel an open order and refund escrow."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    wallet = str(data.get("wallet", "")).strip()

    if not wallet:
        return jsonify({"error": "wallet required"}), 400
    auth_error = require_wallet_auth(data, "cancel_order", order_id, wallet)
    if auth_error:
        return jsonify({"error": auth_error}), 401

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

        # Atomically claim the open -> cancelled transition and COMMIT it BEFORE
        # the irreversible refund. Ordering matters two ways:
        #  - the status guard stops a cancel racing a match from refunding a
        #    matched order's escrow (changes()==0 -> we lost, do NOT refund);
        #  - committing first means a later commit failure can't roll the order
        #    back to 'open' after we've already refunded (which would let it be
        #    re-matched with no escrow). Once cancelled is durable, the refund is
        #    best-effort + alerted.
        # Escrow-bearing orders move to the durable 'refund_pending' transient
        # (not straight to 'cancelled'): if the process crashes between this
        # commit and the refund call, the reconciler finds 'refund_pending' and
        # retries — a terminal 'cancelled' would strand the escrow forever. Both
        # states are out of the open book, so neither is re-matchable. Orders with
        # no escrow go straight to the terminal 'cancelled'.
        has_escrow = bool(order["escrow_job_id"])
        target = "refund_pending" if has_escrow else "cancelled"
        c.execute(
            "UPDATE orders SET status = ? WHERE order_id = ? AND status = 'open'",
            (target, order_id))
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            conn.rollback()
            return jsonify({"error": "Order is no longer open (matched or cancelled concurrently)"}), 409
        conn.commit()

        escrow_refunded = True
        if has_escrow:
            escrow_refunded = safe_refund_escrow(
                order["escrow_job_id"], wallet,
                "OTC escrow refund failed after order cancel",
                {"order_id": order_id, "escrow_job_id": order["escrow_job_id"],
                 "maker_wallet": wallet})
            if escrow_refunded:
                # Refund landed — finalize to terminal 'cancelled'. If the row was
                # already swept by a racing reconcile pass, leave it (equivalent).
                c.execute("UPDATE orders SET status = 'cancelled' "
                          "WHERE order_id = ? AND status = 'refund_pending'", (order_id,))
                conn.commit()
            # else: stays 'refund_pending'; reconcile_settlements() retries + alerts.

        return jsonify({
            "ok": True,
            "order_id": order_id,
            "status": "cancelled" if escrow_refunded else "refund_pending",
            "escrow_refunded": escrow_refunded,
            "message": "Order cancelled. Escrow refunded." if escrow_refunded
                       else "Order cancel accepted; escrow refund is pending and will be "
                            "retried automatically by settlement reconciliation.",
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
    # Fail closed, not open: an unsupported (e.g. typo'd) pair must NOT fall
    # through to the unfiltered full-history feed. Mirrors /api/orderbook.
    if pair and pair not in SUPPORTED_PAIRS:
        return jsonify({"error": "unsupported pair"}), 400

    conn = get_db()
    try:
        if pair:
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


@app.route("/admin/reconcile", methods=["POST"])
def admin_reconcile():
    """Admin-triggered settlement reconciliation pass (ops + tests).

    Idempotent and CAS-guarded — running it concurrently with the timer or
    another caller cannot double-pay or finalize a still-pending payout.
    """
    if not RC_ADMIN_KEY or not hmac.compare_digest(
            request.headers.get("X-Admin-Key", ""), RC_ADMIN_KEY):
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": True, "summary": reconcile_settlements()})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Initialize the schema at import time so the app works under WSGI servers.
# The Dockerfile runs `gunicorn otc_bridge:app`, where __name__ != "__main__"
# and the block below never executes — without this, a fresh container has no
# tables and 500s on first request. init_db() is idempotent (CREATE TABLE IF
# NOT EXISTS + idempotent precision-column migration), so it is safe on every
# import and across concurrent gunicorn workers.
init_db()


# Settlement reconciliation runs in a background thread, started LAZILY on the
# first HTTP request — NOT at import time. Importing this module (tests, CLI
# tools, gunicorn worker boot, reloaders, `from otc_bridge import X`) must never
# make node calls, mutate settlement state, or spawn a forever-thread. The
# once-guard starts exactly one thread per worker process on its first request;
# that thread does a crash-recovery pass then (if enabled) loops. The work is
# idempotent + CAS-guarded, so per-worker redundancy is safe. Set
# OTC_RECONCILE_INTERVAL_SECONDS=0 to skip the timer (the one-shot startup pass
# still runs; drive ongoing reconciliation via POST /admin/reconcile). Set
# OTC_RECONCILE_DISABLED=1 to disable ALL automatic reconciliation (startup pass
# AND timer) — for read-only / admin-less / pure-test environments where no
# settlement mutation or node calls should ever happen implicitly.
RECONCILE_DISABLED = os.environ.get("OTC_RECONCILE_DISABLED", "").strip() not in ("", "0", "false", "False")


def _reconcile_loop():
    while True:
        time.sleep(RECONCILE_INTERVAL_SECONDS)
        try:
            reconcile_settlements()
        except Exception:
            log.exception("reconcile_settlements timer pass failed")


_reconcile_started = False
_reconcile_start_lock = threading.Lock()


def _reconcile_startup_and_loop():
    # OTC_RECONCILE_INTERVAL_SECONDS<=0 now means "no automatic reconciliation at
    # all" — neither the startup pass nor the timer — so an operator who sets it to
    # 0 gets exactly zero implicit settlement mutation / node calls (drive it via
    # POST /admin/reconcile). This avoids the surprise of the first read-only
    # request triggering a settlement pass (#6813 tribrain finding). Use
    # OTC_RECONCILE_DISABLED=1 to also stop the thread from ever starting.
    if RECONCILE_INTERVAL_SECONDS <= 0:
        return
    try:
        reconcile_settlements()
    except Exception:
        log.exception("startup reconcile_settlements pass failed")
    _reconcile_loop()


@app.before_request
def _start_reconciler_once():
    global _reconcile_started
    if _reconcile_started or RECONCILE_DISABLED:
        return
    with _reconcile_start_lock:
        if _reconcile_started:
            return
        _reconcile_started = True
    threading.Thread(target=_reconcile_startup_and_loop, name="otc-reconcile", daemon=True).start()


if __name__ == "__main__":
    port = _int_env("OTC_PORT", 5580)
    app.run(host="0.0.0.0", port=port, debug=False)
