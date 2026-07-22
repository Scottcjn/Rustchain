#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""WT1 regression: process_claims_batch(dry_run=True) must not mutate claim state.

`process_claims_batch(..., dry_run=True)` is documented as "don't actually
process, just report what would be done".  However the stale-'verifying'
handling that transitions claims 'verifying' -> 'review_required' runs
unconditionally, *before* the dry-run early return.  A pure preview therefore
pulls in-flight claims out of the automated verify -> approve -> settle payout
pipeline into manual-review limbo, stalling their eventual payout.

On unmodified main this test FAILS (the verifying claim becomes
'review_required' after a dry run).
"""

import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import claims_settlement


def _init_db(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT,
                epoch INTEGER,
                wallet_address TEXT,
                reward_urtc INTEGER,
                status TEXT,
                submitted_at INTEGER,
                verified_at INTEGER,
                settled_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                rejection_reason TEXT,
                signature TEXT,
                public_key TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER,
                updated_at INTEGER
            );
            CREATE TABLE claims_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT, action TEXT, actor TEXT, details TEXT, timestamp INTEGER
            );
            """
        )


def _insert(path, claim_id, status, submitted_at, reward_urtc=1000):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO claims (claim_id, miner_id, epoch, wallet_address,
                                reward_urtc, status, submitted_at, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (claim_id, f"m-{claim_id}", f"w-{claim_id}", reward_urtc, status,
             submitted_at, submitted_at, submitted_at),
        )


def _status(path, claim_id):
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT status FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()[0]


def test_dry_run_does_not_flag_verifying_claims(tmp_path):
    db = str(tmp_path / "claims.db")
    _init_db(db)
    now = int(time.time())

    # Approved claims so the batch trigger condition is satisfiable.
    _insert(db, "a-1", "approved", now - 9999)
    _insert(db, "a-2", "approved", now - 9999)
    # A claim still verifying, older than max_wait_seconds // 2 -> would be flagged.
    _insert(db, "vfy", "verifying", now - 2000, reward_urtc=5000)

    result = claims_settlement.process_claims_batch(
        db, max_claims=10, min_batch_size=1, max_wait_seconds=1800, dry_run=True
    )

    # Dry run must report a preview...
    assert result["processed"] is True
    assert result["error"] == "Dry run - no actual processing"

    # ...but must NOT have mutated any persistent claim state.
    assert _status(db, "vfy") == "verifying", (
        "dry_run mutated a 'verifying' claim into '%s' — dry_run must be "
        "side-effect free" % _status(db, "vfy")
    )
    assert _status(db, "a-1") == "approved"
    assert _status(db, "a-2") == "approved"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
