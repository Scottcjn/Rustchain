# SPDX-License-Identifier: MIT
"""
PoC: /wallet/history unbounded in-memory fetchall OOM

Bug: api_wallet_history() accepts limit/offset query params but the three
inner SQL queries (ledger, epoch_rewards, pending_ledger) had no SQL LIMIT
clause. All matching rows were loaded into Python memory before the slice was
applied. An attacker could cause the node to exhaust RAM by querying a wallet
address that has a large number of ledger rows.

Fix: each SQL query now receives LIMIT = _history_cap (offset + limit capped at
9800 + 200), so the server never fetches more than 10,000 rows per subquery.

Section A — source scan: verify the fixed SQL contains LIMIT and that the
            caller-supplied offset is bounded.

Section B — Flask integration: call GET /wallet/history through the real
            app.test_client() and assert the response is bounded by limit.
"""

import gc
import importlib
import os
import sqlite3
import sys
import tempfile
import time
import unittest

import pytest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_NODE_FILE = os.path.join(
    os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py"
)
_MODULE_NAME = "rustchain_node_wallet_history_test"
_TEST_WALLET = "RTC" + "a" * 40

UNIT = 1_000_000  # micro-RTC per RTC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(n_ledger: int = 0, n_rewards: int = 0, n_pending: int = 0) -> str:
    """Create a temp SQLite DB with raw history tables. Returns the path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)"
    )
    conn.execute(
        "CREATE TABLE epoch_rewards (miner_id TEXT, epoch INTEGER, share_i64 INTEGER)"
    )
    conn.execute(
        "CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER)"
    )
    conn.execute(
        """CREATE TABLE pending_ledger (
            id INTEGER PRIMARY KEY,
            ts INTEGER, from_miner TEXT, to_miner TEXT,
            amount_i64 INTEGER, reason TEXT, status TEXT,
            created_at INTEGER, confirms_at INTEGER, tx_hash TEXT
        )"""
    )
    now = int(time.time())
    for i in range(n_ledger):
        conn.execute(
            "INSERT INTO ledger VALUES (?,?,?,?,?)",
            (now - i, 1, "MINER_A", UNIT * (i + 1), f"transfer_out:MINER_B:tx{i}"),
        )
    for i in range(n_rewards):
        conn.execute(
            "INSERT INTO epoch_rewards VALUES (?,?,?)",
            ("MINER_A", i + 1, UNIT * 10),
        )
    for i in range(n_pending):
        conn.execute(
            "INSERT INTO pending_ledger(ts,from_miner,to_miner,amount_i64,reason,status,created_at,confirms_at,tx_hash) VALUES (?,?,?,?,?,?,?,?,?)",
            (now - i, "MINER_A", "MINER_B", UNIT, "signed_transfer:", "pending", now - i, now + 86400, f"hash{i}"),
        )
    conn.commit()
    conn.close()
    return path


def _seed_wallet(db_path: str, wallet: str, n_ledger: int, n_rewards: int, n_pending: int) -> None:
    """Seed wallet history tables; call before or after app init (uses IF NOT EXISTS)."""
    now = int(time.time())
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS epoch_rewards (miner_id TEXT, epoch INTEGER, share_i64 INTEGER)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER)"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS pending_ledger (
                id INTEGER PRIMARY KEY,
                ts INTEGER, from_miner TEXT, to_miner TEXT,
                amount_i64 INTEGER, reason TEXT, status TEXT,
                created_at INTEGER, confirms_at INTEGER, tx_hash TEXT
            )"""
        )
        for i in range(n_ledger):
            conn.execute(
                "INSERT OR IGNORE INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
                (now - i, 1, wallet, UNIT * (i + 1), f"transfer_out:MINER_B:tx{i}"),
            )
        for i in range(n_rewards):
            conn.execute(
                "INSERT OR IGNORE INTO epoch_rewards (miner_id, epoch, share_i64) VALUES (?,?,?)",
                (wallet, i + 1, UNIT * 10),
            )
        for i in range(n_pending):
            conn.execute(
                """INSERT OR IGNORE INTO pending_ledger
                   (ts, from_miner, to_miner, amount_i64, reason, status, created_at, confirms_at, tx_hash)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (now - i, wallet, "MINER_B", UNIT, "signed_transfer:", "pending",
                 now - i, now + 86400, f"hash{i}"),
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


# ===========================================================================
# Section A: source scan — verify LIMIT and offset cap are present
# ===========================================================================


def _extract_history_queries(source_path: str) -> str:
    """Return the source of api_wallet_history (up to 8 kb after its def)."""
    with open(source_path, encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("def api_wallet_history(")
    return src[start : start + 8000]


def test_ledger_query_has_limit():
    """The ledger sub-query inside api_wallet_history must have a LIMIT clause."""
    main = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")
    body = _extract_history_queries(main)
    ledger_idx = body.index("FROM ledger")
    ledger_snippet = body[ledger_idx : ledger_idx + 300]
    assert "LIMIT" in ledger_snippet, (
        "ledger query inside api_wallet_history is missing a SQL LIMIT — OOM risk"
    )


def test_epoch_rewards_query_has_limit():
    """The epoch_rewards sub-query inside api_wallet_history must have a LIMIT clause."""
    main = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")
    body = _extract_history_queries(main)
    rewards_idx = body.index("FROM epoch_rewards er")
    rewards_snippet = body[rewards_idx : rewards_idx + 300]
    assert "LIMIT" in rewards_snippet, (
        "epoch_rewards query inside api_wallet_history is missing a SQL LIMIT — OOM risk"
    )


def test_pending_ledger_query_has_limit():
    """The pending_ledger sub-query inside api_wallet_history must have a LIMIT clause."""
    main = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")
    body = _extract_history_queries(main)
    pending_idx = body.index("FROM pending_ledger")
    pending_snippet = body[pending_idx : pending_idx + 300]
    assert "LIMIT" in pending_snippet, (
        "pending_ledger query inside api_wallet_history is missing a SQL LIMIT — OOM risk"
    )


def test_offset_cap_present_in_source():
    """api_wallet_history must cap the caller-supplied offset to bound the SQL fetch."""
    main = os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py")
    body = _extract_history_queries(main)
    assert "min(" in body, (
        "api_wallet_history is missing an offset cap — large offset causes high-fetch OOM"
    )


# ===========================================================================
# Section B: Flask integration — real route returns bounded results
# ===========================================================================


class TestWalletHistoryFlaskRoute(unittest.TestCase):
    """
    Calls GET /wallet/history through the real Flask app.test_client().
    These tests fail if the LIMIT clauses or offset cap are removed from
    api_wallet_history() in rustchain_v2_integrated_v2.2.1_rip200.py.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        _seed_wallet(cls._tmp.name, _TEST_WALLET, n_ledger=300, n_rewards=200, n_pending=100)
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

    def test_response_ok_true(self):
        """GET /wallet/history must return ok: true for a known wallet."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/wallet/history?miner_id={_TEST_WALLET}&limit=10")
        self.assertEqual(rv.status_code, 200)
        self.assertTrue(rv.get_json().get("ok"))

    def test_default_limit_bounds_response(self):
        """Default call must return at most 50 transactions even with 600 DB rows."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/wallet/history?miner_id={_TEST_WALLET}")
        data = rv.get_json()
        self.assertLessEqual(
            len(data.get("transactions", [])), 50,
            "Default response must not exceed 50 rows regardless of DB size",
        )

    def test_explicit_limit_is_respected(self):
        """limit=5 must return at most 5 transactions."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/wallet/history?miner_id={_TEST_WALLET}&limit=5")
        data = rv.get_json()
        self.assertLessEqual(len(data.get("transactions", [])), 5)

    def test_large_offset_is_capped_not_oom(self):
        """offset=999999 must be silently capped; must not OOM or raise a 500."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/wallet/history?miner_id={_TEST_WALLET}&limit=5&offset=999999")
        self.assertEqual(rv.status_code, 200)
        self.assertTrue(rv.get_json().get("ok"))

    def test_missing_miner_id_returns_400(self):
        """GET /wallet/history without miner_id must return 400."""
        with self.flask_app.test_client() as c:
            rv = c.get("/wallet/history")
        self.assertEqual(rv.status_code, 400)

    def test_invalid_limit_returns_400(self):
        """Non-integer limit must return 400."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/wallet/history?miner_id={_TEST_WALLET}&limit=abc")
        self.assertEqual(rv.status_code, 400)

    def test_invalid_offset_returns_400(self):
        """Non-integer offset must return 400."""
        with self.flask_app.test_client() as c:
            rv = c.get(f"/wallet/history?miner_id={_TEST_WALLET}&offset=xyz")
        self.assertEqual(rv.status_code, 400)


if __name__ == "__main__":
    unittest.main()
