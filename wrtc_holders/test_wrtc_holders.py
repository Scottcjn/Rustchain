import unittest
from wrtc_holders import WRTC

class TestWRTC(unittest.TestCase):
    def test_get_holders(self):
        solana_client = SolanaClient("https://api.devnet.solana.com")
        wrtc = WRTC(solana_client)
        holders = wrtc.get_holders()
        self.assertEqual(len(holders), 4)

    def test_get_top_holder(self):
        solana_client = SolanaClient("https://api.devnet.solana.com")
        wrtc = WRTC(solana_client)
        top_holder = wrtc.get_top_holder()
        self.assertEqual(top_holder.address, "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW")

    def test_get_top_holder_balance(self):
        solana_client = SolanaClient("https://api.devnet.solana.com")
        wrtc = WRTC(solana_client)
        balance = wrtc.get_top_holder_balance()
        self.assertEqual(balance, 8296082)

    def test_get_top_holder_percentage(self):
        solana_client = SolanaClient("https://api.devnet.solana.com")
        wrtc = WRTC(solana_client)
        percentage = wrtc.get_top_holder_percentage()
        self.assertEqual(percentage, 99.97)

if __name__ == "__main__":
    unittest.main()