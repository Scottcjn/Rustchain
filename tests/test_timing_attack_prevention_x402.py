"""
Tests for timing-attack prevention fixes (x402 cluster).

Verifies that secret comparisons in x402 and Machine Passport endpoints 
use hmac.compare_digest() instead of direct == operators.
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTimingAttackPreventionX402(unittest.TestCase):
    """Verify admin/auth comparisons in x402-related modules use constant-time comparison."""
    
    def setUp(self):
        self.base = os.path.join(os.path.dirname(__file__), '..')

    def _read_file(self, filename):
        with open(os.path.join(self.base, filename), 'r') as f:
            return f.read()

    def test_beacon_x402_uses_hmac(self):
        """beacon_x402.py set_agent_wallet must use hmac.compare_digest."""
        source = self._read_file('node/beacon_x402.py')
        self.assertIn('hmac.compare_digest(admin_key, expected)', source)
        self.assertNotIn('admin_key != expected', source)

    def test_rustchain_x402_uses_hmac(self):
        """rustchain_x402.py wallet_link_coinbase must use hmac.compare_digest."""
        source = self._read_file('node/rustchain_x402.py')
        self.assertIn('hmac.compare_digest(admin_key, expected)', source)
        self.assertNotIn('admin_key != expected', source)

    def test_machine_passport_api_uses_hmac(self):
        """machine_passport_api.py must use hmac.compare_digest for admin checks."""
        source = self._read_file('node/machine_passport_api.py')
        self.assertIn('hmac.compare_digest(admin_key, expected_admin_key)', source)
        # Ensure no remaining vulnerable comparison
        self.assertNotIn('admin_key != expected_admin_key', source)

    def test_p2p_rips_uses_secure_nonce(self):
        """rips/rustchain-core/networking/p2p.py must use secrets.token_bytes for nonce."""
        source = self._read_file('rips/rustchain-core/networking/p2p.py')
        self.assertIn('secrets.token_bytes(4)', source)
        self.assertNotIn('hashlib.sha256(str(time.time())', source)


if __name__ == '__main__':
    unittest.main()
