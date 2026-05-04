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
    def test_get_holders_with_zero_balance_filter(self, mock_get_token_holders):
        # Include zero and negative balance addresses to test filtering
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 0},
                {"address": "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": -500}
            ]
        ''')
        holders = self.wrtc.get_holders()
        # Only one holder with positive balance should be included
        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0]['amount'], 8296082)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder_with_tie_uses_first(self, mock_get_token_holders):
        # Two holders with same max amount
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "Addr1", "amount": 1000},
                {"address": "Addr2", "amount": 1000},
                {"address": "Addr3", "amount": 500}
            ]
        ''')
        top_holder = self.wrtc.get_top_holder()
        # First one should be picked
        self.assertEqual(top_holder['address'], "Addr1")
        self.assertEqual(top_holder['amount'], 1000)

    def test_wrtc_initialization_with_valid_client(self):
        # Test that WRTC initializes correctly with a SolanaClient
        wrtc = WRTC(self.solana_client)
        self.assertEqual(wrtc.solana_client, self.solana_client)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_network_error(self, mock_get_token_holders):
        # Simulate network error
        mock_get_token_holders.side_effect = Exception("Network unreachable")
        with self.assertRaises(Exception) as context:
            self.wrtc.get_holders()
        self.assertIn("Network unreachable", str(context.exception))

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder_network_error(self, mock_get_token_holders):
        # Simulate network error
        mock_get_token_holders.side_effect = Exception("Node timeout")
        with self.assertRaises(Exception) as context:
            self.wrtc.get_top_holder()
        self.assertIn("Node timeout", str(context.exception))