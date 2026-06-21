"""Tests for the unified GET /wallet/history endpoint (Issue #908)."""

import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _query_result(rows):
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


class TestWalletHistoryEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
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

    def _get_history(self, *, ledger=(), rewards=(), pending=(), query="miner_id=alice"):
        def execute(sql, _params):
            if "FROM ledger" in sql:
                return _query_result(ledger)
            if "FROM epoch_rewards" in sql:
                return _query_result(rewards)
            if "FROM pending_ledger" in sql:
                return _query_result(pending)
            raise AssertionError(f"Unexpected query: {sql}")

        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            connection = mock_connect.return_value.__enter__.return_value
            connection.execute.side_effect = execute
            return self.client.get(f"/wallet/history?{query}")

    def test_unifies_ledger_rewards_and_pending_entries(self):
        response = self._get_history(
            ledger=[
                (1700000200, 12, "alice", 2_500_000, "transfer_in:bob:tx-in"),
                (1700000100, 12, "alice", -1_000_000, "transfer_out:carol:tx-out"),
            ],
            rewards=[(11, 750_000, 2)],
            pending=[
                (1700000300, "dave", "alice", 500_000, "tip", "pending", "tx-pending", 1700000300),
                (
                    1700000400,
                    "alice",
                    "erin",
                    250_000,
                    "tip",
                    "confirmed",
                    "tx-confirmed",
                    1700000400,
                ),
            ],
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["ok"], True)
        self.assertEqual(body["miner_id"], "alice")
        self.assertEqual(body["total"], 4)

        pending, incoming, outgoing, reward = body["transactions"]
        self.assertEqual(
            pending,
            {
                "type": "transfer_in",
                "amount": 0.5,
                "epoch": None,
                "timestamp": 1700000300,
                "tx_hash": "tx-pending",
                "status": "pending",
                "from": "dave",
            },
        )
        self.assertEqual(incoming["type"], "transfer_in")
        self.assertEqual(incoming["from"], "bob")
        self.assertEqual(incoming["amount"], 2.5)
        self.assertEqual(outgoing["type"], "transfer_out")
        self.assertEqual(outgoing["to"], "carol")
        self.assertEqual(outgoing["amount"], 1.0)
        self.assertEqual(reward["type"], "reward")
        self.assertEqual(reward["amount"], 0.75)
        self.assertNotIn("status", incoming)

    def test_non_transfer_ledger_reason_uses_ledger_type(self):
        response = self._get_history(
            ledger=[(1700000000, 9, "alice", 125_000, "manual_adjustment")]
        )

        transaction = response.get_json()["transactions"][0]
        self.assertEqual(transaction["type"], "ledger")
        self.assertEqual(transaction["reason"], "manual_adjustment")
        self.assertNotIn("from", transaction)
        self.assertNotIn("to", transaction)

    def test_unknown_wallet_returns_empty_unified_response(self):
        response = self._get_history(query="miner_id=unknown")

        self.assertEqual(
            response.get_json(),
            {"ok": True, "miner_id": "unknown", "transactions": [], "total": 0},
        )

    def test_pagination_applies_after_unified_sort(self):
        response = self._get_history(
            ledger=[
                (300, 3, "alice", 300_000, "ledger-3"),
                (100, 1, "alice", 100_000, "ledger-1"),
            ],
            rewards=[(2, 200_000, 1)],
            pending=[(400, "alice", "bob", 400_000, None, "pending", "tx-4", 400)],
            query="miner_id=alice&limit=2&offset=1",
        )

        body = response.get_json()
        self.assertEqual(body["total"], 4)
        self.assertEqual(len(body["transactions"]), 2)
        self.assertEqual([tx["timestamp"] for tx in body["transactions"]], [300, 100])

    def test_limit_is_clamped_to_supported_range(self):
        ledger = [
            (timestamp, 1, "alice", 1, f"entry-{timestamp}")
            for timestamp in range(250, 0, -1)
        ]
        for raw_limit, expected in (("0", 1), ("-5", 1), ("1000", 200)):
            with self.subTest(raw_limit=raw_limit):
                response = self._get_history(
                    ledger=ledger, query=f"miner_id=alice&limit={raw_limit}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.get_json()["transactions"]), expected)

    def test_offset_is_clamped_to_supported_range(self):
        ledger = [
            (timestamp, 1, "alice", 1, f"entry-{timestamp}")
            for timestamp in range(10_000, 0, -1)
        ]
        response = self._get_history(
            ledger=ledger, query="miner_id=alice&limit=10&offset=999999"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [tx["timestamp"] for tx in response.get_json()["transactions"]],
            list(range(200, 190, -1)),
        )

    def test_accepts_address_alias_and_matching_identifiers(self):
        alias = self._get_history(query="address=alice")
        matching = self._get_history(query="miner_id=alice&address=alice")

        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.get_json()["miner_id"], "alice")
        self.assertEqual(matching.status_code, 200)

    def test_requires_identifier(self):
        response = self.client.get("/wallet/history")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(), {"ok": False, "error": "miner_id or address required"}
        )

    def test_rejects_conflicting_identifiers(self):
        response = self.client.get("/wallet/history?miner_id=alice&address=bob")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"ok": False, "error": "miner_id and address must match when both are provided"},
        )

    def test_rejects_invalid_limit_and_offset(self):
        for query, error in (
            ("miner_id=alice&limit=abc", "limit must be an integer"),
            ("miner_id=alice&limit=", "limit must be an integer"),
            ("miner_id=alice&offset=abc", "offset must be an integer"),
        ):
            with self.subTest(query=query):
                response = self.client.get(f"/wallet/history?{query}")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"ok": False, "error": error})


if __name__ == "__main__":
    unittest.main()
