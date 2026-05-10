"""Test TOCTOU batch ID fix - claims_settlement.py uses UUID, not /tmp files."""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'node'))

class TestTOCTOUBatchIDFix(unittest.TestCase):
    """Verify batch ID generation uses UUID instead of /tmp file."""
    
    def setUp(self):
        self.base = os.path.dirname(__file__)

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
        """verify batch ID starts with 'batch_' prefix."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('f"batch_{timestamp}_{unique_suffix}"', source)

    def test_fallback_uses_microseconds(self):
        """Fallback must use microsecond timestamp, not static '001'."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('%H%M%S%f', source)
        self.assertNotIn('batch_{timestamp}_001', source)

    def test_generate_batch_id_returns_correct_format(self):
        """generate_batch_id() must return batch_YYYY_MM_DD_<8chars>."""
        from claims_settlement import generate_batch_id
        batch_id = generate_batch_id()
        self.assertTrue(batch_id.startswith('batch_'))
        parts = batch_id.split('_')
        self.assertEqual(len(parts), 5)  # batch, YYYY, MM, DD, <uuid8>
        self.assertEqual(len(parts[4]), 8)  # uuid suffix is 8 chars


if __name__ == '__main__':
    unittest.main()
