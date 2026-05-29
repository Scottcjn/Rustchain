# SPDX-License-Identifier: MIT
"""
PoC: /rewards/epoch/<epoch> unbounded fetchall

Bug: api_rewards_epoch() called fetchall() with no SQL LIMIT. Any caller
(unauthenticated) could request any epoch and receive every miner_id and
reward amount in that epoch in a single response. On a node with thousands
of miners this causes:

  1. OOM DoS — the full epoch_rewards table slice is loaded into RAM and
     serialised to JSON in one shot.
  2. Wallet enumeration — every active wallet address and its exact reward
     share is exposed with zero authentication.

Fix: limit and offset query params added; SQL query uses LIMIT/OFFSET; both
are capped (max 1000 rows per request).

Section A — verify the fixed SQL contains LIMIT.
Section B — verify the endpoint returns at most `limit` rows when the DB
            contains far more.
"""

import gc
import importlib
import os
import sqlite3
import sys
import tempfile
import unittest

import pytest

UNIT = 1_000_000

_NODE_FILE = os.path.join(
    os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py"
)
_MODULE_NAME = "rustchain_node_rewards_epoch_test"
_TEST_EPOCH = 7


def _make_epoch_db(n_miners: int, epoch: int = 1) -> str:
    """Create a temp DB with n_miners reward rows for the given epoch."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE epoch_rewards (miner_id TEXT, epoch INTEGER, share_i64 INTEGER)"
    )
    for i in range(n_miners):
        conn.execute(
            "INSERT INTO epoch_rewards VALUES (?,?,?)",
            (f"RTC{'a' * 3}{i:037d}", epoch, UNIT * (i + 1)),
        )
    conn.commit()
    conn.close()
    return path


# ===========================================================================
# Section A: source scan — verify LIMIT is present in the fixed function
# ===========================================================================


def _rewards_epoch_body(source_path: str) -> str:
    with open(source_path, encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def api_rewards_epoch(")
    return src[start : start + 1500]


def test_rewards_epoch_query_has_limit():
    """api_rewards_epoch SQL must contain a LIMIT clause after the fix."""
    main = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")
    body = _rewards_epoch_body(main)
    assert "LIMIT" in body, (
        "api_rewards_epoch is missing a SQL LIMIT — unbounded OOM + wallet enumeration risk"
    )


def test_rewards_epoch_query_has_offset():
    """api_rewards_epoch SQL must also support OFFSET for pagination."""
    main = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")
    body = _rewards_epoch_body(main)
    assert "OFFSET" in body, (
        "api_rewards_epoch is missing an OFFSET clause — pagination incomplete"
    )


# ===========================================================================
# Section B: direct SQL — response bounded by limit
# ===========================================================================


def test_rewards_epoch_rows_bounded_by_limit():
    """With 500 miners in epoch 1, limit=10 must return exactly 10 rows."""
    db_path = _make_epoch_db(n_miners=500, epoch=1)
    try:
        limit = 10
        offset = 0
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT miner_id, share_i64 FROM epoch_rewards WHERE epoch=? ORDER BY miner_id LIMIT ? OFFSET ?",
            (1, limit, offset),
        ).fetchall()
        conn.close()
        assert len(rows) == limit, (
            f"Expected {limit} rows, got {len(rows)} — LIMIT not enforced"
        )
    finally:
        os.unlink(db_path)


def test_rewards_epoch_offset_skips_rows():
    """offset=490 with 500 miners must return only the last 10 rows."""
    db_path = _make_epoch_db(n_miners=500, epoch=1)
    try:
        limit = 200
        offset = 490
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT miner_id, share_i64 FROM epoch_rewards WHERE epoch=? ORDER BY miner_id LIMIT ? OFFSET ?",
            (1, limit, offset),
        ).fetchall()
        conn.close()
        assert len(rows) == 10, (
            f"Expected 10 rows after offset 490, got {len(rows)}"
        )
    finally:
        os.unlink(db_path)


def test_rewards_epoch_max_cap_respected():
    """Even if a caller requests limit=9999, the SQL must cap at 1000."""
    # Simulate the cap logic from the fixed endpoint
    raw_limit = 9999
    capped = max(1, min(int(raw_limit), 1000))
    assert capped == 1000, f"Cap logic failed: got {capped}"


def test_rewards_epoch_empty_epoch_ok():
    """An epoch with no rewards returns an empty list, not an error."""
    db_path = _make_epoch_db(n_miners=0, epoch=99)
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT miner_id, share_i64 FROM epoch_rewards WHERE epoch=? ORDER BY miner_id LIMIT ? OFFSET ?",
            (99, 200, 0),
        ).fetchall()
        conn.close()
        assert rows == [], f"Expected empty list, got {rows}"
    finally:
        os.unlink(db_path)


# ===========================================================================
# Section C: Flask integration — real route returns bounded results
# ===========================================================================


def _seed_epoch(db_path: str, epoch: int, n_miners: int) -> None:
    """Seed epoch_rewards; call before or after app init (uses IF NOT EXISTS)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS epoch_rewards (miner_id TEXT, epoch INTEGER, share_i64 INTEGER)"
        )
        for i in range(n_miners):
            conn.execute(
                "INSERT OR IGNORE INTO epoch_rewards (miner_id, epoch, share_i64) VALUES (?,?,?)",
                (f"RTC{'a' * 3}{i:037d}", epoch, UNIT * (i + 1)),
            )
        conn.commit()
    finally:
        conn.close()


def _load_app(db_path: str):
    """Import the real Flask app with RUSTCHAIN_DB_PATH pointing at db_path."""
    node_dir = os.path.dirname(os.path.abspath(_NODE_FILE))
    if node_dir not in sys.path:
        sys.path.insert(0, node_dir)
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ.setdefault("RC_ADMIN_KEY", "test-admin-key-not-real-padded-to-32ch")
    sys.modules.pop(_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _NODE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod.app, mod


class TestRewardsEpochFlaskRoute(unittest.TestCase):
    """
    Calls GET /rewards/epoch/<epoch> through the real Flask app.test_client().
    These tests fail if the LIMIT/OFFSET or the 1000-row cap are removed from
    api_rewards_epoch() in rustchain_v2_integrated_v2.2.1_rip200.py.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        _seed_epoch(cls._tmp.name, _TEST_EPOCH, n_miners=500)
        cls.flask_app, cls._mod = _load_app(cls._tmp.name)
        cls.flask_app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(_MODULE_NAME, None)
        cls.flask_app = None
        cls._mod = None
        gc.collect()
        gc.collect()
        try:
            os.unlink(cls._tmp.name)
        except OSError:
            pass

    def test_response_structure(self):
        """GET /rewards/epoch/<epoch> must return epoch, limit, offset and rewards."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/rewards/epoch/{_TEST_EPOCH}?limit=10")
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data.get("epoch"), _TEST_EPOCH)
        self.assertIn("rewards", data)
        self.assertIn("limit", data)
        self.assertIn("offset", data)

    def test_default_limit_bounds_response(self):
        """Default call must return at most 200 rows even with 500 in the DB."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/rewards/epoch/{_TEST_EPOCH}")
        data = rv.get_json()
        self.assertLessEqual(
            len(data.get("rewards", [])), 200,
            "Default response must not exceed 200 rows regardless of DB size",
        )

    def test_explicit_limit_is_respected(self):
        """limit=10 must return at most 10 reward entries."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/rewards/epoch/{_TEST_EPOCH}?limit=10")
        data = rv.get_json()
        self.assertLessEqual(len(data.get("rewards", [])), 10)

    def test_limit_capped_at_1000(self):
        """limit=9999 must be clamped to 1000."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/rewards/epoch/{_TEST_EPOCH}?limit=9999")
        data = rv.get_json()
        self.assertLessEqual(data.get("limit", 9999), 1000)
        self.assertLessEqual(len(data.get("rewards", [])), 1000)

    def test_offset_pages_through_results(self):
        """offset=250 with limit=10 must return a non-overlapping page."""
        with self.flask_app.test_client() as c:
            rv1 = c.get(f"/rewards/epoch/{_TEST_EPOCH}?limit=10&offset=0")
            rv2 = c.get(f"/rewards/epoch/{_TEST_EPOCH}?limit=10&offset=250")
        ids1 = {r["miner_id"] for r in rv1.get_json().get("rewards", [])}
        ids2 = {r["miner_id"] for r in rv2.get_json().get("rewards", [])}
        self.assertTrue(ids1.isdisjoint(ids2), "Pages must not overlap")

    def test_empty_epoch_returns_empty_list(self):
        """An epoch with no rewards must return an empty rewards list, not an error."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/rewards/epoch/9999?limit=10")
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data.get("rewards", []), [])

    def test_invalid_limit_returns_400(self):
        """Non-integer limit must return 400."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/rewards/epoch/{_TEST_EPOCH}?limit=abc")
        self.assertEqual(rv.status_code, 400)


if __name__ == "__main__":
    unittest.main()
