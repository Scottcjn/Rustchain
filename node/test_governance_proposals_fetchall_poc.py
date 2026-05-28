# SPDX-License-Identifier: MIT
"""
PoC + regression: GET /governance/proposals must return at most 200 proposals.

Section A (standalone SQL) documents the vulnerability in isolation:
  - unbounded fetchall() loads all rows when no LIMIT is present
  - LIMIT 200 caps the result set

Section B (Flask integration) is the regression gate:
  - seeds 250 rows in the real app DB
  - calls GET /governance/proposals through app.test_client()
  - asserts the actual handler returns at most 200 proposals
  - this test FAILS if LIMIT 200 is removed from the handler
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


_NODE_PY = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
            (f"RTC{'a' * 40}", f"Proposal {i}", "x" * _DESCRIPTION_BYTES, 0, "active")
            for i in range(n)
        ],
    )
    conn.commit()
    conn.close()


def _load_node_module(db_path: str):
    """
    Import the node module with RUSTCHAIN_DB_PATH and RC_ADMIN_KEY pointing at
    test fixtures so the import succeeds without a real node environment.
    """
    os.environ.setdefault("RC_ADMIN_KEY", "a" * 64)
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    spec = importlib.util.spec_from_file_location("rustchain_node", _NODE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Section A: standalone SQL tests (vulnerability documentation)
# ---------------------------------------------------------------------------

class TestGovernanceProposalsSQLBound(unittest.TestCase):

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


# ---------------------------------------------------------------------------
# Section B: Flask route integration (regression gate)
# ---------------------------------------------------------------------------

class TestGovernanceProposalsRouteLimit(unittest.TestCase):
    """
    Calls GET /governance/proposals through the real Flask app.test_client().

    This test will fail if LIMIT 200 is removed from the governance_proposals()
    handler in rustchain_v2_integrated_v2.2.1_rip200.py, which the standalone
    SQL tests in Section A would not catch.
    """

    _module = None  # loaded once per process to avoid double-import

    @classmethod
    def setUpClass(cls):
        cls._db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._db_tmp.close()
        _make_db(cls._db_tmp.name, _PROPOSAL_COUNT)
        if cls._module is None:
            TestGovernanceProposalsRouteLimit._module = _load_node_module(cls._db_tmp.name)

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls._db_tmp.name)

    def test_route_caps_response_at_200_proposals(self):
        """
        GET /governance/proposals must return at most 200 items even when the
        database contains more. Verifies the real handler applies LIMIT 200.
        """
        client = self._module.app.test_client()
        response = client.get("/governance/proposals")

        self.assertEqual(response.status_code, 200,
                         "Route should return HTTP 200")
        data = response.get_json()
        self.assertTrue(data.get("ok"), "Response envelope should have ok=True")

        proposals = data.get("proposals", [])
        self.assertLessEqual(
            len(proposals),
            200,
            f"Handler returned {len(proposals)} proposals; LIMIT 200 must be enforced",
        )
        self.assertEqual(
            len(proposals),
            200,
            f"With {_PROPOSAL_COUNT} rows in DB the response should be exactly 200",
        )
        self.assertEqual(
            data.get("count"),
            len(proposals),
            "count field in the envelope must match the actual proposals list length",
        )


if __name__ == "__main__":
    unittest.main()
