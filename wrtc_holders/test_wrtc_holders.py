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
        mock_get_token_holders.return_value = json.loads('''
            [
                {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
                {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000}
            ]
        ''')
        top_holder = self.wrtc.get_top_holder()
        self.assertEqual(top_holder['address'], "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")
        self.assertEqual(top_holder['amount'], 8296082)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_empty_response(self, mock_get_token_holders):
        mock_get_token_holders.return_value = json.loads('''
            []
        ''')
        holders = self.wrtc.get_holders()
        self.assertEqual(len(holders), 0)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders_invalid_response(self, mock_get_token_holders):
        mock_get_token_holders.return_value = json.loads('''
            {"error": "Invalid response"}
        ''')
        with self.assertRaises(json.JSONDecodeError):
            self.wrtc.get_holders()

if __name__ == '__main__':
    unittest.main()