import unittest
import os
import warnings
from rustchain.client import RustChainClient

class TestRustChainClientLive(unittest.TestCase):
    def setUp(self):
        # Disable SSL warnings for tests
        warnings.filterwarnings('ignore', message='Unverified HTTPS request')
        self.client = RustChainClient(verify_ssl=False)

    def test_health(self):
        try:
            health = self.client.get_health()
            print(f"\nNode Version: {health.version}")
            self.assertTrue(health.ok)
        except Exception as e:
            self.fail(f"Health check failed: {e}")

    def test_epoch(self):
        try:
            epoch = self.client.get_epoch()
            print(f"Epoch: {epoch.epoch}")
            self.assertGreaterEqual(epoch.epoch, 0)
        except Exception as e:
            self.fail(f"Epoch check failed: {e}")

    def test_miners(self):
        try:
            miners = self.client.get_miners()
            print(f"Active Miners: {len(miners)}")
            self.assertIsInstance(miners, list)
        except Exception as e:
            self.fail(f"Miners check failed: {e}")

if __name__ == '__main__':
    unittest.main()
