"""
Tests for RustChain OTC Bridge
"""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

# Set test DB before importing
_fd, TEST_DB = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OTC_DB_PATH"] = TEST_DB

from otc_bridge import app, init_db


class OTCBridgeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        init_db()

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

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
            r3 = self.app.post(f"/api/orders/{order_id}/confirm", json={
                "wallet": "buyer1",
                "quote_tx": "0xabc123def456",
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


class OTCBridgeFrontendSecurityTestCase(unittest.TestCase):
    def test_frontend_escapes_orderbook_order_and_trade_fields(self):
        static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
        with open(static_path, encoding="utf-8") as f:
            html = f.read()

        self.assertIn("function escapeHtml(value)", html)
        self.assertIn("function safeSide(value)", html)
        self.assertIn("${escapeHtml(o.maker_wallet)}", html)
        self.assertIn("${escapeHtml(o.amount_rtc)} RTC", html)
        self.assertIn("${escapeHtml(o.price_per_rtc)}", html)
        self.assertIn('data-order-index="${index}"', html)
        self.assertIn("button.addEventListener('click'", html)
        self.assertNotIn("onclick=\"openMatch('${o.order_id}'", html)
        self.assertIn("Counterparty: ${escapeHtml(maker)}", html)
        self.assertIn("${escapeHtml(side)}", html)
        self.assertIn("${escapeHtml(quote)}", html)


if __name__ == "__main__":
    unittest.main()
