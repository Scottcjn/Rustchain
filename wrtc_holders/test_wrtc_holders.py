// File: wrtc_holders/test_wrtc_holders.py
# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch, MagicMock
from wrtc_holders import WRTC
from solana_client import SolanaClient

class TestWRTC(unittest.TestCase):
    def setUp(self):
        self.solana_client = SolanaClient("https://api.devnet.solana.com")
        self.wrtc = WRTC(self.solana_client)

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_holders(self, mock_get_token_holders):
        # Mock the response from SolanaClient
        mock_get_token_holders.return_value = [
            {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
            {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000},
            {"address": "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 500},
            {"address": "Dk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 200}
        ]
        holders = self.wrtc.get_holders()
        self.assertEqual(len(holders), 4)
        self.assertEqual(holders[0]['address'], "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder(self, mock_get_token_holders):
        mock_get_token_holders.return_value = [
            {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
            {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000}
        ]
        top_holder = self.wrtc.get_top_holder()
        self.assertEqual(top_holder['address'], "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")

    @patch.object(SolanaClient, 'get_token_holders')
    def test_get_top_holder_balance(self, mock_get_token_holders):
        mock_get_token_holders.return_value = [
            {"address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW", "amount": 8296082},
            {"address": "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM", "amount": 1000}
        ]
        balance = self.wrtc.get_top_holder_balance()
        self.assertEqual(balance, 8296082)