#!/usr/bin/env python3
"""
RustChain Bounty Claims System

Provides endpoints for submitting, verifying, and managing bounty claims
tied to RustChain bounties (e.g., MS-DOS Validator, Classic Mac OS, etc.).

Integrates with existing node infrastructure:
- Uses SQLite database for persistence
- Ties into miner attestation system for verification
- Provides admin endpoints for claim approval/rejection
- Exposes public API for claim status lookup
"""

import os
import time
import json
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import request, jsonify
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

# Constants
CLAIM_STATUS_PENDING = "pending"
CLAIM_STATUS_APPROVED = "approved"
CLAIM_STATUS_REJECTED = "rejected"
CLAIM_STATUS_UNDER_REVIEW = "under_review"

# Bounty IDs from dev_bounties.json
VALID_BOUNTY_IDS = {
    "bounty_dos_port",
    "bounty_macos_75",
    "bounty_win31_progman",
    "bounty_beos_tracker",
    "bounty_web_explorer",
    "bounty_relic_lore_scribe",
}

# Claim validity periods
CLAIM_REVIEW_PERIOD_DAYS = 14
CLAIM_AUTO_CLOSE_DAYS = 30


def init_bounty_tables(db_path: str) -> None:
    """Initialize bounty claims database tables."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            -- Bounty claims table
            CREATE TABLE IF NOT EXISTS bounty_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT UNIQUE NOT NULL,
                bounty_id TEXT NOT NULL,
                claimant_miner_id TEXT NOT NULL,
                claimant_pubkey TEXT,
                submission_ts INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                github_pr_url TEXT,
                github_repo TEXT,
                commit_hash TEXT,
                description TEXT,
                evidence_urls TEXT,
                reviewer_notes TEXT,
                review_ts INTEGER,
                reviewer_id TEXT,
                reward_amount_rtc REAL,
                reward_paid INTEGER DEFAULT 0,
                payment_tx_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            -- Index for fast lookups
            CREATE INDEX IF NOT EXISTS idx_bounty_claims_status 
            ON bounty_claims(status);
            
            CREATE INDEX IF NOT EXISTS idx_bounty_claims_miner 
            ON bounty_claims(claimant_miner_id);
            
            CREATE INDEX IF NOT EXISTS idx_bounty_claims_bounty 
            ON bounty_claims(bounty_id);

            -- Claim attachments/evidence
            CREATE TABLE IF NOT EXISTS bounty_claim_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                evidence_url TEXT NOT NULL,
                description TEXT,
                uploaded_at INTEGER NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES bounty_claims(claim_id)
            );

            -- Bounty configuration overrides (optional runtime config)
            CREATE TABLE IF NOT EXISTS bounty_config (
                bounty_id TEXT PRIMARY KEY,
                reward_rtc REAL,
                reward_badge TEXT,
                requirements_json TEXT,
                active INTEGER DEFAULT 1,
                updated_at INTEGER NOT NULL
            );
        """)


@contextmanager
def get_db_connection(db_path: str):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def generate_claim_id(bounty_id: str, miner_id: str, timestamp: int) -> str:
    """Generate a unique claim ID."""
    data = f"{bounty_id}:{miner_id}:{timestamp}"
    return f"CLM-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"


def validate_claim_payload(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate incoming claim submission payload.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not data or not isinstance(data, dict):
        return False, "Invalid payload: must be a JSON object"
    
    # Required fields
    required = ["bounty_id", "claimant_miner_id", "description"]
    for field in required:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate bounty_id
    bounty_id = data.get("bounty_id", "").strip()
    if bounty_id not in VALID_BOUNTY_IDS:
        return False, f"Invalid bounty_id. Must be one of: {', '.join(sorted(VALID_BOUNTY_IDS))}"
    
    # Validate miner_id format
    miner_id = data.get("claimant_miner_id", "").strip()
    if not miner_id or len(miner_id) > 128:
        return False, "claimant_miner_id must be 1-128 characters"
    
    # Validate description
    description = data.get("description", "").strip()
    if not description or len(description) > 5000:
        return False, "description must be 1-5000 characters"
    
    # Optional: validate GitHub PR URL if provided
    github_pr_url = data.get("github_pr_url", "").strip()
    if github_pr_url:
        if not github_pr_url.startswith("https://github.com/"):
            return False, "github_pr_url must be a valid GitHub PR URL"
        if "/pull/" not in github_pr_url:
            return False, "github_pr_url must point to a pull request"
    
    # Optional: validate commit hash if provided
    commit_hash = data.get("commit_hash", "").strip()
    if commit_hash:
        if not (len(commit_hash) in (7, 40) and all(c in "0123456789abcdef" for c in commit_hash.lower())):
            return False, "commit_hash must be a valid Git commit hash (7 or 40 hex chars)"
    
    return True, None


def submit_claim(
    db_path: str,
    bounty_id: str,
    claimant_miner_id: str,
    description: str,
    claimant_pubkey: Optional[str] = None,
    github_pr_url: Optional[str] = None,
    github_repo: Optional[str] = None,
    commit_hash: Optional[str] = None,
    evidence_urls: Optional[List[str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Submit a new bounty claim.
    
    Returns:
        Tuple of (success, result_dict)
    """
    timestamp = int(time.time())
    claim_id = generate_claim_id(bounty_id, claimant_miner_id, timestamp)
    
    try:
        with get_db_connection(db_path) as conn:
            # Check for duplicate pending claims
            existing = conn.execute(
                """
                SELECT id FROM bounty_claims 
                WHERE bounty_id = ? AND claimant_miner_id = ? AND status IN (?, ?)
                """,
                (bounty_id, claimant_miner_id, CLAIM_STATUS_PENDING, CLAIM_STATUS_UNDER_REVIEW)
            ).fetchone()
            
            if existing:
                return False, {
                    "error": "duplicate_claim",
                    "message": "You already have a pending or under-review claim for this bounty"
                }
            
            # Insert claim
            evidence_json = json.dumps(evidence_urls or [])
            conn.execute(
                """
                INSERT INTO bounty_claims (
                    claim_id, bounty_id, claimant_miner_id, claimant_pubkey,
                    submission_ts, status, github_pr_url, github_repo,
                    commit_hash, description, evidence_urls,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id, bounty_id, claimant_miner_id, claimant_pubkey,
                    timestamp, CLAIM_STATUS_PENDING, github_pr_url, github_repo,
                    commit_hash, description, evidence_json,
                    timestamp, timestamp
                )
            )
            
            conn.commit()
            
            return True, {
                "claim_id": claim_id,
                "bounty_id": bounty_id,
                "status": CLAIM_STATUS_PENDING,
                "submitted_at": timestamp,
                "message": "Claim submitted successfully"
            }
            
    except Exception as e:
        return False, {"error": "database_error", "message": str(e)}


def get_claim(db_path: str, claim_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a claim by ID."""
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM bounty_claims WHERE claim_id = ?",
            (claim_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return dict(row)


def get_claims_by_miner(db_path: str, miner_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve all claims for a specific miner."""
    with get_db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM bounty_claims 
            WHERE claimant_miner_id = ?
            ORDER BY submission_ts DESC
            LIMIT ?
            """,
            (miner_id, limit)
        ).fetchall()
        
        return [dict(row) for row in rows]


def get_claims_by_bounty(db_path: str, bounty_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve claims for a specific bounty, optionally filtered by status."""
    with get_db_connection(db_path) as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM bounty_claims 
                WHERE bounty_id = ? AND status = ?
                ORDER BY submission_ts DESC
                """,
                (bounty_id, status)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM bounty_claims 
                WHERE bounty_id = ?
                ORDER BY submission_ts DESC
                """,
                (bounty_id,)
            ).fetchall()
        
        return [dict(row) for row in rows]


def update_claim_status(
    db_path: str,
    claim_id: str,
    status: str,
    reviewer_id: str,
    reviewer_notes: Optional[str] = None,
    reward_amount_rtc: Optional[float] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Update the status of a claim (admin operation).
    
    Returns:
        Tuple of (success, result_dict)
    """
    if status not in (CLAIM_STATUS_PENDING, CLAIM_STATUS_APPROVED, CLAIM_STATUS_REJECTED, CLAIM_STATUS_UNDER_REVIEW):
        return False, {"error": "invalid_status", "message": f"Invalid status: {status}"}
    
    timestamp = int(time.time())
    
    try:
        with get_db_connection(db_path) as conn:
            # Check claim exists
            existing = conn.execute(
                "SELECT * FROM bounty_claims WHERE claim_id = ?",
                (claim_id,)
            ).fetchone()
            
            if not existing:
                return False, {"error": "not_found", "message": "Claim not found"}
            
            # Update status
            conn.execute(
                """
                UPDATE bounty_claims 
                SET status = ?, reviewer_notes = ?, reviewer_id = ?, 
                    review_ts = ?, reward_amount_rtc = ?, updated_at = ?
                WHERE claim_id = ?
                """,
                (status, reviewer_notes, reviewer_id, timestamp, reward_amount_rtc, timestamp, claim_id)
            )
            
            conn.commit()
            
            return True, {
                "claim_id": claim_id,
                "status": status,
                "updated_at": timestamp,
                "message": f"Claim status updated to {status}"
            }
            
    except Exception as e:
        return False, {"error": "database_error", "message": str(e)}


def mark_claim_paid(
    db_path: str,
    claim_id: str,
    payment_tx_id: str,
    admin_id: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Mark a claim as paid with transaction ID."""
    timestamp = int(time.time())
    
    try:
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                UPDATE bounty_claims 
                SET reward_paid = 1, payment_tx_id = ?, updated_at = ?
                WHERE claim_id = ?
                """,
                (payment_tx_id, timestamp, claim_id)
            )
            
            conn.commit()
            
            return True, {
                "claim_id": claim_id,
                "paid": True,
                "payment_tx_id": payment_tx_id,
                "paid_at": timestamp
            }
            
    except Exception as e:
        return False, {"error": "database_error", "message": str(e)}


def get_bounty_statistics(db_path: str) -> Dict[str, Any]:
    """Get aggregate statistics for bounty claims."""
    with get_db_connection(db_path) as conn:
        # Overall stats
        total = conn.execute("SELECT COUNT(*) FROM bounty_claims").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM bounty_claims WHERE status = ?",
            (CLAIM_STATUS_PENDING,)
        ).fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM bounty_claims WHERE status = ?",
            (CLAIM_STATUS_APPROVED,)
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM bounty_claims WHERE status = ?",
            (CLAIM_STATUS_REJECTED,)
        ).fetchone()[0]
        
        # Total rewards paid
        paid_result = conn.execute(
            "SELECT COALESCE(SUM(reward_amount_rtc), 0) FROM bounty_claims WHERE reward_paid = 1"
        ).fetchone()[0]
        
        # Claims by bounty
        by_bounty = conn.execute(
            """
            SELECT bounty_id, status, COUNT(*) as count
            FROM bounty_claims
            GROUP BY bounty_id, status
            """
        ).fetchall()
        
        bounty_breakdown = {}
        for row in by_bounty:
            bid = row["bounty_id"]
            if bid not in bounty_breakdown:
                bounty_breakdown[bid] = {}
            bounty_breakdown[bid][row["status"]] = row["count"]
        
        return {
            "total_claims": total,
            "status_breakdown": {
                CLAIM_STATUS_PENDING: pending,
                CLAIM_STATUS_APPROVED: approved,
                CLAIM_STATUS_REJECTED: rejected,
                "under_review": total - pending - approved - rejected,
            },
            "total_rewards_paid_rtc": paid_result,
            "by_bounty": bounty_breakdown,
        }


def register_bounty_endpoints(app, db_path: str, admin_key: str) -> None:
    """Register bounty claim endpoints with the Flask app."""
    
    def require_admin(f):
        from functools import wraps
        
        @wraps(f)
        def decorated(*args, **kwargs):
            key = request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key")
            if not key or key != admin_key:
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)
        
        return decorated
    
    @app.route("/api/bounty/claims", methods=["POST"])
    def api_submit_claim():
        """Submit a new bounty claim."""
        data = request.get_json(silent=True)
        
        # Validate payload
        is_valid, error_msg = validate_claim_payload(data)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Submit claim
        success, result = submit_claim(
            db_path=db_path,
            bounty_id=data["bounty_id"],
            claimant_miner_id=data["claimant_miner_id"],
            description=data["description"],
            claimant_pubkey=data.get("claimant_pubkey"),
            github_pr_url=data.get("github_pr_url"),
            github_repo=data.get("github_repo"),
            commit_hash=data.get("commit_hash"),
            evidence_urls=data.get("evidence_urls"),
        )
        
        if success:
            return jsonify(result), 201
        else:
            status_code = 409 if result.get("error") == "duplicate_claim" else 400
            return jsonify(result), status_code
    
    @app.route("/api/bounty/claims/<claim_id>", methods=["GET"])
    def api_get_claim(claim_id: str):
        """Get details of a specific claim."""
        claim = get_claim(db_path, claim_id)
        
        if not claim:
            return jsonify({"error": "Claim not found"}), 404
        
        # Strip sensitive fields for public view
        public_claim = {
            "claim_id": claim["claim_id"],
            "bounty_id": claim["bounty_id"],
            "claimant_miner_id": claim["claimant_miner_id"][:8] + "..." if len(claim["claimant_miner_id"]) > 8 else claim["claimant_miner_id"],
            "submission_ts": claim["submission_ts"],
            "status": claim["status"],
            "github_pr_url": claim["github_pr_url"],
            "github_repo": claim["github_repo"],
            "commit_hash": claim["commit_hash"],
            "description": claim["description"],
            "review_ts": claim["review_ts"],
            "reward_amount_rtc": claim["reward_amount_rtc"],
            "reward_paid": claim["reward_paid"],
        }
        
        return jsonify(public_claim)
    
    @app.route("/api/bounty/claims/miner/<miner_id>", methods=["GET"])
    def api_get_claims_by_miner(miner_id: str):
        """Get all claims for a specific miner."""
        limit = request.args.get("limit", 50, type=int)
        limit = max(1, min(limit, 200))
        
        claims = get_claims_by_miner(db_path, miner_id, limit)
        
        # Strip sensitive fields
        public_claims = []
        for claim in claims:
            public_claims.append({
                "claim_id": claim["claim_id"],
                "bounty_id": claim["bounty_id"],
                "submission_ts": claim["submission_ts"],
                "status": claim["status"],
                "github_pr_url": claim["github_pr_url"],
                "reward_amount_rtc": claim["reward_amount_rtc"],
                "reward_paid": claim["reward_paid"],
            })
        
        return jsonify({"miner_id": miner_id, "claims": public_claims, "count": len(public_claims)})
    
    @app.route("/api/bounty/claims/bounty/<bounty_id>", methods=["GET"])
    @require_admin
    def api_get_claims_by_bounty(bounty_id: str):
        """Get all claims for a specific bounty (admin only)."""
        status = request.args.get("status")
        
        if bounty_id not in VALID_BOUNTY_IDS:
            return jsonify({"error": f"Invalid bounty_id. Must be one of: {', '.join(sorted(VALID_BOUNTY_IDS))}"}), 400
        
        claims = get_claims_by_bounty(db_path, bounty_id, status)
        
        return jsonify({
            "bounty_id": bounty_id,
            "claims": [dict(c) for c in claims],
            "count": len(claims)
        })
    
    @app.route("/api/bounty/claims/<claim_id>/status", methods=["PUT"])
    @require_admin
    def api_update_claim_status(claim_id: str):
        """Update claim status (admin only)."""
        data = request.get_json(silent=True) or {}
        
        status = data.get("status")
        reviewer_notes = data.get("reviewer_notes")
        reward_amount_rtc = data.get("reward_amount_rtc")
        
        if not status:
            return jsonify({"error": "status is required"}), 400
        
        reviewer_id = request.headers.get("X-Admin-Key", "")[:8]
        
        success, result = update_claim_status(
            db_path=db_path,
            claim_id=claim_id,
            status=status,
            reviewer_id=reviewer_id,
            reviewer_notes=reviewer_notes,
            reward_amount_rtc=reward_amount_rtc,
        )
        
        if success:
            return jsonify(result)
        else:
            status_code = 404 if result.get("error") == "not_found" else 400
            return jsonify(result), status_code
    
    @app.route("/api/bounty/claims/<claim_id>/pay", methods=["POST"])
    @require_admin
    def api_mark_claim_paid(claim_id: str):
        """Mark a claim as paid (admin only)."""
        data = request.get_json(silent=True) or {}
        payment_tx_id = data.get("payment_tx_id")
        
        if not payment_tx_id:
            return jsonify({"error": "payment_tx_id is required"}), 400
        
        admin_id = request.headers.get("X-Admin-Key", "")[:8]
        
        success, result = mark_claim_paid(
            db_path=db_path,
            claim_id=claim_id,
            payment_tx_id=payment_tx_id,
            admin_id=admin_id,
        )
        
        if success:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route("/api/bounty/statistics", methods=["GET"])
    def api_get_bounty_statistics():
        """Get aggregate bounty statistics."""
        stats = get_bounty_statistics(db_path)
        return jsonify(stats)
    
    @app.route("/api/bounty/list", methods=["GET"])
    def api_list_bounties():
        """List all available bounties with their details."""
        # Load from dev_bounties.json
        bounties_file = os.path.join(os.path.dirname(os.path.dirname(db_path)), "bounties", "dev_bounties.json")
        
        if os.path.exists(bounties_file):
            with open(bounties_file, "r") as f:
                data = json.load(f)
                bounties = data.get("bounties", [])
        else:
            # Fallback to hardcoded list if file not found
            bounties = [
                {
                    "bounty_id": "bounty_dos_port",
                    "title": "MS-DOS Validator Port",
                    "description": "Create a RustChain validator client that runs on real-mode DOS.",
                    "reward": "Uber Dev Badge + RUST 500",
                    "status": "Open",
                },
                {
                    "bounty_id": "bounty_macos_75",
                    "title": "Classic Mac OS 7.5.x Validator",
                    "description": "Build a validator that runs under System 7.5.",
                    "reward": "Uber Dev Badge + RUST 750",
                    "status": "Open",
                },
                {
                    "bounty_id": "bounty_win31_progman",
                    "title": "Win3.1 Progman Validator",
                    "description": "Write a validator that runs under Windows 3.1.",
                    "reward": "Uber Dev Badge + RUST 600",
                    "status": "Open",
                },
                {
                    "bounty_id": "bounty_beos_tracker",
                    "title": "BeOS / Haiku Native Validator",
                    "description": "Build a native BeOS or Haiku application.",
                    "reward": "Uber Dev Badge + RUST 400",
                    "status": "Open",
                },
                {
                    "bounty_id": "bounty_web_explorer",
                    "title": "RustChain Web Explorer – Keeper Faucet Edition",
                    "description": "Develop a web-based blockchain explorer.",
                    "reward": "Uber Dev Badge + RUST 1000",
                    "status": "Open",
                },
                {
                    "bounty_id": "bounty_relic_lore_scribe",
                    "title": "Relic Lore Scribe",
                    "description": "Contribute original lore entries for legacy hardware.",
                    "reward": "Flamekeeper Lore Badge + RUST 350",
                    "status": "Open",
                },
            ]
        
        # Enrich with claim counts
        for bounty in bounties:
            bid = bounty["bounty_id"]
            if bid in VALID_BOUNTY_IDS:
                claims = get_claims_by_bounty(db_path, bid)
                bounty["claim_count"] = len(claims)
                bounty["pending_claims"] = sum(1 for c in claims if c["status"] == CLAIM_STATUS_PENDING)
        
        return jsonify({"bounties": bounties, "count": len(bounties)})
    
    print("[Bounty Claims] Endpoints registered successfully")
