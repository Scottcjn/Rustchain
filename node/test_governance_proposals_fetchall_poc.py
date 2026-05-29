# SPDX-License-Identifier: MIT
"""
PoC + regression: GET /governance/proposals must paginate results and return
description summaries rather than full description text.

Section A (standalone SQL) documents the original vulnerability:
  - unbounded fetchall() loads all rows with no LIMIT or OFFSET
  - LIMIT ? OFFSET ? caps each page and enables pagination

Section B (Flask integration) is the regression gate:
  - seeds 250 rows with large descriptions in the real app DB
  - calls GET /governance/proposals through app.test_client()
  - asserts: default page is capped at 50 rows
  - asserts: limit/offset params control which rows are returned
  - asserts: description_preview is truncated to 200 chars, not the full text
  - asserts: total count reflects the full table size

Section C (propose contract) tests description length enforcement at creation:
  - POST /governance/propose with description > 4000 chars must be rejected with 400
  - POST /governance/propose with description <= 4000 chars must succeed
"""

import gc
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
    LIMIT ? OFFSET ?
"""

_PROPOSAL_COUNT = 250
_DESCRIPTION_BYTES = 10_000   # 10 KB per proposal
_DESCRIPTION_PREVIEW_LEN = 200
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
_DESCRIPTION_MAX_LEN = 4_000


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
    node_dir = os.path.dirname(os.path.abspath(_NODE_PY))
    if node_dir not in sys.path:
        sys.path.insert(0, node_dir)
    spec = importlib.util.spec_from_file_location("rustchain_node", _NODE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED_NODE_MODULE = None


def _get_or_load_module(db_path: str):
    # Load once per process; re-importing registers Prometheus counters twice
    # and raises ValueError: Duplicated timeseries in CollectorRegistry.
    global _SHARED_NODE_MODULE
    if _SHARED_NODE_MODULE is None:
        _SHARED_NODE_MODULE = _load_node_module(db_path)
    return _SHARED_NODE_MODULE


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

    def test_bounded_query_caps_at_limit_with_offset(self):
        """Fixed behaviour: LIMIT/OFFSET pages through results without loading all rows."""
        conn = sqlite3.connect(self._tmp.name)
        page1 = conn.execute(_SELECT_BOUNDED, (_DEFAULT_LIMIT, 0)).fetchall()
        page2 = conn.execute(_SELECT_BOUNDED, (_DEFAULT_LIMIT, _DEFAULT_LIMIT)).fetchall()
        conn.close()

        self.assertEqual(len(page1), _DEFAULT_LIMIT,
                         "First page must return exactly the default limit")
        self.assertEqual(len(page2), _DEFAULT_LIMIT,
                         "Second page must return exactly the default limit")
        ids_page1 = {r[0] for r in page1}
        ids_page2 = {r[0] for r in page2}
        self.assertEqual(len(ids_page1 & ids_page2), 0,
                         "Pages must not overlap")


# ---------------------------------------------------------------------------
# Section B: Flask route integration (regression gate)
# ---------------------------------------------------------------------------

class TestGovernanceProposalsRouteLimit(unittest.TestCase):
    """
    Calls GET /governance/proposals through the real Flask app.test_client().

    These tests fail if pagination or description truncation is removed from
    the governance_proposals() handler.
    """

    _module = None  # loaded once per process to avoid double-import

    @classmethod
    def setUpClass(cls):
        cls._db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._db_tmp.close()
        _make_db(cls._db_tmp.name, _PROPOSAL_COUNT)
        if cls._module is None:
            TestGovernanceProposalsRouteLimit._module = _get_or_load_module(cls._db_tmp.name)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        gc.collect()
        try:
            os.unlink(cls._db_tmp.name)
        except PermissionError:
            pass

    def _get(self, path):
        client = self._module.app.test_client()
        return client.get(path)

    def test_default_page_returns_fifty_proposals(self):
        """GET /governance/proposals with no params must return the default 50 rows."""
        response = self._get("/governance/proposals")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("limit"), _DEFAULT_LIMIT)
        self.assertEqual(data.get("offset"), 0)
        self.assertEqual(len(data.get("proposals", [])), _DEFAULT_LIMIT)

    def test_total_reflects_full_table_size(self):
        """Response must include total equal to the full row count."""
        response = self._get("/governance/proposals")
        data = response.get_json()
        self.assertEqual(data.get("total"), _PROPOSAL_COUNT,
                         "total must reflect the full table, not just the page")

    def test_limit_param_controls_page_size(self):
        """?limit=10 must return exactly 10 proposals."""
        response = self._get("/governance/proposals?limit=10")
        data = response.get_json()
        self.assertEqual(data.get("limit"), 10)
        self.assertEqual(len(data.get("proposals", [])), 10)

    def test_limit_is_capped_at_max(self):
        """?limit=999 must be clamped to the max of 200."""
        response = self._get(f"/governance/proposals?limit=999")
        data = response.get_json()
        self.assertLessEqual(data.get("limit"), _MAX_LIMIT,
                             "limit must be clamped to MAX_LIMIT")
        self.assertLessEqual(len(data.get("proposals", [])), _MAX_LIMIT)

    def test_offset_param_pages_to_next_page(self):
        """?offset=50 must return a non-overlapping page."""
        r1 = self._get(f"/governance/proposals?limit={_DEFAULT_LIMIT}&offset=0").get_json()
        r2 = self._get(f"/governance/proposals?limit={_DEFAULT_LIMIT}&offset={_DEFAULT_LIMIT}").get_json()

        ids1 = {p["id"] for p in r1["proposals"]}
        ids2 = {p["id"] for p in r2["proposals"]}
        self.assertEqual(len(ids1 & ids2), 0, "Pages must not overlap")
        self.assertEqual(len(ids2), _DEFAULT_LIMIT, "Second page must have the same size")

    def test_description_is_truncated_to_preview(self):
        """List response must return description_preview capped at 200 chars, not full text."""
        response = self._get("/governance/proposals?limit=1")
        data = response.get_json()
        proposal = data["proposals"][0]

        self.assertNotIn("description", proposal,
                         "Full description must not appear in list response")
        self.assertIn("description_preview", proposal,
                      "description_preview must be present in list response")
        self.assertLessEqual(len(proposal["description_preview"]), _DESCRIPTION_PREVIEW_LEN,
                             "description_preview must be at most 200 chars")
        self.assertLess(len(proposal["description_preview"]), _DESCRIPTION_BYTES,
                        "description_preview must be shorter than the full description")

    def test_count_matches_proposals_list_length(self):
        """count in the envelope must equal the actual proposals list length."""
        response = self._get("/governance/proposals")
        data = response.get_json()
        self.assertEqual(data.get("count"), len(data.get("proposals", [])),
                         "count field must match the actual proposals list length")


# ---------------------------------------------------------------------------
# Section C: description length enforcement at creation (regression gate)
# ---------------------------------------------------------------------------

class TestGovernanceProposeDescriptionCap(unittest.TestCase):
    """
    Verifies that POST /governance/propose rejects descriptions that exceed
    GOVERNANCE_DESCRIPTION_MAX_LEN (4000 chars) with HTTP 400.

    These tests fail if the creation-time guard is removed from
    governance_propose().
    """

    _module = None

    @classmethod
    def setUpClass(cls):
        cls._db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._db_tmp.close()
        if cls._module is None:
            TestGovernanceProposeDescriptionCap._module = _get_or_load_module(cls._db_tmp.name)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        gc.collect()
        try:
            os.unlink(cls._db_tmp.name)
        except PermissionError:
            pass

    def _post_propose(self, description: str):
        client = self._module.app.test_client()
        return client.post(
            "/governance/propose",
            json={
                "wallet": "RTC" + "a" * 40,
                "title": "Test proposal",
                "description": description,
                "signature": "00" * 64,
            },
            content_type="application/json",
        )

    def test_description_over_limit_is_rejected(self):
        """POST /governance/propose with description > 4000 chars must return 400."""
        response = self._post_propose("x" * (_DESCRIPTION_MAX_LEN + 1))
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("ok"))
        self.assertEqual(data.get("error"), "description_too_long")
        self.assertEqual(data.get("max_len"), _DESCRIPTION_MAX_LEN)

    def test_description_at_limit_is_accepted_or_blocked_by_balance(self):
        """POST /governance/propose with description == 4000 chars must not fail on length."""
        response = self._post_propose("x" * _DESCRIPTION_MAX_LEN)
        data = response.get_json()
        self.assertNotEqual(data.get("error"), "description_too_long",
                            "Exactly-at-limit description must not be rejected for length")


if __name__ == "__main__":
    unittest.main()
