"""
Tests for GET /wallet/history endpoint (Issue #908)

Tests cover:
- Success cases with various transaction states
- Empty history for valid/invalid wallets
- Invalid wallet parameter handling
- Pagination behavior (clamping, defaults, edge cases)
- Response format validation
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


class TestWalletHistoryEndpoint(unittest.TestCase):
    """Comprehensive tests for /wallet/history endpoint"""

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

    # ==================== Success Cases ====================

    def test_wallet_history_success_sent_transaction(self):
        """Test history returns sent transaction correctly formatted"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (
                    1,
                    1700000000,
                    "alice",
                    "bob",
                    5000000,  # 5 RTC in micro-units
                    "signed_transfer:payment",
                    "confirmed",
                    1700000000,
                    1700086400,
                    1700086500,
                    "tx_hash_abc123",
                    None,
                )
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(len(body), 1)
            tx = body[0]
            self.assertEqual(tx["tx_id"], "tx_hash_abc123")
            self.assertEqual(tx["tx_hash"], "tx_hash_abc123")
            self.assertEqual(tx["from_addr"], "alice")
            self.assertEqual(tx["to_addr"], "bob")
            self.assertEqual(tx["amount"], 5.0)
            self.assertEqual(tx["amount_i64"], 5000000)
            self.assertEqual(tx["amount_rtc"], 5.0)
            self.assertEqual(tx["direction"], "sent")
            self.assertEqual(tx["counterparty"], "bob")
            self.assertEqual(tx["status"], "confirmed")
            self.assertEqual(tx["confirmations"], 1)
            self.assertEqual(tx["memo"], "payment")
            self.assertEqual(tx["confirmed_at"], 1700086500)
            self.assertEqual(tx["confirms_at"], 1700086400)

    def test_wallet_history_success_received_transaction(self):
        """Test history returns received transaction with correct direction"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (
                    2,
                    1700001000,
                    "carol",
                    "alice",
                    2500000,
                    "signed_transfer:refund",
                    "pending",
                    1700001000,
                    1700087400,
                    None,
                    None,
                    None,
                )
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(len(body), 1)
            tx = body[0]
            self.assertEqual(tx["direction"], "received")
            self.assertEqual(tx["counterparty"], "carol")
            self.assertEqual(tx["status"], "pending")
            self.assertEqual(tx["confirmations"], 0)
            self.assertEqual(tx["memo"], "refund")
            self.assertIsNone(tx["confirmed_at"])
            self.assertEqual(tx["confirms_at"], 1700087400)

    def test_wallet_history_success_failed_transaction(self):
        """Test history returns failed/voided transaction correctly"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (
                    3,
                    1700002000,
                    "alice",
                    "mallory",
                    1000000,
                    "manual_review",
                    "voided",
                    1700002000,
                    1700088400,
                    None,
                    "tx_voided",
                    "suspicious_activity",
                )
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            tx = body[0]
            self.assertEqual(tx["status"], "failed")
            self.assertEqual(tx["raw_status"], "voided")
            self.assertEqual(tx["status_reason"], "suspicious_activity")
            self.assertEqual(tx["confirmations"], 0)

    def test_wallet_history_success_pending_without_tx_hash(self):
        """Test pending transaction uses pending_ID as tx_id"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (
                    42,
                    1700003000,
                    "alice",
                    "bob",
                    500000,
                    None,
                    "pending",
                    1700003000,
                    1700089400,
                    None,
                    None,  # No tx_hash for pending
                    None,
                )
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            tx = body[0]
            self.assertEqual(tx["tx_id"], "pending_42")
            self.assertEqual(tx["tx_hash"], "pending_42")

    def test_wallet_history_success_without_memo(self):
        """Test transaction without memo returns None"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (
                    5,
                    1700004000,
                    "alice",
                    "bob",
                    100000,
                    None,  # No reason/memo
                    "confirmed",
                    1700004000,
                    1700090400,
                    1700090500,
                    "tx_nomemo",
                    None,
                )
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()
            self.assertIsNone(body[0]["memo"])

    def test_wallet_history_success_multiple_transactions_ordering(self):
        """Test transactions are ordered by created_at DESC, id DESC"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (3, 1700003000, "alice", "bob", 300000, None, "confirmed", 1700003000, 1700089400, 1700089500, "tx3", None),
                (2, 1700002000, "carol", "alice", 200000, None, "confirmed", 1700002000, 1700088400, 1700088500, "tx2", None),
                (1, 1700001000, "alice", "dave", 100000, None, "confirmed", 1700001000, 1700087400, 1700087500, "tx1", None),
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()

            self.assertEqual(len(body), 3)
            # Should be ordered by created_at DESC
            self.assertEqual(body[0]["tx_id"], "tx3")
            self.assertEqual(body[1]["tx_id"], "tx2")
            self.assertEqual(body[2]["tx_id"], "tx1")

    # ==================== Empty History Cases ====================

    def test_wallet_history_empty_no_transactions(self):
        """Test empty array returned for wallet with no history"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=newbie")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertEqual(body, [])

    def test_wallet_history_empty_nonexistent_wallet(self):
        """Test empty array returned for non-existent wallet (not error)"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=does_not_exist")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json(), [])

    # ==================== Invalid Wallet Parameter Cases ====================

    def test_wallet_history_missing_identifier(self):
        """Test error when neither miner_id nor address provided"""
        resp = self.client.get("/wallet/history")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "miner_id or address required"},
        )

    def test_wallet_history_empty_miner_id(self):
        """Test error when miner_id is empty string"""
        resp = self.client.get("/wallet/history?miner_id=")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "miner_id or address required"},
        )

    def test_wallet_history_conflicting_identifiers(self):
        """Test error when miner_id and address don't match"""
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
        """Test default limit of 50 is applied"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertEqual(resp.status_code, 200)

            # Verify query used limit=50
            call_args = mock_conn.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            self.assertIn("LIMIT ?", query)
            self.assertEqual(params[-1], 50)  # Last param is limit

    def test_wallet_history_pagination_custom_limit(self):
        """Test custom limit is respected"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=10")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 10)

    def test_wallet_history_pagination_limit_clamped_to_minimum(self):
        """Test limit=0 is clamped to 1"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=0")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 1)  # Clamped to minimum

    def test_wallet_history_pagination_limit_negative_clamped(self):
        """Test negative limit is clamped to 1"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=-100")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 1)  # Clamped to minimum

    def test_wallet_history_pagination_limit_clamped_to_maximum(self):
        """Test limit > 200 is clamped to 200"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=1000")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 200)  # Clamped to maximum

    def test_wallet_history_pagination_limit_exactly_200(self):
        """Test limit=200 is accepted"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=200")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 200)

    def test_wallet_history_pagination_limit_exactly_1(self):
        """Test limit=1 is accepted"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=1")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 1)

    def test_wallet_history_pagination_invalid_limit_string(self):
        """Test invalid limit string returns error"""
        resp = self.client.get("/wallet/history?miner_id=alice&limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "limit must be an integer"},
        )

    def test_wallet_history_pagination_invalid_limit_float(self):
        """Test float limit returns error"""
        resp = self.client.get("/wallet/history?miner_id=alice&limit=10.5")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {"ok": False, "error": "limit must be an integer"},
        )

    def test_wallet_history_pagination_empty_limit_uses_default(self):
        """Test empty limit parameter uses default"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&limit=")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[-1], 50)  # Default

    # ==================== Address Alias Cases ====================

    def test_wallet_history_address_alias_works(self):
        """Test address parameter works as alias for miner_id"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?address=alice")
            self.assertEqual(resp.status_code, 200)

            call_args = mock_conn.execute.call_args
            params = call_args[0][1]
            self.assertEqual(params[0], "alice")
            self.assertEqual(params[1], "alice")

    def test_wallet_history_matching_identifiers_accepted(self):
        """Test same miner_id and address is accepted"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = []

            resp = self.client.get("/wallet/history?miner_id=alice&address=alice")
            self.assertEqual(resp.status_code, 200)

    # ==================== Response Schema Validation ====================

    def test_wallet_history_response_contains_required_fields(self):
        """Test response contains all required fields per OpenAPI spec"""
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchall.return_value = [
                (
                    1,
                    1700000000,
                    "alice",
                    "bob",
                    1000000,
                    "signed_transfer:test",
                    "confirmed",
                    1700000000,
                    1700086400,
                    1700086500,
                    "tx123",
                    None,
                )
            ]

            resp = self.client.get("/wallet/history?miner_id=alice")
            body = resp.get_json()

            required_fields = [
                "tx_id", "from_addr", "to_addr", "amount",
                "timestamp", "status", "direction", "counterparty"
            ]
            optional_fields = [
                "amount_i64", "amount_rtc", "memo", "confirmed_at",
                "confirms_at", "raw_status", "status_reason", "confirmations"
            ]

            tx = body[0]
            for field in required_fields:
                self.assertIn(field, tx, f"Required field '{field}' missing")

            for field in optional_fields:
                self.assertIn(field, tx, f"Optional field '{field}' missing")

    def test_wallet_history_status_enum_values(self):
        """Test status field only contains valid enum values"""
        valid_statuses = {"pending", "confirmed", "failed"}

        test_cases = [
            ("pending", "pending"),
            ("confirmed", "confirmed"),
            ("voided", "failed"),
            ("rejected", "failed"),
            ("unknown_status", "failed"),
        ]

        for raw_status, expected_public_status in test_cases:
            with patch.object(self.mod.sqlite3, "connect") as mock_connect:
                mock_conn = mock_connect.return_value.__enter__.return_value
                mock_conn.execute.return_value.fetchall.return_value = [
                    (1, 1700000000, "alice", "bob", 1000000, None, raw_status,
                     1700000000, 1700086400, None, "tx", None)
                ]

                resp = self.client.get("/wallet/history?miner_id=alice")
                body = resp.get_json()
                self.assertIn(body[0]["status"], valid_statuses)
                self.assertEqual(body[0]["status"], expected_public_status)

    def test_wallet_history_direction_enum_values(self):
        """Test direction field only contains valid enum values"""
        valid_directions = {"sent", "received"}

        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value

            # Test sent
            mock_conn.execute.return_value.fetchall.return_value = [
                (1, 1700000000, "alice", "bob", 1000000, None, "confirmed",
                 1700000000, 1700086400, 1700086500, "tx", None)
            ]
            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertIn(resp.get_json()[0]["direction"], valid_directions)

            # Test received
            mock_conn.execute.return_value.fetchall.return_value = [
                (1, 1700000000, "bob", "alice", 1000000, None, "confirmed",
                 1700000000, 1700086400, 1700086500, "tx", None)
            ]
            resp = self.client.get("/wallet/history?miner_id=alice")
            self.assertIn(resp.get_json()[0]["direction"], valid_directions)


if __name__ == "__main__":
    unittest.main()
