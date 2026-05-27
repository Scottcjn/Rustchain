#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: Governance vote tally race condition (C9)

Demonstrates that concurrent vote-change requests can corrupt the vote
tally when cast_vote() does not wrap the INSERT/UPDATE in a transaction.

Bug: cast_vote() uses bare with sqlite3.connect() which auto-commits.
When a miner already voted, the INSERT raises IntegrityError, followed
by UPDATE to subtract old weight and add new weight. Without BEGIN IMMEDIATE,
concurrent threads can both read the old vote, subtract old weight twice,
and add new weight twice → tally corrupted.
"""

import os
import sys
import sqlite3
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

VOTE_CHOICES = ("for", "against", "abstain")
STATUS_ACTIVE = "active"


class TestGovernanceVoteTallyRace(unittest.TestCase):
    """Verify vote tally is correct under concurrent vote-change."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_c9.db")
        self._init_db()

    def tearDown(self):
        import shutil
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS governance_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                proposer TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                votes_for REAL DEFAULT 0,
                votes_against REAL DEFAULT 0,
                votes_abstain REAL DEFAULT 0,
                quorum_met INTEGER DEFAULT 0,
                vetoed INTEGER DEFAULT 0,
                vetoed_by TEXT
            );
            CREATE TABLE IF NOT EXISTS governance_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER NOT NULL,
                miner_id TEXT NOT NULL,
                vote TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                voted_at INTEGER NOT NULL,
                UNIQUE(proposal_id, miner_id)
            );
        """)
        conn.execute(
            "INSERT INTO governance_proposals (id, title, description, proposer, status, created_at, expires_at) "
            "VALUES (1, 'Test Proposal', 'desc', 'RTC_miner_a', 'active', ?, ?)",
            (int(time.time()), int(time.time()) + 86400),
        )
        conn.commit()
        conn.close()

    def _simulate_vote_change_race(self):
        """Simulate what cast_vote() does under concurrent requests."""
        def change_vote(miner_id, old_vote, new_vote, weight):
            conn = sqlite3.connect(self.db_path)
            try:
                # This simulates cast_vote() WITHOUT BEGIN IMMEDIATE
                try:
                    conn.execute(
                        "INSERT INTO governance_votes (proposal_id, miner_id, vote, weight, voted_at) "
                        "VALUES (1, ?, ?, ?, ?)",
                        (miner_id, new_vote, weight, int(time.time())),
                    )
                except sqlite3.IntegrityError:
                    # Already voted — update
                    old = conn.execute(
                        "SELECT vote, weight FROM governance_votes WHERE proposal_id = 1 AND miner_id = ?",
                        (miner_id,),
                    ).fetchone()
                    if old:
                        old_col = f"votes_{old[0]}"
                        conn.execute(
                            f"UPDATE governance_proposals SET {old_col} = {old_col} - ? WHERE id = 1",
                            (old[1],),
                        )
                    conn.execute(
                        "UPDATE governance_votes SET vote = ?, weight = ?, voted_at = ? "
                        "WHERE proposal_id = 1 AND miner_id = ?",
                        (new_vote, weight, int(time.time()), miner_id),
                    )
                # Add new vote
                col = f"votes_{new_vote}"
                conn.execute(
                    f"UPDATE governance_proposals SET {col} = {col} + ? WHERE id = 1",
                    (weight,),
                )
                conn.commit()
            finally:
                conn.close()

        # First vote: for
        change_vote("RTC_miner_a", None, "for", 1.0)

        # Then 5 concurrent threads all change from "for" to "against"
        # Use a barrier to force all threads to hit the IntegrityError path
        # simultaneously — this maximizes the race window.
        barrier = threading.Barrier(10)
        results = []
        results_lock = threading.Lock()
        results = []
        results_lock = threading.Lock()

        def race_vote():
            conn = sqlite3.connect(self.db_path)
            try:
                barrier.wait(timeout=5)
                try:
                    conn.execute(
                        "INSERT INTO governance_votes (proposal_id, miner_id, vote, weight, voted_at) "
                        "VALUES (1, ?, ?, ?, ?)",
                        ("RTC_miner_a", "against", 1.0, int(time.time())),
                    )
                except sqlite3.IntegrityError:
                    old = conn.execute(
                        "SELECT vote, weight FROM governance_votes WHERE proposal_id = 1 AND miner_id = ?",
                        ("RTC_miner_a",),
                    ).fetchone()
                    if old:
                        old_col = f"votes_{old[0]}"
                        conn.execute(
                            f"UPDATE governance_proposals SET {old_col} = {old_col} - ? WHERE id = 1",
                            (old[1],),
                        )
                    conn.execute(
                        "UPDATE governance_votes SET vote = ?, weight = ?, voted_at = ? "
                        "WHERE proposal_id = 1 AND miner_id = ?",
                        ("against", 1.0, int(time.time()), "RTC_miner_a"),
                    )
                col = "votes_against"
                conn.execute(
                    f"UPDATE governance_proposals SET {col} = {col} + ? WHERE id = 1",
                    (1.0,),
                )
                conn.commit()
            finally:
                conn.close()

        threads = [threading.Thread(target=race_vote) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT votes_for, votes_against, votes_abstain FROM governance_proposals WHERE id = 1"
        ).fetchone()
        conn.close()
        return row

    def test_tally_race_does_not_corrupt(self):
        """Verify concurrent vote-changes don't inflate/deflate tally."""
        votes_for, votes_against, votes_abstain = self._simulate_vote_change_race()

        total = votes_for + votes_against + votes_abstain
        print(f"\n  votes_for={votes_for}, votes_against={votes_against}, votes_abstain={votes_abstain}, total={total}")

        # After all 5 concurrent changes, miner voted "against" with weight 1.0
        # Expected: votes_for=0, votes_against=1.0, votes_abstain=0
        self.assertEqual(
            (votes_for, votes_against, votes_abstain),
            (0, 1.0, 0),
            f"\nTALLY CORRUPTED! Expected (0, 1.0, 0) got ({votes_for}, {votes_against}, {votes_abstain})"
            f"\n{'🔴 BUG: Race condition inflated/deflated tally!' if total != 1.0 else '✅ Tally correct'}"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
