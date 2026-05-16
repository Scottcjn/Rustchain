"""
RIP-305 Track C: Bridge API
Cross-chain bridge endpoints for wRTC (Wrapped RTC) on Solana + Base L2

Endpoints:
  POST /bridge/lock      - Lock RTC, get lock_id for cross-chain mint
  POST /bridge/release   - Admin: release wRTC on target chain
  GET  /bridge/ledger    - Query lock ledger (transparent)
  GET  /bridge/status/<lock_id> - Check lock status

Admin-controlled Phase 1 (upgrade to trustless lock in Phase 2)
"""

import os
import json
import sqlite3
import hashlib
import hmac
import math
import time
import threading
import uuid
from functools import wraps
from flask import Flask, Blueprint, request, jsonify

# ─── Config ──────────────────────────────────────────────────────────────────
BRIDGE_DB_PATH = os.environ.get("BRIDGE_DB_PATH", "bridge_ledger.db")
BRIDGE_ADMIN_KEY = os.environ.get("BRIDGE_ADMIN_KEY", "")  # set in production
BRIDGE_RECEIPT_SECRET = os.environ.get("BRIDGE_RECEIPT_SECRET", "")

# Security: require proof for all bridge locks (Issue #727)
BRIDGE_REQUIRE_PROOF = os.environ.get("BRIDGE_REQUIRE_PROOF", "true").lower() == "true"

# Target chain identifiers
CHAIN_SOLANA = "solana"
CHAIN_BASE = "base"
SUPPORTED_CHAINS = {CHAIN_SOLANA, CHAIN_BASE}

# RTC decimal precision
RTC_DECIMALS = 6

# Minimum lock amounts
MIN_LOCK_AMOUNT = 1  # 1 RTC
MAX_LOCK_AMOUNT = 10_000  # 10,000 RTC per transaction

# Lock states
STATE_REQUESTED = "requested"  # User submitted request, awaiting proof review
STATE_PENDING   = "pending"    # Lock received, awaiting processing
STATE_CONFIRMED = "confirmed"  # Lock confirmed on-chain
STATE_RELEASING = "releasing"  # Admin is minting wRTC
STATE_COMPLETE  = "complete"   # wRTC minted on target chain
STATE_FAILED    = "failed"     # Lock failed / expired
STATE_REFUNDED  = "refunded"   # RTC refunded to sender

# Lock expiry (24h in seconds)
LOCK_EXPIRY_SECONDS = 86_400

# ─── Database ─────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(BRIDGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_bridge_db():
    """Initialize the bridge ledger database."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS bridge_locks (
            lock_id       TEXT PRIMARY KEY,
            sender_wallet TEXT NOT NULL,
            amount_rtc    INTEGER NOT NULL,       -- in base units (millionths)
            target_chain  TEXT NOT NULL,
            target_wallet TEXT NOT NULL,
            state         TEXT NOT NULL DEFAULT 'pending',
            tx_hash       TEXT,                  -- RustChain tx that locked RTC
            proof_type    TEXT DEFAULT '',
            proof_ref     TEXT DEFAULT '',
            release_tx    TEXT,                  -- Target chain tx that minted wRTC
            confirmed_at  INTEGER DEFAULT 0,
            confirmed_by  TEXT DEFAULT '',
            created_at    INTEGER NOT NULL,
            updated_at    INTEGER NOT NULL,
            expires_at    INTEGER NOT NULL,
            notes         TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_locks_sender ON bridge_locks(sender_wallet);
        CREATE INDEX IF NOT EXISTS idx_locks_state  ON bridge_locks(state);
        CREATE INDEX IF NOT EXISTS idx_locks_chain  ON bridge_locks(target_chain);

        CREATE TABLE IF NOT EXISTS bridge_events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lock_id       TEXT NOT NULL,
            event_type    TEXT NOT NULL,
            actor         TEXT,
            details       TEXT,
            ts            INTEGER NOT NULL
        );
        """)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(bridge_locks)").fetchall()}
        migrations = {
            "proof_type": "ALTER TABLE bridge_locks ADD COLUMN proof_type TEXT DEFAULT ''",
            "proof_ref": "ALTER TABLE bridge_locks ADD COLUMN proof_ref TEXT DEFAULT ''",
            "confirmed_at": "ALTER TABLE bridge_locks ADD COLUMN confirmed_at INTEGER DEFAULT 0",
            "confirmed_by": "ALTER TABLE bridge_locks ADD COLUMN confirmed_by TEXT DEFAULT ''",
        }
        for col, sql in migrations.items():
            if col not in cols:
                conn.execute(sql)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_locks_tx_hash ON bridge_locks(tx_hash) WHERE tx_hash IS NOT NULL AND tx_hash != ''")
    print("[bridge] DB initialized:", BRIDGE_DB_PATH)


def log_event(conn, lock_id: str, event_type: str, actor: str = None, details: dict = None):
    conn.execute(
        "INSERT INTO bridge_events (lock_id, event_type, actor, details, ts) VALUES (?,?,?,?,?)",
        (lock_id, event_type, actor, json.dumps(details or {}), int(time.time()))
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _amount_to_base(amount_float: float) -> int:
    """Convert human-readable RTC to base units (6 decimal places)."""
    return int(round(amount_float * (10 ** RTC_DECIMALS)))


def _amount_from_base(amount_int: int) -> float:
    """Convert base units to human-readable RTC."""
    return amount_int / (10 ** RTC_DECIMALS)


def _generate_lock_id(sender: str, amount: int, target_chain: str, ts: int) -> str:
    """Deterministic lock ID from key fields."""
    raw = f"{sender}:{amount}:{target_chain}:{ts}:{uuid.uuid4()}"
    return "lock_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _canonical_lock_receipt(sender: str, amount_base: int, target_chain: str, target_wallet: str, tx_hash: str) -> bytes:
    """Canonical payload for signed lock receipts."""
    payload = {
        "sender_wallet": sender,
        "amount_base": amount_base,
        "target_chain": target_chain,
        "target_wallet": target_wallet,
        "tx_hash": tx_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_receipt_signature(sender: str, amount_base: int, target_chain: str, target_wallet: str, tx_hash: str, receipt_signature: str) -> bool:
    """Verify HMAC-SHA256 bridge receipt signature when a receipt secret is configured."""
    if not BRIDGE_RECEIPT_SECRET:
        return False
    message = _canonical_lock_receipt(sender, amount_base, target_chain, target_wallet, tx_hash)
    expected = hmac.new(BRIDGE_RECEIPT_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, receipt_signature.lower())


def _require_admin(fn):
    """Decorator: require X-Admin-Key header."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-Admin-Key", "")
        if not BRIDGE_ADMIN_KEY:
            return jsonify({"error": "admin key not configured on server"}), 500
        if not hmac.compare_digest(key, BRIDGE_ADMIN_KEY):
            return jsonify({"error": "unauthorized"}), 403
        return fn(*args, **kwargs)
    return wrapper


def _json_object_body():
    """Return the parsed JSON body only when it is an object."""
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON object body is required"}), 400)
    return data, None


def _clean_string_field(data, field_name, *, optional=False, lower=False):
    value = data.get(field_name)
    if value is None:
        return None if optional else ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if lower:
        value = value.lower()
    if optional and not value:
        return None
    return value


# ─── Blueprint ────────────────────────────────────────────────────────────────
bridge_bp = Blueprint("bridge", __name__, url_prefix="/bridge")


@bridge_bp.route("/lock", methods=["POST"])
def lock_rtc():
    """
    Lock RTC for cross-chain bridge.

    Body (JSON):
      sender_wallet  : str   - RustChain wallet name
      amount         : float - RTC to lock (e.g. 100.5)
      target_chain   : str   - "solana" or "base"
      target_wallet  : str   - Solana address or Base EVM address
      tx_hash        : str   - RustChain tx confirming the lock request
      receipt_signature : str - (optional) HMAC-SHA256 signed receipt for direct confirmation

    Returns:
      lock_id        : str   - Unique identifier for this lock
      state          : str   - "requested" or "confirmed"
      expires_at     : int   - Unix timestamp when lock expires
      amount_rtc     : float - Amount locked

    Security (Issue #727):
      - Requires verifiable proof (signed receipt) when BRIDGE_REQUIRE_PROOF is enabled
      - Rejects requests with invalid proof signatures
      - Validates proof before accepting lock into ledger
    """
    data, error_response = _json_object_body()
    if error_response:
        return error_response

    # ── Validate inputs ──
    try:
        sender = _clean_string_field(data, "sender_wallet")
        target_chain = _clean_string_field(data, "target_chain", lower=True)
        target_wallet = _clean_string_field(data, "target_wallet")
        tx_hash = _clean_string_field(data, "tx_hash", optional=True)
        receipt_signature = _clean_string_field(data, "receipt_signature", optional=True, lower=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        amount_float = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid amount"}), 400
    if not math.isfinite(amount_float):
        return jsonify({"error": "invalid amount"}), 400

    if not sender:
        return jsonify({"error": "sender_wallet is required"}), 400
    if target_chain not in SUPPORTED_CHAINS:
        return jsonify({"error": f"target_chain must be one of: {', '.join(sorted(SUPPORTED_CHAINS))}"}), 400
    if not target_wallet:
        return jsonify({"error": "target_wallet is required"}), 400
    if not tx_hash:
        return jsonify({"error": "tx_hash is required for bridge lock requests"}), 400
    if amount_float < MIN_LOCK_AMOUNT:
        return jsonify({"error": f"minimum lock amount is {MIN_LOCK_AMOUNT} RTC"}), 400
    if amount_float > MAX_LOCK_AMOUNT:
        return jsonify({"error": f"maximum lock amount is {MAX_LOCK_AMOUNT} RTC"}), 400

    # Validate target wallet format
    if target_chain == CHAIN_BASE and not target_wallet.startswith("0x"):
        return jsonify({"error": "Base wallet must be a 0x EVM address"}), 400
    if target_chain == CHAIN_SOLANA and len(target_wallet) < 32:
        return jsonify({"error": "Solana wallet must be a valid base58 address"}), 400

    amount_base = _amount_to_base(amount_float)
    now = int(time.time())
    expires_at = now + LOCK_EXPIRY_SECONDS
    lock_id = _generate_lock_id(sender, amount_base, target_chain, now)

    # ── Issue #727: Strict proof validation ──
    proof_type = None
    proof_ref = None
    state = None
    confirmed_at = 0
    confirmed_by = ""

    if receipt_signature:
        # User provided a signed receipt - verify it
        if not BRIDGE_RECEIPT_SECRET:
            return jsonify({
                "error": "bridge receipt verification is not configured on server"
            }), 503
        if not _verify_receipt_signature(
            sender, amount_base, target_chain, target_wallet, tx_hash, receipt_signature
        ):
            return jsonify({
                "error": "invalid receipt_signature - proof verification failed"
            }), 403
        # Valid signed receipt - lock is confirmed immediately
        proof_type = "signed_receipt"
        proof_ref = f"receipt:{tx_hash}"
        state = STATE_CONFIRMED
        confirmed_at = now
        confirmed_by = "receipt"
    elif BRIDGE_REQUIRE_PROOF:
        # No proof provided but proof is required
        return jsonify({
            "error": "proof required: receipt_signature must be provided for bridge lock acceptance"
        }), 400
    else:
        # Proof not required - accept for manual review (legacy mode)
        proof_type = "tx_hash_review"
        proof_ref = tx_hash
        state = STATE_REQUESTED

    with _db_lock:
        with get_db() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO bridge_locks
                      (lock_id, sender_wallet, amount_rtc, target_chain, target_wallet,
                       state, tx_hash, proof_type, proof_ref, confirmed_at, confirmed_by,
                       created_at, updated_at, expires_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        lock_id,
                        sender,
                        amount_base,
                        target_chain,
                        target_wallet,
                        state,
                        tx_hash,
                        proof_type,
                        proof_ref,
                        confirmed_at,
                        confirmed_by,
                        now,
                        now,
                        expires_at,
                    )
                )
            except sqlite3.IntegrityError:
                return jsonify({"error": "tx_hash already used for another bridge lock"}), 409

            log_event(conn, lock_id, "lock_created", actor=sender, details={
                "amount": amount_float,
                "target_chain": target_chain,
                "target_wallet": target_wallet,
                "tx_hash": tx_hash,
                "proof_type": proof_type,
                "state": state,
            })
            if state == STATE_CONFIRMED:
                log_event(conn, lock_id, "lock_confirmed", actor=confirmed_by, details={
                    "proof_type": proof_type,
                    "proof_ref": proof_ref,
                })
            conn.commit()

    return jsonify({
        "lock_id": lock_id,
        "state": state,
        "sender_wallet": sender,
        "amount_rtc": amount_float,
        "target_chain": target_chain,
        "target_wallet": target_wallet,
        "tx_hash": tx_hash,
        "proof_type": proof_type,
        "proof_ref": proof_ref,
        "expires_at": expires_at,
        "message": (
            f"Lock {'confirmed' if state == STATE_CONFIRMED else 'requested'}. "
            f"Admin will only mint {amount_float} wRTC on {target_chain} "
            f"to {target_wallet[:12]}... after proof confirmation."
        )
    }), 201


@bridge_bp.route("/confirm", methods=["POST"])
@_require_admin
def confirm_lock():
    """Admin: confirm a requested lock after reviewing proof."""
    data, error_response = _json_object_body()
    if error_response:
        return error_response
    try:
        lock_id = _clean_string_field(data, "lock_id")
        proof_ref = _clean_string_field(data, "proof_ref")
        notes = _clean_string_field(data, "notes", optional=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not lock_id:
        return jsonify({"error": "lock_id is required"}), 400
    if not proof_ref:
        return jsonify({"error": "proof_ref is required"}), 400

    now = int(time.time())
    with _db_lock:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM bridge_locks WHERE lock_id = ?",
                (lock_id,),
            ).fetchone()
            if not row:
                return jsonify({"error": "lock not found"}), 404
            if row["state"] == STATE_CONFIRMED:
                return jsonify({"error": "lock already confirmed"}), 409
            if row["state"] != STATE_REQUESTED:
                return jsonify({"error": f"cannot confirm lock in state '{row['state']}'"}), 409
            if row["expires_at"] < now:
                return jsonify({"error": "lock has expired"}), 410

            conn.execute(
                """
                UPDATE bridge_locks
                SET state = ?, proof_ref = ?, confirmed_at = ?, confirmed_by = ?, updated_at = ?, notes = ?
                WHERE lock_id = ?
                """,
                (STATE_CONFIRMED, proof_ref, now, "admin", now, notes, lock_id),
            )
            log_event(conn, lock_id, "lock_confirmed", actor="admin", details={
                "proof_ref": proof_ref,
                "notes": notes,
            })
            conn.commit()

    return jsonify({
        "lock_id": lock_id,
        "state": STATE_CONFIRMED,
        "proof_ref": proof_ref,
        "message": "Lock confirmed and eligible for release",
    })


@bridge_bp.route("/release", methods=["POST"])
@_require_admin
def release_wrtc():
    """
    Admin: mark a lock as released (wRTC minted on target chain).

    Body (JSON):
      lock_id      : str - Lock to release
      release_tx   : str - Target chain tx hash (Solana or Base)
      notes        : str - (optional) admin notes

    Returns success/error.
    """
    data, error_response = _json_object_body()
    if error_response:
        return error_response
    try:
        lock_id = _clean_string_field(data, "lock_id")
        release_tx = _clean_string_field(data, "release_tx")
        notes = _clean_string_field(data, "notes", optional=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not lock_id:
        return jsonify({"error": "lock_id is required"}), 400
    if not release_tx:
        return jsonify({"error": "release_tx is required (target chain tx hash)"}), 400

    now = int(time.time())
    with _db_lock:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM bridge_locks WHERE lock_id = ?", (lock_id,)
            ).fetchone()

            if not row:
                return jsonify({"error": "lock not found"}), 404
            if row["state"] not in (STATE_CONFIRMED, STATE_RELEASING):
                return jsonify({
                    "error": f"cannot release lock in state '{row['state']}'"
                }), 409
            if row["expires_at"] < now:
                return jsonify({"error": "lock has expired"}), 410

            conn.execute(
                "UPDATE bridge_locks SET state=?, release_tx=?, updated_at=?, notes=? WHERE lock_id=?",
                (STATE_COMPLETE, release_tx, now, notes, lock_id)
            )
            log_event(conn, lock_id, "released", actor="admin", details={
                "release_tx": release_tx,
                "notes": notes,
            })
            conn.commit()

    return jsonify({
        "lock_id": lock_id,
        "state": STATE_COMPLETE,
        "release_tx": release_tx,
        "message": "wRTC successfully minted on target chain",
    })


@bridge_bp.route("/ledger", methods=["GET"])
def get_ledger():
    """
    Query the lock ledger (transparent).

    Query params:
      state       : filter by state (pending/confirmed/complete/failed)
      chain       : filter by target_chain (solana/base)
      sender      : filter by sender_wallet
      limit       : max results (default 50, max 200)
      offset      : pagination offset

    Returns list of locks.
    """
    state_filter  = request.args.get("state", "").strip() or None
    chain_filter  = request.args.get("chain", "").strip() or None
    sender_filter = request.args.get("sender", "").strip() or None
    try:
        limit  = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "limit and offset must be integers"}), 400
    limit = max(1, min(limit, 200))
    offset = max(offset, 0)

    where_clauses, params = [], []
    if state_filter:
        where_clauses.append("state = ?"); params.append(state_filter)
    if chain_filter:
        where_clauses.append("target_chain = ?"); params.append(chain_filter)
    if sender_filter:
        where_clauses.append("sender_wallet = ?"); params.append(sender_filter)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params += [limit, offset]

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT lock_id, sender_wallet, amount_rtc, target_chain, target_wallet,
                   state, tx_hash, proof_type, proof_ref, release_tx, confirmed_at, confirmed_by,
                   created_at, updated_at, expires_at
            FROM bridge_locks
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params
        ).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM bridge_locks {where_sql}",
            params[:-2]
        ).fetchone()[0]

    locks = [
        {
            "lock_id":       r["lock_id"],
            "sender_wallet": r["sender_wallet"],
            "amount_rtc":    _amount_from_base(r["amount_rtc"]),
            "target_chain":  r["target_chain"],
            "target_wallet": r["target_wallet"],
            "state":         r["state"],
            "tx_hash":       r["tx_hash"],
            "proof_type":    r["proof_type"],
            "proof_ref":     r["proof_ref"],
            "release_tx":    r["release_tx"],
            "confirmed_at":  r["confirmed_at"],
            "confirmed_by":  r["confirmed_by"],
            "created_at":    r["created_at"],
            "updated_at":    r["updated_at"],
            "expires_at":    r["expires_at"],
        }
        for r in rows
    ]

    return jsonify({
        "locks": locks,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@bridge_bp.route("/status/<lock_id>", methods=["GET"])
def lock_status(lock_id: str):
    """Get status of a specific lock."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM bridge_locks WHERE lock_id = ?", (lock_id,)
        ).fetchone()

    if not row:
        return jsonify({"error": "lock not found"}), 404

    events = []
    with get_db() as conn:
        evs = conn.execute(
            "SELECT * FROM bridge_events WHERE lock_id = ? ORDER BY ts ASC",
            (lock_id,)
        ).fetchall()
        events = [{"type": e["event_type"], "actor": e["actor"],
                   "ts": e["ts"], "details": json.loads(e["details"] or "{}")}
                  for e in evs]

    return jsonify({
        "lock_id":       row["lock_id"],
        "sender_wallet": row["sender_wallet"],
        "amount_rtc":    _amount_from_base(row["amount_rtc"]),
        "target_chain":  row["target_chain"],
        "target_wallet": row["target_wallet"],
        "state":         row["state"],
        "tx_hash":       row["tx_hash"],
        "proof_type":    row["proof_type"],
        "proof_ref":     row["proof_ref"],
        "release_tx":    row["release_tx"],
        "confirmed_at":  row["confirmed_at"],
        "confirmed_by":  row["confirmed_by"],
        "created_at":    row["created_at"],
        "updated_at":    row["updated_at"],
        "expires_at":    row["expires_at"],
        "events":        events,
    })


@bridge_bp.route("/stats", methods=["GET"])
def bridge_stats():
    """Bridge statistics overview."""
    with get_db() as conn:
        stats = {}
        for state in [STATE_REQUESTED, STATE_PENDING, STATE_CONFIRMED, STATE_RELEASING,
                      STATE_COMPLETE, STATE_FAILED, STATE_REFUNDED]:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_rtc),0) FROM bridge_locks WHERE state = ?",
                (state,)
            ).fetchone()
            stats[state] = {"count": row[0], "total_rtc": _amount_from_base(row[1])}

        total_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_rtc),0) FROM bridge_locks"
        ).fetchone()

        by_chain = {}
        for chain in SUPPORTED_CHAINS:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_rtc),0) FROM bridge_locks "
                "WHERE target_chain = ? AND state = ?",
                (chain, STATE_COMPLETE)
            ).fetchone()
            by_chain[chain] = {"bridged_count": row[0], "total_wrtc_minted": _amount_from_base(row[1])}

    return jsonify({
        "by_state": stats,
        "by_chain": by_chain,
        "all_time": {
            "total_locks": total_row[0],
            "total_rtc_locked": _amount_from_base(total_row[1]),
        }
    })


# ─── Integration shim ─────────────────────────────────────────────────────────
def register_bridge_routes(app: Flask):
    """Register bridge blueprint with an existing Flask app."""
    init_bridge_db()
    app.register_blueprint(bridge_bp)
    print("[bridge] RIP-305 bridge endpoints registered at /bridge/*")


# ─── Standalone dev server ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = Flask(__name__)
    register_bridge_routes(app)
    print("Bridge dev server on http://0.0.0.0:8096")
    app.run(host="0.0.0.0", port=8096, debug=True)
