"""
RIP-302: Agent-to-Agent RTC Economy
====================================
Transforms RTC from mining reward token into native currency for
autonomous agent-to-agent job marketplace.

Phases:
  1. Agent Wallets & Job Posting      (this file)
  2. Escrow & Delivery                (this file)
  3. Reputation & Discovery           (this file)
  4. Autonomous Pipelines             (future)

Economics:
  - 5% platform fee on job payments → founder_community
  - Jobs are escrowed: poster locks RTC when posting
  - Escrow released to worker on delivery acceptance
  - Timeout: escrow returns to poster after TTL (default 7 days)
  - Disputes: admin can void/refund

Author: Elyan Labs / Scott Boudreaux
Date: 2026-03-05
"""

import hashlib
import hmac
import json
import logging
import math
import re
import sqlite3
import time
from flask import Flask, request, jsonify

# --- RIP-302-SEC: signed-settlement authority (closes the /accept gate-bypass) ---
# Legacy jobs (require_signed_settlement = 0/NULL) keep wallet-string auth, fully
# unchanged. Jobs flagged require_signed_settlement = 1 ALSO require an Ed25519
# signature from the pinned settlement authority over canonical "<job_id>:<action>".
# So knowing the public poster wallet string is no longer enough to release escrow
# or dispute — only the settlement authority (which signs ONLY after the SophiaCore
# gate passes) can authorize settlement. Single-use is enforced by the existing job
# status guard; the signature binds job_id so it can't be replayed onto another job.
import os as _os
# FAIL CLOSED: no hardcoded default. The deployment MUST pin its own trusted
# settlement pubkey via the RC_SETTLEMENT_PUBKEY env (set in the systemd unit).
# If unset, _verify_settlement_authority returns no_settlement_pubkey_configured,
# so a signed-settlement job simply can't be settled (escrow safely held) rather
# than trusting a baked-in key an operator never chose.
SETTLEMENT_PUBKEY_HEX = _os.environ.get("RC_SETTLEMENT_PUBKEY", "").strip()

# RIP-302-SEC (MODEL A): signed settlement is MANDATORY, not opt-in, because this
# deployment runs a central settlement authority. The private key for
# RC_SETTLEMENT_PUBKEY is held off-node by the operator/SophiaCore staked gate,
# which signs "<job_id>:<action>" only after the gate passes. Every escrow-moving
# action (accept/dispute/cancel) must carry that signature, EXCEPT legacy jobs
# created before the enforcement cutoff, which are grandfathered onto the old
# wallet-string path (WARN-logged) so pre-fix in-flight escrow is never stranded.
# The cutoff is set just above the newest pre-fix in-flight job (created_at
# 1782951948 on node 1, 2026-07-02). Override with RC_SETTLEMENT_ENFORCE_FROM to
# re-baseline during a later migration.
_enforce_from = _os.environ.get("RC_SETTLEMENT_ENFORCE_FROM", "1782960000")
try:
    SETTLEMENT_ENFORCEMENT_CUTOFF_TS = int(_enforce_from)
except ValueError:
    # A mistyped security setting must not be silently replaced by a default.
    raise ValueError(
        f"RC_SETTLEMENT_ENFORCE_FROM must be an integer unix timestamp, got {_enforce_from!r}"
    ) from None


def _settlement_enforced(job):
    """Return True if this job's escrow-moving actions MUST carry a valid
    settlement-authority signature (MODEL A). Enforced for every job whose
    require_signed_settlement flag is set AND for every job created at/after the
    enforcement cutoff. Legacy jobs created before the cutoff with the flag unset
    are grandfathered (return False) so pre-fix in-flight escrow can still be
    settled by the operator on the wallet-string path. A client cannot opt a new
    job out of enforcement by passing require_signed_settlement=false: such a job
    is created after the cutoff and still returns True here."""
    if job.get("require_signed_settlement"):
        return True
    try:
        created = int(job.get("created_at") or 0)
    except (TypeError, ValueError):
        created = 0
    # Grandfather ONLY a genuine legacy job: a real positive timestamp strictly
    # before the cutoff. A missing/invalid/zero created_at is anomalous and fails
    # closed (enforced) rather than being treated as pre-cutoff.
    if 0 < created < SETTLEMENT_ENFORCEMENT_CUTOFF_TS:
        return False
    return True


def _verify_settlement_authority(job_id, action, data):
    """Return (ok: bool, error: str). Verifies data['settlement_sig'] (hex Ed25519)
    over b'<job_id>:<action>' against the pinned settlement pubkey."""
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
    except Exception:
        return False, "settlement_verify_unavailable"
    if not SETTLEMENT_PUBKEY_HEX:
        return False, "no_settlement_pubkey_configured"
    sig_hex = str(data.get("settlement_sig", "")).strip()
    if not sig_hex:
        return False, "settlement_sig_required"
    try:
        VerifyKey(bytes.fromhex(SETTLEMENT_PUBKEY_HEX)).verify(
            f"{job_id}:{action}".encode("utf-8"), bytes.fromhex(sig_hex))
    except (BadSignatureError, ValueError):
        return False, "invalid_settlement_signature"
    return True, ""


def _settlement_verifier_ready():
    """True iff a job CAN later be settled under signed-settlement: a pubkey is
    pinned AND PyNaCl is importable. Used to reject opting a job into signed
    settlement that could never be accepted/disputed (escrow stuck)."""
    if not SETTLEMENT_PUBKEY_HEX:
        return False
    try:
        from nacl.signing import VerifyKey
        # Construct the key: validates it's well-formed hex AND a 32-byte Ed25519
        # public key, so a malformed env can't pass the gate and strand escrow.
        VerifyKey(bytes.fromhex(SETTLEMENT_PUBKEY_HEX))
    except Exception:
        return False
    return True


# --- RIP-302-SEC-2: signed poster on CREATE (closes audit #71 create-side hole) ---
# The settlement fix above closed accept/dispute/cancel: those require the pinned
# settlement-authority signature, not just the poster_wallet STRING. But CREATE
# (POST /agent/jobs) was untouched — it still authenticates the poster purely by
# that string. Anyone who knows a wallet id (e.g. the published founder_community
# treasury id) can post a job "AS" it, debiting ITS balance into escrow, then
# claim+deliver+accept as themselves to drain it (~26,580 RTC exposed).
#
# Two wallet shapes exist on this chain and need two different proofs of control:
#
#   1. KEYED wallets — "RTC" + 40 hex chars (address_from_pubkey format) or a
#      bcn_ beacon id. These ARE cryptographic identities: holding the Ed25519
#      private key IS ownership, exactly like /wallet/transfer/signed. Require
#      poster_sig + poster_pubkey, confirm pubkey -> poster_wallet (RTC address
#      derivation, or Beacon Atlas lookup for bcn_), and verify the signature over
#      a canonical message binding poster_wallet + nonce + reward + category, so a
#      captured signature can't be replayed onto a different job/amount. The nonce
#      is single-use (agent_create_nonces) so an identical create can't replay either.
#
#   2. NAMED / TREASURY wallets — "founder_community", "founder_dev_fund",
#      "founder_team_bounty", "founder_founders", and ad-hoc agent name strings
#      (e.g. "hermes-agent") seen in production. These have NO registered Ed25519
#      keypair on this deployment.
#
#      COORDINATION FINDING (checked against agent_work_daemon.py, the only
#      process observed posting as founder_community — 333 jobs on node1, 126 on
#      node2): it signs nothing and sends no admin key today. There is no
#      founder_community private key wired into any legitimate posting flow to
#      verify against, so requiring poster_sig for these wallets would correctly
#      reject forgeries but would ALSO 401 every legitimate post, with no key to
#      fall back on. Rolling out a brand-new keypair + updating that daemon is a
#      separate coordinated step (that file is owned elsewhere, not touched here).
#
#      SAFE DEFAULT CHOSEN: for named/treasury wallets, require the RC_ADMIN_KEY
#      this node already trusts for /wallet/transfer (X-Admin-Key header,
#      constant-time compare) instead of inventing new key infrastructure — same
#      secret, already in the systemd unit, zero key-generation ceremony. This
#      IS a breaking change for agent_work_daemon.py until it adds that one
#      header; flagged here and in the handoff rather than silently deployed.
#
# Gate: RC_CREATE_REQUIRE_SIG (default enforced — "0"/"false"/"no"/"off" disables
# it as a temporary bridge only; every hour disabled is an hour #71 stays open).
CREATE_REQUIRE_SIG = _os.environ.get(
    "RC_CREATE_REQUIRE_SIG", "1").strip().lower() not in ("0", "false", "no", "off")

_RTC_ADDRESS_RE = re.compile(r"^RTC[0-9a-f]{40}$")
_BEACON_ATLAS_DB = "/root/beacon/beacon_atlas.db"


def _is_keyed_wallet(wallet: str) -> bool:
    """True if `wallet` is a cryptographic identity (RTC address or bcn_ beacon
    id) that can prove control via Ed25519, vs. a bare named/treasury string."""
    if not wallet:
        return False
    if wallet.startswith("bcn_") and len(wallet) >= 8:
        return True
    return bool(_RTC_ADDRESS_RE.match(wallet))


def _address_from_pubkey(public_key_hex: str) -> str:
    """Mirror of address_from_pubkey() in the main node file (RTC + first 40 hex
    of SHA256(pubkey)). Reimplemented locally — this module is self-contained
    (same pattern as _verify_settlement_authority above) since the main node
    file's module name isn't import-safe (dots in the filename)."""
    pubkey_hash = hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]
    return f"RTC{pubkey_hash}"


def _resolve_bcn_pubkey(bcn_id: str):
    """Resolve a bcn_ beacon id to its registered Ed25519 pubkey via the same
    Beacon Atlas DB the main node file's wallet_transfer_signed reads. Returns
    (pubkey_hex, error)."""
    try:
        conn = sqlite3.connect(_BEACON_ATLAS_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT pubkey_hex, status FROM relay_agents WHERE agent_id = ?",
            (bcn_id,),
        ).fetchone()
        conn.close()
    except Exception as e:
        return None, f"atlas_lookup_failed:{e}"
    if not row:
        return None, "beacon_id_not_registered"
    if row["status"] != "active":
        return None, f"beacon_agent_status:{row['status']}"
    return row["pubkey_hex"], None


def _create_job_message(poster_wallet, nonce, reward_rtc, category) -> bytes:
    """Canonical bytes the poster signs to authorize a job CREATE. Binds poster +
    nonce + reward + category so a captured signature can't be replayed onto a
    different amount/category; the nonce (agent_create_nonces) stops replay of an
    identical create."""
    payload = {
        "action": "agent_post_job",
        "poster": poster_wallet,
        "nonce": str(nonce),
        "reward_rtc": reward_rtc,
        "category": category,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_poster_signature(poster_wallet, nonce, reward_rtc, category, data):
    """Return (ok, error) for KEYED wallets: verify data['poster_sig'] (hex
    Ed25519) over the canonical create message, and that data['poster_pubkey']
    actually derives to poster_wallet (RTC address math, or Beacon Atlas for
    bcn_ ids) — mirrors the pubkey<->from_address check in /wallet/transfer/signed."""
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
    except Exception:
        return False, "poster_sig_verify_unavailable"

    pubkey_hex = str(data.get("poster_pubkey", "")).strip()
    sig_hex = str(data.get("poster_sig", "")).strip()
    nonce_str = str(nonce or "").strip()
    if not pubkey_hex or not sig_hex:
        return False, "poster_sig_required"
    if not nonce_str:
        return False, "nonce_required"

    if poster_wallet.startswith("bcn_"):
        atlas_pubkey, err = _resolve_bcn_pubkey(poster_wallet)
        if err:
            return False, f"beacon_lookup_failed:{err}"
        if pubkey_hex != atlas_pubkey:
            return False, "pubkey_does_not_match_beacon_registration"
    else:
        try:
            expected = _address_from_pubkey(pubkey_hex)
        except (ValueError, TypeError):
            return False, "invalid_poster_pubkey"
        if expected != poster_wallet:
            return False, "pubkey_does_not_match_poster_wallet"

    message = _create_job_message(poster_wallet, nonce_str, reward_rtc, category)
    try:
        VerifyKey(bytes.fromhex(pubkey_hex)).verify(message, bytes.fromhex(sig_hex))
    except (BadSignatureError, ValueError):
        return False, "invalid_poster_signature"
    return True, ""


def _verify_create_admin_key(data=None):
    """Return (ok, error) for NAMED/TREASURY posters (no derivable Ed25519 key):
    require the same RC_ADMIN_KEY already trusted for /wallet/transfer, via the
    X-Admin-Key header, constant-time compared. Fails closed if unset — a server
    that never had an admin key configured cannot be tricked into treating an
    absent header as a match."""
    admin_key_env = _os.environ.get("RC_ADMIN_KEY", "")
    if not admin_key_env:
        return False, "no_admin_key_configured"
    supplied = request.headers.get("X-Admin-Key", "")
    if not hmac.compare_digest(supplied, admin_key_env):
        return False, "invalid_admin_key"
    return True, ""


def _reserve_create_nonce(c, poster_wallet, nonce, used_at) -> bool:
    """Single-use guard for KEYED-wallet create signatures. Returns True iff this
    (poster_wallet, nonce) pair was not already spent."""
    c.execute(
        "INSERT OR IGNORE INTO agent_create_nonces (poster_wallet, nonce, used_at) "
        "VALUES (?, ?, ?)",
        (poster_wallet, str(nonce), used_at),
    )
    return c.rowcount == 1


log = logging.getLogger("rip302")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLATFORM_FEE_RATE = 0.05        # 5% platform fee
PLATFORM_FEE_WALLET = "founder_community"
JOB_TTL_DEFAULT = 7 * 86400    # 7 days default TTL
JOB_TTL_MAX = 30 * 86400       # 30 days max TTL
MAX_ACTIVE_JOBS_PER_AGENT = 20  # prevent spam
ESCROW_WALLET = "agent_escrow"  # internal escrow holding wallet

# Job statuses
STATUS_OPEN = "open"            # Posted, accepting claims
STATUS_CLAIMED = "claimed"      # Worker assigned
STATUS_DELIVERED = "delivered"   # Worker submitted result
STATUS_COMPLETED = "completed"  # Poster accepted delivery
STATUS_DISPUTED = "disputed"    # Poster rejected delivery
STATUS_EXPIRED = "expired"      # TTL passed without completion
STATUS_CANCELLED = "cancelled"  # Poster cancelled before claim

VALID_CATEGORIES = [
    "research", "code", "video", "audio", "writing",
    "translation", "data", "design", "testing", "other"
]


# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

def init_agent_economy_tables(db_path: str):
    """Create agent economy tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # Jobs marketplace
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_jobs (
                job_id TEXT PRIMARY KEY,
                poster_wallet TEXT NOT NULL,
                worker_wallet TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT DEFAULT 'other',
                reward_rtc REAL NOT NULL,
                reward_i64 INTEGER NOT NULL,
                escrow_i64 INTEGER NOT NULL,
                platform_fee_i64 INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                deliverable_url TEXT,
                deliverable_hash TEXT,
                result_summary TEXT,
                rejection_reason TEXT,
                created_at INTEGER NOT NULL,
                claimed_at INTEGER,
                delivered_at INTEGER,
                completed_at INTEGER,
                expires_at INTEGER NOT NULL,
                tags TEXT DEFAULT '[]'
            )
        """)

        # Agent reputation scores
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_reputation (
                wallet_id TEXT PRIMARY KEY,
                jobs_posted INTEGER DEFAULT 0,
                jobs_completed_as_poster INTEGER DEFAULT 0,
                jobs_completed_as_worker INTEGER DEFAULT 0,
                jobs_disputed INTEGER DEFAULT 0,
                jobs_expired INTEGER DEFAULT 0,
                total_rtc_paid REAL DEFAULT 0,
                total_rtc_earned REAL DEFAULT 0,
                avg_rating REAL DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                first_seen INTEGER,
                last_active INTEGER
            )
        """)

        # Job ratings (poster rates worker, worker rates poster)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                rater_wallet TEXT NOT NULL,
                ratee_wallet TEXT NOT NULL,
                role TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at INTEGER NOT NULL,
                UNIQUE(job_id, rater_wallet)
            )
        """)

        # Job activity log
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_job_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_wallet TEXT,
                details TEXT,
                created_at INTEGER NOT NULL
            )
        """)

        # RIP-302-SEC-2: single-use nonces for KEYED-wallet CREATE signatures,
        # so a captured poster_sig can't be replayed to post a second job.
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_create_nonces (
                poster_wallet TEXT NOT NULL,
                nonce TEXT NOT NULL,
                used_at INTEGER NOT NULL,
                PRIMARY KEY (poster_wallet, nonce)
            )
        """)

        conn.commit()
    log.info("RIP-302 Agent Economy tables initialized")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_job_id(poster: str, title: str) -> str:
    """Deterministic job ID from poster + title + timestamp."""
    seed = f"{poster}:{title}:{time.time()}:{id(poster)}"
    return "job_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def _get_balance_i64(c: sqlite3.Cursor, wallet_id: str) -> int:
    """Get wallet balance in micro-units."""
    try:
        row = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?",
                        (wallet_id,)).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    # Legacy fallback
    for col, key in (("balance_rtc", "miner_pk"), ("balance_rtc", "miner_id")):
        try:
            row = c.execute(f"SELECT {col} FROM balances WHERE {key} = ?",
                            (wallet_id,)).fetchone()
            if row and row[0] is not None:
                return int(round(float(row[0]) * 1000000))
        except Exception:
            continue
    return 0


def _adjust_balance(c: sqlite3.Cursor, wallet_id: str, delta_i64: int):
    """Adjust wallet balance by delta (positive = credit, negative = debit)."""
    current = _get_balance_i64(c, wallet_id)
    new_balance = current + delta_i64
    c.execute("""
        INSERT INTO balances (miner_id, amount_i64)
        VALUES (?, ?)
        ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = ?
    """, (wallet_id, new_balance, new_balance))


def _log_job_action(c: sqlite3.Cursor, job_id: str, action: str,
                    actor: str = None, details: str = None):
    """Record job activity."""
    c.execute("""
        INSERT INTO agent_job_log (job_id, action, actor_wallet, details, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, action, actor, details, int(time.time())))


def _update_reputation(c: sqlite3.Cursor, wallet_id: str, field: str,
                       increment: int = 1):
    """Increment a reputation field for an agent."""
    # FIX(#2867 H4): Whitelist allowed fields to prevent SQL injection via f-string
    ALLOWED_REP_FIELDS = frozenset({
        "jobs_posted", "jobs_completed_as_poster",
        "jobs_completed_as_worker", "jobs_disputed", "jobs_expired",
    })
    if field not in ALLOWED_REP_FIELDS:
        return
    now = int(time.time())
    c.execute("""
        INSERT INTO agent_reputation (wallet_id, first_seen, last_active)
        VALUES (?, ?, ?)
        ON CONFLICT(wallet_id) DO UPDATE SET last_active = ?
    """, (wallet_id, now, now, now))
    c.execute(f"""
        UPDATE agent_reputation SET {field} = {field} + ? WHERE wallet_id = ?
    """, (increment, wallet_id))


def _get_client_ip():
    """Get real client IP (trust nginx X-Real-IP only)."""
    return request.headers.get("X-Real-IP", request.remote_addr)


def _parse_non_negative_int_arg(name: str, default: int, max_value: int = None):
    raw = request.args.get(name)
    if raw is None:
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, f"{name} must be an integer"
    if value < 0:
        return None, f"{name} must be non-negative"
    if max_value is not None:
        value = min(value, max_value)
    return value, None


def _parse_non_negative_float_arg(name: str, default: float):
    raw = request.args.get(name)
    if raw is None:
        return default, None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f"{name} must be a number"
    if not math.isfinite(value) or value < 0:
        return None, f"{name} must be a non-negative number"
    return value, None


def _get_json_object(required: bool = True):
    data = request.get_json(silent=True)
    if data is None:
        if required:
            return None, (jsonify({"error": "JSON body required"}), 400)
        return {}, None
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON object required"}), 400)
    return data, None


def _parse_job_reward(raw):
    if isinstance(raw, bool):
        return None, "reward_rtc must be a finite number"
    try:
        reward = float(raw)
    except (TypeError, ValueError):
        return None, "reward_rtc must be a finite number"
    if not math.isfinite(reward):
        return None, "reward_rtc must be a finite number"
    if reward < 0.01:
        return None, "Minimum reward is 0.01 RTC"
    if reward > 10000:
        return None, "Maximum reward is 10,000 RTC"
    return reward, None


def _parse_ttl_seconds(raw):
    if isinstance(raw, bool):
        return None, "ttl_seconds must be an integer"
    try:
        ttl_seconds = int(raw)
    except (TypeError, ValueError):
        return None, "ttl_seconds must be an integer"
    return min(max(ttl_seconds, 3600), JOB_TTL_MAX), None


def _internal_error_response(action: str, exc: Exception):
    log.exception("%s failed with %s", action, type(exc).__name__)
    return jsonify({"error": "Internal error"}), 500


# ---------------------------------------------------------------------------
# Route Registration
# ---------------------------------------------------------------------------

def register_agent_economy(app: Flask, db_path: str):
    """Register all RIP-302 Agent Economy routes."""

    init_agent_economy_tables(db_path)
    # RIP-302-SEC migration: additive signed-settlement flag (default off = legacy).
    # Swallow ONLY the duplicate-column case; any other migration failure must
    # surface (else the INSERT below would reference a column that doesn't exist).
    try:
        with sqlite3.connect(db_path) as _mc:
            _mc.execute("ALTER TABLE agent_jobs ADD COLUMN "
                        "require_signed_settlement INTEGER DEFAULT 0")
    except sqlite3.OperationalError as _e:
        # "duplicate column" = already migrated (normal on every restart). Any other
        # OperationalError (e.g. a read-only DB) is LOGGED, not raised — a migration
        # hiccup must degrade the agent economy gracefully, never crash the whole
        # node at route registration.
        if "duplicate column" not in str(_e).lower():
            logging.getLogger("rip302").error(
                "RIP-302-SEC migration ALTER failed: %s (agent-economy posts may fail; "
                "rest of node unaffected)", _e)
    # Sanity-check the column is present, but LOG rather than raise — refusing to
    # serve the whole node on a migration quirk is worse than failing loudly later.
    # NOTE: every new POST's INSERT references this column, so if ADD COLUMN truly
    # failed, ALL job creation (not just signed) would 500 — a loud, safe failure,
    # not silent corruption. (SQLite ADD COLUMN is reliable; this is belt-and-braces.)
    # Legacy SETTLEMENT behavior is unchanged: existing jobs keep wallet-string auth.
    try:
        with sqlite3.connect(db_path) as _mc:
            _cols = [r[1] for r in _mc.execute("PRAGMA table_info(agent_jobs)").fetchall()]
        if "require_signed_settlement" not in _cols:
            logging.getLogger("rip302").error(
                "RIP-302-SEC: require_signed_settlement column missing after migration; "
                "signed-settlement posts will fail until resolved (legacy unaffected).")
    except Exception:
        pass

    def _expire_refundable_job(c: sqlite3.Cursor, job: dict, now: int) -> bool:
        """Expire an open/claimed job past TTL and refund escrow once."""
        if job["status"] not in (STATUS_OPEN, STATUS_CLAIMED):
            return False
        if int(job["expires_at"]) >= now:
            return False

        c.execute("""
            UPDATE agent_jobs
            SET status = ?
            WHERE job_id = ?
              AND status IN (?, ?)
              AND expires_at < ?
        """, (STATUS_EXPIRED, job["job_id"], STATUS_OPEN, STATUS_CLAIMED, now))
        if c.rowcount == 0:
            return False

        _refund_escrow(c, job)
        _update_reputation(c, job["poster_wallet"], "jobs_expired")
        _log_job_action(c, job["job_id"], "expired", job["poster_wallet"],
                       f"status={job['status']}")
        return True

    # -----------------------------------------------------------------------
    # POST /agent/jobs — Create a new job (locks escrow)
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs", methods=["POST"])
    def agent_post_job():
        data, error = _get_json_object(required=True)
        if error:
            return error

        poster = str(data.get("poster_wallet", "")).strip()
        title = str(data.get("title", "")).strip()
        description = str(data.get("description", "")).strip()
        category = str(data.get("category", "other")).strip().lower()
        reward_rtc = data.get("reward_rtc", 0)
        ttl_seconds = data.get("ttl_seconds", JOB_TTL_DEFAULT)
        tags = data.get("tags", [])
        # RIP-302-SEC (MODEL A): signed settlement is ON by default. A central
        # settlement authority governs settlement, so new jobs are signed-settlement
        # unless a client explicitly passes require_signed_settlement=false. Even then
        # enforcement still applies (see _settlement_enforced) because the job is
        # created after the cutoff; opting the flag out only changes the DB record,
        # not whether a signature is required to move escrow.
        # Parse as a real boolean so the string "false"/"0" doesn't opt in.
        _rss = data.get("require_signed_settlement", 1)
        if isinstance(_rss, str):
            _rss = _rss.strip().lower() not in ("", "0", "false", "no", "off")
        require_signed = 1 if _rss else 0
        # Don't create a job that could never be settled: signed settlement needs a
        # usable verifier (pinned pubkey + PyNaCl). Fail closed at POST time.
        if require_signed and not _settlement_verifier_ready():
            return jsonify({"error": "signed_settlement_unavailable: "
                            "RC_SETTLEMENT_PUBKEY not configured on this node"}), 400

        # Validation
        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400
        if not title or len(title) < 5:
            return jsonify({"error": "title must be at least 5 characters"}), 400
        if not description or len(description) < 20:
            return jsonify({"error": "description must be at least 20 characters"}), 400
        if category not in VALID_CATEGORIES:
            return jsonify({"error": f"category must be one of: {VALID_CATEGORIES}"}), 400

        reward_rtc, error = _parse_job_reward(reward_rtc)
        if error:
            return jsonify({"error": error}), 400

        ttl_seconds, error = _parse_ttl_seconds(ttl_seconds)
        if error:
            return jsonify({"error": error}), 400

        # RIP-302-SEC-2: poster must prove control of poster_wallet before any
        # escrow moves — closes audit #71 (create-side wallet-string spoofing).
        # See the RIP-302-SEC-2 block above for the full model.
        nonce = data.get("nonce")
        if CREATE_REQUIRE_SIG:
            if poster == ESCROW_WALLET:
                return jsonify({"error": "poster_wallet cannot be the escrow wallet"}), 400
            if _is_keyed_wallet(poster):
                _ok, _err = _verify_poster_signature(poster, nonce, reward_rtc, category, data)
                if not _ok:
                    return jsonify({"error": f"poster_signature_required:{_err}",
                                    "code": "SIG_REQUIRED"}), 401
            else:
                _ok, _err = _verify_create_admin_key(data)
                if not _ok:
                    return jsonify({"error": f"treasury_poster_auth_required:{_err}",
                                    "code": "ADMIN_KEY_REQUIRED"}), 401
        else:
            log.warning("RIP-302-SEC-2: job create for poster=%s accepted with NO "
                        "auth proof (RC_CREATE_REQUIRE_SIG=0 — bridge mode, audit "
                        "#71 is OPEN while this is set)", poster)

        reward_i64 = int(reward_rtc * 1000000)
        platform_fee_i64 = int(reward_i64 * PLATFORM_FEE_RATE)
        escrow_i64 = reward_i64 + platform_fee_i64  # poster pays reward + fee

        now = int(time.time())
        job_id = _generate_job_id(poster, title)

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()

            # RIP-302-SEC-2: single-use the poster's create signature so a
            # captured (poster_sig, nonce) pair can't post a second job.
            if CREATE_REQUIRE_SIG and _is_keyed_wallet(poster):
                if not _reserve_create_nonce(c, poster, nonce, now):
                    conn.rollback()
                    return jsonify({"error": "nonce_already_used", "code": "REPLAY"}), 409

            # Check poster balance
            poster_balance = _get_balance_i64(c, poster)
            if poster_balance < escrow_i64:
                return jsonify({
                    "error": "Insufficient balance for escrow",
                    "balance_rtc": poster_balance / 1000000,
                    "escrow_required_rtc": escrow_i64 / 1000000,
                    "reward_rtc": reward_rtc,
                    "platform_fee_rtc": platform_fee_i64 / 1000000,
                    "hint": "Total escrow = reward + 5% platform fee"
                }), 400

            # Check active job limit
            active_count = c.execute("""
                SELECT COUNT(*) FROM agent_jobs
                WHERE poster_wallet = ? AND status IN ('open', 'claimed', 'delivered')
            """, (poster,)).fetchone()[0]

            if active_count >= MAX_ACTIVE_JOBS_PER_AGENT:
                return jsonify({
                    "error": f"Maximum {MAX_ACTIVE_JOBS_PER_AGENT} active jobs per agent",
                    "active_jobs": active_count
                }), 429

            # Lock escrow: debit poster, credit escrow wallet
            _adjust_balance(c, poster, -escrow_i64)
            _adjust_balance(c, ESCROW_WALLET, escrow_i64)

            # Create job
            c.execute("""
                INSERT INTO agent_jobs
                (job_id, poster_wallet, title, description, category,
                 reward_rtc, reward_i64, escrow_i64, platform_fee_i64,
                 status, created_at, expires_at, tags, require_signed_settlement)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
            """, (job_id, poster, title, description, category,
                  reward_rtc, reward_i64, escrow_i64, platform_fee_i64,
                  now, now + ttl_seconds, json.dumps(tags), require_signed))

            _log_job_action(c, job_id, "posted", poster,
                           f"reward={reward_rtc} RTC, escrow={escrow_i64/1000000} RTC")
            _update_reputation(c, poster, "jobs_posted")

            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_OPEN,
                "poster_wallet": poster,
                "reward_rtc": reward_rtc,
                "platform_fee_rtc": platform_fee_i64 / 1000000,
                "escrow_total_rtc": escrow_i64 / 1000000,
                "expires_at": now + ttl_seconds,
                "expires_in_hours": ttl_seconds / 3600,
                "message": f"Job posted! {escrow_i64/1000000} RTC locked in escrow."
            }), 201

        except Exception as e:
            conn.rollback()
            return _internal_error_response("agent_post_job", e)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/claim — Claim a job
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/claim", methods=["POST"])
    def agent_claim_job(job_id):
        data, error = _get_json_object(required=False)
        if error:
            return error
        worker = str(data.get("worker_wallet", "")).strip()

        if not worker:
            return jsonify({"error": "worker_wallet required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()

            job = c.execute("SELECT * FROM agent_jobs WHERE job_id = ?",
                           (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404

            # Map columns
            cols = [d[0] for d in c.description]
            j = dict(zip(cols, job))

            if j["status"] != STATUS_OPEN:
                return jsonify({
                    "error": f"Job is not open (status: {j['status']})"
                }), 409

            if j["poster_wallet"] == worker:
                return jsonify({"error": "Cannot claim your own job"}), 400

            now = int(time.time())
            if now > j["expires_at"]:
                if _expire_refundable_job(c, j, now):
                    conn.commit()
                    return jsonify({"error": "Job has expired"}), 410
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            # Claim it
            c.execute("""
                UPDATE agent_jobs
                SET worker_wallet = ?, status = 'claimed', claimed_at = ?
                WHERE job_id = ? AND status = 'open'
            """, (worker, now, job_id))

            if c.execute("SELECT changes()").fetchone()[0] == 0:
                return jsonify({"error": "Job was claimed by another worker"}), 409

            _log_job_action(c, job_id, "claimed", worker)
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_CLAIMED,
                "worker_wallet": worker,
                "reward_rtc": j["reward_rtc"],
                "expires_at": j["expires_at"],
                "message": "Job claimed! Submit your deliverable when ready."
            })

        except Exception as e:
            conn.rollback()
            return _internal_error_response("agent_claim_job", e)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/deliver — Submit deliverable
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/deliver", methods=["POST"])
    def agent_deliver_job(job_id):
        data, error = _get_json_object(required=False)
        if error:
            return error
        worker = str(data.get("worker_wallet", "")).strip()
        deliverable_url = str(data.get("deliverable_url", "")).strip()
        deliverable_hash = str(data.get("deliverable_hash", "")).strip()
        result_summary = str(data.get("result_summary", "")).strip()

        if not worker:
            return jsonify({"error": "worker_wallet required"}), 400
        if not deliverable_url and not result_summary:
            return jsonify({"error": "deliverable_url or result_summary required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            # A disputed job is a re-delivery, not a first delivery: /dispute
            # answers the worker with "Worker can re-deliver or admin can
            # refund", and no route ever moved 'disputed' back to 'claimed',
            # so rejecting it here left the worker with no way to act on the
            # rejection reason while the escrow stayed locked.
            if j["status"] not in (STATUS_CLAIMED, STATUS_DISPUTED):
                return jsonify({
                    "error": f"Job must be in 'claimed' or 'disputed' status (current: {j['status']})"
                }), 409
            redelivery = j["status"] == STATUS_DISPUTED

            if j["worker_wallet"] != worker:
                return jsonify({"error": "Only the assigned worker can deliver"}), 403

            now = int(time.time())
            # TTL only gates a first delivery. A disputed job is deliberately
            # outside the expiry sweep (_expire_refundable_job ignores it), so
            # applying the gate here would fail re-delivery with a misleading
            # STATE_RACE once the original TTL elapsed.
            if not redelivery and now > j["expires_at"]:
                if _expire_refundable_job(c, j, now):
                    conn.commit()
                    return jsonify({"error": "Job has expired"}), 410
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            expected_status = STATUS_DISPUTED if redelivery else STATUS_CLAIMED
            c.execute("""
                UPDATE agent_jobs
                SET status = 'delivered', deliverable_url = ?,
                    deliverable_hash = ?, result_summary = ?, delivered_at = ?,
                    rejection_reason = ''
                WHERE job_id = ? AND status = ?
            """, (deliverable_url, deliverable_hash, result_summary, now, job_id, expected_status))
            if c.rowcount == 0:
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            _log_job_action(c, job_id, "redelivered" if redelivery else "delivered", worker,
                           f"url={deliverable_url}")
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_DELIVERED,
                "message": "Deliverable submitted! Waiting for poster to accept."
            })

        except Exception as e:
            conn.rollback()
            return _internal_error_response("agent_deliver_job", e)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/accept — Accept delivery (releases escrow)
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/accept", methods=["POST"])
    def agent_accept_delivery(job_id):
        data, error = _get_json_object(required=False)
        if error:
            return error
        poster = str(data.get("poster_wallet", "")).strip()
        rating = data.get("rating")  # 1-5 optional

        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["status"] != STATUS_DELIVERED:
                return jsonify({"error": f"Job must be in 'delivered' status (current: {j['status']})"}), 409

            if j["poster_wallet"] != poster:
                return jsonify({"error": "Only the poster can accept delivery"}), 403
            # RIP-302-SEC (MODEL A): releasing escrow requires the settlement-authority
            # sig over "<job_id>:accept" in addition to the poster string (the string
            # is public/forgeable). Enforced for every non-grandfathered job; legacy
            # pre-cutoff jobs keep the wallet-string path (WARN-logged).
            if _settlement_enforced(j):
                _ok, _err = _verify_settlement_authority(job_id, "accept", data)
                if not _ok:
                    return jsonify({"error": f"signed_settlement_required:{_err}",
                                    "code": "SIG_REQUIRED"}), 403
            else:
                log.warning("RIP-302-SEC: job %s accepted via legacy wallet-string "
                            "(grandfathered, created<%d)", job_id,
                            SETTLEMENT_ENFORCEMENT_CUTOFF_TS)

            now = int(time.time())
            worker = j["worker_wallet"]
            reward_i64 = j["reward_i64"]
            fee_i64 = j["platform_fee_i64"]
            escrow_i64 = j["escrow_i64"]

            # FIX(#2867 F2 / 15183848750): Atomic state transition.
            # Update FIRST, with WHERE status=? guard. If the row was
            # already moved (e.g., concurrent /cancel or /accept), rows-
            # affected = 0 and we abort BEFORE touching balances. This
            # prevents the read-check-then-mutate race where two requests
            # both pass the `if status` check and both apply escrow moves.
            c.execute("""
                UPDATE agent_jobs
                SET status = 'completed', completed_at = ?
                WHERE job_id = ? AND status = ?
            """, (now, job_id, STATUS_DELIVERED))
            if c.rowcount == 0:
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            # Release escrow: pay worker + platform fee (only after the
            # status transition has been atomically claimed above).
            _adjust_balance(c, ESCROW_WALLET, -escrow_i64)
            _adjust_balance(c, worker, reward_i64)
            _adjust_balance(c, PLATFORM_FEE_WALLET, fee_i64)

            # Update reputation
            _update_reputation(c, poster, "jobs_completed_as_poster")
            _update_reputation(c, worker, "jobs_completed_as_worker")
            c.execute("""
                UPDATE agent_reputation
                SET total_rtc_paid = total_rtc_paid + ?
                WHERE wallet_id = ?
            """, (j["reward_rtc"], poster))
            c.execute("""
                UPDATE agent_reputation
                SET total_rtc_earned = total_rtc_earned + ?
                WHERE wallet_id = ?
            """, (j["reward_rtc"], worker))

            # Optional rating
            if rating is not None:
                try:
                    rating = max(1, min(5, int(rating)))
                    c.execute("""
                        INSERT INTO agent_ratings
                        (job_id, rater_wallet, ratee_wallet, role, rating, created_at)
                        VALUES (?, ?, ?, 'poster_rates_worker', ?, ?)
                    """, (job_id, poster, worker, rating, now))
                    # Update average
                    avg = c.execute("""
                        SELECT AVG(rating), COUNT(*) FROM agent_ratings
                        WHERE ratee_wallet = ?
                    """, (worker,)).fetchone()
                    if avg[0]:
                        c.execute("""
                            UPDATE agent_reputation
                            SET avg_rating = ?, rating_count = ?
                            WHERE wallet_id = ?
                        """, (round(avg[0], 2), avg[1], worker))
                except (TypeError, ValueError):
                    pass  # Skip bad rating silently

            _log_job_action(c, job_id, "completed", poster,
                           f"worker={worker}, reward={j['reward_rtc']} RTC, fee={fee_i64/1000000} RTC")
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_COMPLETED,
                "worker_wallet": worker,
                "reward_paid_rtc": reward_i64 / 1000000,
                "platform_fee_rtc": fee_i64 / 1000000,
                "message": f"Job complete! {reward_i64/1000000} RTC paid to {worker}."
            })

        except Exception as e:
            conn.rollback()
            return _internal_error_response("agent_accept_delivery", e)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/dispute — Reject delivery
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/dispute", methods=["POST"])
    def agent_dispute_job(job_id):
        data, error = _get_json_object(required=False)
        if error:
            return error
        poster = str(data.get("poster_wallet", "")).strip()
        reason = str(data.get("reason", "")).strip()

        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400
        if not reason:
            return jsonify({"error": "reason required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["status"] != STATUS_DELIVERED:
                return jsonify({"error": f"Can only dispute delivered jobs (current: {j['status']})"}), 409

            if j["poster_wallet"] != poster:
                return jsonify({"error": "Only the poster can dispute"}), 403
            # RIP-302-SEC (MODEL A): disputing holds/redirects escrow, so it needs the
            # settlement-authority sig over "<job_id>:dispute" too (else anyone could
            # grief a worker via the public poster string). Enforced for every
            # non-grandfathered job; legacy pre-cutoff jobs keep wallet-string (WARN).
            if _settlement_enforced(j):
                _ok, _err = _verify_settlement_authority(job_id, "dispute", data)
                if not _ok:
                    return jsonify({"error": f"signed_settlement_required:{_err}",
                                    "code": "SIG_REQUIRED"}), 403
            else:
                log.warning("RIP-302-SEC: job %s disputed via legacy wallet-string "
                            "(grandfathered, created<%d)", job_id,
                            SETTLEMENT_ENFORCEMENT_CUTOFF_TS)

            now = int(time.time())
            c.execute("""
                UPDATE agent_jobs
                SET status = 'disputed', rejection_reason = ?
                WHERE job_id = ? AND status = ?
            """, (reason[:500], job_id, STATUS_DELIVERED))
            if c.rowcount == 0:
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            _update_reputation(c, j["worker_wallet"], "jobs_disputed")
            _log_job_action(c, job_id, "disputed", poster, reason[:200])
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_DISPUTED,
                "message": ("Job disputed. Escrow held pending resolution. The assigned worker "
                            "can re-deliver via POST /agent/jobs/<id>/deliver, or the poster can "
                            "refund the escrow via POST /agent/jobs/<id>/cancel.")
            })

        except Exception as e:
            conn.rollback()
            return _internal_error_response("agent_dispute_job", e)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # POST /agent/jobs/<job_id>/cancel — Cancel open job (refund escrow)
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>/cancel", methods=["POST"])
    def agent_cancel_job(job_id):
        data, error = _get_json_object(required=False)
        if error:
            return error
        poster = str(data.get("poster_wallet", "")).strip()

        if not poster:
            return jsonify({"error": "poster_wallet required"}), 400

        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM agent_jobs WHERE job_id = ?", (job_id,))
            cols = [d[0] for d in c.description]
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Job not found"}), 404
            j = dict(zip(cols, row))

            if j["poster_wallet"] != poster:
                return jsonify({"error": "Only the poster can cancel"}), 403

            now = int(time.time())
            if j["status"] == STATUS_CLAIMED and now > j["expires_at"]:
                if _expire_refundable_job(c, j, now):
                    conn.commit()
                    return jsonify({
                        "ok": True,
                        "job_id": job_id,
                        "status": STATUS_EXPIRED,
                        "refunded_rtc": j["escrow_i64"] / 1000000,
                        "message": "Job expired. Escrow refunded."
                    })
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            if j["status"] not in (STATUS_OPEN, STATUS_DISPUTED):
                return jsonify({
                    "error": f"Can only cancel open or disputed jobs (current: {j['status']})"
                }), 409

            # RIP-302-SEC (MODEL A): a discretionary cancel refunds escrow to the
            # poster (and, for a disputed job, can rug a worker who already
            # delivered), so it needs the settlement-authority sig over
            # "<job_id>:cancel" too. The poster string alone is public/forgeable.
            # The TTL-expiry auto-refund path above is intentionally NOT gated: it
            # only fires once now > expires_at and only returns escrow to the poster,
            # so requiring an operator sig there would strand naturally-expired jobs.
            # Legacy pre-cutoff jobs keep the wallet-string path (WARN-logged).
            if _settlement_enforced(j):
                _ok, _err = _verify_settlement_authority(job_id, "cancel", data)
                if not _ok:
                    return jsonify({"error": f"signed_settlement_required:{_err}",
                                    "code": "SIG_REQUIRED"}), 403
            else:
                log.warning("RIP-302-SEC: job %s cancelled via legacy wallet-string "
                            "(grandfathered, created<%d)", job_id,
                            SETTLEMENT_ENFORCEMENT_CUTOFF_TS)

            # FIX(#2867 F2 / 15183848750): Atomic state transition.
            # Move status FIRST with WHERE-clause guard; if rows-affected
            # is 0, another request already claimed this job (concurrent
            # /accept or another /cancel) and we must abort before
            # touching balances.
            c.execute("""
                UPDATE agent_jobs SET status = 'cancelled' WHERE job_id = ?
                  AND status IN (?, ?)
            """, (job_id, STATUS_OPEN, STATUS_DISPUTED))
            if c.rowcount == 0:
                conn.rollback()
                return jsonify({
                    "error": "Job state changed under concurrent request — please retry",
                    "code": "STATE_RACE",
                }), 409

            # Refund escrow only after status transition is atomically claimed.
            _refund_escrow(c, j)
            _log_job_action(c, job_id, "cancelled", poster)
            conn.commit()

            return jsonify({
                "ok": True,
                "job_id": job_id,
                "status": STATUS_CANCELLED,
                "refunded_rtc": j["escrow_i64"] / 1000000,
                "message": "Job cancelled. Escrow refunded."
            })

        except Exception as e:
            conn.rollback()
            return _internal_error_response("agent_cancel_job", e)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # GET /agent/jobs — Browse open jobs
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs", methods=["GET"])
    def agent_list_jobs():
        category = request.args.get("category", "").strip().lower()
        status_filter = request.args.get("status", STATUS_OPEN).strip().lower()
        limit, error = _parse_non_negative_int_arg("limit", 50, max_value=100)
        if error:
            return jsonify({"error": error}), 400
        offset, error = _parse_non_negative_int_arg("offset", 0)
        if error:
            return jsonify({"error": error}), 400
        min_reward, error = _parse_non_negative_float_arg("min_reward", 0)
        if error:
            return jsonify({"error": error}), 400

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Expire old jobs first
            now = int(time.time())
            expired = c.execute("""
                SELECT *
                FROM agent_jobs
                WHERE status IN (?, ?) AND expires_at < ?
            """, (STATUS_OPEN, STATUS_CLAIMED, now)).fetchall()
            for ej in expired:
                _expire_refundable_job(c, dict(ej), now)
            if expired:
                conn.commit()

            # Build query
            where = ["status = ?", "reward_rtc >= ?"]
            params = [status_filter, min_reward]

            if category and category in VALID_CATEGORIES:
                where.append("category = ?")
                params.append(category)

            query = f"""
                SELECT job_id, poster_wallet, title, description, category,
                       reward_rtc, status, created_at, expires_at, tags,
                       worker_wallet
                FROM agent_jobs
                WHERE {' AND '.join(where)}
                ORDER BY reward_rtc DESC, created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            jobs = [dict(row) for row in c.execute(query, params).fetchall()]

            # Get total count
            count_query = f"SELECT COUNT(*) FROM agent_jobs WHERE {' AND '.join(where)}"
            total = c.execute(count_query, params[:-2]).fetchone()[0]

            return jsonify({
                "ok": True,
                "jobs": jobs,
                "total": total,
                "limit": limit,
                "offset": offset,
                "categories": VALID_CATEGORIES
            })

    # -----------------------------------------------------------------------
    # GET /agent/jobs/<job_id> — Job details
    # -----------------------------------------------------------------------
    @app.route("/agent/jobs/<job_id>", methods=["GET"])
    def agent_get_job(job_id):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            job = c.execute("SELECT * FROM agent_jobs WHERE job_id = ?",
                           (job_id,)).fetchone()
            if not job:
                return jsonify({"error": "Job not found"}), 404

            j = dict(job)

            now = int(time.time())
            if _expire_refundable_job(c, j, now):
                conn.commit()
                job = c.execute("SELECT * FROM agent_jobs WHERE job_id = ?",
                               (job_id,)).fetchone()
                j = dict(job)

            # Get activity log
            log_rows = c.execute("""
                SELECT action, actor_wallet, details, created_at
                FROM agent_job_log WHERE job_id = ?
                ORDER BY created_at ASC
            """, (job_id,)).fetchall()
            j["activity_log"] = [dict(r) for r in log_rows]

            # Get ratings
            ratings = c.execute("""
                SELECT rater_wallet, ratee_wallet, role, rating, comment, created_at
                FROM agent_ratings WHERE job_id = ?
            """, (job_id,)).fetchall()
            j["ratings"] = [dict(r) for r in ratings]

            return jsonify({"ok": True, "job": j})

    # -----------------------------------------------------------------------
    # GET /agent/reputation/<wallet_id> — Agent reputation
    # -----------------------------------------------------------------------
    @app.route("/agent/reputation/<wallet_id>", methods=["GET"])
    def agent_reputation(wallet_id):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            rep = c.execute("SELECT * FROM agent_reputation WHERE wallet_id = ?",
                           (wallet_id,)).fetchone()
            if not rep:
                return jsonify({
                    "ok": True,
                    "wallet_id": wallet_id,
                    "reputation": None,
                    "message": "No reputation history"
                })

            r = dict(rep)

            # Compute trust score (0-100)
            completed = r["jobs_completed_as_worker"] + r["jobs_completed_as_poster"]
            disputed = r["jobs_disputed"]
            expired = r["jobs_expired"]
            total = completed + disputed + expired

            if total == 0:
                trust_score = 50  # Neutral for new agents
            else:
                success_rate = completed / total
                rating_bonus = (
                    min(r["avg_rating"] / 5 * 20, 20) if r["rating_count"] > 0 else 10
                )
                trust_score = int(min(100, max(0,
                    success_rate * 80 + rating_bonus
                )))

            r["trust_score"] = trust_score
            r["trust_level"] = (
                "legendary" if trust_score >= 90 else
                "trusted" if trust_score >= 70 else
                "neutral" if trust_score >= 40 else
                "risky"
            )

            return jsonify({"ok": True, "wallet_id": wallet_id, "reputation": r})

    # -----------------------------------------------------------------------
    # GET /agent/stats — Marketplace stats
    # -----------------------------------------------------------------------
    @app.route("/agent/stats", methods=["GET"])
    def agent_stats():
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()

            stats = {}
            stats["total_jobs"] = c.execute("SELECT COUNT(*) FROM agent_jobs").fetchone()[0]
            stats["open_jobs"] = c.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE status = 'open'").fetchone()[0]
            stats["completed_jobs"] = c.execute(
                "SELECT COUNT(*) FROM agent_jobs WHERE status = 'completed'").fetchone()[0]
            stats["total_rtc_volume"] = c.execute(
                "SELECT COALESCE(SUM(reward_rtc), 0) FROM agent_jobs WHERE status = 'completed'"
            ).fetchone()[0]
            stats["total_fees_collected"] = c.execute(
                "SELECT COALESCE(SUM(platform_fee_i64), 0) FROM agent_jobs WHERE status = 'completed'"
            ).fetchone()[0] / 1000000
            stats["active_agents"] = c.execute(
                "SELECT COUNT(*) FROM agent_reputation WHERE last_active > ?",
                (int(time.time()) - 7 * 86400,)).fetchone()[0]
            stats["platform_fee_rate"] = f"{PLATFORM_FEE_RATE * 100}%"
            stats["escrow_wallet"] = ESCROW_WALLET
            stats["escrow_balance_rtc"] = _get_balance_i64(c, ESCROW_WALLET) / 1000000

            # Top categories
            cats = c.execute("""
                SELECT category, COUNT(*) as cnt, SUM(reward_rtc) as total_rtc
                FROM agent_jobs GROUP BY category ORDER BY cnt DESC
            """).fetchall()
            stats["categories"] = [
                {"category": r[0], "jobs": r[1], "total_rtc": r[2]} for r in cats
            ]

            return jsonify({"ok": True, "stats": stats})

    # -----------------------------------------------------------------------
    # Internal: Refund escrow to poster
    # -----------------------------------------------------------------------
    def _refund_escrow(c: sqlite3.Cursor, job: dict):
        """Return escrowed funds to the poster."""
        escrow_i64 = job["escrow_i64"]
        poster = job["poster_wallet"]
        _adjust_balance(c, ESCROW_WALLET, -escrow_i64)
        _adjust_balance(c, poster, escrow_i64)
        _log_job_action(c, job["job_id"], "escrow_refunded", poster,
                       f"refunded {escrow_i64/1000000} RTC")

    log.info("RIP-302 Agent Economy endpoints registered: "
             "/agent/jobs, /agent/reputation, /agent/stats")
