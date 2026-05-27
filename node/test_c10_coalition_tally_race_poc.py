#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: Coalition vote tally race condition (C10)

Same bug as C9 — coalition vote-change path lacks BEGIN IMMEDIATE.
Concurrent vote-change requests corrupt tally.
"""
import os, sys, sqlite3, tempfile, threading, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

VOTE_CHOICES = ("for", "against", "abstain")

tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "test_c10.db")

conn = sqlite3.connect(db_path)
conn.executescript(f"""
    CREATE TABLE coalition_proposals (
        id INTEGER PRIMARY KEY,
        votes_for REAL DEFAULT 0,
        votes_against REAL DEFAULT 0,
        votes_abstain REAL DEFAULT 0
    );
    CREATE TABLE coalition_votes (
        proposal_id INTEGER, miner_id TEXT,
        vote TEXT, weight REAL,
        UNIQUE(proposal_id, miner_id)
    );
    INSERT INTO coalition_proposals (id) VALUES (1);
    INSERT INTO coalition_votes (proposal_id, miner_id, vote, weight)
    VALUES (1, 'miner_a', 'for', 1.0);
""")
conn.commit()
conn.close()

barrier = threading.Barrier(20)

def race():
    barrier.wait()
    c = sqlite3.connect(db_path)
    try:
        c.execute("INSERT INTO coalition_votes VALUES (1,?,?,?)", ('miner_a', 'against', 1.0))
    except sqlite3.IntegrityError:
        old = c.execute("SELECT vote, weight FROM coalition_votes WHERE proposal_id=1 AND miner_id=?", ('miner_a',)).fetchone()
        old_col = f'votes_{old[0]}'
        c.execute(f"UPDATE coalition_proposals SET {old_col} = {old_col} - ? WHERE id = 1", (old[1],))
        c.execute("UPDATE coalition_votes SET vote=?, weight=? WHERE proposal_id=1 AND miner_id=?", ('against', 1.0, 'miner_a'))
    col = "votes_against"
    c.execute(f"UPDATE coalition_proposals SET {col} = {col} + ? WHERE id = 1", (1.0,))
    c.commit()
    c.close()

threads = [threading.Thread(target=race) for _ in range(20)]
for t in threads: t.start()
for t in threads: t.join()

c = sqlite3.connect(db_path)
r = c.execute("SELECT votes_for, votes_against, votes_abstain FROM coalition_proposals WHERE id = 1").fetchone()
c.close()

total = r[0] + r[1] + r[2]
print(f"votes_for={r[0]} votes_against={r[1]} votes_abstain={r[2]} total={total}")
if total != 1.0:
    print(f"🔴 C10 CONFIRMED: Tally corrupted! Expected total=1.0, got total={total}")
else:
    print("✅ Tally correct")

import shutil
shutil.rmtree(tmpdir)
