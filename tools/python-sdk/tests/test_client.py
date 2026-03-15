"""Unit tests for RustChainClient with mocked HTTP responses."""

import json
import unittest
from unittest.mock import patch, MagicMock

import requests as _requests

from rustchain.client import RustChainClient, APIError


def _mock_response(json_data, status_code=200, ok=True):
    """Build a fake ``requests.Response``."""
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data)
    return resp


class TestRustChainClient(unittest.TestCase):
    """Tests against mocked HTTP layer."""

    def setUp(self):
        self.client = RustChainClient(
            base_url="https://localhost:9999",
            verify_ssl=False,
            retries=1,
        )

    def tearDown(self):
        self.client.close()

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_health(self, mock_req):
        body = {"ok": True, "version": "2.2.1-rip200", "uptime_s": 86400}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_health()

        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "2.2.1-rip200")
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        self.assertEqual(args[0], "GET")
        self.assertIn("/health", args[1])

    @patch("rustchain.client.requests.Session.request")
    def test_get_ready(self, mock_req):
        body = {"ready": True, "version": "2.2.1-security-hardened"}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_ready()
        self.assertTrue(result["ready"])

    @patch("rustchain.client.requests.Session.request")
    def test_get_stats(self, mock_req):
        body = {"total_miners": 50, "total_blocks": 12345}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_stats()
        self.assertEqual(result["total_miners"], 50)

    # ------------------------------------------------------------------
    # Epoch & Lottery
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_epoch(self, mock_req):
        body = {"epoch": 95, "slot": 13365, "height": 67890}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_epoch()

        self.assertEqual(result["epoch"], 95)
        self.assertEqual(result["slot"], 13365)

    @patch("rustchain.client.requests.Session.request")
    def test_get_eligibility(self, mock_req):
        body = {"eligible": True, "slot": 13365, "slot_producer": "miner-1"}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_eligibility("miner-1")
        self.assertTrue(result["eligible"])

    # ------------------------------------------------------------------
    # Chain
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_chain_tip(self, mock_req):
        body = {"height": 67890, "hash": "abc123", "slot": 13365}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_chain_tip()
        self.assertEqual(result["height"], 67890)

    # ------------------------------------------------------------------
    # Miners
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_miners(self, mock_req):
        body = [
            {"miner": "windows-gaming-121", "antiquity_multiplier": 1.0},
            {"miner": "g4-powerbook-01", "antiquity_multiplier": 2.5},
        ]
        mock_req.return_value = _mock_response(body)

        result = self.client.get_miners()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["miner"], "windows-gaming-121")

    # ------------------------------------------------------------------
    # Wallet / Balance
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_balance(self, mock_req):
        body = {
            "amount_i64": 155000000,
            "amount_rtc": 155.0,
            "miner_id": "Ivan-houzhiwen",
        }
        mock_req.return_value = _mock_response(body)

        result = self.client.get_balance("Ivan-houzhiwen")

        self.assertEqual(result["amount_rtc"], 155.0)
        self.assertEqual(result["miner_id"], "Ivan-houzhiwen")
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["params"], {"miner_id": "Ivan-houzhiwen"})

    @patch("rustchain.client.requests.Session.request")
    def test_get_wallet_history(self, mock_req):
        body = [{"tx_id": "tx1", "amount": 10}, {"tx_id": "tx2", "amount": 5}]
        mock_req.return_value = _mock_response(body)

        result = self.client.get_wallet_history("miner-1", limit=10)
        self.assertEqual(len(result), 2)

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_submit_transaction(self, mock_req):
        body = {"success": True, "tx_hash": "0xdeadbeef"}
        mock_req.return_value = _mock_response(body)

        result = self.client.submit_transaction(
            from_wallet="wallet-a",
            to_wallet="wallet-b",
            amount=1000000,
            fee=0.001,
            signature="abcdef1234567890",
            timestamp=1700000000,
        )

        self.assertTrue(result["success"])
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["from"], "wallet-a")
        self.assertEqual(kwargs["json"]["amount"], 1000000)

    # ------------------------------------------------------------------
    # Governance
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_list_proposals(self, mock_req):
        body = [{"id": 1, "title": "Increase epoch length"}]
        mock_req.return_value = _mock_response(body)

        result = self.client.list_proposals()
        self.assertEqual(len(result), 1)

    # ------------------------------------------------------------------
    # P2P
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_p2p_stats(self, mock_req):
        body = {"peers": 12, "inbound": 5, "outbound": 7}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_p2p_stats()
        self.assertEqual(result["peers"], 12)

    # ------------------------------------------------------------------
    # Fee Pool
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_get_fee_pool(self, mock_req):
        body = {"total_fees": 42.5, "epoch": 95}
        mock_req.return_value = _mock_response(body)

        result = self.client.get_fee_pool()
        self.assertEqual(result["total_fees"], 42.5)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @patch("rustchain.client.requests.Session.request")
    def test_api_error_on_4xx(self, mock_req):
        mock_req.return_value = _mock_response(
            {"error": "not found"}, status_code=404, ok=False
        )

        with self.assertRaises(APIError) as ctx:
            self.client.get_balance("nonexistent")

        self.assertEqual(ctx.exception.status_code, 404)

    @patch("rustchain.client.requests.Session.request")
    def test_retry_on_connection_error(self, mock_req):
        mock_req.side_effect = [
            _requests.ConnectionError("refused"),
            _mock_response({"ok": True}),
        ]
        client = RustChainClient(
            base_url="https://localhost:9999",
            verify_ssl=False,
            retries=2,
            retry_delay=0.0,
        )
        result = client.get_health()
        self.assertTrue(result["ok"])
        self.assertEqual(mock_req.call_count, 2)
        client.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def test_context_manager(self):
        with RustChainClient(base_url="https://localhost:9999") as client:
            self.assertIsInstance(client, RustChainClient)

    def test_repr(self):
        self.assertIn("localhost:9999", repr(self.client))


if __name__ == "__main__":
    unittest.main()
