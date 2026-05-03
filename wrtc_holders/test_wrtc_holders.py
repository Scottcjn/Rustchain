// File: wrtc_holders/test_wrtc_holders.py
# SPDX-License-Identifier: MIT
import unittest
from wrtc_holders import WRTC
from solana_client import SolanaClient

class TestWRTC(unittest.TestCase):
    def setUp(self):
        self.solana_client = SolanaClient("https://api.devnet.solana.com")
        self.wrtc = WRTC(self.solana_client)

    def test_get_holders(self):
        holders = self.wrtc.get_holders()
        self.assertEqual(len(holders), 4)

    def test_get_top_holder(self):
        top_holder = self.wrtc.get_top_holder()
        self.assertEqual(top_holder.address, "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")

    def test_get_top_holder_balance(self):
        balance = self.wrtc.get_top_holder_balance()
        self.assertEqual(balance, 8296082)

    def test_get_top_holder_percentage(self):
        percentage = self.wrtc.get_top_holder_percentage()
        self.assertEqual(percentage, 99.97)

    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()