// File: wrtc_holders/test_wrtc_holders.py
# SPDX-License-Identifier: MIT
import unittest
from unittest.mock import patch, MagicMock
from wrtc_holders import WRTC
from solana_client import SolanaClient
import json


def _validate_holders(holders):
    if not isinstance(holders, list):
        raise ValueError("Holders must be a list")
    for holder in holders:
        if not isinstance(holder, dict):
            raise ValueError("Each holder must be a dictionary")
        required_keys = ["address", "amount"]
        if not all(key in holder for key in required_keys):
            raise ValueError(f"Each holder must have '{required_keys}' keys")


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
        _validate_holders(holders)
        self.assertEqual(len(holders), 4)
        self.assertEqual(holders[0]['address'], "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")
        self.assertEqual(holders[0]['amount'], 8296082)
        self.assertEqual(holders[1]['address'], "Bk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM")
        self.assertEqual(holders[1]['amount'], 1000)
        self.assertEqual(holders[2]['address'], "Ck9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM")
        self.assertEqual(holders[2]['amount'], 500)
        self.assertEqual(holders[3]['address'], "Dk9gDyK6nZGdfevAzJdGmGtiqF3MEyZm1S7v11J2q3pM")
        self.assertEqual(holders[3]['amount'], 200)

if __name__ == '__main__':
    unittest.main()