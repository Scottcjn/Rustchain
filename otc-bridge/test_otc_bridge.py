"""
Tests for RustChain OTC Bridge
"""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

# Set an initial test DB before importing, then replace it per test.
_fd, TEST_DB = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OTC_DB_PATH"] = TEST_DB

import otc_bridge
from otc_bridge import app, init_db


class OTCBridgeTestCase(unittest.TestCase):
    def setUp(self):
        global TEST_DB
        _fd, TEST_DB = tempfile.mkstemp(suffix=".db")
        os.close(_fd)
        otc_bridge.DB_PATH = TEST_DB
        self.app = app.test_client()
        self.app.testing = True
        init_db()

    def tearDown(self):
        self.app = None
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except PermissionError:
                pass

    def create_legacy_money_schema(self):
        """Create the pre-migration schema with REAL NOT NULL money columns."""
        with sqlite3.connect(TEST_DB) as conn:
            c = conn.cursor()
            c.execute("DROP TABLE IF EXISTS orders")
            c.execute("DROP TABLE IF EXISTS trades")
            c.execute("DROP TABLE IF EXISTS rate_limits")
            c.execute("""
                CREATE TABLE orders (
                    order_id TEXT PRIMARY KEY,
                    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
                    pair TEXT NOT NULL,
                    maker_wallet TEXT NOT NULL,
                    amount_rtc REAL NOT NULL,
                    price_per_rtc REAL NOT NULL,
                    total_quote REAL NOT NULL,
                    status TEXT DEFAULT 'open',
                    escrow_job_id TEXT,
                    htlc_hash TEXT,
                    htlc_secret TEXT,
                    taker_wallet TEXT,
                    taker_eth_address TEXT,
                    maker_eth_address TEXT,
                    settlement_tx TEXT,
                    created_at INTEGER NOT NULL,
                    matched_at INTEGER,
                    confirmed_at INTEGER,
                    expires_at INTEGER NOT NULL,
                    ip_hash TEXT
                )
            """)
            c.execute("""
                CREATE TABLE trades (
                    trade_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    maker_wallet TEXT NOT NULL,
                    taker_wallet TEXT NOT NULL,
                    amount_rtc REAL NOT NULL,
                    price_per_rtc REAL NOT NULL,
                    total_quote REAL NOT NULL,
                    rtc_tx TEXT,
                    quote_tx TEXT,
                    completed_at INTEGER NOT NULL
                )
            """)
            conn.commit()

    # ---------------------------------------------------------------
    # Order Creation
    # ---------------------------------------------------------------

    def test_create_buy_order(self):
        """Buy orders don't need escrow -- just post to order book."""
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "test-buyer",
            "amount_rtc": 100,
            "price_per_rtc": 0.10,
        })
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["side"], "buy")
        self.assertEqual(data["amount_rtc"], 100)
        self.assertEqual(data["price_per_rtc"], 0.10)
        self.assertAlmostEqual(data["total_quote"], 10.0)
        self.assertEqual(data["status"], "open")
        self.assertIn("otc_", data["order_id"])

    def test_create_order_rejects_non_object_json(self):
        r = self.app.post("/api/orders", json=["not-an-object"])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json(), {"error": "JSON object required"})

    def test_create_order_rejects_non_integer_ttl(self):
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "test-buyer",
            "amount_rtc": "1",
            "price_per_rtc": "0.10",
            "ttl_seconds": "abc",
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json(), {"error": "ttl_seconds must be an integer"})

    def test_create_buy_order_accepts_valid_ttl(self):
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "ttl-buyer",
            "amount_rtc": "1",
            "price_per_rtc": "0.10",
            "ttl_seconds": "3600",
        })
        data = r.get_json()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(data["ok"])
        self.assertEqual(data["side"], "buy")

    def test_create_order_stores_scaled_integer_money_fields(self):
        """OTC money values are stored as integer scaled units, not SQLite REAL."""
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "precision-buyer",
            "amount_rtc": "0.3",
            "price_per_rtc": "0.1",
        })
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["amount_micro_rtc"], 300000)
        self.assertEqual(data["price_per_rtc_nano_quote"], 100000000)
        self.assertEqual(data["total_quote_nano"], 30000000)

        with sqlite3.connect(TEST_DB) as conn:
            conn.row_factory = sqlite3.Row
            columns = {row["name"]: row["type"] for row in conn.execute("PRAGMA table_info(orders)")}
            self.assertNotIn("amount_rtc", columns)
            self.assertNotIn("price_per_rtc", columns)
            self.assertNotIn("total_quote", columns)

            row = conn.execute(
                "SELECT amount_micro_rtc, price_per_rtc_nano_quote, total_quote_nano FROM orders WHERE order_id = ?",
                (data["order_id"],),
            ).fetchone()
            self.assertEqual(row["amount_micro_rtc"], 300000)
            self.assertEqual(row["price_per_rtc_nano_quote"], 100000000)
            self.assertEqual(row["total_quote_nano"], 30000000)

    @patch("requests.post")
    @patch("otc_bridge.rtc_get_balance", return_value=500.0)
    @patch("otc_bridge.rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_legacy"})
    def test_legacy_money_schema_accepts_new_orders_and_trades(self, mock_escrow, mock_balance, mock_post):
        """Migrated legacy tables still accept inserts despite old REAL NOT NULL columns."""
        self.create_legacy_money_schema()
        init_db()
        mock_post.return_value = MagicMock(ok=True, text='{"ok":true}')

        r1 = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "legacy-buyer",
            "amount_rtc": "0.3",
            "price_per_rtc": "0.1",
        })
        data = r1.get_json()
        self.assertEqual(r1.status_code, 201)
        self.assertTrue(data["ok"])
        order_id = data["order_id"]

        r2 = self.app.post(f"/api/orders/{order_id}/match", json={
            "wallet": "legacy-seller",
        })
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.get_json()["ok"])

        with sqlite3.connect(TEST_DB) as conn:
            secret = conn.execute(
                "SELECT htlc_secret FROM orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()[0]

        r3 = self.app.post(f"/api/orders/{order_id}/confirm", json={
            "wallet": "legacy-buyer",
            "quote_tx": "0xlegacy",
            "secret": secret,
        })
        self.assertEqual(r3.status_code, 200)
        self.assertTrue(r3.get_json()["ok"])

        with sqlite3.connect(TEST_DB) as conn:
            conn.row_factory = sqlite3.Row
            order = conn.execute(
                "SELECT amount_rtc, price_per_rtc, total_quote, amount_micro_rtc, "
                "price_per_rtc_nano_quote, total_quote_nano FROM orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            self.assertEqual(order["amount_rtc"], 0.3)
            self.assertEqual(order["price_per_rtc"], 0.1)
            self.assertEqual(order["total_quote"], 0.03)
            self.assertEqual(order["amount_micro_rtc"], 300000)
            self.assertEqual(order["price_per_rtc_nano_quote"], 100000000)
            self.assertEqual(order["total_quote_nano"], 30000000)

            trade = conn.execute(
                "SELECT amount_rtc, price_per_rtc, total_quote, amount_micro_rtc, "
                "price_per_rtc_nano_quote, total_quote_nano FROM trades WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            self.assertEqual(trade["amount_rtc"], 0.3)
            self.assertEqual(trade["price_per_rtc"], 0.1)
            self.assertEqual(trade["total_quote"], 0.03)
            self.assertEqual(trade["amount_micro_rtc"], 300000)
            self.assertEqual(trade["price_per_rtc_nano_quote"], 100000000)
            self.assertEqual(trade["total_quote_nano"], 30000000)

    @patch("otc_bridge.rtc_get_balance", return_value=500.0)
    @patch("otc_bridge.rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_test123"})
    def test_create_sell_order_with_escrow(self, mock_escrow, mock_balance):
        """Sell orders lock RTC in RIP-302 escrow."""
        r = self.app.post("/api/orders", json={
            "side": "sell",
            "pair": "RTC/USDC",
            "wallet": "test-seller",
            "amount_rtc": 50,
            "price_per_rtc": 0.12,
        })
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["side"], "sell")
        self.assertEqual(data["escrow_job_id"], "job_test123")
        self.assertEqual(data["escrow_status"], "locked")
        mock_escrow.assert_called_once()

    @patch("otc_bridge.rtc_get_balance", return_value=10.0)
    def test_sell_order_insufficient_balance(self, mock_balance):
        """Reject sell order if balance too low."""
        r = self.app.post("/api/orders", json={
            "side": "sell",
            "pair": "RTC/USDC",
            "wallet": "poor-seller",
            "amount_rtc": 500,
            "price_per_rtc": 0.10,
        })
        data = r.get_json()
        self.assertIn("Insufficient", data.get("error", ""))

    def test_invalid_side(self):
        r = self.app.post("/api/orders", json={
            "side": "hold",
            "pair": "RTC/USDC",
            "wallet": "test",
            "amount_rtc": 10,
            "price_per_rtc": 0.10,
        })
        self.assertEqual(r.status_code, 400)

    def test_invalid_pair(self):
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/DOGE",
            "wallet": "test",
            "amount_rtc": 10,
            "price_per_rtc": 0.10,
        })
        self.assertEqual(r.status_code, 400)

    def test_missing_wallet(self):
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "",
            "amount_rtc": 10,
            "price_per_rtc": 0.10,
        })
        self.assertEqual(r.status_code, 400)

    def test_amount_below_minimum(self):
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "test",
            "amount_rtc": 0.001,
            "price_per_rtc": 0.10,
        })
        self.assertEqual(r.status_code, 400)

    def test_negative_price(self):
        r = self.app.post("/api/orders", json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "test",
            "amount_rtc": 10,
            "price_per_rtc": -0.50,
        })
        self.assertEqual(r.status_code, 400)

    # ---------------------------------------------------------------
    # Order Listing & Book
    # ---------------------------------------------------------------

    def test_list_orders_empty(self):
        r = self.app.get("/api/orders")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["total"], 0)

    def test_list_orders_with_filter(self):
        # Create buy and sell orders
        self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer1", "amount_rtc": 50, "price_per_rtc": 0.09,
        })
        self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/ETH",
            "wallet": "buyer2", "amount_rtc": 100, "price_per_rtc": 0.00005,
        })

        # Filter by pair
        r = self.app.get("/api/orders?pair=RTC/USDC")
        data = r.get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["orders"][0]["pair"], "RTC/USDC")

        # Filter by side
        r = self.app.get("/api/orders?side=buy")
        data = r.get_json()
        self.assertEqual(data["total"], 2)

    def test_orderbook(self):
        # Create some orders
        self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer1", "amount_rtc": 100, "price_per_rtc": 0.09,
        })
        self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer2", "amount_rtc": 50, "price_per_rtc": 0.08,
        })

        r = self.app.get("/api/orderbook?pair=RTC/USDC")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["bids"]), 2)
        # Bids sorted by price descending
        self.assertGreaterEqual(data["bids"][0]["price"], data["bids"][1]["price"])

    def test_orderbook_keeps_distinct_scaled_prices(self):
        """Prices that rounded together at 4 decimals stay distinct internally."""
        self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer-precision-1", "amount_rtc": 1, "price_per_rtc": "0.100001",
        })
        self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer-precision-2", "amount_rtc": 1, "price_per_rtc": "0.100002",
        })

        r = self.app.get("/api/orderbook?pair=RTC/USDC")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["bids"]), 2)
        self.assertEqual(data["bids"][0]["price"], 0.100002)
        self.assertEqual(data["bids"][1]["price"], 0.100001)

    # ---------------------------------------------------------------
    # Order Matching
    # ---------------------------------------------------------------

    def test_match_buy_order(self):
        # Create buy order
        r1 = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer1", "amount_rtc": 100, "price_per_rtc": 0.10,
        })
        order_id = r1.get_json()["order_id"]

        # Match it (taker is seller, needs escrow)
        with patch("otc_bridge.rtc_get_balance", return_value=500.0), \
             patch("otc_bridge.rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_match1"}):
            r2 = self.app.post(f"/api/orders/{order_id}/match", json={
                "wallet": "seller1",
                "eth_address": "0xabc123",
            })
            data = r2.get_json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["status"], "matched")

    def test_cannot_match_own_order(self):
        r1 = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "same-wallet", "amount_rtc": 10, "price_per_rtc": 0.10,
        })
        order_id = r1.get_json()["order_id"]

        r2 = self.app.post(f"/api/orders/{order_id}/match", json={
            "wallet": "same-wallet",
        })
        self.assertEqual(r2.status_code, 400)
        self.assertIn("own order", r2.get_json()["error"])

    def test_cannot_match_nonexistent(self):
        r = self.app.post("/api/orders/otc_fake123/match", json={
            "wallet": "test",
        })
        self.assertEqual(r.status_code, 404)

    # ---------------------------------------------------------------
    # Order Cancellation
    # ---------------------------------------------------------------

    def test_cancel_order(self):
        r1 = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "canceler", "amount_rtc": 10, "price_per_rtc": 0.10,
        })
        order_id = r1.get_json()["order_id"]

        r2 = self.app.post(f"/api/orders/{order_id}/cancel", json={
            "wallet": "canceler",
        })
        data = r2.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["status"], "cancelled")

    def test_cannot_cancel_others_order(self):
        r1 = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "owner", "amount_rtc": 10, "price_per_rtc": 0.10,
        })
        order_id = r1.get_json()["order_id"]

        r2 = self.app.post(f"/api/orders/{order_id}/cancel", json={
            "wallet": "not-owner",
        })
        self.assertEqual(r2.status_code, 403)

    @patch("otc_bridge.rtc_get_balance", return_value=500.0)
    @patch("otc_bridge.rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_cancel1"})
    @patch("otc_bridge.rtc_cancel_escrow", return_value=True)
    def test_cancel_sell_order_refunds_escrow(self, mock_cancel, mock_create, mock_bal):
        r1 = self.app.post("/api/orders", json={
            "side": "sell", "pair": "RTC/USDC",
            "wallet": "seller1", "amount_rtc": 50, "price_per_rtc": 0.12,
        })
        order_id = r1.get_json()["order_id"]

        r2 = self.app.post(f"/api/orders/{order_id}/cancel", json={
            "wallet": "seller1",
        })
        self.assertTrue(r2.get_json()["ok"])
        mock_cancel.assert_called_once_with("job_cancel1", "seller1")

    # ---------------------------------------------------------------
    # Settlement Confirmation
    # ---------------------------------------------------------------

    def test_confirm_matched_order(self):
        # Create and match an order
        r1 = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer1", "amount_rtc": 100, "price_per_rtc": 0.10,
        })
        order_id = r1.get_json()["order_id"]

        with patch("otc_bridge.rtc_get_balance", return_value=500.0), \
             patch("otc_bridge.rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_conf1"}):
            self.app.post(f"/api/orders/{order_id}/match", json={
                "wallet": "seller1",
            })

        # Confirm settlement
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(ok=True, text='{"ok":true}')
            with sqlite3.connect(TEST_DB) as conn:
                secret = conn.execute(
                    "SELECT htlc_secret FROM orders WHERE order_id = ?",
                    (order_id,),
                ).fetchone()[0]
            r3 = self.app.post(f"/api/orders/{order_id}/confirm", json={
                "wallet": "buyer1",
                "quote_tx": "0xabc123def456",
                "secret": secret,
            })
            data = r3.get_json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["status"], "completed")
            self.assertIn("htlc_secret", data)

    def test_cannot_confirm_unmatched(self):
        r1 = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "buyer1", "amount_rtc": 10, "price_per_rtc": 0.10,
        })
        order_id = r1.get_json()["order_id"]

        r2 = self.app.post(f"/api/orders/{order_id}/confirm", json={
            "wallet": "buyer1",
            "quote_tx": "0x123",
        })
        self.assertEqual(r2.status_code, 409)

    # ---------------------------------------------------------------
    # Stats & Trades
    # ---------------------------------------------------------------

    def test_stats_endpoint(self):
        r = self.app.get("/api/stats")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("total_trades", data["stats"])
        self.assertIn("supported_pairs", data["stats"])

    def test_trades_empty(self):
        r = self.app.get("/api/trades")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["trades"]), 0)

    # ---------------------------------------------------------------
    # Rate Limiting
    # ---------------------------------------------------------------

    def test_rate_limiting(self):
        """Should reject after too many requests."""
        for i in range(10):
            self.app.post("/api/orders", json={
                "side": "buy", "pair": "RTC/USDC",
                "wallet": f"spammer-{i}", "amount_rtc": 1, "price_per_rtc": 0.10,
            })
        # 11th should be rate limited
        r = self.app.post("/api/orders", json={
            "side": "buy", "pair": "RTC/USDC",
            "wallet": "spammer-11", "amount_rtc": 1, "price_per_rtc": 0.10,
        })
        self.assertEqual(r.status_code, 429)

    # ---------------------------------------------------------------
    # Frontend
    # ---------------------------------------------------------------

    def test_frontend_served(self):
        r = self.app.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"RustChain OTC Bridge", r.data)


if __name__ == "__main__":
    unittest.main()
