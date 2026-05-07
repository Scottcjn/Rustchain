"""
Tests for TOCTOU batch ID fix and miner enrollment fix (Issue #4004 cluster).

1. claims_settlement.py: UUID-based batch IDs prevent TOCTOU race conditions
2. miner.rs: Correct use of public_key_hex instead of wallet in enrollment
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTOCTOUBatchIDFix(unittest.TestCase):
    """Verify batch ID generation uses UUID instead of /tmp file."""
    
    def setUp(self):
        self.base = os.path.join(os.path.dirname(__file__), '..')

    def _read_file(self, filename):
        with open(os.path.join(self.base, filename), 'r') as f:
            return f.read()

    def test_no_tmp_file_usage(self):
        """claims_settlement.py must not use /tmp files for batch IDs."""
        source = self._read_file('node/claims_settlement.py')
        self.assertNotIn('/tmp/rustchain_settlement_batch', source)

    def test_uses_uuid(self):
        """claims_settlement.py must use uuid.uuid4() for batch IDs."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('uuid.uuid4()', source)

    def test_batch_id_format(self):
        """verify batch ID still starts with 'batch_' prefix."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('f"batch_{timestamp}_{unique_suffix}"', source)

    def test_fallback_uses_microseconds(self):
        """Fallback must use microsecond timestamp, not static '001'."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('%H%M%S%f', source)
        self.assertNotIn('batch_{timestamp}_001', source)

class TestMinerEnrollmentFix(unittest.TestCase):
    """Verify miner uses correct public key for enrollment."""

    def setUp(self):
        self.base = os.path.join(os.path.dirname(__file__), '..')

    def _read_file(self, filename):
        with open(os.path.join(self.base, filename), 'r') as f:
            return f.read()

    def test_enroll_uses_public_key_hex(self):
        """miner.rs must use public_key_hex (not wallet) in enrollment."""
        source = self._read_file('rustchain-miner/src/miner.rs')
        self.assertIn('self.public_key_hex, self.miner_id, epoch', source)
        # The old vulnerable pattern should not exist
        self.assertNotIn('self.wallet, self.miner_id, epoch', source)

    def test_miner_pubkey_uses_public_key_hex(self):
        """miner.rs payload must use public_key_hex for miner_pubkey."""
        source = self._read_file('rustchain-miner/src/miner.rs')
        self.assertIn('"miner_pubkey": self.public_key_hex', source)


if __name__ == '__main__':
    unittest.main()
