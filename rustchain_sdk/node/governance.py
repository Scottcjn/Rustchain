"""
RIP-0002: On-Chain Governance System
=====================================
Implements proposal creation, voting, lifecycle management, and optional
Sophia AI evaluation for RustChain protocol governance.

Voting Rules:
  - 1 attesting miner = 1 vote, weighted by antiquity multiplier
  - 7-day voting window per proposal
  - 33% quorum of active miners required
  - Simple majority wins
  - Founder veto for security-critical changes (first 2 years)

API Endpoints:
  POST /api/governance/propose      — Create proposal (active miner required)
  GET  /api/governance/proposals    — List all proposals
  GET  /api/governance/proposal/<n> — Get proposal details + votes
  POST /api/governance/vote         — Cast vote (active attestation required)
  GET  /api/governance/results/<n>  — Get final results
  GET  /api/governance/stats        — Governance statistics

Author: NOX Ventures (noxxxxybot-sketch)
Date: 2026-03-07
"""

import hashlib
import json
import logging
import sqlite3
import time
from typing import Optional
from flask import Blueprint, request, jsonify

log = logging.getLogger("rip0002_governance")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VOTING_WINDOW_SECONDS = 7 * 86400      # 7 days
QUORUM_THRESHOLD = 0.33                 # 33% of active miners
FOUNDER_VETO_DURATION = 2 * 365 * 86400  # 2 years from genesis
GENESIS_TIMESTAMP = 1700000000          # Approximate RustChain genesis (override if needed)
MAX_PROPOSALS_PER_MINER = 10            # Anti-spam: max active proposals
MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 10000

PROPOSAL_TYPES = ("parameter_change", "feature_activation", "emergency")
VOTE_CHOICES = ("for", "against", "abstain")

STATUS_ACTIVE = "active"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"
STATUS_VETOED = "vetoed"

# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

GOVERNANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS governance_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    proposed_by TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    parameter_key TEXT,
    parameter_value TEXT,
    votes_for REAL DEFAULT 0.0,
    votes_against REAL DEFAULT 0.0,
    votes_abstain REAL DEFAULT 0.0,
    quorum_met INTEGER DEFAULT 0,
    vetoed_by TEXT,
    veto_reason TEXT,
    sophia_analysis TEXT
);

CREATE TABLE IF NOT EXISTS governance_votes (
    proposal_id INTEGER NOT NULL,
    miner_id TEXT NOT NULL,
    vote TEXT NOT NULL,
    weight REAL NOT NULL,
    voted_at INTEGER NOT NULL,
    PRIMARY KEY (proposal_id, miner_id),
    FOREIGN KEY (proposal_id) REFERENCES governance_proposals(id)
);
"""


def init_governance_tables(db_path: str):
    """Create governance tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(GOVERNANCE_SCHEMA)
        conn.commit()
    log.info("Governance tables initialized at %s", db_path)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_miner_antiquity_weight(miner_id: str, db_path: str) -> float:
    """Return the antiquity multiplier for a miner (default 1.0 if not found)."""
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT antiquity_multiplier FROM miners WHERE wallet_name = ?",
                (miner_id,)
            ).fetchone()
            if row:
                return max(float(row[0]), 1.0)
    except Exception as e:
        log.debug("Could not fetch antiquity for %s: %s", miner_id, e)
    return 1.0


def _is_active_miner(miner_id: str, db_path: str) -> bool:
    """Check if the miner has attested recently (within last 2 epochs ~24h)."""
    try:
        cutoff = int(time.time()) - 86400 * 2
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM attestations WHERE miner_id = ? AND timestamp >= ?",
                (miner_id, cutoff)
            ).fetchone()
            return bool(row and row[0] > 0)
    except Exception as e:
        log.debug("Attestation check failed for %s: %s", miner_id, e)
    return False


def _count_active_miners(db_path: str) -> int:
    """Count miners who attested in the last 2 days (quorum denominator)."""
    try:
        cutoff = int(time.time()) - 86400 * 2
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT miner_id) FROM attestations WHERE timestamp >= ?",
                (cutoff,)
            ).fetchone()
            return int(row[0]) if row else 0
    except Exception as e:
        log.debug("Active miner count failed: %s", e)
    return 0


def _is_within_founder_veto_period() -> bool:
    """Return True if still within the 2-year founder veto window."""
    return (time.time() - GENESIS_TIMESTAMP) < FOUNDER_VETO_DURATION


def _settle_expired_proposals(db_path: str):
    """Settle any proposals whose voting window has closed."""
    now = int(time.time())
    try:
        with sqlite3.connect(db_path) as conn:
            active = conn.execute(
                "SELECT id, votes_for, votes_against, votes_abstain FROM governance_proposals "
                "WHERE status = ? AND expires_at <= ?",
                (STATUS_ACTIVE, now)
            ).fetchall()

            for (pid, v_for, v_against, v_abstain) in active:
                total_votes = v_for + v_against + v_abstain
                active_miners = _count_active_miners(db_path)
                quorum_met = (total_votes >= active_miners * QUORUM_THRESHOLD) if active_miners > 0 else False
                if not quorum_met:
                    new_status = STATUS_EXPIRED
                elif v_for > v_against:
                    new_status = STATUS_PASSED
                else:
                    new_status = STATUS_FAILED

                conn.execute(
                    "UPDATE governance_proposals SET status = ?, quorum_met = ? WHERE id = ?",
                    (new_status, 1 if quorum_met else 0, pid)
                )
            conn.commit()
    except Exception as e:
        log.error("Error settling expired proposals: %s", e)


def _sophia_evaluate(proposal: dict) -> str:
    """Generate a simple AI-style impact analysis for a proposal."""
    ptype = proposal.get("proposal_type", "unknown")
    title = proposal.get("title", "")
    desc = proposal.get("description", "")[:500]

    # Lightweight deterministic analysis (no external API needed)
    risk_words = ["emergency", "halt", "pause", "freeze", "override", "bypass"]
    risk_level = "HIGH" if any(w in title.lower() or w in desc.lower() for w in risk_words) else "LOW"

    param_key = proposal.get("parameter_key") or ""
    analysis_lines = [
        f"**Sophia AI Evaluation** (auto-generated, non-binding)",
        f"- Proposal type: `{ptype}`",
        f"- Risk level: **{risk_level}**",
    ]
    if ptype == "parameter_change" and param_key:
        analysis_lines.append(f"- Modifies parameter: `{param_key}`")
        analysis_lines.append("- Recommend: review current parameter value before voting")
    elif ptype == "feature_activation":
        analysis_lines.append("- Activates a new RIP feature — ensure backward compatibility")
    elif ptype == "emergency":
        analysis_lines.append("- Emergency action — requires careful deliberation despite urgency")
    analysis_lines.append(
        f"- Summary: {desc[:200]}..." if len(desc) > 200 else f"- Summary: {desc}"
    )
    return "\n".join(analysis_lines)


# ---------------------------------------------------------------------------
# Flask Blueprint
# ---------------------------------------------------------------------------

def create_governance_blueprint(db_path: str) -> Blueprint:
    bp = Blueprint("governance", __name__)

    # -- POST /api/governance/propose ----------------------------------------
    @bp.route("/api/governance/propose", methods=["POST"])
    def create_proposal():
        _settle_expired_proposals(db_path)
        data = request.get_json(silent=True) or {}

        miner_id = data.get("miner_id", "").strip()
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        proposal_type = data.get("proposal_type", "").strip()
        parameter_key = data.get("parameter_key", "").strip() or None
        parameter_value = str(data.get("parameter_value", "")).strip() or None

        # Validation
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        if not title or len(title) > MAX_TITLE_LEN:
            return jsonify({"error": f"title required (max {MAX_TITLE_LEN} chars)"}), 400
        if not description or len(description) > MAX_DESCRIPTION_LEN:
            return jsonify({"error": f"description required (max {MAX_DESCRIPTION_LEN} chars)"}), 400
        if proposal_type not in PROPOSAL_TYPES:
            return jsonify({"error": f"proposal_type must be one of {PROPOSAL_TYPES}"}), 400
        if proposal_type == "parameter_change" and not parameter_key:
            return jsonify({"error": "parameter_key required for parameter_change proposals"}), 400
        if not _is_active_miner(miner_id, db_path):
            return jsonify({"error": "miner_id must be an active attesting miner"}), 403

        now = int(time.time())
        expires_at = now + VOTING_WINDOW_SECONDS

        try:
            with sqlite3.connect(db_path) as conn:
                # Anti-spam: max active proposals per miner
                active_count = conn.execute(
                    "SELECT COUNT(*) FROM governance_proposals WHERE proposed_by = ? AND status = ?",
                    (miner_id, STATUS_ACTIVE)
                ).fetchone()[0]
                if active_count >= MAX_PROPOSALS_PER_MINER:
                    return jsonify({"error": f"Max {MAX_PROPOSALS_PER_MINER} active proposals per miner"}), 429

                proposal_data = {
                    "title": title,
                    "description": description,
                    "proposal_type": proposal_type,
                    "parameter_key": parameter_key,
                    "parameter_value": parameter_value,
                }
                sophia_text = _sophia_evaluate(proposal_data)

                cursor = conn.execute(
                    """INSERT INTO governance_proposals
                       (title, description, proposal_type, proposed_by, created_at, expires_at,
                        status, parameter_key, parameter_value, sophia_analysis)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (title, description, proposal_type, miner_id, now, expires_at,
                     STATUS_ACTIVE, parameter_key, parameter_value, sophia_text)
                )
                proposal_id = cursor.lastrowid
                conn.commit()

        except Exception as e:
            log.error("Proposal creation error: %s", e)
            return jsonify({"error": "internal error"}), 500

        log.info("Proposal #%s created by %s: %s", proposal_id, miner_id, title)
        return jsonify({
            "ok": True,
            "proposal_id": proposal_id,
            "title": title,
            "proposal_type": proposal_type,
            "status": STATUS_ACTIVE,
            "expires_at": expires_at,
            "sophia_analysis": sophia_text,
        }), 201

    # -- GET /api/governance/proposals ----------------------------------------
    @bp.route("/api/governance/proposals", methods=["GET"])
    def list_proposals():
        _settle_expired_proposals(db_path)
        status_filter = request.args.get("status")
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                if status_filter:
                    rows = conn.execute(
                        "SELECT * FROM governance_proposals WHERE status = ? "
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (status_filter, limit, offset)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM governance_proposals ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        (limit, offset)
                    ).fetchall()
                proposals = [dict(r) for r in rows]

        except Exception as e:
            log.error("List proposals error: %s", e)
            return jsonify({"error": "internal error"}), 500

        return jsonify({"proposals": proposals, "count": len(proposals)}), 200

    # -- GET /api/governance/proposal/<n> ------------------------------------
    @bp.route("/api/governance/proposal/<int:proposal_id>", methods=["GET"])
    def get_proposal(proposal_id: int):
        _settle_expired_proposals(db_path)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                proposal = conn.execute(
                    "SELECT * FROM governance_proposals WHERE id = ?", (proposal_id,)
                ).fetchone()
                if not proposal:
                    return jsonify({"error": "proposal not found"}), 404

                votes = conn.execute(
                    "SELECT miner_id, vote, weight, voted_at FROM governance_votes "
                    "WHERE proposal_id = ? ORDER BY voted_at DESC",
                    (proposal_id,)
                ).fetchall()

        except Exception as e:
            log.error("Get proposal error: %s", e)
            return jsonify({"error": "internal error"}), 500

        now = int(time.time())
        p = dict(proposal)
        p["votes"] = [dict(v) for v in votes]
        p["time_remaining_seconds"] = max(0, p["expires_at"] - now)
        return jsonify(p), 200

    # -- POST /api/governance/vote -------------------------------------------
    @bp.route("/api/governance/vote", methods=["POST"])
    def cast_vote():
        _settle_expired_proposals(db_path)
        data = request.get_json(silent=True) or {}

        miner_id = data.get("miner_id", "").strip()
        proposal_id = data.get("proposal_id")
        vote_choice = data.get("vote", "").strip().lower()

        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        if proposal_id is None:
            return jsonify({"error": "proposal_id required"}), 400
        if vote_choice not in VOTE_CHOICES:
            return jsonify({"error": f"vote must be one of {VOTE_CHOICES}"}), 400
        if not _is_active_miner(miner_id, db_path):
            return jsonify({"error": "miner must be active (attested in last 48h)"}), 403

        weight = _get_miner_antiquity_weight(miner_id, db_path)
        now = int(time.time())

        try:
            with sqlite3.connect(db_path) as conn:
                proposal = conn.execute(
                    "SELECT id, status, expires_at FROM governance_proposals WHERE id = ?",
                    (proposal_id,)
                ).fetchone()

                if not proposal:
                    return jsonify({"error": "proposal not found"}), 404
                if proposal[1] != STATUS_ACTIVE:
                    return jsonify({"error": f"proposal is {proposal[1]}, not active"}), 409
                if proposal[2] < now:
                    return jsonify({"error": "voting window has closed"}), 409

                # Upsert vote
                try:
                    conn.execute(
                        "INSERT INTO governance_votes (proposal_id, miner_id, vote, weight, voted_at) "
                        "VALUES (?,?,?,?,?)",
                        (proposal_id, miner_id, vote_choice, weight, now)
                    )
                except sqlite3.IntegrityError:
                    # Already voted — update
                    old_vote = conn.execute(
                        "SELECT vote, weight FROM governance_votes WHERE proposal_id = ? AND miner_id = ?",
                        (proposal_id, miner_id)
                    ).fetchone()
                    if old_vote:
                        # Remove old weight
                        old_col = f"votes_{old_vote[0]}"
                        conn.execute(
                            f"UPDATE governance_proposals SET {old_col} = {old_col} - ? WHERE id = ?",
                            (old_vote[1], proposal_id)
                        )
                    conn.execute(
                        "UPDATE governance_votes SET vote = ?, weight = ?, voted_at = ? "
                        "WHERE proposal_id = ? AND miner_id = ?",
                        (vote_choice, weight, now, proposal_id, miner_id)
                    )

                # Update tally
                col = f"votes_{vote_choice}"
                conn.execute(
                    f"UPDATE governance_proposals SET {col} = {col} + ? WHERE id = ?",
                    (weight, proposal_id)
                )

                # Check quorum after vote
                updated = conn.execute(
                    "SELECT votes_for, votes_against, votes_abstain FROM governance_proposals WHERE id = ?",
                    (proposal_id,)
                ).fetchone()
                total = sum(updated)
                active_miners = _count_active_miners(db_path)
                quorum_met = (total >= active_miners * QUORUM_THRESHOLD) if active_miners > 0 else False
                conn.execute(
                    "UPDATE governance_proposals SET quorum_met = ? WHERE id = ?",
                    (1 if quorum_met else 0, proposal_id)
                )
                conn.commit()

        except Exception as e:
            log.error("Vote error: %s", e)
            return jsonify({"error": "internal error"}), 500

        log.info("Vote cast: proposal #%s, miner=%s, vote=%s, weight=%.2f",
                 proposal_id, miner_id, vote_choice, weight)
        return jsonify({
            "ok": True,
            "proposal_id": proposal_id,
            "miner_id": miner_id,
            "vote": vote_choice,
            "weight": weight,
            "quorum_met": quorum_met,
        }), 200

    # -- GET /api/governance/results/<n> ------------------------------------
    @bp.route("/api/governance/results/<int:proposal_id>", methods=["GET"])
    def get_results(proposal_id: int):
        _settle_expired_proposals(db_path)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                proposal = conn.execute(
                    "SELECT * FROM governance_proposals WHERE id = ?", (proposal_id,)
                ).fetchone()
                if not proposal:
                    return jsonify({"error": "proposal not found"}), 404
                p = dict(proposal)

        except Exception as e:
            log.error("Get results error: %s", e)
            return jsonify({"error": "internal error"}), 500

        total_votes = p["votes_for"] + p["votes_against"] + p["votes_abstain"]
        active_miners = _count_active_miners(db_path)
        quorum_required = active_miners * QUORUM_THRESHOLD if active_miners > 0 else 0

        return jsonify({
            "proposal_id": proposal_id,
            "title": p["title"],
            "status": p["status"],
            "votes_for": p["votes_for"],
            "votes_against": p["votes_against"],
            "votes_abstain": p["votes_abstain"],
            "total_votes": total_votes,
            "quorum_required": quorum_required,
            "quorum_met": bool(p["quorum_met"]),
            "active_miners": active_miners,
            "participation_pct": round(total_votes / active_miners * 100, 1) if active_miners > 0 else 0,
            "sophia_analysis": p.get("sophia_analysis"),
        }), 200

    # -- POST /api/governance/veto/<n> (founder veto) -----------------------
    @bp.route("/api/governance/veto/<int:proposal_id>", methods=["POST"])
    def founder_veto(proposal_id: int):
        if not _is_within_founder_veto_period():
            return jsonify({"error": "Founder veto period has expired"}), 403

        data = request.get_json(silent=True) or {}
        admin_key = data.get("admin_key", "").strip()
        reason = data.get("reason", "Security-critical change").strip()

        # Admin key is validated via environment variable (not hardcoded)
        import os
        expected_key = os.environ.get("RUSTCHAIN_ADMIN_KEY", "")
        if not expected_key or admin_key != expected_key:
            return jsonify({"error": "invalid admin_key"}), 403

        try:
            with sqlite3.connect(db_path) as conn:
                proposal = conn.execute(
                    "SELECT id, status FROM governance_proposals WHERE id = ?",
                    (proposal_id,)
                ).fetchone()
                if not proposal:
                    return jsonify({"error": "proposal not found"}), 404
                if proposal[1] != STATUS_ACTIVE:
                    return jsonify({"error": f"proposal is already {proposal[1]}"}), 409

                conn.execute(
                    "UPDATE governance_proposals SET status = ?, vetoed_by = ?, veto_reason = ? WHERE id = ?",
                    (STATUS_VETOED, "founder", reason, proposal_id)
                )
                conn.commit()

        except Exception as e:
            log.error("Veto error: %s", e)
            return jsonify({"error": "internal error"}), 500

        log.info("Proposal #%s vetoed by founder: %s", proposal_id, reason)
        return jsonify({"ok": True, "proposal_id": proposal_id, "status": STATUS_VETOED, "reason": reason}), 200

    # -- GET /api/governance/stats ------------------------------------------
    @bp.route("/api/governance/stats", methods=["GET"])
    def governance_stats():
        _settle_expired_proposals(db_path)
        try:
            with sqlite3.connect(db_path) as conn:
                counts = {}
                for status in [STATUS_ACTIVE, STATUS_PASSED, STATUS_FAILED, STATUS_EXPIRED, STATUS_VETOED]:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM governance_proposals WHERE status = ?", (status,)
                    ).fetchone()
                    counts[status] = row[0] if row else 0

                total_votes = conn.execute(
                    "SELECT COUNT(*) FROM governance_votes"
                ).fetchone()

        except Exception as e:
            log.error("Stats error: %s", e)
            return jsonify({"error": "internal error"}), 500

        return jsonify({
            "proposal_counts": counts,
            "total_proposals": sum(counts.values()),
            "total_votes_cast": total_votes[0] if total_votes else 0,
            "active_miners": _count_active_miners(db_path),
            "founder_veto_active": _is_within_founder_veto_period(),
            "quorum_threshold_pct": QUORUM_THRESHOLD * 100,
            "voting_window_days": VOTING_WINDOW_SECONDS // 86400,
        }), 200

    return bp
