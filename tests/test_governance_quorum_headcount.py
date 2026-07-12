# SPDX-License-Identifier: MIT
"""Governance quorum must be a headcount of distinct voters.

`votes_for/against/abstain` store an antiquity-*weighted* sum (each vote adds
the miner's antiquity_multiplier, clamped >= 1.0). Quorum, however, is a
participation gate compared against a count-based denominator
(`active_miners * QUORUM_THRESHOLD`). Comparing the weighted vote sum against a
headcount lets a handful of high-antiquity miners satisfy quorum on their own,
mirroring the bug fixed here. coalition.py already counts DISTINCT voters for
its quorum; governance.py now does the same.
"""

import sqlite3
import time

from node import governance


def _setup(tmp_path, active_miner_count):
    db_path = tmp_path / "governance.db"
    governance.init_governance_tables(str(db_path))
    now = int(time.time())
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE attestations (miner_id TEXT, timestamp INTEGER)")
        for i in range(active_miner_count):
            conn.execute(
                "INSERT INTO attestations (miner_id, timestamp) VALUES (?, ?)",
                (f"miner-{i}", now),
            )
        conn.commit()
    return db_path, now


def _add_proposal(db_path, now, votes_for, expired=True):
    expires_at = now - 10 if expired else now + 3600
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO governance_proposals "
            "(title, description, proposal_type, proposed_by, created_at, expires_at, "
            " status, votes_for, votes_against, votes_abstain) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("Prop", "desc", "parameter_change", "miner-0", now - 100, expires_at,
             governance.STATUS_ACTIVE, votes_for, 0.0, 0.0),
        )
        pid = cur.lastrowid
        conn.commit()
    return pid


def _cast_weighted_votes(db_path, pid, voters, weight, now):
    """Record `voters` distinct 'for' votes each carrying `weight`."""
    with sqlite3.connect(db_path) as conn:
        for i in range(voters):
            conn.execute(
                "INSERT INTO governance_votes (proposal_id, miner_id, vote, weight, voted_at) "
                "VALUES (?,?,?,?,?)",
                (pid, f"voter-{i}", "for", weight, now),
            )
        conn.commit()


def _status(db_path, pid):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT status, quorum_met FROM governance_proposals WHERE id = ?", (pid,)
        ).fetchone()


def test_few_heavy_voters_do_not_fake_quorum(tmp_path):
    # 10 active miners -> quorum needs ceil-ish of 10*0.33 = 3.3 -> 4 distinct voters.
    db_path, now = _setup(tmp_path, active_miner_count=10)
    # Only 2 distinct miners vote, each with antiquity weight 2.0.
    # Weighted sum = 4.0 (>= 3.3), but real participation = 2 miners (< 3.3).
    pid = _add_proposal(db_path, now, votes_for=4.0)
    _cast_weighted_votes(db_path, pid, voters=2, weight=2.0, now=now)

    governance._settle_expired_proposals(str(db_path))

    status, quorum_met = _status(db_path, pid)
    # Participation gate must reject: 2 voters < 3.3 required.
    assert quorum_met == 0
    assert status == governance.STATUS_EXPIRED


def test_enough_distinct_voters_reach_quorum(tmp_path):
    db_path, now = _setup(tmp_path, active_miner_count=10)
    pid = _add_proposal(db_path, now, votes_for=4.0)
    # 4 distinct miners vote (>= 3.3) -> quorum met, and votes_for > votes_against -> passed.
    _cast_weighted_votes(db_path, pid, voters=4, weight=1.0, now=now)

    governance._settle_expired_proposals(str(db_path))

    status, quorum_met = _status(db_path, pid)
    assert quorum_met == 1
    assert status == governance.STATUS_PASSED
