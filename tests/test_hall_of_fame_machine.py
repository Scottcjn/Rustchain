# SPDX-License-Identifier: MIT

import unittest
import sqlite3
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hall_of_fame_machine import app

class TestHallOfFameMachine(unittest.TestCase):

    def setUp(self):
        """Set up test database and Flask test client."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.config['TESTING'] = True
        app.config['DATABASE'] = self.db_path
        self.client = app.test_client()

        # Create test database with sample data
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create machines table
            cursor.execute('''
                CREATE TABLE machines (
                    fingerprint_hash TEXT PRIMARY KEY,
                    name TEXT,
                    rust_score INTEGER,
                    epochs_participated INTEGER,
                    first_attestation TIMESTAMP,
                    last_seen TIMESTAMP,
                    status TEXT,
                    operator_email TEXT
                )
            ''')

            # Insert test data
            cursor.execute('''
                INSERT INTO machines VALUES
                ('abc123def456', 'Mining Rig Alpha', 8750, 142,
                 '2024-01-15 10:30:00', '2024-03-10 14:22:00', 'active', 'operator@example.com'),
                ('def789ghi012', 'Beta Node', 7200, 98,
                 '2024-02-01 09:15:00', '2024-02-28 16:45:00', 'deceased', 'beta@test.com'),
                ('ghi345jkl678', 'Gamma Processor', 9100, 201,
                 '2023-12-01 08:00:00', '2024-03-11 11:30:00', 'active', 'gamma@node.org')
            ''')

            conn.commit()

    def tearDown(self):
        """Clean up test database."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_machine_detail_page_missing_id(self):
        """Test machine detail page without machine ID."""
        response = self.client.get('/hall-of-fame/machine')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Machine ID required', response.data)

    def test_machine_detail_page_nonexistent(self):
        """Test machine detail page for nonexistent machine."""
        response = self.client.get('/hall-of-fame/machine?id=nonexistent')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Machine not found', response.data)

    @patch('hall_of_fame_machine.get_machine_details')
    def test_machine_detail_page_success(self, mock_get_details):
        """Test successful machine detail page rendering."""
        mock_get_details.return_value = {
            'machine': {
                'fingerprint_hash': 'abc123def456',
                'machine_name': 'Test Machine',
                'first_seen': '2024-01-01',
                'total_attestations': 100,
                'rust_score': 8500,
                'fleet_rank': 5
            },
            'attestation_history': [
                {'epoch': 1000, 'rust_score': 8500, 'timestamp': '2024-03-01 12:00:00'}
            ],
            'fleet_stats': {'avg_score': 8000, 'total_machines': 50}
        }

        response = self.client.get('/hall-of-fame/machine?id=abc123def456')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Machine', response.data)
        self.assertIn(b'abc123def456', response.data)

if __name__ == '__main__':
    unittest.main()
