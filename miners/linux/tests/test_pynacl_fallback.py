import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import rustchain_linux_miner

class TestPyNaClFallback(unittest.TestCase):
    @patch('rustchain_linux_miner.generate_keypair', side_effect=Exception("Mocked PyNaCl failure"))
    def test_dry_run_fallback(self, mock_generate):
        miner = rustchain_linux_miner.LocalMiner(wallet="test_wallet", verbose=False, persist_key=False)
        self.assertEqual(miner.public_key, "")
        self.assertEqual(miner.keypair, {})

    @patch('rustchain_linux_miner.get_or_create_keypair', side_effect=Exception("Mocked PyNaCl failure"))
    def test_real_execution_throws(self, mock_get):
        with self.assertRaises(Exception) as context:
            rustchain_linux_miner.LocalMiner(wallet="test_wallet", verbose=False, persist_key=True)
        self.assertTrue("Mocked PyNaCl failure" in str(context.exception))

if __name__ == '__main__':
    unittest.main()
