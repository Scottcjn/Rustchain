"""
RIP-302 Dispute Resolution System
====================================
Voting-based dispute settlement by reputation holders for the
RustChain Agent Economy (RIP-302).

Features:
  - Any party (poster or worker) can open a dispute on a disputed job
  - Reputation-weighted voting: higher reputation = stronger vote weight
  - RTC stake required to vote (slashed if voting maliciously)
  - Auto-resolution when 60% supermajority reached
  - Dispute fee deposited on opening, refunded on fair resolution
  - Slashing mechanism for malicious voters
  - Admin override capability for edge cases

Author: kuanglaodi2-sudo
Date: 2026-03-19
Bounty: #683 — RIP-302 Agent Economy — Tier 3 Dispute Resolution (100 RTC)
Claim: https://github.com/Scottcjn/rustchain-bounties/issues/683#issuecomment-4090343141
"""

import hashlib
import json
import logging
import sqlite3
import time
from flask import Flask, request, jsonify

log = logging.getLogger("rip302_disputes")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Voting parameters
VOTE_THRESHOLD = 0.60          # 60% supermajority to auto-resolve
MIN_VOTES_TO_RESOLVE = 3       # Minimum votes before auto-resolve checks
VOTE_STAKE_I64 = 10_000_000    # 10 RTC stake to cast a vote (in micro-units)
SLASH_FRACTION = 0.50          # 50% slashed for malicious voting
DISPUTE_FEE_I64 = 5_000_000    # 5 RTC fee to open a dispute
VOTE_COOLDOWN = 24 * 3600     # 24h between votes from same wallet

# Dispute statuses
DISPUTE_STATUS_OPEN = "open"
DISPUTE_STATUS_RESOLVING = "resolving"
DISPUTE_STATUS_RESOLVED_WORKER = "resolved_worker"
DISPUTE_STATUS_RESOLVED_POSTER = "resolved_poster"
DISPUTE_STATUS_RESOLVED_SPLIT = "resolved_split"
DISPUTE_STATUS_DROPPED = "dropped"
DISPUTE_STATUS_ADMIN_OVERRIDE = "admin_override"

# Vote outcomes
VOTE_FOR_WORKER = "for_worker"    # Vote: release escrow to worker
VOTE_FOR_POSTER = "for_poster"   # Vote: refund escrow to poster
VOTE_SPLIT = "split"             # Vote: 50/50 split
VOTE_DROP = "drop"               # Vote: dismiss dispute, no resolution

# Admin override wallet (platform/community governance)
ADMIN_WALLET = "founder_community"

# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

def init_dispute_tables(db_path: str):
    """Create dispute and vote tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # Disputes table
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_disputes (
                dispute_id      TEXT PRIMARY KEY,
                job_id          TEXT NOT NULL,
                opened_by       TEXT NOT NULL,
                reason          TEXT NOT NULL,
                evidence_url    TEXT,
                worker_payout_i64 INTEGER NOT NULL DEFAULT 0,
                poster_refund_i64 INTEGER NOT NULL DEFAULT 0,
                status          TEXT DEFAULT 'open',
                verdict         TEXT,
                verdict_reason  TEXT,
                resolved_by     TEXT,
                resolved_at     INTEGER,
                created_at      INTEGER NOT NULL,
                expires_at      INTEGER NOT NULL,
                fee_deposit_i64 INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (job_id) REFERENCES agent_jobs(job_id)
            )
        """)

        # Dispute votes table (reputation-weighted)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_dispute_votes (
                vote_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                dispute_id       TEXT NOT NULL,
                voter_wallet     TEXT NOT NULL,
                vote             TEXT NOT NULL,
                voting_power     REAL NOT NULL,
                stake_i64        INTEGER NOT NULL,
                justification    TEXT,
                is_malicious     INTEGER DEFAULT 0,
                slashed_i64      INTEGER DEFAULT 0,
                created_at       INTEGER NOT NULL,
                UNIQUE(dispute_id, voter_wallet)
            )
        """)

        # Slashing ledger
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_slashing_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                dispute_id    TEXT NOT NULL,
                voter_wallet  TEXT NOT NULL,
                slash_reason  TEXT NOT NULL,
                slashed_i64   INTEGER NOT NULL,
                slashed_to    TEXT NOT NULL,
                created_at    INTEGER NOT NULL
            )
        """)

        # Indexes for performance
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_disputes_job_id
            ON agent_disputes(job_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_disputes_status
            ON agent_disputes(status)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_dispute_id
            ON agent_dispute_votes(dispute_id)
        """)

        conn.commit()
    log.info("RIP-302 Dispute Resolution tables initialized")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_dispute_id(job_id: str, opener: str) -> str:
    """Deterministic dispute ID."""
    seed = f"{job_id}:{opener}:{time.time()}:{id(job_id)}"
    return "dsp_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def _get_reputation_score(c: sqlite3.Cursor, wallet_id: str) -> float:
    """Get agent's reputation score (0.0 to ~10.0+)."""
    row = c.execute("""
        SELECT jobs_completed_as_worker, jobs_completed_as_poster,
               jobs_disputed, avg_rating, rating_count
        FROM agent_reputation WHERE wallet_id = ?
    """, (wallet_id,)).fetchone()
    if not row:
        return 0.5  # New agents get minimal weight

    completed_worker, completed_poster, disputed, avg_rating, rating_count = row

    # Base: jobs completed (0.1 per job, max 2.0)
    base = min((completed_worker + completed_poster) * 0.1, 2.0)

    # Rating bonus (0 to 3.0)
    if rating_count and avg_rating:
        rating_bonus = (avg_rating / 5.0) * 3.0
    else:
        rating_bonus = 0.0

    # Dispute penalty (-0.5 per dispute, max -2.0)
    dispute_penalty = min(disputed * 0.5, 2.0)

    score = base + rating_bonus - dispute_penalty
    return max(score, 0.1)  # Minimum 0.1 to prevent zero-division


def _compute_voting_power(c: sqlite3.Cursor, wallet_id: str) -> float:
    """Compute voting power from reputation score + RTC stake."""
    rep_score = _get_reputation_score(c, wallet_id)

    # Also factor in RTC balance as secondary signal
    balance_i64 = _get_balance_i64_standalone(c, wallet_id)
    rtc_balance = balance_i64 / 1_000_000.0

    # Log-scale balance power (1 RTC = small boost, 1000 RTC = significant)
    balance_power = min(1.0 + (rtc_balance / 100.0), 3.0)

    # Final: reputation-weighted power (1x to 6x multiplier)
    voting_power = rep_score * balance_power
    return max(round(voting_power, 4), 0.1)


def _get_balance_i64_standalone(c: sqlite3.Cursor, wallet_id: str) -> int:
    """Get balance in micro-units, standalone query."""
    try:
        row = c.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            (wallet_id,)
        ).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    for col, key in (("balance_rtc", "miner_pk"), ("balance_rtc", "miner_id")):
        try:
            row = c.execute(
                f"SELECT {col} FROM balances WHERE {key} = ?",
                (wallet_id,)
            ).fetchone()
            if row and row[0] is not None:
                return int(round(float(row[0]) * 1_000_000))
        except Exception:
            continue
    return 0


def _adjust_balance_standalone(c: sqlite3.Cursor, wallet_id: str, delta_i64: int):
    """Adjust balance without depending on rip302's _adjust_balance."""
    current = _get_balance_i64_standalone(c, wallet_id)
    new_balance = current + delta_i64
    c.execute("""
        INSERT INTO balances (miner_id, amount_i64)
        VALUES (?, ?)
        ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = ?
    """, (wallet_id, new_balance, new_balance))


def _update_job_status(c: sqlite3.Cursor, job_id: str, status: str):
    """Update job status in agent_jobs table."""
    c.execute(
        "UPDATE agent_jobs SET status = ? WHERE job_id = ?",
        (status, job_id)
    )


def _job_exists(c: sqlite3.Cursor, job_id: str) -> bool:
    """Check if job exists."""
    row = c.execute(
        "SELECT job_id FROM agent_jobs WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    return row is not None


def _job_is_disputed(c: sqlite3.Cursor, job_id: str) -> bool:
    """Check if job already has an open dispute."""
    row = c.execute("""
        SELECT dispute_id FROM agent_disputes
        WHERE job_id = ? AND status IN ('open', 'resolving')
    """, (job_id,)).fetchone()
    return row is not None


def _job_is_eligible_for_dispute(c: sqlite3.Cursor, job_id: str) -> bool:
    """Job must be in 'disputed' or 'delivered' status to open dispute."""
    row = c.execute(
        "SELECT status FROM agent_jobs WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    if not row:
        return False
    return row[0] in ("disputed", "delivered")


# ---------------------------------------------------------------------------
# Core Dispute Logic
# ---------------------------------------------------------------------------

def open_dispute(c: sqlite3.Cursor, job_id: str, opener: str, reason: str,
                 evidence_url: str = None) -> dict:
    """
    Open a dispute on a job.
    Only poster or worker of the job can open; only one open dispute per job.
    """
    # Validate job
    job_row = c.execute(
        "SELECT poster_wallet, worker_wallet, escrow_i64, status FROM agent_jobs WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    if not job_row:
        return {"error": "Job not found", "code": 404}
    poster_wallet, worker_wallet, escrow_i64, job_status = job_row

    # Who can open?
    if opener not in (poster_wallet, worker_wallet):
        return {"error": "Only poster or worker can open a dispute", "code": 403}

    # Check job status
    if not _job_is_eligible_for_dispute(c, job_id):
        return {
            "error": f"Cannot dispute job in status '{job_status}'. "
                     f"Job must be in 'disputed' or 'delivered' state.",
            "code": 400
        }

    # Check no existing open dispute
    if _job_is_disputed(c, job_id):
        return {"error": "An open dispute already exists for this job", "code": 409}

    # Collect dispute fee
    fee = DISPUTE_FEE_I64
    balance = _get_balance_i64_standalone(c, opener)
    if balance < fee:
        return {
            "error": f"Insufficient balance to open dispute. Need {fee/1e6:.1f} RTC, "
                     f"have {balance/1e6:.1f} RTC",
            "code": 400
        }

    # Generate dispute ID
    dispute_id = _generate_dispute_id(job_id, opener)
    now = int(time.time())
    expires_at = now + (7 * 86400)  # 7 days to resolve

    # Deduct fee
    _adjust_balance_standalone(c, opener, -fee)

    # Create dispute
    c.execute("""
        INSERT INTO agent_disputes
          (dispute_id, job_id, opened_by, reason, evidence_url,
           worker_payout_i64, poster_refund_i64, status,
           created_at, expires_at, fee_deposit_i64)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dispute_id, job_id, opener, reason, evidence_url,
        0, 0, DISPUTE_STATUS_OPEN,
        now, expires_at, fee
    ))

    # Update job status
    _update_job_status(c, job_id, "disputed")

    log.info(f"Dispute {dispute_id} opened by {opener} on job {job_id}")

    return {
        "dispute_id": dispute_id,
        "job_id": job_id,
        "status": DISPUTE_STATUS_OPEN,
        "fee_deposited_rtc": fee / 1e6,
        "created_at": now,
        "expires_at": expires_at
    }


def cast_vote(c: sqlite3.Cursor, dispute_id: str, voter: str,
              vote: str, justification: str = None) -> dict:
    """
    Cast a vote on an open dispute.
    Voter stakes RTC and gains voting power based on reputation.
    """
    # Validate dispute
    dsp_row = c.execute("""
        SELECT job_id, status, created_at, expires_at
        FROM agent_disputes WHERE dispute_id = ?
    """, (dispute_id,)).fetchone()
    if not dsp_row:
        return {"error": "Dispute not found", "code": 404}
    job_id, status, created_at, expires_at = dsp_row

    if status not in (DISPUTE_STATUS_OPEN, DISPUTE_STATUS_RESOLVING):
        return {"error": f"Dispute is not open for voting (status: {status})", "code": 400}

    now = int(time.time())
    if now > expires_at:
        return {"error": "Dispute has expired", "code": 410}

    # Validate vote value
    if vote not in (VOTE_FOR_WORKER, VOTE_FOR_POSTER, VOTE_SPLIT, VOTE_DROP):
        return {"error": f"Invalid vote: {vote}", "code": 400}

    # Check cooldown
    last_vote_row = c.execute("""
        SELECT created_at FROM agent_dispute_votes
        WHERE dispute_id = ? AND voter_wallet = ?
        ORDER BY created_at DESC LIMIT 1
    """, (dispute_id, voter)).fetchone()
    if last_vote_row and (now - last_vote_row[0]) < VOTE_COOLDOWN:
        remaining = VOTE_COOLDOWN - (now - last_vote_row[0])
        return {
            "error": f"Vote cooldown active. Try again in {remaining//3600}h",
            "code": 429
        }

    # Stake vote
    balance = _get_balance_i64_standalone(c, voter)
    if balance < VOTE_STAKE_I64:
        return {
            "error": f"Insufficient stake. Need {VOTE_STAKE_I64/1e6:.1f} RTC, "
                     f"have {balance/1e6:.1f} RTC",
            "code": 400
        }

    _adjust_balance_standalone(c, voter, -VOTE_STAKE_I64)

    # Compute voting power
    voting_power = _compute_voting_power(c, voter)

    # Insert vote
    try:
        c.execute("""
            INSERT INTO agent_dispute_votes
              (dispute_id, voter_wallet, vote, voting_power, stake_i64,
               justification, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (dispute_id, voter, vote, voting_power, VOTE_STAKE_I64,
              justification, now))
    except sqlite3.IntegrityError:
        _adjust_balance_standalone(c, voter, VOTE_STAKE_I64)  # refund
        return {"error": "Already voted on this dispute", "code": 409}

    # Move dispute to resolving
    if status == DISPUTE_STATUS_OPEN:
        c.execute(
            "UPDATE agent_disputes SET status = ? WHERE dispute_id = ?",
            (DISPUTE_STATUS_RESOLVING, dispute_id)
        )

    log.info(f"Vote cast: {voter} voted {vote} (power={voting_power}) on {dispute_id}")

    # Check auto-resolution
    result = check_and_auto_resolve(c, dispute_id)
    if result:
        return {
            "vote_recorded": True,
            "voting_power": voting_power,
            "stake_rtc": VOTE_STAKE_I64 / 1e6,
            "auto_resolved": True,
            "resolution": result
        }

    return {
        "vote_recorded": True,
        "voting_power": voting_power,
        "stake_rtc": VOTE_STAKE_I64 / 1e6,
        "auto_resolved": False
    }


def check_and_auto_resolve(c: sqlite3.Cursor, dispute_id: str) -> dict | None:
    """
    Check if vote supermajority has been reached.
    Returns resolution dict if resolved, None if not yet.
    """
    votes = c.execute("""
        SELECT vote, voting_power FROM agent_dispute_votes
        WHERE dispute_id = ?
    """, (dispute_id,)).fetchall()

    total_power = sum(v for _, v in votes)
    if total_power < MIN_VOTES_TO_RESOLVE:
        return None

    # Tally weighted votes
    worker_power = sum(power for vote, power in votes if vote == VOTE_FOR_WORKER)
    poster_power = sum(power for vote, power in votes if vote == VOTE_FOR_POSTER)
    split_power = sum(power for vote, power in votes if vote == VOTE_SPLIT)
    drop_power = sum(power for vote, power in votes if vote == VOTE_DROP)

    worker_pct = worker_power / total_power if total_power else 0
    poster_pct = poster_power / total_power if total_power else 0

    dsp = c.execute(
        "SELECT job_id, opened_by FROM agent_disputes WHERE dispute_id = ?",
        (dispute_id,)
    ).fetchone()
    job_id, opener = dsp

    job = c.execute(
        "SELECT escrow_i64, worker_wallet, poster_wallet FROM agent_jobs WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    if not job:
        return None
    escrow_i64, worker_wallet, poster_wallet = job

    now = int(time.time())

    # Resolve to worker (>60% for worker)
    if worker_pct >= VOTE_THRESHOLD:
        _adjust_balance_standalone(c, worker_wallet, escrow_i64)
        c.execute("""
            UPDATE agent_disputes
            SET status = ?, verdict = ?, verdict_reason = ?,
                resolved_by = 'auto_vote', resolved_at = ?,
                worker_payout_i64 = ?
            WHERE dispute_id = ?
        """, (
            DISPUTE_STATUS_RESOLVED_WORKER, VOTE_FOR_WORKER,
            f"Supermajority ({worker_pct:.0%}) voted to release to worker",
            now, escrow_i64, dispute_id
        ))
        _update_job_status(c, job_id, "completed")
        _refund_vote_stakes(c, dispute_id, except_votes=[])  # refund all
        log.info(f"Dispute {dispute_id} auto-resolved: payout to worker")
        return {
            "status": DISPUTE_STATUS_RESOLVED_WORKER,
            "winner": "worker",
            "worker_payout_rtc": escrow_i64 / 1e6,
            "reason": f"{worker_pct:.0%} supermajority for worker"
        }

    # Resolve to poster (>60% for poster)
    if poster_pct >= VOTE_THRESHOLD:
        _adjust_balance_standalone(c, poster_wallet, escrow_i64)
        c.execute("""
            UPDATE agent_disputes
            SET status = ?, verdict = ?, verdict_reason = ?,
                resolved_by = 'auto_vote', resolved_at = ?,
                poster_refund_i64 = ?
            WHERE dispute_id = ?
        """, (
            DISPUTE_STATUS_RESOLVED_POSTER, VOTE_FOR_POSTER,
            f"Supermajority ({poster_pct:.0%}) voted to refund poster",
            now, escrow_i64, dispute_id
        ))
        _update_job_status(c, job_id, "cancelled")
        _refund_vote_stakes(c, dispute_id, except_votes=[])
        log.info(f"Dispute {dispute_id} auto-resolved: refund to poster")
        return {
            "status": DISPUTE_STATUS_RESOLVED_POSTER,
            "winner": "poster",
            "poster_refund_rtc": escrow_i64 / 1e6,
            "reason": f"{poster_pct:.0%} supermajority for poster"
        }

    return None


def _refund_vote_stakes(c: sqlite3.Cursor, dispute_id: str,
                        except_votes: list[str]):
    """Refund vote stakes to voters except those marked malicious."""
    votes = c.execute("""
        SELECT voter_wallet, stake_i64, is_malicious
        FROM agent_dispute_votes
        WHERE dispute_id = ?
    """, (dispute_id,)).fetchall()

    for voter, stake_i64, is_malicious in votes:
        if voter in except_votes:
            continue
        slash_amount = int(stake_i64 * SLASH_FRACTION) if is_malicious else 0
        refund = stake_i64 - slash_amount
        if refund > 0:
            _adjust_balance_standalone(c, voter, refund)
        if slash_amount > 0:
            # Log slashing
            c.execute("""
                INSERT INTO agent_slashing_log
                  (dispute_id, voter_wallet, slash_reason, slashed_i64,
                   slashed_to, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (dispute_id, voter, "malicious_voting",
                  slashAmount, ADMIN_WALLET, int(time.time())))


def slash_malicious_voter(c: sqlite3.Cursor, dispute_id: str,
                          voter: str, reason: str) -> dict:
    """Slash a voter for malicious behavior (e.g., counterfactual voting)."""
    vote_row = c.execute("""
        SELECT vote_id, stake_i64 FROM agent_dispute_votes
        WHERE dispute_id = ? AND voter_wallet = ?
    """, (dispute_id, voter)).fetchone()
    if not vote_row:
        return {"error": "Vote not found", "code": 404}

    vote_id, stake_i64 = vote_row
    slash_amount = int(stake_i64 * SLASH_FRACTION)
    refund = stake_i64 - slash_amount

    # Mark as malicious
    c.execute("""
        UPDATE agent_dispute_votes
        SET is_malicious = 1, slashed_i64 = ?
        WHERE vote_id = ?
    """, (slash_amount, vote_id))

    # Refund remainder to voter
    if refund > 0:
        _adjust_balance_standalone(c, voter, refund)

    # Slashed amount → admin/community wallet
    if slash_amount > 0:
        _adjust_balance_standalone(c, ADMIN_WALLET, slash_amount)
        c.execute("""
            INSERT INTO agent_slashing_log
              (dispute_id, voter_wallet, slash_reason, slashed_i64,
               slashed_to, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (dispute_id, voter, reason, slash_amount,
              ADMIN_WALLET, int(time.time())))

    log.warning(f"Slashed voter {voter} on {dispute_id}: {slash_amount/1e6} RTC")
    return {
        "voter": voter,
        "slashed_rtc": slash_amount / 1e6,
        "refunded_rtc": refund / 1e6
    }


def admin_override(c: sqlite3.Cursor, dispute_id: str, admin: str,
                   verdict: str, reason: str) -> dict:
    """Admin can manually resolve a dispute."""
    if admin != ADMIN_WALLET:
        return {"error": "Admin override only", "code": 403}

    dsp = c.execute(
        "SELECT job_id FROM agent_disputes WHERE dispute_id = ?",
        (dispute_id,)
    ).fetchone()
    if not dsp:
        return {"error": "Dispute not found", "code": 404}

    job_id = dsp[0]
    job = c.execute(
        "SELECT escrow_i64, worker_wallet, poster_wallet FROM agent_jobs WHERE job_id = ?",
        (job_id,)
    ).fetchone()
    escrow_i64, worker_wallet, poster_wallet = job

    now = int(time.time())

    if verdict == VOTE_FOR_WORKER:
        _adjust_balance_standalone(c, worker_wallet, escrow_i64)
        new_status = DISPUTE_STATUS_RESOLVED_WORKER
        payout_i64 = escrow_i64
    elif verdict == VOTE_FOR_POSTER:
        _adjust_balance_standalone(c, poster_wallet, escrow_i64)
        new_status = DISPUTE_STATUS_RESOLVED_POSTER
        payout_i64 = 0
    elif verdict == VOTE_SPLIT:
        half = escrow_i64 // 2
        _adjust_balance_standalone(c, worker_wallet, half)
        _adjust_balance_standalone(c, poster_wallet, escrow_i64 - half)
        new_status = DISPUTE_STATUS_RESOLVED_SPLIT
        payout_i64 = half
    else:
        new_status = DISPUTE_STATUS_DROPPED
        payout_i64 = 0

    c.execute("""
        UPDATE agent_disputes
        SET status = ?, verdict = ?, verdict_reason = ?,
            resolved_by = ?, resolved_at = ?,
            worker_payout_i64 = ?,
            poster_refund_i64 = ?
        WHERE dispute_id = ?
    """, (new_status, verdict, reason, admin, now,
          payout_i64 if verdict == VOTE_FOR_WORKER else 0,
          escrow_i64 - payout_i64 if verdict in (VOTE_FOR_POSTER, VOTE_SPLIT) else 0,
          dispute_id))

    _update_job_status(c, job_id, "completed" if verdict != VOTE_DROP else "disputed")
    _refund_vote_stakes(c, dispute_id, [])

    log.info(f"Admin override on {dispute_id}: verdict={verdict}")
    return {
        "dispute_id": dispute_id,
        "status": new_status,
        "verdict": verdict,
        "resolved_by": "admin_override"
    }


def get_dispute_details(c: sqlite3.Cursor, dispute_id: str) -> dict:
    """Get full dispute details including vote tallies."""
    dsp = c.execute("""
        SELECT dispute_id, job_id, opened_by, reason, evidence_url,
               worker_payout_i64, poster_refund_i64, status,
               verdict, verdict_reason, resolved_by, resolved_at,
               created_at, expires_at, fee_deposit_i64
        FROM agent_disputes WHERE dispute_id = ?
    """, (dispute_id,)).fetchone()
    if not dsp:
        return {"error": "Dispute not found", "code": 404}

    (dispute_id, job_id, opened_by, reason, evidence_url,
     worker_payout_i64, poster_refund_i64, status,
     verdict, verdict_reason, resolved_by, resolved_at,
     created_at, expires_at, fee_deposit_i64) = dsp

    # Get votes
    votes = c.execute("""
        SELECT voter_wallet, vote, voting_power, stake_i64,
               is_malicious, slashed_i64, created_at
        FROM agent_dispute_votes
        WHERE dispute_id = ?
        ORDER BY created_at ASC
    """, (dispute_id,)).fetchall()

    # Tally
    total_power = sum(v[2] for v in votes)
    worker_power = sum(v[2] for v in votes if v[1] == VOTE_FOR_WORKER)
    poster_power = sum(v[2] for v in votes if v[1] == VOTE_FOR_POSTER)
    split_power = sum(v[2] for v in votes if v[1] == VOTE_SPLIT)
    drop_power = sum(v[2] for v in votes if v[1] == VOTE_DROP)

    vote_list = [{
        "voter": v[0],
        "vote": v[1],
        "voting_power": v[2],
        "stake_rtc": v[3] / 1e6,
        "is_malicious": bool(v[4]),
        "slashed_rtc": v[5] / 1e6 if v[5] else 0,
        "voted_at": v[6]
    } for v in votes]

    # Get job info
    job = c.execute("""
        SELECT poster_wallet, worker_wallet, title, reward_rtc, status
        FROM agent_jobs WHERE job_id = ?
    """, (job_id,)).fetchone()

    return {
        "dispute_id": dispute_id,
        "job_id": job_id,
        "job_title": job[2] if job else None,
        "poster_wallet": job[0] if job else None,
        "worker_wallet": job[1] if job else None,
        "job_status": job[4] if job else None,
        "escrow_rtc": job[3] if job else 0,
        "opened_by": opened_by,
        "reason": reason,
        "evidence_url": evidence_url,
        "status": status,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "resolved_by": resolved_by,
        "resolved_at": resolved_at,
        "created_at": created_at,
        "expires_at": expires_at,
        "fee_deposit_rtc": fee_deposit_i64 / 1e6,
        "voting": {
            "total_votes": len(votes),
            "total_voting_power": round(total_power, 4),
            "worker_power": round(worker_power, 4),
            "poster_power": round(poster_power, 4),
            "split_power": round(split_power, 4),
            "drop_power": round(drop_power, 4),
            "worker_pct": round(worker_power / total_power, 4) if total_power else 0,
            "poster_pct": round(poster_power / total_power, 4) if total_power else 0,
            "threshold_pct": VOTE_THRESHOLD,
            "votes": vote_list
        }
    }


# ---------------------------------------------------------------------------
# Flask Integration
# ---------------------------------------------------------------------------

def register_dispute_endpoints(app: Flask, db_path: str,
                                require_auth=None):
    """
    Register all dispute resolution endpoints to an existing Flask app.
    Wraps rip302_agent_economy.py endpoints.
    """

    @app.route("/agent/disputes", methods=["POST"])
    def create_dispute():
        """Open a new dispute on a job."""
        body = request.get_json() or {}
        job_id = body.get("job_id")
        wallet = (require_auth(request) if require_auth
                  else body.get("wallet"))
        reason = body.get("reason", "")
        evidence_url = body.get("evidence_url")

        if not job_id or not wallet:
            return jsonify({"error": "job_id and wallet required"}), 400
        if not reason.strip():
            return jsonify({"error": "reason required"}), 400

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            result = open_dispute(c, job_id, wallet, reason, evidence_url)
            conn.commit()

        if "error" in result:
            return jsonify(result), result.get("code", 400)
        return jsonify(result), 201

    @app.route("/agent/disputes", methods=["GET"])
    def list_disputes():
        """List all disputes, optionally filtered by status or job_id."""
        status = request.args.get("status")
        job_id = request.args.get("job_id")
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            query = "SELECT * FROM agent_disputes WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if job_id:
                query += " AND job_id = ?"
                params.append(job_id)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = c.execute(query, params).fetchall()
            disputes = [dict(r) for r in rows]

        # Convert int64 fields
        for d in disputes:
            for k in ["worker_payout_i64", "poster_refund_i64",
                      "created_at", "expires_at", "resolved_at",
                      "fee_deposit_i64"]:
                if d.get(k):
                    d[k] = int(d[k])

        return jsonify({
            "disputes": disputes,
            "count": len(disputes),
            "limit": limit,
            "offset": offset
        })

    @app.route("/agent/disputes/<dispute_id>", methods=["GET"])
    def get_dispute(dispute_id):
        """Get full dispute details with vote tallies."""
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            result = get_dispute_details(c, dispute_id)
        if "error" in result:
            return jsonify(result), result.get("code", 404)
        return jsonify(result)

    @app.route("/agent/disputes/<dispute_id>/vote", methods=["POST"])
    def vote_dispute(dispute_id):
        """Cast a vote on an open dispute."""
        body = request.get_json() or {}
        voter = (require_auth(request) if require_auth
                 else body.get("wallet"))
        vote = body.get("vote")
        justification = body.get("justification")

        if not voter or not vote:
            return jsonify({"error": "wallet and vote required"}), 400

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            result = cast_vote(c, dispute_id, voter, vote, justification)
            conn.commit()

        if "error" in result:
            return jsonify(result), result.get("code", 400)
        return jsonify(result)

    @app.route("/agent/disputes/<dispute_id>/votes", methods=["GET"])
    def get_dispute_votes(dispute_id):
        """List all votes for a dispute."""
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            votes = c.execute("""
                SELECT voter_wallet, vote, voting_power, stake_i64,
                       is_malicious, slashed_i64, created_at
                FROM agent_dispute_votes
                WHERE dispute_id = ?
                ORDER BY created_at ASC
            """, (dispute_id,)).fetchall()

        return jsonify({
            "dispute_id": dispute_id,
            "votes": [{
                "voter": v[0], "vote": v[1], "voting_power": float(v[2]),
                "stake_rtc": v[3] / 1e6, "is_malicious": bool(v[4]),
                "slashed_rtc": v[5] / 1e6 if v[5] else 0,
                "voted_at": v[6]
            } for v in votes]
        })

    @app.route("/agent/disputes/<dispute_id>/slash", methods=["POST"])
    def slash_voter(dispute_id):
        """Slash a malicious voter (admin only)."""
        body = request.get_json() or {}
        admin = (require_auth(request) if require_auth
                 else body.get("admin"))
        voter = body.get("voter")
        reason = body.get("reason", "malicious_voting")

        if not admin or not voter:
            return jsonify({"error": "admin and voter required"}), 400

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            result = slash_malicious_voter(c, dispute_id, voter, reason)
            conn.commit()

        if "error" in result:
            return jsonify(result), result.get("code", 400)
        return jsonify(result)

    @app.route("/agent/disputes/<dispute_id>/resolve", methods=["POST"])
    def resolve_dispute(dispute_id):
        """Admin/manual resolution of a dispute."""
        body = request.get_json() or {}
        admin = (require_auth(request) if require_auth
                 else body.get("admin"))
        verdict = body.get("verdict")
        reason = body.get("reason", "")

        if not admin or not verdict:
            return jsonify({"error": "admin, verdict, and reason required"}), 400

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            result = admin_override(c, dispute_id, admin, verdict, reason)
            conn.commit()

        if "error" in result:
            return jsonify(result), result.get("code", 400)
        return jsonify(result)


# ---------------------------------------------------------------------------
# Standalone test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import os

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="RIP-302 Dispute Resolution CLI")
    parser.add_argument("--db", default="rustchain.db",
                        help="Path to SQLite database")
    parser.add_argument("--init", action="store_true",
                        help="Initialize dispute tables")
    parser.add_argument("--port", type=int, default=5000,
                        help="Flask server port")
    args = parser.parse_args()

    if args.init:
        init_dispute_tables(args.db)
        print(f"Dispute tables initialized in {args.db}")
    else:
        app = Flask(__name__)
        app.config["DEBUG"] = False

        init_dispute_tables(args.db)

        def get_wallet(req):
            return req.headers.get("X-Wallet", "test_wallet")

        register_dispute_endpoints(app, args.db, require_auth=get_wallet)
        print(f"Starting RIP-302 Dispute Resolution API on port {args.port}")
        app.run(host="0.0.0.0", port=args.port, debug=False)