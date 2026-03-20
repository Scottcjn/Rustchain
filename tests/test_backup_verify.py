// SPDX-License-Identifier: MIT
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

            cursor.execute('''
                CREATE TABLE epoch_rewards (
                    epoch INTEGER,
                    miner_id TEXT,
                    reward REAL,
                    timestamp INTEGER
                )
            ''')

            # Insert sample data
            cursor.execute('INSERT INTO balances VALUES (?, ?)', ('addr1', 100.5))
            cursor.execute('INSERT INTO balances VALUES (?, ?)', ('addr2', 250.0))

            if is_backup:
                # Backup has slightly less data (older)
                cursor.execute('INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?)',
                              ('miner1', 'hash1', 1640995200, 100))
                cursor.execute('INSERT INTO headers VALUES (?, ?, ?, ?)',
                              (1, 'block1', 'genesis', 1640995200))
                cursor.execute('INSERT INTO ledger VALUES (?, ?, ?, ?, ?)',
                              (1, 'addr1', 'addr2', 50.0, 1640995200))
                cursor.execute('INSERT INTO epoch_rewards VALUES (?, ?, ?, ?)',
                              (100, 'miner1', 10.0, 1640995200))
            else:
                # Live DB has more recent data
                cursor.execute('INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?)',
                              ('miner1', 'hash1', 1640995200, 100))
                cursor.execute('INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?)',
                              ('miner2', 'hash2', 1641000000, 101))

                cursor.execute('INSERT INTO headers VALUES (?, ?, ?, ?)',
                              (1, 'block1', 'genesis', 1640995200))
                cursor.execute('INSERT INTO headers VALUES (?, ?, ?, ?)',
                              (2, 'block2', 'block1', 1641000000))

                cursor.execute('INSERT INTO ledger VALUES (?, ?, ?, ?, ?)',
                              (1, 'addr1', 'addr2', 50.0, 1640995200))
                cursor.execute('INSERT INTO ledger VALUES (?, ?, ?, ?, ?)',
                              (2, 'addr2', 'addr1', 25.0, 1641000000))

                cursor.execute('INSERT INTO epoch_rewards VALUES (?, ?, ?, ?)',
                              (100, 'miner1', 10.0, 1640995200))
                cursor.execute('INSERT INTO epoch_rewards VALUES (?, ?, ?, ?)',
                              (101, 'miner2', 15.0, 1641000000))

    def test_find_latest_backup_file(self):
        """Test finding the latest backup file"""
        from backup_verify import find_latest_backup

        # Test with existing backup
        backup_path = find_latest_backup(self.test_dir)
        self.assertEqual(backup_path, self.backup_db_path)

        # Test with no backup
        empty_dir = tempfile.mkdtemp()
        backup_path = find_latest_backup(empty_dir)
        self.assertIsNone(backup_path)
        shutil.rmtree(empty_dir)

    def test_sqlite_integrity_check(self):
        """Test SQLite integrity check functionality"""
        from backup_verify import check_db_integrity

        # Test valid database
        result = check_db_integrity(self.backup_db_path)
        self.assertTrue(result)

        # Test corrupted database
        corrupt_db = os.path.join(self.test_dir, 'corrupt.db')
        with open(corrupt_db, 'w') as f:
            f.write('not a database')

        result = check_db_integrity(corrupt_db)
        self.assertFalse(result)

    def test_verify_key_tables_exist(self):
        """Test verification that key tables exist and have data"""
        from backup_verify import verify_key_tables

        # Test with valid backup
        result = verify_key_tables(self.backup_db_path)
        self.assertTrue(result['success'])
        self.assertIn('balances', result['tables'])
        self.assertIn('miner_attest_recent', result['tables'])

        # Test with missing table
        incomplete_db = os.path.join(self.test_dir, 'incomplete.db')
        with sqlite3.connect(incomplete_db) as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE balances (address TEXT, amount REAL)')

        result = verify_key_tables(incomplete_db)
        self.assertFalse(result['success'])

    def test_compare_row_counts(self):
        """Test row count comparison between live and backup DBs"""
        from backup_verify import compare_row_counts

        result = compare_row_counts(self.live_db_path, self.backup_db_path)
        self.assertTrue(result['within_tolerance'])

        # Check specific table counts
        self.assertGreaterEqual(result['live_counts']['balances'],
                               result['backup_counts']['balances'])
        self.assertGreaterEqual(result['live_counts']['ledger'],
                               result['backup_counts']['ledger'])

    def test_verify_positive_balances(self):
        """Test verification that balances table has positive amounts"""
        from backup_verify import verify_positive_balances

        result = verify_positive_balances(self.backup_db_path)
        self.assertTrue(result)

        # Test with zero/negative balances
        bad_db = os.path.join(self.test_dir, 'bad_balances.db')
        with sqlite3.connect(bad_db) as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE balances (address TEXT, amount REAL)')
            cursor.execute('INSERT INTO balances VALUES (?, ?)', ('addr1', 0.0))
            cursor.execute('INSERT INTO balances VALUES (?, ?)', ('addr2', -10.0))

        result = verify_positive_balances(bad_db)
        self.assertFalse(result)

    def test_verify_recent_attestations(self):
        """Test verification of recent miner attestations"""
        from backup_verify import verify_recent_attestations

        result = verify_recent_attestations(self.backup_db_path)
        self.assertTrue(result)

        # Test with old attestations
        old_db = os.path.join(self.test_dir, 'old_attestations.db')
        with sqlite3.connect(old_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE miner_attest_recent (
                    miner_id TEXT, block_hash TEXT, timestamp INTEGER, epoch INTEGER
                )
            ''')
            # Very old timestamp
            cursor.execute('INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?)',
                          ('miner1', 'hash1', 1000000000, 1))

        result = verify_recent_attestations(old_db)
        self.assertFalse(result)

    @patch('backup_verify.find_latest_backup')
    def test_full_verification_workflow(self, mock_find_backup):
        """Test the complete backup verification workflow"""
        from backup_verify import verify_backup

        mock_find_backup.return_value = self.backup_db_path

        result = verify_backup(self.live_db_path, backup_dir=self.test_dir)
        self.assertTrue(result['overall_pass'])
        self.assertIn('integrity_check', result)
        self.assertIn('table_verification', result)
        self.assertIn('row_count_comparison', result)

    def test_backup_verification_failure_scenarios(self):
        """Test various failure scenarios in backup verification"""
        from backup_verify import verify_backup

        # Test with non-existent backup directory
        result = verify_backup(self.live_db_path, backup_dir='/nonexistent')
        self.assertFalse(result['overall_pass'])
        self.assertIn('error', result)

        # Test with corrupted backup file
        corrupt_backup = os.path.join(self.test_dir, 'corrupt.db.bak')
        with open(corrupt_backup, 'w') as f:
            f.write('corrupted data')

        with patch('backup_verify.find_latest_backup', return_value=corrupt_backup):
            result = verify_backup(self.live_db_path, backup_dir=self.test_dir)
            self.assertFalse(result['overall_pass'])

    def test_epoch_tolerance_checking(self):
        """Test epoch tolerance in backup age verification"""
        from backup_verify import check_epoch_tolerance

        # Within tolerance (1 epoch difference)
        result = check_epoch_tolerance(101, 100)
        self.assertTrue(result)

        # Exactly at tolerance boundary
        result = check_epoch_tolerance(102, 100)
        self.assertTrue(result)

        # Outside tolerance (more than 2 epochs behind)
        result = check_epoch_tolerance(105, 100)
        self.assertFalse(result)

    def test_temp_file_cleanup(self):
        """Test that temporary files are properly cleaned up"""
        from backup_verify import verify_backup_with_temp_copy

        initial_temp_files = len(os.listdir(tempfile.gettempdir()))

        result = verify_backup_with_temp_copy(self.backup_db_path)

        final_temp_files = len(os.listdir(tempfile.gettempdir()))

        # Should not leave temp files behind
        self.assertEqual(initial_temp_files, final_temp_files)
        self.assertTrue(result['cleanup_success'])

    def test_concurrent_database_access(self):
        """Test backup verification while database is in use"""
        from backup_verify import verify_backup

        # Simulate active database connection
        with sqlite3.connect(self.live_db_path) as conn:
            result = verify_backup(self.live_db_path, backup_dir=self.test_dir)
            self.assertTrue(result['overall_pass'])

    def test_large_database_handling(self):
        """Test verification with larger datasets"""
        large_db = os.path.join(self.test_dir, 'large.db')

        with sqlite3.connect(large_db) as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE balances (address TEXT, amount REAL)')

            # Insert many records
            for i in range(10000):
                cursor.execute('INSERT INTO balances VALUES (?, ?)',
                              (f'addr{i}', float(i + 1)))

        from backup_verify import verify_positive_balances
        result = verify_positive_balances(large_db)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
