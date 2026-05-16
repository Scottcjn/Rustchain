"""Test TOCTOU batch ID fix - claims_settlement.py uses SQLite, not /tmp files."""
import unittest
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'node'))

class TestTOCTOUBatchIDFix(unittest.TestCase):
    """Verify batch ID generation uses SQLite instead of /tmp file."""
    
    def setUp(self):
        self.base = os.path.dirname(__file__)

    def _read_file(self, filename):
        with open(os.path.join(self.base, filename), 'r') as f:
            return f.read()

    def test_no_tmp_file_usage(self):
        """claims_settlement.py must not use /tmp files for batch IDs."""
        source = self._read_file('node/claims_settlement.py')
        self.assertNotIn('/tmp/rustchain_settlement_batch', source)

    def test_uses_sqlite_sequence(self):
        """claims_settlement.py must use the settlement DB for batch IDs."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('settlement_batch_sequence', source)
        self.assertIn('BEGIN IMMEDIATE', source)

    def test_batch_id_format(self):
        """verify batch ID keeps the batch_YYYY_MM_DD_NNN format."""
        source = self._read_file('node/claims_settlement.py')
        self.assertIn('f"batch_{batch_day}_{row[0]:03d}"', source)

    def test_no_static_fallback(self):
        """Batch IDs must not fall back to a static 001 suffix."""
        source = self._read_file('node/claims_settlement.py')
        self.assertNotIn('batch_{batch_day}_001', source)
        self.assertNotIn('batch_{timestamp}_001', source)

    def test_generate_batch_id_returns_correct_format(self):
        """generate_batch_id() must return batch_YYYY_MM_DD_NNN."""
        from claims_settlement import generate_batch_id

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "claims.db")
            conn = sqlite3.connect(db_path)
            conn.close()

            batch_id = generate_batch_id(db_path)
            self.assertTrue(batch_id.startswith('batch_'))
            parts = batch_id.split('_')
            self.assertEqual(len(parts), 5)  # batch, YYYY, MM, DD, NNN
            self.assertEqual(parts[4], "001")


if __name__ == '__main__':
    unittest.main()
