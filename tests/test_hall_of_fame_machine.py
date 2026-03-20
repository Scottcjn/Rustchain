// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import sqlite3
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

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

    def test_machine_detail_page(self):
        """Test the machine detail page renders correctly for active machine."""
        response = self.client.get('/hall-of-fame/?machine=abc123def456')
        self.assertEqual(response.status_code, 200)

        # Check that machine details are present
        data = response.get_data(as_text=True)
        self.assertIn('Mining Rig Alpha', data)
        self.assertIn('8750', data)  # rust_score
        self.assertIn('142', data)   # epochs_participated
        self.assertIn('2024-01-15', data)  # first_attestation date
        self.assertIn('active', data)

        # Check for proper styling/structure
        self.assertIn('machine-detail', data)
        self.assertIn('rust-score', data)

    def test_api_machine_endpoint(self):
        """Test the API endpoint returns correct JSON data."""
        response = self.client.get('/api/machine/ghi345jkl678')
        self.assertEqual(response.status_code, 200)

        json_data = response.get_json()
        self.assertEqual(json_data['fingerprint_hash'], 'ghi345jkl678')
        self.assertEqual(json_data['name'], 'Gamma Processor')
        self.assertEqual(json_data['rust_score'], 9100)
        self.assertEqual(json_data['epochs_participated'], 201)
        self.assertEqual(json_data['status'], 'active')

        # Check date format
        self.assertIn('first_attestation', json_data)
        self.assertIn('last_seen', json_data)

    def test_deceased_machine_styling(self):
        """Test that deceased machines display with proper styling."""
        response = self.client.get('/hall-of-fame/?machine=def789ghi012')
        self.assertEqual(response.status_code, 200)

        data = response.get_data(as_text=True)
        self.assertIn('Beta Node', data)
        self.assertIn('deceased', data)

        # Check for deceased-specific styling
        self.assertIn('machine-deceased', data)
        self.assertIn('7200', data)  # rust_score should still be shown
        self.assertIn('98', data)    # epochs_participated

        # Should indicate machine is no longer active
        self.assertIn('Last Seen:', data)

    def test_invalid_machine_id(self):
        """Test handling of non-existent machine IDs."""
        response = self.client.get('/hall-of-fame/?machine=nonexistent123')
        self.assertEqual(response.status_code, 404)

        data = response.get_data(as_text=True)
        self.assertIn('Machine not found', data)

        # Test API endpoint with invalid ID
        response = self.client.get('/api/machine/invalid456')
        self.assertEqual(response.status_code, 404)

        json_data = response.get_json()
        self.assertEqual(json_data['error'], 'Machine not found')

    def test_machine_comparison_data(self):
        """Test that machine page includes fleet comparison data."""
        response = self.client.get('/hall-of-fame/?machine=abc123def456')
        self.assertEqual(response.status_code, 200)

        data = response.get_data(as_text=True)
        # Should show how this machine compares to fleet average
        self.assertIn('fleet', data.lower())
        self.assertIn('average', data.lower())

    def test_hall_of_fame_main_page_links(self):
        """Test that main hall of fame page has clickable machine links."""
        response = self.client.get('/hall-of-fame/')
        self.assertEqual(response.status_code, 200)

        data = response.get_data(as_text=True)
        # Should contain links to machine detail pages
        self.assertIn('?machine=abc123def456', data)
        self.assertIn('?machine=def789ghi012', data)
        self.assertIn('?machine=ghi345jkl678', data)

        # Machine names should be clickable
        self.assertIn('href=', data)

    @patch('sqlite3.connect')
    def test_database_error_handling(self, mock_connect):
        """Test graceful handling of database connection errors."""
        mock_connect.side_effect = sqlite3.Error("Database connection failed")

        response = self.client.get('/hall-of-fame/?machine=abc123def456')
        self.assertEqual(response.status_code, 500)

        # API should also handle errors gracefully
        response = self.client.get('/api/machine/abc123def456')
        self.assertEqual(response.status_code, 500)

if __name__ == '__main__':
    unittest.main()
