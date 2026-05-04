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
    def test_get_top_holder_empty(self, mock_get_token_holders):
        # Mock empty response
        mock_get_token_holders.return_value = []
        top_holder = self.wrtc.get_top_holder()
        self.assertIsNone(top_holder)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_with_minimum_balance(self, mock_get_token_holders):
        # Mock the response from SolanaClient
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000},
                {"address": "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 500},
                {"address": "Dk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 200}
            ]
        ''')
        holders = self.wrtc.get_holders_with_minimum_balance(600)
        self.assertEqual(len(holders), 2)
        self.assertEqual(holders[0]['amount'], 8296082)
        self.assertEqual(holders[1]['amount'], 1000)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_with_minimum_balance_no_matches(self, mock_get_token_holders):
        # Mock the response from SolanaClient
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000},
                {"address": "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 500},
                {"address": "Dk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 200}
            ]
        ''')
        holders = self.wrtc.get_holders_with_minimum_balance(2000)
        self.assertEqual(len(holders), 0)

    def test_calculate_incentive_share(self):
        total_supply = 1000000
        holder_balance = 10000
        expected_share = (holder_balance / total_supply) * 100
        share = self.wrtc.calculate_incentive_share(holder_balance, total_supply)
        self.assertAlmostEqual(share, expected_share, places=5)

    def test_calculate_incentive_share_zero_supply(self):
        total_supply = 0
        holder_balance = 10000
        with self.assertRaises(ValueError) as context:
            self.wrtc.calculate_incentive_share(holder_balance, total_supply)
        self.assertEqual(str(context.exception), "Total supply must be greater than zero.")

    def test_calculate_incentive_share_negative_balance(self):
        total_supply = 1000000
        holder_balance = -1000
        with self.assertRaises(ValueError) as context:
            self.wrtc.calculate_incentive_share(holder_balance, total_supply)
        self.assertEqual(str(context.exception), "Holder balance cannot be negative.")

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_network_error(self, mock_get_token_holders):
        # Simulate network error
        mock_get_token_holders.side_effect = Exception("Network error: failed to connect")
        with self.assertRaises(Exception) as context:
            self.wrtc.get_holders()
        self.assertIn("Network error", str(context.exception))

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_invalid_json_response(self, mock_get_token_holders):
        # Simulate invalid JSON response
        mock_get_token_holders.return_value = "invalid json"
        with patch('json.loads', side_effect=json.JSONDecodeError("Expecting value", "doc", 0)):
            with self.assertRaises(json.JSONDecodeError):
                self.wrtc.get_holders()


if __name__ == '__main__':
    unittest.main()