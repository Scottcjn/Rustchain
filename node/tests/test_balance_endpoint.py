"""
Comprehensive tests for GET /wallet/balance endpoint (Issue #305).

Tests cover:
- Success cases for existing and zero balances.
- Error handling for missing/invalid miner_id.
- Database operational errors (e.g., locked database).
- General unexpected database errors.
- Correct response format and RTC conversion.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Define the path to the node directory and the integrated module.
NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

# Constants for test scenarios
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_rustchain_balance.db")
MINER_ID_ALICE = "alice"
MINER_ID_BOB = "bob"
MINER_ID_CHARLIE = "charlie"
ALICE_BALANCE_I64 = 150_000_000
BOB_BALANCE_I64 = 0
UNIT = 1_000_000  # uRTC per 1 RTC, from rewards_implementation_rip200.py
RTC_DECIMAL_PRECISION = 8
DATABASE_LOCKED_ERROR_MESSAGE = "Service unavailable due to database issues"
UNEXPECTED_DATABASE_ERROR_MESSAGE = "An unexpected database error occurred"


class TestWalletBalanceEndpoint(unittest.TestCase):
    """Comprehensive tests for the /wallet/balance endpoint."""

    @classmethod
    def setUpClass(cls):
        """Set up for all tests in this class."""
        # Ensure NODE_DIR is in sys.path for module import
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        # Import the module containing the Flask app
        spec = importlib.util.spec_from_file_location("rustchain_integrated_rewards_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

        # Override DB_PATH within the module for testing purposes
        cls.original_db_path = cls.mod.DB_PATH
        cls.mod.DB_PATH = TEST_DB_PATH

        # Initialize Flask test client
        cls.client = cls.mod.app.test_client()

        # Create a temporary database for setup and ensure it's clean
        cls._init_db()

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in this class."""
        # Restore original DB_PATH
        cls.mod.DB_PATH = cls.original_db_path
        # Clean up temporary database file
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    @classmethod
    def _init_db(cls):
        """Initialize and populate the test database."""
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL
            );
            """
        )
        cursor.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = excluded.amount_i64;",
            (MINER_ID_ALICE, ALICE_BALANCE_I64),
        )
        conn.commit()
        conn.close()

    def setUp(self):
        """Reset the database for each test to ensure isolation."""
        self._init_db()  # Re-initialize the DB before each test

    # --- Success Cases ---

    def test_get_balance_success_existing_miner(self):
        """Test fetching balance for an existing miner with funds."""
        resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_ALICE}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIsNotNone(data)
        self.assertEqual(data["miner_id"], MINER_ID_ALICE)
        self.assertEqual(data["amount_i64"], ALICE_BALANCE_I64)
        self.assertAlmostEqual(data["amount_rtc"], round(ALICE_BALANCE_I64 / UNIT, RTC_DECIMAL_PRECISION))
        self.assertIsInstance(data["amount_rtc"], float)

    def test_get_balance_success_non_existent_miner(self):
        """Test fetching balance for a miner not in the database."""
        resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_BOB}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIsNotNone(data)
        self.assertEqual(data["miner_id"], MINER_ID_BOB)
        self.assertEqual(data["amount_i64"], BOB_BALANCE_I64)
        self.assertEqual(data["amount_rtc"], 0.0)

    # --- Error Cases: miner_id parameter ---

    def test_get_balance_missing_miner_id(self):
        """Test request without 'miner_id' parameter."""
        resp = self.client.get("/wallet/balance")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"], "miner_id required")

    def test_get_balance_empty_miner_id(self):
        """Test request with an empty 'miner_id' parameter."""
        resp = self.client.get("/wallet/balance?miner_id=")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"], "miner_id required")

    # --- Error Cases: Database Issues ---

    def test_get_balance_operational_error(self):
        """Test database operational error (e.g., locked DB)."""
        with patch.object(self.mod.sqlite3, "connect", side_effect=sqlite3.OperationalError("database is locked")):
            resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_ALICE}")
            self.assertEqual(resp.status_code, 503)
            data = resp.get_json()
            self.assertEqual(data["error"], DATABASE_LOCKED_ERROR_MESSAGE)

    def test_get_balance_general_sqlite_error(self):
        """Test a general unexpected sqlite3.Error."""
        with patch.object(self.mod.sqlite3, "connect", side_effect=sqlite3.Error("disk I/O error")):
            resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_ALICE}")
            self.assertEqual(resp.status_code, 500)
            data = resp.get_json()
            self.assertEqual(data["error"], UNEXPECTED_DATABASE_ERROR_MESSAGE)

    def test_get_balance_operational_error_during_execute(self):
        """Test database operational error during query execution."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = sqlite3.OperationalError("database table locked")
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_cursor
        mock_db.__enter__.return_value = mock_db
        mock_db.__exit__.return_value = None

        with patch.object(self.mod.sqlite3, "connect", return_value=mock_db):
            resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_ALICE}")
            self.assertEqual(resp.status_code, 503)
            data = resp.get_json()
            self.assertEqual(data["error"], DATABASE_LOCKED_ERROR_MESSAGE)
            mock_db.execute.assert_called_once_with(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?", (MINER_ID_ALICE,)
            )

    def test_get_balance_general_sqlite_error_during_execute(self):
        """Test a general unexpected sqlite3.Error during query execution."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = sqlite3.Error("malformed database schema")
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_cursor
        mock_db.__enter__.return_value = mock_db
        mock_db.__exit__.return_value = None

        with patch.object(self.mod.sqlite3, "connect", return_value=mock_db):
            resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_ALICE}")
            self.assertEqual(resp.status_code, 500)
            data = resp.get_json()
            self.assertEqual(data["error"], UNEXPECTED_DATABASE_ERROR_MESSAGE)
            mock_db.execute.assert_called_once_with(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?", (MINER_ID_ALICE,)
            )

    # --- Response Format Validation ---

    def test_get_balance_response_schema(self):
        """Verify the response matches the expected schema."""
        resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_ALICE}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("miner_id", data)
        self.assertIn("amount_i64", data)
        self.assertIn("amount_rtc", data)
        self.assertIsInstance(data["miner_id"], str)
        self.assertIsInstance(data["amount_i64"], int)
        self.assertIsInstance(data["amount_rtc"], float)

    def test_get_balance_rtc_precision(self):
        """Test that amount_rtc is rounded to the specified precision."""
        # Assume UNIT and RTC_DECIMAL_PRECISION are accessible from the module or hardcoded for test
        balance_i64_complex = 123_456_789
        expected_rtc = round(balance_i64_complex / UNIT, RTC_DECIMAL_PRECISION)

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = excluded.amount_i64;",
            (MINER_ID_CHARLIE, balance_i64_complex),
        )
        conn.commit()
        conn.close()

        resp = self.client.get(f"/wallet/balance?miner_id={MINER_ID_CHARLIE}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertAlmostEqual(data["amount_rtc"], expected_rtc)
        # Verify the number of decimal places for amount_rtc
        rtc_str = str(data["amount_rtc"])
        if "." in rtc_str:
            actual_precision = len(rtc_str.split(".")[-1])
            self.assertLessEqual(actual_precision, RTC_DECIMAL_PRECISION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
