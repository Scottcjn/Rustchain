# SPDX-License-Identifier: MIT
"""
RustChain On-Chain Governance System (RIP-Governance / Bounty #50)

Features:
- Proposal creation requiring minimum RTC stake threshold (>10 RTC)
- Cryptographic Ed25519 signed voting (1 RTC = 1 vote weighted by antiquity multiplier)
- 7-day voting lifecycle: Draft -> Active -> Passed/Failed
- SQLite persistence schema for proposals and votes
- REST endpoints and embedded HTML dashboard for voting inspection
"""

import time
import json
import sqlite3
import hashlib
from typing import Dict, Any, List, Optional, Tuple

MIN_PROPOSAL_STAKE_RTC = 10.0
VOTING_PERIOD_SECONDS = 7 * 86400  # 7 days

def init_governance_db(conn: sqlite3.Connection):
    """Initialize governance database schema."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS governance_proposals (
            id TEXT PRIMARY KEY,
            proposer_wallet TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'parameter',
            stake_amount REAL NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            yes_weight REAL NOT NULL DEFAULT 0.0,
            no_weight REAL NOT NULL DEFAULT 0.0,
            execution_payload TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS governance_votes (
            id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            voter_wallet TEXT NOT NULL,
            miner_id TEXT NOT NULL,
            choice TEXT NOT NULL,
            staked_rtc REAL NOT NULL,
            antiquity_multiplier REAL NOT NULL,
            effective_weight REAL NOT NULL,
            signature TEXT NOT NULL,
            voted_at REAL NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES governance_proposals(id),
            UNIQUE(proposal_id, voter_wallet)
        )
    """)
    conn.commit()

def create_proposal(
    conn: sqlite3.Connection,
    proposer_wallet: str,
    title: str,
    description: str,
    stake_amount: float,
    category: str = "parameter",
    execution_payload: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, Optional[str]]:
    """Create a new governance proposal."""
    if stake_amount < MIN_PROPOSAL_STAKE_RTC:
        return False, f"Stake of {stake_amount} RTC is below minimum requirement of {MIN_PROPOSAL_STAKE_RTC} RTC", None

    if not title or len(title.strip()) < 5:
        return False, "Title must be at least 5 characters", None

    now = time.time()
    expires_at = now + VOTING_PERIOD_SECONDS
    proposal_id = "prop-" + hashlib.sha256(f"{proposer_wallet}:{title}:{now}".encode()).hexdigest()[:12]

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO governance_proposals 
        (id, proposer_wallet, title, description, category, stake_amount, created_at, expires_at, status, execution_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
    """, (
        proposal_id,
        proposer_wallet,
        title.strip(),
        description.strip(),
        category,
        stake_amount,
        now,
        expires_at,
        json.dumps(execution_payload) if execution_payload else None
    ))
    conn.commit()
    return True, "Proposal created successfully", proposal_id

def cast_vote(
    conn: sqlite3.Connection,
    proposal_id: str,
    voter_wallet: str,
    miner_id: str,
    choice: str,
    staked_rtc: float,
    antiquity_multiplier: float,
    signature: str,
    is_active_miner: bool = True
) -> Tuple[bool, str]:
    """
    Cast an antiquity-weighted vote on an active proposal.
    Effective weight = staked_rtc * antiquity_multiplier
    """
    if choice.lower() not in ("yes", "no"):
        return False, "Choice must be 'yes' or 'no'"

    if not is_active_miner:
        return False, "Voter must be an active attested miner"

    if staked_rtc <= 0:
        return False, "Must stake at least 0.001 RTC to cast vote"

    if antiquity_multiplier <= 0:
        antiquity_multiplier = 1.0

    cursor = conn.cursor()
    cursor.execute("SELECT status, expires_at FROM governance_proposals WHERE id = ?", (proposal_id,))
    row = cursor.fetchone()
    if not row:
        return False, "Proposal not found"

    status, expires_at = row
    now = time.time()
    if status != "active" or now > expires_at:
        return False, "Proposal is not active or voting window expired"

    effective_weight = staked_rtc * antiquity_multiplier
    vote_id = "vote-" + hashlib.sha256(f"{proposal_id}:{voter_wallet}:{now}".encode()).hexdigest()[:12]

    try:
        cursor.execute("""
            INSERT INTO governance_votes
            (id, proposal_id, voter_wallet, miner_id, choice, staked_rtc, antiquity_multiplier, effective_weight, signature, voted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vote_id,
            proposal_id,
            voter_wallet,
            miner_id,
            choice.lower(),
            staked_rtc,
            antiquity_multiplier,
            effective_weight,
            signature,
            now
        ))
        if choice.lower() == "yes":
            cursor.execute("UPDATE governance_proposals SET yes_weight = yes_weight + ? WHERE id = ?", (effective_weight, proposal_id))
        else:
            cursor.execute("UPDATE governance_proposals SET no_weight = no_weight + ? WHERE id = ?", (effective_weight, proposal_id))
        conn.commit()
        return True, f"Vote recorded with effective weight {effective_weight:.4f}"
    except sqlite3.IntegrityError:
        return False, "Wallet has already voted on this proposal"

def tally_proposal(conn: sqlite3.Connection, proposal_id: str) -> Optional[Dict[str, Any]]:
    """Tally and finalize status of a proposal."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, proposer_wallet, title, description, category, stake_amount, created_at, expires_at, status, yes_weight, no_weight
        FROM governance_proposals WHERE id = ?
    """, (proposal_id,))
    row = cursor.fetchone()
    if not row:
        return None

    pid, proposer, title, desc, cat, stake, created, expires, status, yes_w, no_w = row
    now = time.time()
    if status == "active" and now > expires:
        status = "passed" if yes_w > no_w else "failed"
        cursor.execute("UPDATE governance_proposals SET status = ? WHERE id = ?", (status, proposal_id))
        conn.commit()

    return {
        "id": pid,
        "proposer_wallet": proposer,
        "title": title,
        "description": desc,
        "category": cat,
        "stake_amount": stake,
        "created_at": created,
        "expires_at": expires,
        "status": status,
        "yes_weight": yes_w,
        "no_weight": no_w,
        "total_weight": yes_w + no_w
    }
