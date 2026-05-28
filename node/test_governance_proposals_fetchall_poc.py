# SPDX-License-Identifier: MIT
"""
PoC: GET /governance/proposals fetches every row from governance_proposals
with no LIMIT, including the full description column.

Each description can hold up to several kilobytes of text. With 250 active
proposals at 10 KB each, a single unauthenticated request forces the node
to deserialise and serialise ~2.5 MB of JSON per call. A sustained flood
of such requests exhausts Flask worker memory and causes OOM.

Fix: add LIMIT 200 to the SELECT so the response size is bounded
regardless of how many proposals exist.
"""

import sqlite3
import tempfile
import os
import unittest


_SELECT_UNBOUNDED = """
    SELECT id, proposer_wallet, title, description, created_at, activated_at,
           ends_at, status, yes_weight, no_weight
    FROM governance_proposals
    ORDER BY id DESC
"""

_SELECT_BOUNDED = """
    SELECT id, proposer_wallet, title, description, created_at, activated_at,
           ends_at, status, yes_weight, no_weight
    FROM governance_proposals
    ORDER BY id DESC
    LIMIT 200
"""

_PROPOSAL_COUNT = 250
_DESCRIPTION_BYTES = 10_000   # 10 KB per proposal


def _make_db(path: str, n: int) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE governance_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposer_wallet TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            activated_at INTEGER,
            ends_at INTEGER,
            status TEXT NOT NULL DEFAULT 'draft',
            yes_weight REAL NOT NULL DEFAULT 0,
            no_weight REAL NOT NULL DEFAULT 0
        )"""
    )
    conn.executemany(
        "INSERT INTO governance_proposals"
        " (proposer_wallet, title, description, created_at, status)"
        " VALUES (?,?,?,?,?)",
        [
            (f"RTC{'a'*40}", f"Proposal {i}", "x" * _DESCRIPTION_BYTES, 0, "active")
            for i in range(n)
        ],
    )
    conn.commit()
    conn.close()


class TestGovernanceProposalsLimit(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        _make_db(self._tmp.name, _PROPOSAL_COUNT)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_unbounded_query_returns_all_rows(self):
        """Documents the vulnerable behaviour: all 250 proposals are returned."""
        conn = sqlite3.connect(self._tmp.name)
        rows = conn.execute(_SELECT_UNBOUNDED).fetchall()
        conn.close()
        total_bytes = sum(len(r[3]) for r in rows)
        self.assertEqual(len(rows), _PROPOSAL_COUNT,
                         "Unbounded query should return every proposal (vulnerability)")
        self.assertGreater(total_bytes, _DESCRIPTION_BYTES * (_PROPOSAL_COUNT - 1),
                           "Unbounded query loads all description data into memory")

    def test_bounded_query_caps_at_200(self):
        """Fixed behaviour: LIMIT 200 prevents loading more than 200 proposals."""
        conn = sqlite3.connect(self._tmp.name)
        rows = conn.execute(_SELECT_BOUNDED).fetchall()
        conn.close()
        self.assertLessEqual(len(rows), 200,
                             "Bounded query must return at most 200 proposals")
        self.assertEqual(len(rows), 200,
                         "With 250 proposals the cap should be exactly 200")


if __name__ == "__main__":
    unittest.main()
