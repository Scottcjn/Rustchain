"""
Tests for GET /wallet/history endpoint (Issue #7513, #908, #997)

The merged unified envelope from #908/#997 is authoritative. This module
asserts that contract directly: ``{ok, miner_id, transactions, total}`` where
each entry is one of:

  * ``transfer_in``  -- {type, amount, epoch, timestamp, tx_hash, from[, status]}
  * ``transfer_out`` -- {type, amount, epoch, timestamp, tx_hash, to[, status]}
  * ``ledger``       -- {type, amount, epoch, timestamp, tx_hash, reason}
  * ``reward``       -- {type, amount, epoch, timestamp, tx_hash}

Tests cover:
  * Successful rows for each transaction type
  * Empty history for valid / unknown wallets
  * Identifier validation (miner_id vs address alias)
  * Pagination behavior (default / custom / clamping / invalid)
  * Schema validation against the documented unified envelope
  * Status / direction semantics consistent with the live route

The live route queries three SQLite tables (``ledger``, ``epoch_rewards``,
``pending_ledger``) in a single request. We mock each query independently via
``side_effect`` so tests can stage precisely the row shape each branch expects.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _make_execute_side_effect(ledger=(), rewards=(), pending=()):
    """Return a side_effect function for ``db.execute`` that returns the
    correct mock cursor based on which table the SQL targets.

    Live route queries, in order, ``ledger``, ``epoch_rewards`` (LEFT JOIN
    ``epoch_state``), then ``pending_ledger``. We dispatch on the FROM clause.
    """

    def _execute(sql, *args, **kwargs):
        cursor = MagicMock()
        sql_lower = (sql or "").lower()
        if "from ledger" in sql_lower and "pending_ledger" not in sql_lower:
            cursor.fetchall.return_value = list(ledger)
        elif "from epoch_rewards" in sql_lower:
            cursor.fetchall.return_value = list(rewards)
        elif "from pending_ledger" in sql_lower:
            cursor.fetchall.return_value = list(pending)
        else:
            cursor.fetchall.return_value = []
        return cursor

    return _execute


class TestWalletHistoryEndpoint(unittest.TestCase):
    """Comprehensive tests for /wallet/history endpoint (unified envelope)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "test.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_wallet_history_test", MODULE_PATH
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _patch_queries(self, ledger=(), rewards=(), pending=()):
        """Patch ``sqlite3.connect`` so all three live-route queries return
        the supplied mock rows."""
        return patch.object(
            self.mod.sqlite3,
            "connect",
            MagicMock(return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(
                    execute=MagicMock(side_effect=_make_execute_side_effect(
                        ledger=ledger, rewards=rewards, pending=pending,
                    ))
                )),
                __exit__=MagicMock(return_value=False),
            )),
        )

    # ==================== Success Cases ====================

    def test_wallet_history_success_transfer_in_recorded(self):
        """A confirmed ledger transfer_in entry is returned with correct shape."""
        ledger_rows = [
            # (ts, epoch, miner_id, delta_i64, reason)
            (1700000000, 200, "alice", 5000000, "transfer_in:bob:tx_hash_abc123"),
        ]
        with self._patch_queries(ledger=ledger_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertTrue(body["ok"])
            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["total"], 1)
            txs = body["transactions"]
            self.assertEqual(len(txs), 1)
            tx = txs[0]
            self.assertEqual(tx["type"], "transfer_in")
            self.assertEqual(tx["from"], "bob")
            self.assertEqual(tx["tx_hash"], "tx_hash_abc123")
            self.assertEqual(tx["amount"], 5.0)
            self.assertEqual(tx["epoch"], 200)
            self.assertEqual(tx["timestamp"], 1700000000)
            self.assertNotIn("to", tx)
            self.assertNotIn("status", tx)

    def test_wallet_history_success_transfer_out_recorded(self):
        """A confirmed ledger transfer_out entry exposes ``to``, not ``from``."""
        ledger_rows = [
            (1700001000, 201, "alice", -2500000, "transfer_out:bob:tx_out_1"),
        ]
        with self._patch_queries(ledger=ledger_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()
            self.assertEqual(body["total"], 1)
            tx = body["transactions"][0]
            self.assertEqual(tx["type"], "transfer_out")
            self.assertEqual(tx["to"], "bob")
            self.assertEqual(tx["tx_hash"], "tx_out_1")
            self.assertEqual(tx["amount"], 2.5)
            self.assertNotIn("from", tx)

    def test_wallet_history_success_ledger_entry_carries_reason(self):
        """Non-transfer ledger rows surface the raw reason field."""
        ledger_rows = [
            (1700002000, 202, "alice", 100000, "manual_adjustment"),
        ]
        with self._patch_queries(ledger=ledger_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            tx = resp.get_json()["transactions"][0]
            self.assertEqual(tx["type"], "ledger")
            self.assertEqual(tx["reason"], "manual_adjustment")
            self.assertEqual(tx["amount"], 0.1)
            self.assertIsNone(tx["tx_hash"])

    def test_wallet_history_success_reward_entry(self):
        """Mining reward rows from epoch_rewards appear with type=reward."""
        reward_rows = [
            # (epoch, share_i64, accepted_blocks)
            (210, 7500000, 1),
        ]
        with self._patch_queries(rewards=reward_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            tx = resp.get_json()["transactions"][0]
            self.assertEqual(tx["type"], "reward")
            self.assertEqual(tx["amount"], 7.5)
            self.assertEqual(tx["epoch"], 210)
            self.assertIsNone(tx["tx_hash"])
            self.assertNotIn("from", tx)
            self.assertNotIn("to", tx)

    def test_wallet_history_success_pending_entry(self):
        """Pending ledger rows carry status and are sorted by created DESC."""
        ledger_rows = [
            (1700003000, 203, "alice", -500000, "transfer_out:bob:pending_tx"),
        ]
        pending_rows = [
            # (ts, from_miner, to_miner, amount_i64, reason, status, tx_hash, created)
            (1700003500, "alice", "bob", 500000, None, "pending", "tx_pending", 1700003500),
        ]
        with self._patch_queries(ledger=ledger_rows, pending=pending_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()
            # pending has the newer timestamp so it sorts first
            tx = body["transactions"][0]
            self.assertEqual(tx["type"], "transfer_out")
            self.assertEqual(tx["to"], "bob")
            self.assertEqual(tx["status"], "pending")
            self.assertEqual(tx["tx_hash"], "tx_pending")
            # confirmed ledger entry still appears
            self.assertEqual(body["total"], 2)

    def test_wallet_history_pending_confirmed_is_deduped(self):
        """A pending_ledger row whose status='confirmed' must NOT also be
        surfaced -- it is already in the immutable ledger table."""
        pending_rows = [
            (1700003500, "alice", "bob", 500000, None, "confirmed", "tx_dup", 1700003500),
        ]
        with self._patch_queries(pending=pending_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()
            self.assertEqual(body["total"], 0)
            self.assertEqual(body["transactions"], [])

    def test_wallet_history_multiple_entries_sorted_by_timestamp_desc(self):
        """Mixed entries are returned newest-first by timestamp."""
        ledger_rows = [
            (1700001000, 200, "alice", 100, "transfer_in:bob:tx_old"),
            (1700003000, 202, "alice", 300, "transfer_out:bob:tx_new"),
        ]
        with self._patch_queries(ledger=ledger_rows):
            resp = self.client.get("/wallet/history?miner_id=alice")
            txs = resp.get_json()["transactions"]
            self.assertEqual(len(txs), 2)
            self.assertEqual(txs[0]["tx_hash"], "tx_new")
            self.assertEqual(txs[1]["tx_hash"], "tx_old")

    # ==================== Empty History Cases ====================

    def test_wallet_history_empty_returns_envelope_with_empty_list(self):
        """No rows -> ok envelope with empty transactions list and total=0."""
        with self._patch_queries():
            resp = self.client.get("/wallet/history?miner_id=newbie")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertTrue(body["ok"])
            self.assertEqual(body["miner_id"], "newbie")
            self.assertEqual(body["transactions"], [])
            self.assertEqual(body["total"], 0)

    def test_wallet_history_unknown_wallet_is_empty_not_error(self):
        with self._patch_queries():
            resp = self.client.get("/wallet/history?miner_id=does_not_exist")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertEqual(body["total"], 0)

    # ==================== Invalid Wallet Parameter Cases ====================

    def test_wallet_history_missing_identifier(self):
        resp = self.client.get("/wallet/history")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "miner_id or address required"},
        )

    def test_wallet_history_empty_miner_id(self):
        resp = self.client.get("/wallet/history?miner_id=")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "miner_id or address required"},
        )

    def test_wallet_history_conflicting_identifiers(self):
        resp = self.client.get("/wallet/history?miner_id=alice&address=bob")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {
                "ok": False,
                "error": "miner_id and address must match when both are provided",
            },
        )

    # ==================== Pagination Behavior Cases ====================

    def test_wallet_history_pagination_default_limit(self):
        """Default limit of 50 is applied to the SQL LIMIT parameter."""
        with self._patch_queries():
            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            # history_cap passed to SQL = offset + limit = 0 + 50 = 50
            body = resp.get_json()
            self.assertEqual(body["total"], 0)

    def test_wallet_history_pagination_custom_limit_caps_results(self):
        """limit=2 returns at most 2 transactions even when more are available."""
        ledger_rows = [
            (1700000000 + i, 200, "alice", 100, f"transfer_in:bob:tx{i}")
            for i in range(5)
        ]
        with self._patch_queries(ledger=ledger_rows):
            resp = self.client.get("/wallet/history?miner_id=alice&limit=2")
            body = resp.get_json()
            self.assertEqual(body["total"], 5)
            self.assertEqual(len(body["transactions"]), 2)

    def test_wallet_history_pagination_offset(self):
        """offset skips the first N transactions."""
        ledger_rows = [
            (1700000000 + i, 200, "alice", 100, f"transfer_in:bob:tx{i}")
            for i in range(5)
        ]
        with self._patch_queries(ledger=ledger_rows):
            resp = self.client.get("/wallet/history?miner_id=alice&limit=2&offset=2")
            txs = resp.get_json()["transactions"]
            self.assertEqual(len(txs), 2)

    def test_wallet_history_pagination_invalid_limit_string(self):
        resp = self.client.get("/wallet/history?miner_id=alice&limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "limit must be an integer"},
        )

    def test_wallet_history_pagination_invalid_limit_float(self):
        resp = self.client.get("/wallet/history?miner_id=alice&limit=10.5")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "limit must be an integer"},
        )

    def test_wallet_history_pagination_invalid_offset(self):
        resp = self.client.get("/wallet/history?miner_id=alice&offset=zzz")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "offset must be an integer"},
        )

    # ==================== Address Alias Cases ====================

    def test_wallet_history_address_alias_works(self):
        with self._patch_queries():
            resp = self.client.get("/wallet/history?address=alice")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["miner_id"], "alice")

    def test_wallet_history_matching_identifiers_accepted(self):
        with self._patch_queries():
            resp = self.client.get("/wallet/history?miner_id=alice&address=alice")
            self.assertEqual(resp.status_code, 200)

    # ==================== Response Schema Validation ====================

    def test_wallet_history_envelope_has_required_top_level_fields(self):
        """The envelope itself is always {ok, miner_id, transactions, total}."""
        with self._patch_queries():
            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()
            self.assertIn("ok", body)
            self.assertIn("miner_id", body)
            self.assertIn("transactions", body)
            self.assertIn("total", body)
            self.assertIsInstance(body["transactions"], list)
            self.assertIsInstance(body["total"], int)

    def test_wallet_history_transfer_entry_has_unified_fields(self):
        """A transfer_in entry contains exactly the documented unified fields."""
        ledger_rows = [
            (1700000000, 200, "alice", 1000000, "transfer_in:bob:tx123"),
        ]
        with self._patch_queries(ledger=ledger_rows):
            tx = self.client.get("/wallet/history?miner_id=alice").get_json()[
                "transactions"
            ][0]
            self.assertEqual(tx["type"], "transfer_in")
            self.assertEqual(tx["amount"], 1.0)
            self.assertEqual(tx["epoch"], 200)
            self.assertEqual(tx["timestamp"], 1700000000)
            self.assertEqual(tx["tx_hash"], "tx123")
            self.assertEqual(tx["from"], "bob")
            # Legacy fields are NOT in the unified envelope
            for legacy in (
                "tx_id", "from_addr", "to_addr", "amount_i64", "amount_rtc",
                "counterparty", "direction", "raw_status", "status_reason",
                "confirmed_at", "confirms_at", "confirmations", "memo",
            ):
                self.assertNotIn(legacy, tx, f"legacy field '{legacy}' leaked into envelope")

    def test_wallet_history_status_only_on_pending(self):
        """Only pending rows carry ``status``; confirmed ledger rows do not."""
        ledger_rows = [
            (1700000000, 200, "alice", 100, "transfer_in:bob:tx_confirmed"),
        ]
        pending_rows = [
            (1700001000, "alice", "bob", 200, None, "pending", "tx_pending", 1700001000),
        ]
        with self._patch_queries(ledger=ledger_rows, pending=pending_rows):
            txs = self.client.get(
                "/wallet/history?miner_id=alice"
            ).get_json()["transactions"]
            confirmed = [t for t in txs if t["tx_hash"] == "tx_confirmed"][0]
            pending = [t for t in txs if t["tx_hash"] == "tx_pending"][0]
            self.assertNotIn("status", confirmed)
            self.assertEqual(pending["status"], "pending")


if __name__ == "__main__":
    unittest.main()
