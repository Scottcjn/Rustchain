// File: wrtc_holders/test_wrtc_holders.py
# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch, MagicMock
from wrtc_holders import WRTC
from solana_client import SolanaClient
import json


class TestWRTC(unittest.TestCase):
    def setUp(self):
        self.solana_client = SolanaClient("https://api.devnet.solana.com")
        self.wrtc = WRTC(self.solana_client)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders(self, mock_get_token_holders):
        # Mock the response from SolanaClient
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000},
                {"address": "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 500},
                {"address": "Dk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 200}
            ]
        ''')
        holders = self.wrtc.get_holders()
        self.assertEqual(len(holders), 4)
        self.assertEqual(holders[0]['address'], "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")
        self.assertEqual(holders[0]['amount'], 8296082)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder(self, mock_get_token_holders):
        # Mock the response from SolanaClient
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000},
                {"address": "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 500},
                {"address": "Dk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 200}
            ]
        ''')
        top_holder = self.wrtc.get_top_holder()
        self.assertEqual(top_holder['address'], "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")
        self.assertEqual(top_holder['amount'], 8296082)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder_no_holders(self, mock_get_token_holders):
        # Mock empty response
        mock_get_token_holders.return_value = []
        top_holder = self.wrtc.get_top_holder()
        self.assertIsNone(top_holder)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_network_error(self, mock_get_token_holders):
        # Simulate network error
        mock_get_token_holders.side_effect = Exception("Network unreachable")
        with self.assertRaises(Exception) as context:
            self.wrtc.get_holders()
        self.assertIn("Network unreachable", str(context.exception))

    def test_wrtc_instantiation_with_valid_client(self):
        # Test that WRTC initializes correctly with a SolanaClient
        self.assertIsInstance(self.wrtc.solana_client, SolanaClient)
        self.assertEqual(self.wrtc.solana_client.rpc_url, "https://api.devnet.solana.com")

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_returns_sorted_by_amount(self, mock_get_token_holders):
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000},
                {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082}
            ]
        ''')
        holders = self.wrtc.get_holders()
        self.assertEqual(holders[0]['amount'], 8296082)
        self.assertEqual(holders[1]['amount'], 1000)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_eligible_holders(self, mock_get_token_holders):
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "A1", "amount": 1000000},
                {"address": "B2", "amount": 50000},
                {"address": "C3", "amount": 1500000}
            ]
        ''')
        # Assume threshold is 100,000
        with patch.object(WRTC, 'get_incentive_threshold', return_value=100000):
            eligible = self.wrtc.get_eligible_holders()
        self.assertEqual(len(eligible), 2)
        self.assertIn({"address": "A1", "amount": 1000000}, eligible)
        self.assertIn({"address": "C3", "amount": 1500000}, eligible)

    def test_get_incentive_threshold_returns_int(self):
        threshold = self.wrtc.get_incentive_threshold()
        self.assertIsInstance(threshold, int)
        self.assertGreaterEqual(threshold, 0)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder_single_holder(self, mock_get_token_holders):
        mock_get_token_holders.return_value = json.loads('''
            [{"address": "OnlyOne", "amount": 99999}]
        ''')
        top_holder = self.wrtc.get_top_holder()
        self.assertEqual(top_holder['address'], "OnlyOne")
        self.assertEqual(top_holder['amount'], 99999)