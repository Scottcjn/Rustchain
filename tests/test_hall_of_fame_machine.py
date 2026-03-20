# SPDX-License-Identifier: MIT

import unittest
import sqlite3
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hall_of_fame_machine import app, DB_PATH

class TestHallOfFameMachine(unittest.TestCase):

    def setUp(self):
        """Set up test database and Flask test client."""
        self.db_fd, self.test_db_path = tempfile.mkstemp()
        app.config['TESTING'] = True
        self.client = app.test_client()

        # Mock the DB_PATH to use our test database
        self.original_db_path = DB_PATH
        import hall_of_fame_machine
        hall_of_fame_machine.DB_PATH = self.test_db_path

        # Create test database with sample data
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()

            # Create hall_of_fame table
            cursor.execute('''
                CREATE TABLE hall_of_fame (
                    fingerprint_hash TEXT PRIMARY KEY,
                    machine_name TEXT,
                    first_seen TIMESTAMP,
                    total_attestations INTEGER DEFAULT 0,
                    rust_score INTEGER DEFAULT 0,
                    fleet_rank INTEGER
                )
            ''')

            # Create attestations table
            cursor.execute('''
                CREATE TABLE attestations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint_hash TEXT,
                    epoch INTEGER,
                    rust_score INTEGER,
                    timestamp TIMESTAMP,
                    FOREIGN KEY (fingerprint_hash) REFERENCES hall_of_fame(fingerprint_hash)
                )
            ''')

            # Insert test data
            cursor.execute('''
                INSERT INTO hall_of_fame VALUES
                ('abc123def456', 'Mining Rig Alpha', '2024-01-15 10:30:00', 142, 8750, 1),
                ('def789ghi012', 'Beta Node', '2024-02-01 09:15:00', 98, 7200, 2),
                ('ghi345jkl678', 'Gamma Processor', '2023-12-01 08:00:00', 201, 9100, 3)
            ''')

            # Insert attestation data
            cursor.execute('''
                INSERT INTO attestations (fingerprint_hash, epoch, rust_score, timestamp) VALUES
                ('abc123def456', 1001, 8750, '2024-03-10 14:22:00'),
                ('abc123def456', 1000, 8600, '2024-03-09 14:22:00'),
                ('def789ghi012', 999, 7200, '2024-02-28 16:45:00')
            ''')

            conn.commit()

    def tearDown(self):
        """Clean up test database."""
        # Restore original DB_PATH
        import hall_of_fame_machine
        hall_of_fame_machine.DB_PATH = self.original_db_path

        os.close(self.db_fd)
        os.unlink(self.test_db_path)

    def test_machine_detail_page_success(self):
        """Test machine detail page for existing machine."""
        response = self.client.get('/hall-of-fame/machine?id=abc123def456')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Mining Rig Alpha', response.data)
        self.assertIn(b'abc123def456', response.data)
        self.assertIn(b'8750', response.data)  # rust score

    def test_machine_detail_page_nonexistent(self):
        """Test machine detail page for nonexistent machine."""
        response = self.client.get('/hall-of-fame/machine?id=nonexistent')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Machine not found', response.data)

    def test_machine_detail_page_no_id(self):
        """Test machine detail page without machine ID."""
        response = self.client.get('/hall-of-fame/machine')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Machine ID required', response.data)

    def test_machine_detail_page_with_history(self):
        """Test machine detail page includes attestation history."""
        response = self.client.get('/hall-of-fame/machine?id=abc123def456')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Recent Attestation History', response.data)
        self.assertIn(b'1001', response.data)  # epoch
        self.assertIn(b'1000', response.data)  # previous epoch

if __name__ == '__main__':
    unittest.main()
