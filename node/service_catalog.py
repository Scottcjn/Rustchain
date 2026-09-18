#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RustChain RTC service catalog.

Agents list work they can do, priced in RTC, and other agents order it.
Payment happens after delivery, from the buyer's own wallet, through the
existing ``/wallet/transfer/signed`` endpoint with memo ``svc:<order_id>``.

Design rules (see ~/elyan-labs/agent-economy/final.md, roadmap item 5):

* Non-custodial. This module stores listings and order receipts only. It
  never debits, credits, escrows or locks RTC, and takes no fee. Payment
  status is *read* from ``pending_ledger``.
* RTC only. Prices are RTC amounts. Request bodies reject unknown fields,
  and listing text that quotes a fiat figure is refused, so work is priced
  against other work and never in dollars.
* Work, not volume. Provider stats are counts of delivered and accepted
  work and distinct buyers. No RTC totals, no volume or earnings rankings.
  A deliverable hash can settle only one order, and a provider cannot buy
  from itself.

Auth uses the Beacon canonical request signature (same headers and
message layout as beacon_api), with the agent's Ed25519 public key looked
up in the Beacon Atlas ``relay_agents`` table.

Registered from wsgi.py via ``register_service_catalog(app, DB_PATH)``.
"""

import hashlib
import json
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import closing
from decimal import Decimal, DecimalException

from flask import Blueprint, jsonify, request

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except Exception:  # pragma: no cover
    Ed25519PublicKey = None

UNIT = 1_000_000  # uRTC per RTC, matches ledger amount_i64
AUTH_WINDOW_SECONDS = 300
AUTH_MAX_FUTURE_SECONDS = 30
# Same hard-coded path the node's resolve_bcn_wallet uses, so catalog and
# /wallet/transfer/signed always agree on who is registered. Deliberately
# no env override: the node has none either.
BEACON_ATLAS_DB = "/root/beacon/beacon_atlas.db"

CATEGORIES = (
    "render", "review", "hw_test", "vision", "compute",
    "docs", "translation", "testing", "other",
)
LISTING_STATUSES = ("active", "paused", "retired")

MIN_PRICE_I64 = 1                 # 0.000001 RTC
MAX_PRICE_I64 = 100_000 * UNIT    # sanity ceiling per unit of work
MAX_ACTIVE_LISTINGS = 25
MAX_OPEN_ORDERS_PER_BUYER = 20
MAX_LISTINGS_PER_DAY = 50
MAX_ORDERS_PER_DAY = 100
MAX_PAGE = 100
MAX_OFFSET = 10_000

TERMS = (
    "Prices are set by providers in RTC. Pay after delivery from your own "
    "wallet via /wallet/transfer/signed with memo svc:<order_id>. This "
    "catalog holds no funds, moves no RTC and takes no fee. RTC is a work "
    "credit, not for sale, with no price or redemption."
)

_CANONICAL_AGENT_ID = re.compile(r"^bcn_[0-9a-f]{12}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^(lst|ord)_[0-9a-f]{16}$")
# Fiat figures in free text: "$5", "5$", "€3", "10 USD", "USD5", "dollars".
# Best effort: the real control is that bodies accept no price field but
# price_rtc. Text is NFKC-normalised first so fullwidth forms match.
_FIAT = re.compile(
    r"[$€£¥¢₹₩₽]\s*\d|\d\s*[$€£¥¢₹₩₽]"
    r"|(?<![a-z])(usd|usdc|usdt|eur|euros?|gbp|cad|aud|chf|jpy|dollars?|bucks|cents)(?![a-z])",
    re.IGNORECASE,
)

_LISTING_FIELDS = {
    "title", "description", "category", "price_rtc", "unit", "turnaround_hours",
}
_ORDER_FIELDS = {"listing_id", "note"}


class _Reject(Exception):
    """Validation failure carrying an HTTP status and error payload."""

    def __init__(self, http_status, error, **extra):
        super().__init__(error)
        self.http_status = http_status
        self.payload = {"error": error, **extra}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_catalog_tables(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS catalog_listings (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                price_i64 INTEGER NOT NULL,
                unit TEXT NOT NULL DEFAULT 'per job',
                turnaround_hours INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_catalog_listings_provider
                ON catalog_listings(provider, status);
            CREATE INDEX IF NOT EXISTS idx_catalog_listings_category
                ON catalog_listings(category, status);

            CREATE TABLE IF NOT EXISTS catalog_orders (
                id TEXT PRIMARY KEY,
                listing_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                buyer TEXT NOT NULL,
                price_i64 INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'requested',
                deliverable_hash TEXT,
                deliverable_uri TEXT,
                close_reason TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_catalog_orders_provider
                ON catalog_orders(provider, status);
            CREATE INDEX IF NOT EXISTS idx_catalog_orders_buyer
                ON catalog_orders(buyer, status);
            -- A provider cannot settle two live orders with one artifact.
            -- Rejected or cancelled orders free the hash for redelivery.
            CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_orders_live_hash
                ON catalog_orders(provider, deliverable_hash)
                WHERE status IN ('delivered', 'accepted');

            CREATE TABLE IF NOT EXISTS catalog_agent_nonces (
                agent_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (agent_id, nonce)
            );
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rtc_from_i64(amount_i64):
    return float(Decimal(int(amount_i64)) / UNIT)


def _parse_price_i64(value):
    # bool is an int subclass; refuse it explicitly.
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _Reject(400, "price_rtc must be a number")
    try:
        dec = Decimal(str(value))
        if not dec.is_finite():
            raise _Reject(400, "price_rtc must be finite")
        if abs(dec) > Decimal(MAX_PRICE_I64) / UNIT:
            raise _Reject(400, "price_rtc out of range",
                          max_rtc=_rtc_from_i64(MAX_PRICE_I64))
        scaled = dec * UNIT
    except DecimalException:
        raise _Reject(400, "price_rtc must be a number")
    if scaled != scaled.to_integral_value():
        raise _Reject(400, "price_rtc supports at most 6 decimal places")
    price_i64 = int(scaled)
    if not MIN_PRICE_I64 <= price_i64 <= MAX_PRICE_I64:
        raise _Reject(400, "price_rtc out of range",
                      min_rtc=_rtc_from_i64(MIN_PRICE_I64),
                      max_rtc=_rtc_from_i64(MAX_PRICE_I64))
    return price_i64


def _text(data, field, *, min_len=0, max_len, default=None):
    value = data.get(field, default)
    if value is None:
        if min_len:
            raise _Reject(400, f"{field} is required")
        return ""
    if not isinstance(value, str):
        raise _Reject(400, f"{field} must be a string")
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        raise _Reject(400, f"{field} must be {min_len}-{max_len} characters")
    return value


def _no_fiat(field, value):
    if value and _FIAT.search(unicodedata.normalize("NFKC", value)):
        raise _Reject(400, "fiat_reference_not_allowed", field=field,
                      hint="Price work in RTC only; do not quote dollar or other fiat figures.")


def _json_body(allowed):
    raw = request.get_data(cache=True) or b""
    try:
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        raise _Reject(400, "body must be JSON")
    if not isinstance(data, dict):
        raise _Reject(400, "body must be a JSON object")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise _Reject(400, "unknown_fields", fields=unknown, allowed=sorted(allowed))
    return data


def _listing_json(row):
    return {
        "id": row["id"],
        "provider": row["provider"],
        "title": row["title"],
        "description": row["description"],
        "category": row["category"],
        "price_rtc": _rtc_from_i64(row["price_i64"]),
        "unit": row["unit"],
        "turnaround_hours": row["turnaround_hours"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _payment_memo(order_id):
    return f"svc:{order_id}"


def _payment_status(conn, order):
    """Read-only reconciliation against pending_ledger.

    A payment counts when a signed transfer to the provider, from someone
    other than the provider, carries this order's memo and covers the
    snapshot price. Voided transfers never count.
    """
    try:
        rows = conn.execute(
            """
            SELECT status, tx_hash FROM pending_ledger
            WHERE to_miner = ? AND from_miner != ? AND reason = ?
              AND amount_i64 >= ? AND status IN ('pending', 'confirmed')
            ORDER BY CASE status WHEN 'confirmed' THEN 0 ELSE 1 END, id
            """,
            (order["provider"], order["provider"],
             "signed_transfer:" + _payment_memo(order["id"]), order["price_i64"]),
        ).fetchall()
    except sqlite3.OperationalError:
        return {"state": "unknown"}
    if not rows:
        return {"state": "unpaid"}
    return {"state": rows[0]["status"], "tx_hash": rows[0]["tx_hash"]}


def _order_public_json(conn, row):
    """What anyone holding an order id may see. Order ids appear in ledger
    memos, so notes and delivery links stay party-only."""
    out = {
        "id": row["id"],
        "listing_id": row["listing_id"],
        "provider": row["provider"],
        "price_rtc": _rtc_from_i64(row["price_i64"]),
        "status": row["status"],
        "updated_at": row["updated_at"],
    }
    if row["status"] == "accepted":
        out["payment"] = _payment_status(conn, row)
    return out


def _order_json(conn, row):
    """Full view, for the buyer and provider only."""
    out = {
        "id": row["id"],
        "listing_id": row["listing_id"],
        "provider": row["provider"],
        "buyer": row["buyer"],
        "price_rtc": _rtc_from_i64(row["price_i64"]),
        "note": row["note"],
        "status": row["status"],
        "deliverable_hash": row["deliverable_hash"],
        "deliverable_uri": row["deliverable_uri"],
        "close_reason": row["close_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if row["status"] == "accepted":
        out["payment"] = _payment_status(conn, row)
        out["payment_instructions"] = _payment_instructions(row)
    return out


def _payment_instructions(row):
    return {
        "endpoint": "/wallet/transfer/signed",
        "to_address": row["provider"],
        "amount_rtc": _rtc_from_i64(row["price_i64"]),
        "memo": _payment_memo(row["id"]),
        "note": ("Send one signed transfer for the full amount from your own wallet. "
                 "This catalog does not move funds."),
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _atlas_pubkey_resolver(atlas_db_path):
    """Return the Atlas pubkey for an active agent, else None.

    Mirrors resolve_bcn_wallet: suspended or revoked agents are treated as
    unregistered (the transfer endpoint would refuse to pay them anyway).
    """
    def resolve(agent_id):
        try:
            with closing(sqlite3.connect(atlas_db_path)) as conn:
                row = conn.execute(
                    "SELECT pubkey_hex, status FROM relay_agents WHERE agent_id = ?",
                    (agent_id,),
                ).fetchone()
        except sqlite3.Error:
            return None
        if not row or (row[1] or "active") != "active":
            return None
        return row[0]
    return resolve


def _id_matches_pubkey(agent_id, pubkey_hex):
    try:
        key = bytes.fromhex(str(pubkey_hex).strip().removeprefix("0x"))
    except ValueError:
        return False
    return agent_id == "bcn_" + hashlib.sha256(key).hexdigest()[:12]


def _canonical_message(agent_id, timestamp, nonce, body_bytes):
    """Beacon layout (beacon_api._canonical_agent_request), except the path
    includes the query string so signed GET filters can't be altered. For a
    request with no query this is byte-identical to Beacon's message."""
    return "\n".join([
        request.method.upper(),
        request.full_path.rstrip("?"),
        hashlib.sha256(body_bytes or b"").hexdigest(),
        str(timestamp),
        str(nonce),
        str(agent_id),
    ]).encode("utf-8")


def _verify(pubkey_hex, signature_hex, message):
    if Ed25519PublicKey is None:
        return False
    try:
        key = str(pubkey_hex or "").strip()
        if key.lower().startswith("0x"):
            key = key[2:]
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(
            bytes.fromhex(str(signature_hex or "").strip()), message)
        return True
    except Exception:
        return False


def _authenticate(conn, resolve_pubkey):
    agent_id = request.headers.get("X-Agent-Id", "")
    timestamp_raw = request.headers.get("X-Agent-Timestamp", "")
    nonce = request.headers.get("X-Agent-Nonce", "")
    signature = request.headers.get("X-Agent-Signature", "")
    if not all([agent_id, timestamp_raw, nonce, signature]):
        raise _Reject(401, "Missing Beacon signature headers: X-Agent-Id, "
                           "X-Agent-Timestamp, X-Agent-Nonce, X-Agent-Signature")
    if not _CANONICAL_AGENT_ID.match(agent_id):
        raise _Reject(400, "X-Agent-Id must be a canonical bcn_ id")
    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        raise _Reject(400, "Invalid X-Agent-Timestamp")
    now = int(time.time())
    if timestamp < now - AUTH_WINDOW_SECONDS or timestamp > now + AUTH_MAX_FUTURE_SECONDS:
        raise _Reject(401, "Stale Beacon signature timestamp")
    if not nonce.strip() or len(nonce) > 128:
        raise _Reject(400, "Invalid X-Agent-Nonce")

    pubkey_hex = resolve_pubkey(agent_id)
    if not pubkey_hex or not _id_matches_pubkey(agent_id, pubkey_hex):
        raise _Reject(403, "agent not registered and active in Beacon Atlas")
    message = _canonical_message(agent_id, timestamp, nonce, request.get_data(cache=True))
    if not _verify(pubkey_hex, signature, message):
        raise _Reject(401, "Invalid Beacon agent signature")

    # Keep each nonce until its signature can no longer pass the timestamp
    # check (created_at = the later of now and the signed timestamp).
    conn.execute("DELETE FROM catalog_agent_nonces WHERE created_at < ?",
                 (now - AUTH_WINDOW_SECONDS,))
    try:
        conn.execute(
            "INSERT INTO catalog_agent_nonces (agent_id, nonce, created_at) VALUES (?, ?, ?)",
            (agent_id, nonce, max(now, timestamp)))
    except sqlite3.IntegrityError:
        conn.rollback()
        raise _Reject(401, "Replay detected for Beacon agent nonce")
    # Commit now: a signed request is spent even if the action it asks for
    # is refused, so it can't be replayed once the state changes.
    conn.commit()
    return agent_id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def create_catalog_blueprint(db_path, pubkey_resolver):
    bp = Blueprint("service_catalog", __name__, url_prefix="/catalog")

    def connect():
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def handle(fn):
        """Run fn(conn) in one transaction; map _Reject to JSON errors."""
        with closing(connect()) as conn:
            try:
                result = fn(conn)
                conn.commit()
                return result
            except _Reject as rej:
                conn.rollback()
                return jsonify(rej.payload), rej.http_status

    def get_order(conn, order_id):
        if not _ID.match(order_id or ""):
            raise _Reject(404, "order not found")
        row = conn.execute("SELECT * FROM catalog_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise _Reject(404, "order not found")
        return row

    def transition(conn, order, actor_field, agent_id, from_status, to_status, **fields):
        if order[actor_field] != agent_id:
            raise _Reject(403, f"only the {actor_field} can do this")
        sets = ", ".join(f"{k} = ?" for k in fields)
        sql = (f"UPDATE catalog_orders SET status = ?, updated_at = ?"
               f"{', ' + sets if sets else ''} WHERE id = ? AND status = ?")
        try:
            cur = conn.execute(sql, (to_status, int(time.time()), *fields.values(),
                                     order["id"], from_status))
        except sqlite3.IntegrityError:
            raise _Reject(409, "deliverable_hash already used by another order")
        if cur.rowcount != 1:
            raise _Reject(409, f"order must be {from_status}", status=order["status"])
        return conn.execute("SELECT * FROM catalog_orders WHERE id = ?", (order["id"],)).fetchone()

    @bp.route("", methods=["GET"])
    def catalog_index():
        return jsonify({"currency": "RTC", "categories": list(CATEGORIES), "terms": TERMS})

    @bp.route("/listings", methods=["GET"])
    def list_listings():
        clauses, params = ["status = 'active'"], []
        category = request.args.get("category")
        if category:
            clauses.append("category = ?")
            params.append(category)
        provider = request.args.get("provider")
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        try:
            limit = max(1, min(MAX_PAGE, int(request.args.get("limit", 50))))
            offset = max(0, min(MAX_OFFSET, int(request.args.get("offset", 0))))
        except ValueError:
            return jsonify({"error": "limit and offset must be integers"}), 400
        with closing(connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM catalog_listings WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
                (*params, limit, offset)).fetchall()
        return jsonify({"listings": [_listing_json(r) for r in rows],
                        "limit": limit, "offset": offset, "terms": TERMS})

    @bp.route("/listings/<listing_id>", methods=["GET"])
    def get_listing(listing_id):
        with closing(connect()) as conn:
            row = conn.execute("SELECT * FROM catalog_listings WHERE id = ?",
                               (listing_id,)).fetchone()
        if not row:
            return jsonify({"error": "listing not found"}), 404
        return jsonify(_listing_json(row))

    @bp.route("/listings", methods=["POST"])
    def create_listing():
        def run(conn):
            data = _json_body(_LISTING_FIELDS)
            provider = _authenticate(conn, pubkey_resolver)
            title = _text(data, "title", min_len=5, max_len=120)
            description = _text(data, "description", max_len=2000)
            unit = _text(data, "unit", min_len=1, max_len=32, default="per job")
            for field, value in (("title", title), ("description", description), ("unit", unit)):
                _no_fiat(field, value)
            category = data.get("category", "other")
            if category not in CATEGORIES:
                raise _Reject(400, "unknown category", allowed=list(CATEGORIES))
            price_i64 = _parse_price_i64(data.get("price_rtc"))
            turnaround = data.get("turnaround_hours")
            if turnaround is not None and (
                    isinstance(turnaround, bool) or not isinstance(turnaround, int)
                    or not 1 <= turnaround <= 24 * 90):
                raise _Reject(400, "turnaround_hours must be an integer 1-2160")
            active = conn.execute(
                "SELECT COUNT(*) FROM catalog_listings WHERE provider = ? AND status != 'retired'",
                (provider,)).fetchone()[0]
            if active >= MAX_ACTIVE_LISTINGS:
                raise _Reject(429, "too many open listings", max=MAX_ACTIVE_LISTINGS)
            recent = conn.execute(
                "SELECT COUNT(*) FROM catalog_listings WHERE provider = ? AND created_at > ?",
                (provider, int(time.time()) - 86400)).fetchone()[0]
            if recent >= MAX_LISTINGS_PER_DAY:
                raise _Reject(429, "daily listing limit reached", max=MAX_LISTINGS_PER_DAY)
            now = int(time.time())
            listing_id = "lst_" + secrets.token_hex(8)
            conn.execute(
                "INSERT INTO catalog_listings (id, provider, title, description, category, "
                "price_i64, unit, turnaround_hours, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (listing_id, provider, title, description, category, price_i64, unit,
                 turnaround, now, now))
            row = conn.execute("SELECT * FROM catalog_listings WHERE id = ?",
                               (listing_id,)).fetchone()
            return jsonify(_listing_json(row)), 201
        return handle(run)

    @bp.route("/listings/<listing_id>/status", methods=["POST"])
    def set_listing_status(listing_id):
        # Listings are immutable apart from status: to change a price, retire
        # the listing and post a new one. Orders snapshot the price anyway.
        def run(conn):
            data = _json_body({"status"})
            agent_id = _authenticate(conn, pubkey_resolver)
            status = data.get("status")
            if status not in LISTING_STATUSES:
                raise _Reject(400, "unknown status", allowed=list(LISTING_STATUSES))
            row = conn.execute("SELECT * FROM catalog_listings WHERE id = ?",
                               (listing_id,)).fetchone()
            if not row:
                raise _Reject(404, "listing not found")
            if row["provider"] != agent_id:
                raise _Reject(403, "only the provider can change this listing")
            if row["status"] == "retired":
                raise _Reject(409, "retired listings cannot be reopened; post a new listing")
            conn.execute("UPDATE catalog_listings SET status = ?, updated_at = ? WHERE id = ?",
                         (status, int(time.time()), listing_id))
            row = conn.execute("SELECT * FROM catalog_listings WHERE id = ?",
                               (listing_id,)).fetchone()
            return jsonify(_listing_json(row))
        return handle(run)

    @bp.route("/orders", methods=["POST"])
    def create_order():
        def run(conn):
            data = _json_body(_ORDER_FIELDS)
            buyer = _authenticate(conn, pubkey_resolver)
            note = _text(data, "note", max_len=2000)
            _no_fiat("note", note)
            listing = conn.execute("SELECT * FROM catalog_listings WHERE id = ?",
                                   (str(data.get("listing_id", "")),)).fetchone()
            if not listing:
                raise _Reject(404, "listing not found")
            if listing["status"] != "active":
                raise _Reject(409, "listing is not active", status=listing["status"])
            if listing["provider"] == buyer:
                raise _Reject(400, "self_dealing", hint="A provider cannot order its own listing.")
            open_orders = conn.execute(
                "SELECT COUNT(*) FROM catalog_orders WHERE buyer = ? "
                "AND status IN ('requested', 'delivered')", (buyer,)).fetchone()[0]
            if open_orders >= MAX_OPEN_ORDERS_PER_BUYER:
                raise _Reject(429, "too many open orders", max=MAX_OPEN_ORDERS_PER_BUYER)
            recent = conn.execute(
                "SELECT COUNT(*) FROM catalog_orders WHERE buyer = ? AND created_at > ?",
                (buyer, int(time.time()) - 86400)).fetchone()[0]
            if recent >= MAX_ORDERS_PER_DAY:
                raise _Reject(429, "daily order limit reached", max=MAX_ORDERS_PER_DAY)
            now = int(time.time())
            order_id = "ord_" + secrets.token_hex(8)
            conn.execute(
                "INSERT INTO catalog_orders (id, listing_id, provider, buyer, price_i64, note, "
                "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'requested', ?, ?)",
                (order_id, listing["id"], listing["provider"], buyer, listing["price_i64"],
                 note, now, now))
            row = conn.execute("SELECT * FROM catalog_orders WHERE id = ?", (order_id,)).fetchone()
            return jsonify(_order_json(conn, row)), 201
        return handle(run)

    @bp.route("/orders", methods=["GET"])
    def my_orders():
        """Signed inbox: ?role=provider|buyer&status=...  (sign the full path
        including the query string, with an empty body)."""
        def run(conn):
            agent_id = _authenticate(conn, pubkey_resolver)
            role = request.args.get("role", "provider")
            if role not in ("provider", "buyer"):
                raise _Reject(400, "role must be provider or buyer")
            clauses, params = [f"{role} = ?"], [agent_id]
            status = request.args.get("status")
            if status:
                clauses.append("status = ?")
                params.append(status)
            try:
                limit = max(1, min(MAX_PAGE, int(request.args.get("limit", 50))))
                offset = max(0, min(MAX_OFFSET, int(request.args.get("offset", 0))))
            except ValueError:
                raise _Reject(400, "limit and offset must be integers")
            rows = conn.execute(
                f"SELECT * FROM catalog_orders WHERE {' AND '.join(clauses)} "
                "ORDER BY updated_at DESC, id LIMIT ? OFFSET ?",
                (*params, limit, offset)).fetchall()
            return jsonify({"orders": [_order_json(conn, r) for r in rows],
                            "limit": limit, "offset": offset})
        return handle(run)

    @bp.route("/orders/<order_id>", methods=["GET"])
    def get_order_route(order_id):
        """Public summary; the full view needs a signature from a party."""
        def run(conn):
            if not request.headers.get("X-Agent-Id"):
                return jsonify(_order_public_json(conn, get_order(conn, order_id)))
            agent_id = _authenticate(conn, pubkey_resolver)
            order = get_order(conn, order_id)
            if agent_id not in (order["buyer"], order["provider"]):
                raise _Reject(403, "only the buyer or provider can see the full order")
            return jsonify(_order_json(conn, order))
        return handle(run)

    @bp.route("/orders/<order_id>/deliver", methods=["POST"])
    def deliver_order(order_id):
        def run(conn):
            data = _json_body({"deliverable_hash", "deliverable_uri"})
            agent_id = _authenticate(conn, pubkey_resolver)
            digest = str(data.get("deliverable_hash", "")).strip().lower()
            if not _SHA256_HEX.match(digest):
                raise _Reject(400, "deliverable_hash must be a sha256 hex digest")
            uri = _text(data, "deliverable_uri", max_len=500)
            if uri and not uri.startswith("https://"):
                raise _Reject(400, "deliverable_uri must be https")
            order = get_order(conn, order_id)
            row = transition(conn, order, "provider", agent_id, "requested", "delivered",
                             deliverable_hash=digest, deliverable_uri=uri or None)
            return jsonify(_order_json(conn, row))
        return handle(run)

    @bp.route("/orders/<order_id>/accept", methods=["POST"])
    def accept_order(order_id):
        def run(conn):
            _json_body(set())
            agent_id = _authenticate(conn, pubkey_resolver)
            row = transition(conn, get_order(conn, order_id), "buyer", agent_id,
                             "delivered", "accepted")
            return jsonify(_order_json(conn, row))
        return handle(run)

    @bp.route("/orders/<order_id>/reject", methods=["POST"])
    def reject_order(order_id):
        # Disputes affect standing only. Nothing was paid, so nothing refunds.
        def run(conn):
            data = _json_body({"reason"})
            agent_id = _authenticate(conn, pubkey_resolver)
            reason = _text(data, "reason", min_len=3, max_len=500)
            _no_fiat("reason", reason)
            row = transition(conn, get_order(conn, order_id), "buyer", agent_id,
                             "delivered", "rejected", close_reason=reason)
            return jsonify(_order_json(conn, row))
        return handle(run)

    @bp.route("/orders/<order_id>/cancel", methods=["POST"])
    def cancel_order(order_id):
        def run(conn):
            data = _json_body({"reason"})
            agent_id = _authenticate(conn, pubkey_resolver)
            reason = _text(data, "reason", max_len=500)
            _no_fiat("reason", reason)
            order = get_order(conn, order_id)
            actor = "buyer" if order["buyer"] == agent_id else "provider"
            row = transition(conn, order, actor, agent_id, "requested", "cancelled",
                             close_reason=reason or None)
            return jsonify(_order_json(conn, row))
        return handle(run)

    @bp.route("/providers/<agent_id>", methods=["GET"])
    def provider_record(agent_id):
        # Counts of work only. Deliberately no RTC totals and no rankings.
        with closing(connect()) as conn:
            listings = conn.execute(
                "SELECT COUNT(*) FROM catalog_listings WHERE provider = ? AND status = 'active'",
                (agent_id,)).fetchone()[0]
            counts = {s: 0 for s in ("delivered", "accepted", "rejected", "cancelled")}
            for status, n in conn.execute(
                    "SELECT status, COUNT(*) FROM catalog_orders WHERE provider = ? "
                    "GROUP BY status", (agent_id,)):
                if status in counts:
                    counts[status] = n
            distinct_buyers = conn.execute(
                "SELECT COUNT(DISTINCT buyer) FROM catalog_orders "
                "WHERE provider = ? AND status = 'accepted'", (agent_id,)).fetchone()[0]
            # Acceptance costs a buyer nothing, so it can be faked with extra
            # identities. Confirmed payment from someone other than the
            # provider is the stronger signal, reported separately.
            try:
                paid, paying_buyers = conn.execute(
                    """
                    SELECT COUNT(DISTINCT o.id), COUNT(DISTINCT o.buyer)
                    FROM catalog_orders o JOIN pending_ledger p
                      ON p.reason = 'signed_transfer:svc:' || o.id
                     AND p.to_miner = o.provider AND p.from_miner != o.provider
                     AND p.amount_i64 >= o.price_i64 AND p.status = 'confirmed'
                    WHERE o.provider = ? AND o.status = 'accepted'
                    """, (agent_id,)).fetchone()
            except sqlite3.OperationalError:
                paid = paying_buyers = None
        return jsonify({
            "agent_id": agent_id,
            "active_listings": listings,
            # "delivered" counts every order that reached delivery, whatever
            # the buyer decided afterwards.
            "orders_delivered": counts["delivered"] + counts["accepted"] + counts["rejected"],
            "orders_accepted": counts["accepted"],
            "orders_rejected": counts["rejected"],
            "orders_cancelled": counts["cancelled"],
            "distinct_buyers_accepted": distinct_buyers,
            "orders_paid_confirmed": paid,
            "distinct_paying_buyers": paying_buyers,
            "note": ("accepted counts are reported by buyers; paid counts are "
                     "confirmed signed transfers from a wallet other than the provider's id"),
        })

    return bp


def register_service_catalog(app, db_path, atlas_db_path=None, pubkey_resolver=None):
    """Create tables and mount /catalog. Never raises into node startup."""
    try:
        init_catalog_tables(db_path)
        resolver = pubkey_resolver or _atlas_pubkey_resolver(atlas_db_path or BEACON_ATLAS_DB)
        app.register_blueprint(create_catalog_blueprint(db_path, resolver))
        print("[catalog] RTC service catalog registered at /catalog")
        return True
    except Exception as exc:
        print(f"[catalog] registration failed: {exc}")
        return False
