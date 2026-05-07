"""
Tests for timing-attack prevention fixes (Issues #3959 cluster).

Verifies that secret comparisons use hmac.compare_digest() instead of 
direct == operators, preventing timing side-channel attacks.
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTimingAttackPrevention(unittest.TestCase):
    """Verify all admin/auth comparisons use constant-time comparison."""
    
    FILES_TO_CHECK = [
        ('node/governance.py', 'hmac.compare_digest(admin_key, expected_key)'),
        ('node/rustchain_sync_endpoints.py', 'hmac.compare_digest(key, admin_key)'),
        ('node/sophia_attestation_inspector.py', 'hmac.compare_digest(got, need)'),
        ('node/sophia_governor_review_service.py', 'hmac.compare_digest(provided_admin, required_admin)'),
    ]
    
    def setUp(self):
        self.base = os.path.join(os.path.dirname(__file__), '..')

    def _read_file(self, filename):
        with open(os.path.join(self.base, filename), 'r') as f:
            return f.read()

    def test_governance_uses_hmac(self):
        """governance.py founder_veto must use hmac.compare_digest."""
        source = self._read_file('node/governance.py')
        self.assertIn('hmac.compare_digest(admin_key, expected_key)', source)
        # Ensure no remaining vulnerable comparison
        self.assertNotIn('admin_key != expected_key', source)

    def test_sync_endpoints_uses_hmac(self):
        """rustchain_sync_endpoints.py require_admin must use hmac.compare_digest."""
        source = self._read_file('node/rustchain_sync_endpoints.py')
        self.assertIn('hmac.compare_digest(key, admin_key)', source)
        self.assertNotIn('key != admin_key', source)

    def test_sophia_attestation_uses_hmac(self):
        """sophia_attestation_inspector.py _is_admin must use hmac.compare_digest."""
        source = self._read_file('node/sophia_attestation_inspector.py')
        self.assertIn('hmac.compare_digest(got, need)', source)
        self.assertNotIn('need == got', source)

    def test_sophia_governor_uses_hmac(self):
        """sophia_governor_review_service.py _is_authorized must use hmac.compare_digest."""
        source = self._read_file('node/sophia_governor_review_service.py')
        self.assertIn('hmac.compare_digest(provided_admin, required_admin)', source)
        self.assertNotIn('provided_admin == required_admin', source)

    def test_beacon_api_to_agent_required(self):
        """beacon_api.py update_contract must require to_agent key (no .get default)."""
        source = self._read_file('node/beacon_api.py')
        # The fix: to_agent = contract['to_agent'] (not contract.get('to_agent', ''))
        self.assertIn("to_agent = contract['to_agent']", source)
        self.assertNotIn("contract.get('to_agent', '')", source)


if __name__ == '__main__':
    unittest.main()
