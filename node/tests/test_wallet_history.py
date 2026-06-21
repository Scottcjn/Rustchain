"""
Tests for GET /wallet/history endpoint (Issues #908, #997).

These tests assert the **unified live contract** that the merged implementation
actually serves, instead of the older flat-array transaction shape that the live
node no longer returns (see #7513).

The endpoint returns an envelope::

    {
        "ok": true,
        "miner_id": "<id>",
        "transactions": [ <unified tx>, ... ],   # newest-first by timestamp
        "total": <int>
    }

and merges three on-disk sources into one time-sorted list:

* ``ledger``        — settled transfers / generic ledger movements
* ``epoch_rewards`` — mining payouts (joined to ``epoch_state``)
* ``pending_ledger``— in-flight (non-confirmed) transfers

Rather than mocking ``sqlite3`` (which is fragile now that the route issues one
query per source table), these tests seed a real temporary SQLite database with
the exact columns the route reads, then exercise the live route — a small
"live-contract smoke test" so the route, docs and tests cannot drift apart again.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _init_history_schema(db_path):
    """(Re)create the minimal set of tables the /wallet/history route reads.

    The column lists mirror the live ``CREATE TABLE`` statements in the node so
    the seeded rows flow through the production SQL untouched.
    """
    con = sqlite3.connect(db_path)
    try:
        con.executescript(
            """
            DROP TABLE IF EXISTS ledger;
            DROP TABLE IF EXISTS epoch_rewards;
            DROP TABLE IF EXISTS epoch_state;
            DROP TABLE IF EXISTS pending_ledger;

            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                miner_id TEXT NOT NULL,
                delta_i64 INTEGER NOT NULL,
                reason TEXT
            );

            CREATE TABLE epoch_rewards (
                epoch INTEGER,
                miner_id TEXT,
                share_i64 INTEGER
            );

            CREATE TABLE epoch_state (
                epoch INTEGER PRIMARY KEY,
                accepted_blocks INTEGER DEFAULT 0
            );

            CREATE TABLE pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                from_miner TEXT NOT NULL,
                to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                confirms_at INTEGER NOT NULL,
                tx_hash TEXT,
                voided_by TEXT,
                voided_reason TEXT,
                confirmed_at INTEGER
            );
            """
        )
        con.commit()
    finally:
        con.close()


class TestWalletHistoryEndpoint(unittest.TestCase):
    """Comprehensive tests for the unified /wallet/history contract."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._db_path = os.path.join(cls._tmp.name, "test.db")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db_path
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_wallet_history_test", MODULE_PATH
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        # Route reads module-level DB_PATH captured at import; pin it to our temp DB.
        cls.mod.DB_PATH = cls._db_path
        cls.client = cls.mod.app.test_client()
        cls.UNIT = cls.mod.UNIT

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        cls._tmp.cleanup()

    def setUp(self):
        # Fresh, empty tables for every test → full isolation.
        _init_history_schema(self._db_path)

    # ---- seed helpers ----------------------------------------------------

    def _con(self):
        return sqlite3.connect(self._db_path)

    def _add_ledger(self, ts, miner_id, delta_i64, reason, epoch=10):
        con = self._con()
        con.execute(
            "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
            (ts, epoch, miner_id, delta_i64, reason),
        )
        con.commit()
        con.close()

    def _add_reward(self, epoch, miner_id, share_i64, accepted_blocks=None):
        con = self._con()
        con.execute(
            "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?,?,?)",
            (epoch, miner_id, share_i64),
        )
        if accepted_blocks is not None:
            con.execute(
                "INSERT OR REPLACE INTO epoch_state (epoch, accepted_blocks) VALUES (?,?)",
                (epoch, accepted_blocks),
            )
        con.commit()
        con.close()

    def _add_pending(self, ts, from_m, to_m, amount_i64, reason, status,
                     tx_hash=None, created_at=None, epoch=10):
        con = self._con()
        con.execute(
            """INSERT INTO pending_ledger
               (ts, epoch, from_miner, to_miner, amount_i64, reason, status,
                created_at, confirms_at, tx_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ts, epoch, from_m, to_m, amount_i64, reason, status,
             created_at if created_at is not None else ts, ts + 86400, tx_hash),
        )
        con.commit()
        con.close()

    def _get(self, query):
        resp = self.client.get(query)
        return resp, resp.get_json()

    # ==================== Envelope shape ====================

    def test_response_is_unified_envelope(self):
        """Response is the {ok, miner_id, transactions, total} envelope, not a flat array."""
        self._add_ledger(1700000000, "alice", 5_000_000, "transfer_out:bob:tx_abc")
        resp, body = self._get("/wallet/history?miner_id=alice")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(body, dict)
        self.assertTrue(body["ok"])
        self.assertEqual(body["miner_id"], "alice")
        self.assertIsInstance(body["transactions"], list)
        self.assertEqual(body["total"], 1)

    # ==================== Per-type transaction formatting ====================

    def test_ledger_transfer_out(self):
        self._add_ledger(1700000000, "alice", 5_000_000, "transfer_out:bob:tx_abc", epoch=12)
        _, body = self._get("/wallet/history?miner_id=alice")
        tx = body["transactions"][0]
        self.assertEqual(tx["type"], "transfer_out")
        self.assertEqual(tx["amount"], 5_000_000 / self.UNIT)
        self.assertEqual(tx["epoch"], 12)
        self.assertEqual(tx["timestamp"], 1700000000)
        self.assertEqual(tx["tx_hash"], "tx_abc")
        self.assertEqual(tx["to"], "bob")
        self.assertNotIn("from", tx)

    def test_ledger_transfer_in(self):
        self._add_ledger(1700001000, "alice", 2_500_000, "transfer_in:carol:tx_def")
        _, body = self._get("/wallet/history?miner_id=alice")
        tx = body["transactions"][0]
        self.assertEqual(tx["type"], "transfer_in")
        self.assertEqual(tx["amount"], 2.5)
        self.assertEqual(tx["tx_hash"], "tx_def")
        self.assertEqual(tx["from"], "carol")
        self.assertNotIn("to", tx)

    def test_ledger_generic_entry(self):
        """A ledger row whose reason is not a transfer maps to the generic 'ledger' type."""
        self._add_ledger(1700002000, "alice", 1_000_000, "epoch_reward_settlement")
        _, body = self._get("/wallet/history?miner_id=alice")
        tx = body["transactions"][0]
        self.assertEqual(tx["type"], "ledger")
        self.assertIsNone(tx["tx_hash"])
        self.assertEqual(tx["reason"], "epoch_reward_settlement")
        self.assertNotIn("from", tx)
        self.assertNotIn("to", tx)

    def test_reward_entry(self):
        self._add_reward(epoch=7, miner_id="alice", share_i64=3_000_000, accepted_blocks=4)
        _, body = self._get("/wallet/history?miner_id=alice")
        tx = body["transactions"][0]
        self.assertEqual(tx["type"], "reward")
        self.assertEqual(tx["amount"], 3.0)
        self.assertEqual(tx["epoch"], 7)
        self.assertEqual(tx["timestamp"], 0)
        self.assertIsNone(tx["tx_hash"])

    def test_pending_transfer_carries_status(self):
        """Pending (non-confirmed) rows surface a status field; ledger rows do not."""
        self._add_pending(1700003000, "alice", "bob", 750_000, "signed_transfer:coffee",
                          "pending", tx_hash="tx_pending")
        _, body = self._get("/wallet/history?miner_id=alice")
        tx = body["transactions"][0]
        self.assertEqual(tx["type"], "transfer_out")
        self.assertEqual(tx["status"], "pending")
        self.assertEqual(tx["amount"], 0.75)
        self.assertIsNone(tx["epoch"])  # pending entries are not yet epoch-bound
        self.assertEqual(tx["tx_hash"], "tx_pending")
        self.assertEqual(tx["to"], "bob")

    def test_pending_confirmed_is_excluded(self):
        """A pending row already marked confirmed is captured by ledger, not duplicated here."""
        self._add_pending(1700004000, "alice", "bob", 100_000, None, "confirmed",
                          tx_hash="tx_conf")
        _, body = self._get("/wallet/history?miner_id=alice")
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["transactions"], [])

    def test_unified_fields_present_per_type(self):
        """Every transaction type exposes the documented unified field set."""
        common = {"type", "amount", "epoch", "timestamp", "tx_hash"}
        self._add_ledger(1700000000, "alice", 5_000_000, "transfer_out:bob:tx1")
        self._add_reward(epoch=3, miner_id="alice", share_i64=1_000_000)
        self._add_pending(1700005000, "carol", "alice", 250_000, None, "pending",
                          tx_hash="tx2")
        _, body = self._get("/wallet/history?miner_id=alice")
        self.assertEqual(body["total"], 3)
        for tx in body["transactions"]:
            self.assertTrue(common.issubset(tx.keys()),
                            f"missing unified fields in {tx}")

    # ==================== Merging & ordering ====================

    def test_sources_merge_and_sort_newest_first(self):
        self._add_ledger(1700000000, "alice", 1_000_000, "transfer_out:bob:old")
        self._add_ledger(1700009000, "alice", 1_000_000, "transfer_in:carol:new")
        self._add_pending(1700005000, "alice", "dave", 1_000_000, None, "pending",
                          tx_hash="mid")
        _, body = self._get("/wallet/history?miner_id=alice")
        ts = [t["timestamp"] for t in body["transactions"]]
        self.assertEqual(ts, sorted(ts, reverse=True))
        self.assertEqual(body["transactions"][0]["tx_hash"], "new")
        self.assertEqual(body["total"], 3)

    # ==================== Empty history ====================

    def test_empty_history_returns_envelope_with_empty_list(self):
        resp, body = self._get("/wallet/history?miner_id=newbie")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["transactions"], [])
        self.assertEqual(body["total"], 0)

    # ==================== Identifier validation (unchanged contract) ====================

    def test_missing_identifier(self):
        resp = self.client.get("/wallet/history")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "miner_id or address required"})

    def test_empty_miner_id(self):
        resp = self.client.get("/wallet/history?miner_id=")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "miner_id or address required"})

    def test_conflicting_identifiers(self):
        resp = self.client.get("/wallet/history?miner_id=alice&address=bob")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "miner_id and address must match when both are provided"},
        )

    def test_address_alias_resolves_to_miner_id(self):
        self._add_ledger(1700000000, "alice", 1_000_000, "transfer_out:bob:tx1")
        resp, body = self._get("/wallet/history?address=alice")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["miner_id"], "alice")
        self.assertEqual(body["total"], 1)

    def test_matching_identifiers_accepted(self):
        resp = self.client.get("/wallet/history?miner_id=alice&address=alice")
        self.assertEqual(resp.status_code, 200)

    # ==================== Pagination ====================

    def _seed_n_ledger(self, n, miner_id="alice"):
        con = self._con()
        con.executemany(
            "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
            [(1700000000 + i, 10, miner_id, 1_000_000, f"transfer_out:bob:tx{i}") for i in range(n)],
        )
        con.commit()
        con.close()

    def test_default_limit_is_50(self):
        # Note: the route fetches at most ``offset+limit`` rows per source table,
        # so ``total`` reflects the capped fetch (50) rather than the 60 seeded.
        self._seed_n_ledger(60)
        _, body = self._get("/wallet/history?miner_id=alice")
        self.assertEqual(len(body["transactions"]), 50)
        self.assertEqual(body["total"], 50)

    def test_custom_limit_respected(self):
        self._seed_n_ledger(10)
        _, body = self._get("/wallet/history?miner_id=alice&limit=3")
        self.assertEqual(len(body["transactions"]), 3)

    def test_limit_clamped_to_minimum(self):
        self._seed_n_ledger(5)
        _, body = self._get("/wallet/history?miner_id=alice&limit=0")
        self.assertEqual(len(body["transactions"]), 1)

    def test_limit_negative_clamped(self):
        self._seed_n_ledger(5)
        _, body = self._get("/wallet/history?miner_id=alice&limit=-100")
        self.assertEqual(len(body["transactions"]), 1)

    def test_limit_clamped_to_maximum(self):
        self._seed_n_ledger(201)
        _, body = self._get("/wallet/history?miner_id=alice&limit=1000")
        self.assertEqual(len(body["transactions"]), 200)

    def test_offset_paginates(self):
        self._seed_n_ledger(5)
        _, body_all = self._get("/wallet/history?miner_id=alice&limit=5")
        _, body_off = self._get("/wallet/history?miner_id=alice&limit=2&offset=2")
        self.assertEqual(
            [t["tx_hash"] for t in body_off["transactions"]],
            [t["tx_hash"] for t in body_all["transactions"][2:4]],
        )

    def test_invalid_limit_string(self):
        resp = self.client.get("/wallet/history?miner_id=alice&limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_invalid_limit_float(self):
        resp = self.client.get("/wallet/history?miner_id=alice&limit=10.5")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_invalid_offset_string(self):
        resp = self.client.get("/wallet/history?miner_id=alice&offset=xyz")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "offset must be an integer"})


if __name__ == "__main__":
    unittest.main()
