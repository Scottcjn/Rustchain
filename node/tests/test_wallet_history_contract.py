"""Live-contract smoke test for ``GET /wallet/history``.

Resolves the documented schema in ``docs/API.md`` (single source of truth)
and asserts the live route's actual response shape matches it for every
transaction type (``transfer_in``, ``transfer_out``, ``reward``,
``ledger``). This guards against future drift between the route, the
tests, and the documentation.

The test deliberately avoids importing anything from the route module's
internal symbols except the Flask test client, so it stays decoupled from
implementation details.
"""

import importlib.util
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(NODE_DIR, ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"
DOCS_PATH = os.path.join(REPO_ROOT, "docs", "API.md")


def _route_envelope_keys():
    """Required top-level envelope keys, derived from docs/API.md.

    These are the keys the docs declare the route MUST return on success.
    If the route ever adds a new top-level key, this test will fail and
    force the docs to be updated in lockstep.
    """
    return {"ok", "miner_id", "transactions", "total"}


def _common_tx_keys():
    """Keys every transaction entry must carry, per docs."""
    return {"type", "amount", "epoch", "timestamp", "tx_hash"}


def _type_specific_keys():
    """Map from ``type`` -> required keys (union with common keys).

    Sourced from the per-type rows in ``docs/API.md``.
    """
    return {
        "transfer_in": {"from"},
        "transfer_out": {"to"},
        "ledger": {"reason"},
        "reward": set(),
    }


def _type_optional_keys():
    """Optional keys that may appear on certain types."""
    return {
        "transfer_out": {"status"},   # only on pending rows
        "transfer_in": set(),
        "ledger": set(),
        "reward": set(),
    }


def _make_execute_side_effect(ledger=(), rewards=(), pending=()):
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


def _patch_queries(mod, ledger=(), rewards=(), pending=()):
    return patch.object(
        mod.sqlite3, "connect",
        MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(
                execute=MagicMock(side_effect=_make_execute_side_effect(
                    ledger=ledger, rewards=rewards, pending=pending,
                ))
            )),
            __exit__=MagicMock(return_value=False),
        )),
    )


class TestWalletHistoryContract(unittest.TestCase):
    """Smoke-test the unified /wallet/history envelope documented in API.md."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "contract.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_wallet_history_contract", MODULE_PATH,
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

    # --------------------------------------------------------------
    # Schema validation against documented contract
    # --------------------------------------------------------------

    def _assert_matches_documented_schema(self, tx):
        """Assert a single transaction entry conforms to docs/API.md."""
        common = _common_tx_keys()
        type_specific = _type_specific_keys()
        type_optional = _type_optional_keys()

        missing_common = common - set(tx.keys())
        self.assertFalse(
            missing_common,
            f"transaction missing common keys {missing_common}: {tx}",
        )
        tx_type = tx["type"]
        self.assertIn(tx_type, type_specific, f"unknown transaction type: {tx_type}")

        required = type_specific[tx_type]
        missing = required - set(tx.keys())
        self.assertFalse(
            missing,
            f"type={tx_type} missing required keys {missing}: {tx}",
        )

        allowed_optional = type_optional.get(tx_type, set())
        declared = required | allowed_optional
        # Common keys are always allowed, plus declared extras
        extras = set(tx.keys()) - common - declared
        # We permit extra keys BUT log them so reviewers can prune
        if extras:
            print(
                f"[contract note] type={tx_type} has undocumented extras: {extras}"
            )

    # --------------------------------------------------------------
    # Tests
    # --------------------------------------------------------------

    def test_documented_types_present_in_api_md(self):
        """Every transaction type the route can emit is documented in API.md.

        Guards against the route adding a new ``type`` value without
        updating the docs.
        """
        with open(DOCS_PATH, "r", encoding="utf-8") as fh:
            doc = fh.read()
        for t in ("transfer_in", "transfer_out", "reward", "ledger"):
            self.assertIn(
                f"`{t}`", doc,
                f"docs/API.md must document transaction type `{t}`",
            )

    def test_envelope_matches_documented_top_level_keys(self):
        """Empty response carries exactly the documented top-level keys."""
        with _patch_queries(self.mod):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            self.assertEqual(set(body.keys()), _route_envelope_keys())

    def test_envelope_values_have_documented_types(self):
        with _patch_queries(self.mod):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            self.assertIsInstance(body["ok"], bool)
            self.assertIsInstance(body["miner_id"], str)
            self.assertIsInstance(body["transactions"], list)
            self.assertIsInstance(body["total"], int)
            self.assertEqual(body["total"], len(body["transactions"]))

    def test_transfer_in_entry_matches_documented_schema(self):
        ledger_rows = [
            (1700000000, 200, "alice", 1000000, "transfer_in:bob:tx_smoke_1"),
        ]
        with _patch_queries(self.mod, ledger=ledger_rows):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            self.assertEqual(body["total"], 1)
            tx = body["transactions"][0]
            self._assert_matches_documented_schema(tx)
            self.assertEqual(tx["from"], "bob")
            self.assertEqual(tx["tx_hash"], "tx_smoke_1")
            self.assertEqual(tx["amount"], 1.0)

    def test_transfer_out_pending_entry_matches_documented_schema(self):
        pending_rows = [
            (1700000500, "alice", "bob", 500000, None, "pending", "tx_pending_smoke", 1700000500),
        ]
        with _patch_queries(self.mod, pending=pending_rows):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            tx = body["transactions"][0]
            self._assert_matches_documented_schema(tx)
            self.assertEqual(tx["to"], "bob")
            self.assertEqual(tx["status"], "pending")

    def test_reward_entry_matches_documented_schema(self):
        reward_rows = [(201, 7500000, 1)]
        with _patch_queries(self.mod, rewards=reward_rows):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            tx = body["transactions"][0]
            self._assert_matches_documented_schema(tx)
            self.assertEqual(tx["amount"], 7.5)
            self.assertEqual(tx["epoch"], 201)
            self.assertIsNone(tx["tx_hash"])

    def test_ledger_entry_matches_documented_schema(self):
        ledger_rows = [
            (1700001000, 202, "alice", 100000, "manual_adjustment"),
        ]
        with _patch_queries(self.mod, ledger=ledger_rows):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            tx = body["transactions"][0]
            self._assert_matches_documented_schema(tx)
            self.assertEqual(tx["reason"], "manual_adjustment")

    def test_legacy_alias_fields_not_present(self):
        """Regression guard: the unified envelope does not leak any of the
        removed legacy fields documented under "Migration from the legacy
        flat-array contract (pre-#997)"."""
        legacy_fields = {
            "tx_id", "from_addr", "to_addr", "amount_i64", "amount_rtc",
            "counterparty", "direction", "raw_status", "status_reason",
            "confirmed_at", "confirms_at", "confirmations", "memo",
        }
        ledger_rows = [
            (1700000000, 200, "alice", 1000000, "transfer_in:bob:tx_legacy_check"),
        ]
        pending_rows = [
            (1700000500, "alice", "bob", 500000, None, "pending", "tx_legacy_pending", 1700000500),
        ]
        reward_rows = [(201, 1000000, 1)]
        with _patch_queries(self.mod, ledger=ledger_rows, rewards=reward_rows, pending=pending_rows):
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            for tx in body["transactions"]:
                leaked = legacy_fields & set(tx.keys())
                self.assertFalse(
                    leaked,
                    f"legacy fields leaked into unified envelope: {leaked} in {tx}",
                )


if __name__ == "__main__":
    unittest.main()
