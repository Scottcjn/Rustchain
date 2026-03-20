# SPDX-License-Identifier: MIT

import unittest
import sqlite3
import tempfile
import shutil
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBackupVerify(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.live_db_path = os.path.join(self.test_dir, 'rustchain_v2.db')
        self.backup_db_path = os.path.join(self.test_dir, 'rustchain_v2.db.bak')

        # Create test databases
        self._create_test_database(self.live_db_path, is_backup=False)
        self._create_test_database(self.backup_db_path, is_backup=True)

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir)

    def _create_test_database(self, db_path, is_backup=False):
        """Create a test database with sample data"""
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Create required tables
            cursor.execute('''
                CREATE TABLE balances (
                    address TEXT PRIMARY KEY,
                    amount REAL DEFAULT 0
                )
            ''')

            cursor.execute('''
                CREATE TABLE miner_attest_recent (
                    miner_id TEXT,
                    block_hash TEXT,
                    timestamp INTEGER,
                    epoch INTEGER
                )
            ''')

            cursor.execute('''
                CREATE TABLE headers (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT,
                    prev_hash TEXT,
                    timestamp INTEGER
                )
            ''')

            cursor.execute('''
                CREATE TABLE ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_addr TEXT,
                    to_addr TEXT,
                    amount REAL,
                    timestamp INTEGER
                )
            ''')

            # Add sample data
            cursor.execute("INSERT INTO balances (address, amount) VALUES (?, ?)",
                          ('test_addr_1', 100.0))
            cursor.execute("INSERT INTO headers (height, block_hash, prev_hash, timestamp) VALUES (?, ?, ?, ?)",
                          (1, 'hash1', 'prev_hash1', 1234567890))

            conn.commit()

    def test_verify_backup_integrity(self):
        """Test backup integrity verification"""
        import backup_verify

        result = backup_verify.verify_backup_integrity(self.backup_db_path)
        self.assertTrue(result)

        # Test with non-existent file
        result = backup_verify.verify_backup_integrity('/nonexistent/file.db')
        self.assertFalse(result)

    def test_verify_table_existence(self):
        """Test table existence verification"""
        import backup_verify

        required_tables = ['balances', 'miner_attest_recent', 'headers', 'ledger']
        result = backup_verify.verify_table_existence(self.backup_db_path, required_tables)
        self.assertTrue(result)

        # Test with missing table
        missing_tables = required_tables + ['missing_table']
        result = backup_verify.verify_table_existence(self.backup_db_path, missing_tables)
        self.assertFalse(result)

    def test_get_table_row_counts(self):
        """Test row count retrieval"""
        import backup_verify

        counts = backup_verify.get_table_row_counts(self.backup_db_path)
        self.assertIsInstance(counts, dict)
        self.assertIn('balances', counts)
        self.assertEqual(counts['balances'], 1)
        self.assertEqual(counts['headers'], 1)

    def test_verify_data_consistency(self):
        """Test data consistency verification"""
        import backup_verify

        result = backup_verify.verify_data_consistency(self.live_db_path, self.backup_db_path)
        self.assertTrue(result)

    @patch('backup_verify.find_latest_backup')
    def test_verify_backup_full(self, mock_find_backup):
        """Test full backup verification process"""
        import backup_verify

        mock_find_backup.return_value = self.backup_db_path

        result = backup_verify.verify_backup(self.live_db_path)
        self.assertTrue(result)

    def test_find_latest_backup_no_files(self):
        """Test find_latest_backup with no backup files"""
        import backup_verify

        with patch('backup_verify.BACKUP_PATTERN', '/nonexistent/pattern*'):
            result = backup_verify.find_latest_backup()
            self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
