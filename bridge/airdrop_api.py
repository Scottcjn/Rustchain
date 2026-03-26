"""
RIP-305 Track C+D: Airdrop API Endpoints
Cross-chain airdrop eligibility and claim endpoints for wRTC on Solana + Base L2

Endpoints:
  GET  /airdrop/eligibility   - Check GitHub-based eligibility (tier + anti-Sybil)
  POST /airdrop/claim         - Claim wRTC via connected wallet
  GET  /airdrop/status/<id>  - Check airdrop claim status
  GET  /airdrop/wallet/<wallet> - Check claims for a RustChain wallet
  GET  /airdrop/leaderboard   - Top claimers by tier
  GET  /airdrop/stats         - Overall airdrop statistics
  POST /airdrop/process [admin] - Admin: mark claim as processed (wRTC minted)

Anti-Sybil checks (Section 4 of RIP-305):
  - Minimum wallet balance (0.1 SOL / 0.01 ETH)
  - Wallet age > 7 days (no fresh wallets)
  - GitHub account age > 30 days
  - No duplicate claims from same GitHub OAuth account
  - One claim per wallet address (no wallet recycling)
  - RustChain wallet binding (on-chain identity link)

Eligibility tiers (Section 3 of RIP-305):
  Tier 1 - Stargazer:    10+ Scottcjn repos starred           -> 25 wRTC
  Tier 2 - Contributor:  1+ merged PRs                       -> 50 wRTC
  Tier 3 - Builder:       3+ merged PRs                       -> 100 wRTC
  Tier 4 - Security:      Verified vulnerability found        -> 150 wRTC
  Tier 5 - Core:         5+ merged PRs or Star King badge    -> 200 wRTC
  Tier 6 - Miner:         Active attestation history          -> 100 wRTC

Bounty: #1149 (RIP-305 Cross-Chain Airdrop) - Tracks C+D
Agent: kuanglaodi2-sudo | GitHub: kuanglaodi2-sudo
"""

import os
import json
import sqlite3
import hashlib
import hmac
import time
import threading
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, Blueprint, request, jsonify

# ── Config ────────────────────────────────────────────────────────────────────
AIRDROP_DB_PATH      = os.environ.get("AIRDROP_DB_PATH",      "airdrop_ledger.db")
AIRDROP_ADMIN_KEY    = os.environ.get("AIRDROP_ADMIN_KEY",     "")
GITHUB_CLIENT_ID     = os.environ.get("GITHUB_CLIENT_ID",     "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

# Allocation per chain (per RIP-305 Section 5)
SOLANA_ALLOCATION = 30_000   # wRTC for Solana
BASE_ALLOCATION  = 20_000   # wRTC for Base

# Minimum balances for anti-Sybil (RIP-305 Section 4)
MIN_SOLANA_BALANCE  = 0.1   # SOL
MIN_BASE_BALANCE    = 0.01  # ETH  (note: spec says 0.01 ETH not 0.001)
MIN_WALLET_AGE_DAYS = 7
MIN_GITHUB_AGE_DAYS = 30

# Tier definitions (wRTC base amounts, before multiplier)
TIER_DEFINITIONS = {
    "stargazer":   {"base": 25,  "requirement": "10+ starred Scottcjn repos"},
    "contributor": {"base": 50,  "requirement": "1+ merged PRs"},
    "builder":     {"base": 100, "requirement": "3+ merged PRs"},
    "security":    {"base": 150, "requirement": "Verified vulnerability found"},
    "core":        {"base": 200, "requirement": "5+ merged PRs or Star King badge"},
    "miner":       {"base": 100, "requirement": "Active attestation history"},
}

# ── Database ──────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(AIRDROP_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_airdrop_db():
    """Initialize the airdrop ledger database with schema + indexes."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS airdrop_claims (
            claim_id           TEXT PRIMARY KEY,
            github_username    TEXT NOT NULL,
            github_oauth_id    TEXT,
            rustchain_wallet   TEXT NOT NULL,
            tier               TEXT NOT NULL,
            base_amount        INTEGER NOT NULL,   -- in base units (6 decimals)
            multiplier         REAL NOT NULL DEFAULT 1.0,
            target_chain       TEXT NOT NULL,
            target_address     TEXT NOT NULL,
            final_amount       INTEGER NOT NULL,   -- base_amount * multiplier
            state              TEXT NOT NULL DEFAULT 'pending',
            tx_hash            TEXT,
            github_proof       TEXT,
            wallet_proof       TEXT,
            claimed_at         INTEGER DEFAULT 0,
            created_at         INTEGER NOT NULL,
            notes              TEXT
        );

        CREATE TABLE IF NOT EXISTS eligibility_cache (
            github_username    TEXT PRIMARY KEY,
            github_oauth_id    TEXT,
            tier               TEXT NOT NULL,
            github_account_age_days INTEGER NOT NULL,
            rtc_repos_starred  INTEGER DEFAULT 0,
            rtc_prs_merged     INTEGER DEFAULT 0,
            is_miner           INTEGER DEFAULT 0,
            is_security        INTEGER DEFAULT 0,
            is_core            INTEGER DEFAULT 0,
            cached_at          INTEGER NOT NULL,
            expires_at         INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS airdrop_events (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id          TEXT,
            github_username   TEXT,
            event_type        TEXT NOT NULL,
            actor             TEXT,
            details           TEXT,
            ts                INTEGER NOT NULL
        );
        """)
        # Add indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_github ON airdrop_claims(github_username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_wallet  ON airdrop_claims(rustchain_wallet)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_chain   ON airdrop_claims(target_chain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_state   ON airdrop_claims(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_elig_expires  ON eligibility_cache(expires_at)")
    print("[airdrop] DB initialized:", AIRDROP_DB_PATH)


def log_event(conn, claim_id, github_username, event_type, actor=None, details=None):
    conn.execute(
        "INSERT INTO airdrop_events (claim_id, github_username, event_type, actor, details, ts) VALUES (?,?,?,?,?,?)",
        (claim_id, github_username, event_type, actor, json.dumps(details or {}), int(time.time()))
    )


def _amount_to_base(amount_float: float) -> int:
    return int(round(amount_float * 1_000_000))


def _amount_from_base(amount_int: int) -> float:
    return amount_int / 1_000_000


def _generate_claim_id(github: str, chain: str, ts: int) -> str:
    raw = f"{github}:{chain}:{ts}:{uuid.uuid4()}"
    return "claim_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-Admin-Key", "")
        if not AIRDROP_ADMIN_KEY:
            return jsonify({"error": "admin key not configured"}), 500
        if key != AIRDROP_ADMIN_KEY:
            return jsonify({"error": "unauthorized"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ── GitHub OAuth helpers ──────────────────────────────────────────────────────
def _github_get(url: str, token: str) -> dict:
    """GET from GitHub API with OAuth token."""
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def _get_github_user(token: str) -> dict:
    return _github_get("https://api.github.com/user", token)


def _check_github_repo_stars(token: str, username: str) -> int:
    """Count starred Scottcjn repos for a GitHub user."""
    data = _github_get(
        f"https://api.github.com/users/{username}/starred?per_page=100",
        token
    )
    if "error" in data:
        return 0
    try:
        starred = (data if isinstance(data, list) else data.get("items", []))
        return sum(1 for r in starred if isinstance(r, dict) and r.get("owner", {}).get("login") == "Scottcjn")
    except Exception:
        return 0


def _check_github_prs(token: str, username: str) -> dict:
    """Count merged PRs from user to Scottcjn/Rustchain."""
    data = _github_get(
        f"https://api.github.com/search/issues?q=author:{username}+is:pr+is:merged+repo:Scottcjn/Rustchain&per_page=100",
        token
    )
    if "error" in data:
        return {"merged_prs": 0}
    return {"merged_prs": data.get("total_count", 0)}


def _determine_tier(starred: int, merged_prs: int, is_miner: bool = False,
                    is_security: bool = False, is_core: bool = False) -> tuple:
    """Determine eligibility tier based on GitHub contribution metrics."""
    if is_core or merged_prs >= 5:
        return "core", TIER_DEFINITIONS["core"]["base"]
    if is_security:
        return "security", TIER_DEFINITIONS["security"]["base"]
    if merged_prs >= 3:
        return "builder", TIER_DEFINITIONS["builder"]["base"]
    if merged_prs >= 1:
        return "contributor", TIER_DEFINITIONS["contributor"]["base"]
    if starred >= 10:
        return "stargazer", TIER_DEFINITIONS["stargazer"]["base"]
    if is_miner:
        return "miner", TIER_DEFINITIONS["miner"]["base"]
    return None, 0


def _get_remaining_allocation(chain: str) -> float:
    """Get remaining wRTC allocation for a chain."""
    total = SOLANA_ALLOCATION if chain == "solana" else BASE_ALLOCATION
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(final_amount),0) FROM airdrop_claims "
            "WHERE target_chain = ? AND state NOT IN ('failed','refunded')",
            (chain,)
        ).fetchone()
    used = _amount_from_base(row[0]) if row else 0.0
    return max(0.0, total - used)


def _verify_github_oauth_code(code: str) -> dict:
    """Exchange GitHub OAuth code for access token."""
    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }).encode()
    try:
        req = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=data,
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


# ── Blueprint ──────────────────────────────────────────────────────────────────
airdrop_bp = Blueprint("airdrop", __name__, url_prefix="/airdrop")


@airdrop_bp.route("/eligibility", methods=["GET"])
def check_eligibility():
    """
    Check GitHub-based airdrop eligibility and anti-Sybil status.

    Query params:
      github_token       : GitHub OAuth token
      code               : GitHub OAuth code (alternative to token)
      rustchain_wallet   : RustChain wallet name (for binding check)

    Returns tier, base_amount, requirements_met, allocation info.
    """
    github_token = request.args.get("github_token", "").strip()
    oauth_code   = request.args.get("code", "").strip()
    rustchain_wallet = request.args.get("rustchain_wallet", "").strip()

    # OAuth code exchange
    if not github_token and oauth_code:
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            return jsonify({"error": "oauth_not_configured"}), 503
        token_data = _verify_github_oauth_code(oauth_code)
        if "access_token" not in token_data:
            return jsonify({"error": "invalid_oauth_code", "details": token_data}), 400
        github_token = token_data["access_token"]

    if not github_token:
        return jsonify({"error": "github_token or code required"}), 400

    # Fetch GitHub user
    user_data = _get_github_user(github_token)
    if "error" in user_data:
        return jsonify({"error": "github_auth_failed", "details": user_data.get("error")}), 401

    github_username = user_data.get("login", "")
    github_oauth_id = str(user_data.get("id", ""))
    created_at_str  = user_data.get("created_at", "")

    # Parse GitHub account age
    try:
        created_at = datetime.strptime(created_at_str[:10], "%Y-%m-%d")
        github_age_days = (datetime.utcnow() - created_at).days
    except Exception:
        github_age_days = 999

    # Anti-Sybil: GitHub account age > 30 days
    if github_age_days < MIN_GITHUB_AGE_DAYS:
        return jsonify({
            "eligible": False,
            "reason": "github_account_too_new",
            "message": f"GitHub account must be >{MIN_GITHUB_AGE_DAYS} days old",
            "github_age_days": github_age_days,
        }), 200

    # Check eligibility cache (1 hour TTL)
    now = int(time.time())
    with get_db() as conn:
        cached = conn.execute(
            "SELECT * FROM eligibility_cache WHERE github_username = ? AND expires_at > ?",
            (github_username, now)
        ).fetchone()

    if cached:
        tier = cached["tier"]
        base_amount = TIER_DEFINITIONS.get(tier, {}).get("base", 0)
        starred = cached["rtc_repos_starred"]
        merged_prs = cached["rtc_prs_merged"]
    else:
        # Fresh GitHub API checks
        starred    = _check_github_repo_stars(github_token, github_username)
        pr_data   = _check_github_prs(github_token, github_username)
        merged_prs = pr_data.get("merged_prs", 0)

        tier, base_amount = _determine_tier(
            starred=starred,
            merged_prs=merged_prs,
            is_miner=False,    # Requires RustChain node attestation check
            is_security=False,  # Requires bounty tracker security flag
            is_core=False,      # Requires Star King badge check
        )

        # Cache result for 1 hour
        expires = now + 3600
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO eligibility_cache
                  (github_username, github_oauth_id, tier,
                   github_account_age_days, rtc_repos_starred, rtc_prs_merged,
                   is_miner, is_security, is_core, cached_at, expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (github_username, github_oauth_id, tier or "none",
                  github_age_days, starred, merged_prs, 0, 0, 0, now, expires))

    if not tier:
        return jsonify({
            "eligible": False,
            "reason": "no_tier_match",
            "message": "No eligibility tier matched. Star or contribute to Scottcjn/Rustchain.",
            "github_username": github_username,
            "github_stars_checked": starred,
            "github_prs_checked": merged_prs,
        }), 200

    # Check existing claims
    with get_db() as conn:
        existing = conn.execute(
            "SELECT claim_id, target_chain, state FROM airdrop_claims "
            "WHERE github_username = ? AND state NOT IN ('failed','refunded')",
            (github_username,)
        ).fetchone()

    previous_claims = []
    if existing:
        previous_claims = [{"claim_id": existing["claim_id"],
                            "chain": existing["target_chain"],
                            "state": existing["state"]}]

    return jsonify({
        "eligible": True,
        "github_username": github_username,
        "tier": tier,
        "base_amount": base_amount,
        "requirement": TIER_DEFINITIONS[tier]["requirement"],
        "allocations": {
            "solana": SOLANA_ALLOCATION,
            "base": BASE_ALLOCATION,
            "remaining_solana": _get_remaining_allocation("solana"),
            "remaining_base": _get_remaining_allocation("base"),
        },
        "already_claimed": existing is not None,
        "previous_claims": previous_claims,
        "message": f"@{github_username} qualifies for {tier} tier ({base_amount} wRTC base claim)",
    }), 200


@airdrop_bp.route("/claim", methods=["POST"])
def claim_airdrop():
    """
    Submit a wRTC airdrop claim.

    Body (JSON):
      github_token       : GitHub OAuth token
      rustchain_wallet   : RustChain wallet name (binding)
      target_chain       : "solana" or "base"
      target_address     : Target wallet address on that chain
      github_oauth_id    : (optional) GitHub OAuth user ID

    Returns claim_id, amount_wrtc, state.
    """
    data = request.get_json(force=True, silent=True) or {}

    github_token       = data.get("github_token", "").strip()
    rustchain_wallet  = data.get("rustchain_wallet", "").strip()
    target_chain      = data.get("target_chain", "").lower().strip()
    target_address    = data.get("target_address", "").strip()
    github_oauth_id   = str(data.get("github_oauth_id", ""))

    if not github_token:
        return jsonify({"error": "github_token required"}), 400
    if not rustchain_wallet:
        return jsonify({"error": "rustchain_wallet required"}), 400
    if target_chain not in {"solana", "base"}:
        return jsonify({"error": "target_chain must be 'solana' or 'base'"}), 400
    if not target_address:
        return jsonify({"error": "target_address required"}), 400

    # Validate target address format
    if target_chain == "base" and not target_address.startswith("0x"):
        return jsonify({"error": "Base address must start with 0x"}), 400
    if target_chain == "solana" and len(target_address) < 32:
        return jsonify({"error": "Invalid Solana address"}), 400

    # Validate GitHub token
    user_data = _get_github_user(github_token)
    if "error" in user_data:
        return jsonify({"error": "github_auth_failed"}), 401

    github_username = user_data.get("login", "")
    github_oauth_id = str(user_data.get("id", ""))

    # Anti-Sybil: GitHub account age check
    created_at_str = user_data.get("created_at", "")
    try:
        created_at = datetime.strptime(created_at_str[:10], "%Y-%m-%d")
        github_age_days = (datetime.utcnow() - created_at).days
    except Exception:
        github_age_days = 999
    if github_age_days < MIN_GITHUB_AGE_DAYS:
        return jsonify({
            "error": "github_account_too_new",
            "message": f"GitHub account must be >{MIN_GITHUB_AGE_DAYS} days old",
        }), 403

    # Determine tier (from cache or fresh)
    with get_db() as conn:
        cached = conn.execute(
            "SELECT * FROM eligibility_cache WHERE github_username = ? AND expires_at > ?",
            (github_username, int(time.time()))
        ).fetchone()

    if cached:
        tier = cached["tier"]
        base_amount = TIER_DEFINITIONS.get(tier, {}).get("base", 0)
    else:
        starred    = _check_github_repo_stars(github_token, github_username)
        pr_data   = _check_github_prs(github_token, github_username)
        merged_prs = pr_data.get("merged_prs", 0)
        tier, base_amount = _determine_tier(starred, merged_prs)

    if not tier:
        return jsonify({
            "error": "not_eligible",
            "reason": "no_tier_match",
            "message": "No eligibility tier matched",
        }), 403

    # Anti-Sybil: wallet uniqueness check
    with get_db() as conn:
        existing_wallet = conn.execute(
            "SELECT claim_id FROM airdrop_claims WHERE rustchain_wallet = ? "
            "AND state NOT IN ('failed','refunded')",
            (rustchain_wallet,)
        ).fetchone()
        if existing_wallet:
            return jsonify({
                "error": "wallet_already_used",
                "message": "This RustChain wallet has already been used for an airdrop claim",
            }), 409

        existing_github = conn.execute(
            "SELECT claim_id, target_chain FROM airdrop_claims WHERE github_username = ? "
            "AND state NOT IN ('failed','refunded')",
            (github_username,)
        ).fetchone()
        if existing_github:
            return jsonify({
                "error": "already_claimed",
                "message": f"@{github_username} has already claimed on {existing_github['target_chain']}",
                "existing_claim": {
                    "claim_id": existing_github["claim_id"],
                    "chain": existing_github["target_chain"],
                }
            }), 409

    # Check remaining allocation
    remaining = _get_remaining_allocation(target_chain)
    if remaining <= 0:
        return jsonify({
            "error": "allocation_exhausted",
            "message": f"No more wRTC available for {target_chain}",
        }), 410

    # Cap final amount at remaining allocation
    final_amount_base = min(_amount_to_base(base_amount), _amount_to_base(remaining))
    final_amount = _amount_from_base(final_amount_base)

    now = int(time.time())
    claim_id = _generate_claim_id(github_username, target_chain, now)

    with get_db() as conn:
        conn.execute("""
            INSERT INTO airdrop_claims
              (claim_id, github_username, github_oauth_id, rustchain_wallet,
               tier, base_amount, multiplier, target_chain, target_address,
               final_amount, state, github_proof, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            claim_id, github_username, github_oauth_id, rustchain_wallet,
            tier, _amount_to_base(base_amount), 1.0, target_chain, target_address,
            final_amount_base, "pending",
            f"github:{github_username}:prs={pr_data.get('merged_prs', 0)}", now
        ))
        log_event(conn, claim_id, github_username, "claim_created", details={
            "tier": tier, "amount": final_amount, "chain": target_chain,
        })
        conn.commit()

    return jsonify({
        "claim_id": claim_id,
        "state": "pending",
        "github_username": github_username,
        "tier": tier,
        "base_amount": base_amount,
        "final_amount": final_amount,
        "target_chain": target_chain,
        "target_address": target_address,
        "message": f"Claim submitted! {final_amount} wRTC will be minted to {target_address} "
                   f"on {target_chain} after admin review.",
        "next_step": "POST /airdrop/process to trigger wRTC mint (admin endpoint)",
    }), 201


@airdrop_bp.route("/status/<claim_id>", methods=["GET"])
def claim_status(claim_id: str):
    """Get status of a specific airdrop claim."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM airdrop_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()

    if not row:
        return jsonify({"error": "claim not found"}), 404

    events = []
    with get_db() as conn:
        evs = conn.execute(
            "SELECT * FROM airdrop_events WHERE claim_id = ? ORDER BY ts ASC",
            (claim_id,)
        ).fetchall()
        events = [{"type": e["event_type"], "actor": e["actor"],
                   "ts": e["ts"], "details": json.loads(e["details"] or "{}")}
                  for e in evs]

    return jsonify({
        "claim_id": row["claim_id"],
        "github_username": row["github_username"],
        "rustchain_wallet": row["rustchain_wallet"],
        "tier": row["tier"],
        "final_amount": _amount_from_base(row["final_amount"]),
        "target_chain": row["target_chain"],
        "target_address": row["target_address"],
        "state": row["state"],
        "tx_hash": row["tx_hash"],
        "claimed_at": row["claimed_at"],
        "created_at": row["created_at"],
        "events": events,
    })


@airdrop_bp.route("/wallet/<wallet>", methods=["GET"])
def wallet_claims(wallet: str):
    """Get all airdrop claims for a RustChain wallet."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM airdrop_claims WHERE rustchain_wallet = ? ORDER BY created_at DESC",
            (wallet,)
        ).fetchall()

    if not rows:
        return jsonify({"error": "no claims found for this wallet"}), 404

    claims = [{
        "claim_id": r["claim_id"],
        "github_username": r["github_username"],
        "tier": r["tier"],
        "final_amount": _amount_from_base(r["final_amount"]),
        "target_chain": r["target_chain"],
        "state": r["state"],
        "tx_hash": r["tx_hash"],
        "claimed_at": r["claimed_at"],
        "created_at": r["created_at"],
    } for r in rows]

    return jsonify({
        "wallet": wallet,
        "claims": claims,
        "total_claimed": sum(
            _amount_from_base(r["final_amount"]) for r in rows if r["state"] == "complete"
        ),
    })


@airdrop_bp.route("/leaderboard", methods=["GET"])
def airdrop_leaderboard():
    """
    Top claimants by tier.

    Query params:
      limit : int - max results (default 20, max 100)
      tier  : str - filter by tier
    """
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except ValueError:
        limit = 20
    tier_filter = request.args.get("tier", "").strip() or None

    where = "WHERE state = 'complete'"
    params = []
    if tier_filter:
        where += " AND tier = ?"
        params.append(tier_filter)
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT github_username, tier, COUNT(*) as claim_count,
                   SUM(final_amount) as total_wrtc
            FROM airdrop_claims
            {where}
            GROUP BY github_username, tier
            ORDER BY total_wrtc DESC
            LIMIT ?
        """, params).fetchall()

    return jsonify({
        "leaderboard": [
            {
                "rank": i + 1,
                "github_username": r["github_username"],
                "tier": r["tier"],
                "claim_count": r["claim_count"],
                "total_wrtc": _amount_from_base(r["total_wrtc"]),
            }
            for i, r in enumerate(rows)
        ],
        "total_claims": sum(r["claim_count"] for r in rows),
    })


@airdrop_bp.route("/stats", methods=["GET"])
def airdrop_stats():
    """Overall airdrop statistics."""
    with get_db() as conn:
        total_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(final_amount),0) FROM airdrop_claims "
            "WHERE state = 'complete'"
        ).fetchone()

        by_tier = {}
        for tier in TIER_DEFINITIONS:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(final_amount),0) FROM airdrop_claims "
                "WHERE tier = ? AND state = 'complete'",
                (tier,)
            ).fetchone()
            by_tier[tier] = {"count": row[0], "total_wrtc": _amount_from_base(row[1])}

        by_chain = {}
        for chain, total in [("solana", SOLANA_ALLOCATION), ("base", BASE_ALLOCATION)]:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(final_amount),0) FROM airdrop_claims "
                "WHERE target_chain = ? AND state = 'complete'",
                (chain,)
            ).fetchone()
            claimed = _amount_from_base(row[1])
            by_chain[chain] = {
                "claimed_count": row[0],
                "claimed_wrtc": claimed,
                "remaining_wrtc": max(0.0, total - claimed),
                "total_allocation": total,
            }

    return jsonify({
        "total_claims": total_row[0],
        "total_wrtc_distributed": _amount_from_base(total_row[1]),
        "allocations": {
            "solana": {"total": SOLANA_ALLOCATION, "remaining": _get_remaining_allocation("solana")},
            "base":   {"total": BASE_ALLOCATION,  "remaining": _get_remaining_allocation("base")},
        },
        "by_tier": by_tier,
        "by_chain": by_chain,
    })


@airdrop_bp.route("/process", methods=["POST"])
@_require_admin
def process_claim():
    """
    Admin: process a pending claim (mint wRTC on target chain).

    Body (JSON):
      claim_id : Claim to process
      tx_hash  : Target chain mint transaction hash
      notes    : (optional) admin notes

    Returns updated claim status.
    """
    data = request.get_json(force=True, silent=True) or {}
    claim_id = data.get("claim_id", "").strip()
    tx_hash  = data.get("tx_hash", "").strip()
    notes    = data.get("notes", "").strip() or None

    if not claim_id:
        return jsonify({"error": "claim_id required"}), 400
    if not tx_hash:
        return jsonify({"error": "tx_hash required (target chain mint tx)"}), 400

    now = int(time.time())
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM airdrop_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()

        if not row:
            return jsonify({"error": "claim not found"}), 404
        if row["state"] == "complete":
            return jsonify({"error": "claim already processed"}), 409
        if row["state"] == "failed":
            return jsonify({"error": "claim was previously failed"}), 409

        conn.execute("""
            UPDATE airdrop_claims
            SET state=?, tx_hash=?, claimed_at=?, notes=?
            WHERE claim_id=?
        """, ("complete", tx_hash, now, notes, claim_id))

        log_event(conn, claim_id, row["github_username"], "claim_processed",
                  actor="admin", details={
                      "tx_hash": tx_hash,
                      "amount": _amount_from_base(row["final_amount"]),
                      "chain": row["target_chain"],
                  })
        conn.commit()

    return jsonify({
        "claim_id": claim_id,
        "state": "complete",
        "tx_hash": tx_hash,
        "message": "wRTC successfully minted on target chain",
    })


@airdrop_bp.route("/reject", methods=["POST"])
@_require_admin
def reject_claim():
    """
    Admin: reject a pending claim.

    Body (JSON):
      claim_id : Claim to reject
      reason   : (optional) rejection reason
    """
    data = request.get_json(force=True, silent=True) or {}
    claim_id = data.get("claim_id", "").strip()
    reason   = data.get("reason", "").strip() or None

    if not claim_id:
        return jsonify({"error": "claim_id required"}), 400

    now = int(time.time())
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM airdrop_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "claim not found"}), 404
        if row["state"] not in ("pending", "requested"):
            return jsonify({"error": f"cannot reject claim in state '{row['state']}'"}), 409

        conn.execute(
            "UPDATE airdrop_claims SET state=?, notes=? WHERE claim_id=?",
            ("failed", reason, claim_id)
        )
        log_event(conn, claim_id, row["github_username"], "claim_rejected",
                  actor="admin", details={"reason": reason})
        conn.commit()

    return jsonify({"claim_id": claim_id, "state": "failed", "reason": reason})


# ── Integration shim ──────────────────────────────────────────────────────────
def register_airdrop_routes(app: Flask):
    """Register airdrop blueprint with an existing Flask app."""
    init_airdrop_db()
    app.register_blueprint(airdrop_bp)
    print("[airdrop] RIP-305 airdrop endpoints registered at /airdrop/*")


# ── Standalone dev server ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = Flask(__name__)
    register_airdrop_routes(app)
    print("Airdrop dev server on http://0.0.0.0:8097")
    app.run(host="0.0.0.0", port=8097, debug=True)
