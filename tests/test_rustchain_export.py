# SPDX-License-Identifier: MIT
"""
Comprehensive test suite for RustChain attestation data export functionality.
Tests CLI parsing, API fetching, database operations, export formats, and error handling.
"""

import csv
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch, MagicMock, mock_open

import sys
sys.path.insert(0, '.')
from rustchain_export import (
    parse_arguments, fetch_attestation_data, query_database,
    export_to_csv, export_to_json, export_to_parquet, main
)


class TestRustChainExport(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Setup test database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE attestations (
                    id INTEGER PRIMARY KEY,
                    miner_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    hardware_type TEXT,
                    cpu_model TEXT,
                    architecture TEXT,
                    verification_status TEXT,
                    attestation_hash TEXT,
                    block_height INTEGER,
                    reward_multiplier REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert test data
            test_data = [
                ('miner_001', '2024-01-15 10:30:00', 'PowerPC G4', 'MPC7447A', 'powerpc',
                 'verified', 'abc123def456', 1000, 2.5, '2024-01-15 10:30:00'),
                ('miner_002', '2024-01-16 14:20:00', 'PowerPC G5', 'PPC970FX', 'powerpc64',
                 'verified', 'def789abc012', 1001, 3.0, '2024-01-16 14:20:00'),
                ('miner_003', '2024-01-17 09:15:00', '68K Mac', 'MC68030', 'm68k',
                 'pending', 'ghi345jkl678', 1002, 4.0, '2024-01-17 09:15:00'),
                ('miner_001', '2024-01-18 16:45:00', 'PowerPC G4', 'MPC7447A', 'powerpc',
                 'failed', 'mno901pqr234', 1003, 0.0, '2024-01-18 16:45:00'),
            ]

            cursor.executemany("""
                INSERT INTO attestations
                (miner_id, timestamp, hardware_type, cpu_model, architecture,
                 verification_status, attestation_hash, block_height, reward_multiplier, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, test_data)
            conn.commit()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_parse_arguments_default(self):
        """Test CLI argument parsing with default values"""
        test_args = ['--database', '/tmp/test.db']
        args = parse_arguments(test_args)

        self.assertEqual(args.database, '/tmp/test.db')
        self.assertEqual(args.format, 'csv')
        self.assertEqual(args.output, 'attestations_export')
        self.assertIsNone(args.start_date)
        self.assertIsNone(args.end_date)
        self.assertIsNone(args.miner_id)

    def test_parse_arguments_full(self):
        """Test CLI parsing with all arguments"""
        test_args = [
            '--database', '/path/to/db.sqlite',
            '--format', 'json',
            '--output', 'my_export',
            '--start-date', '2024-01-01',
            '--end-date', '2024-12-31',
            '--miner-id', 'miner_123',
            '--status', 'verified'
        ]
        args = parse_arguments(test_args)

        self.assertEqual(args.database, '/path/to/db.sqlite')
        self.assertEqual(args.format, 'json')
        self.assertEqual(args.output, 'my_export')
        self.assertEqual(args.start_date, '2024-01-01')
        self.assertEqual(args.end_date, '2024-12-31')
        self.assertEqual(args.miner_id, 'miner_123')
        self.assertEqual(args.status, 'verified')

    @patch('rustchain_export.requests.get')
    def test_fetch_attestation_data_success(self, mock_get):
        """Test successful API data fetching"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'attestations': [
                {
                    'miner_id': 'api_miner_001',
                    'timestamp': '2024-01-20T12:00:00Z',
                    'hardware_type': 'SPARC',
                    'verification_status': 'verified'
                }
            ]
        }
        mock_get.return_value = mock_response

        data = fetch_attestation_data('https://test-api.com/attestations')

        self.assertIsNotNone(data)
        self.assertEqual(len(data['attestations']), 1)
        self.assertEqual(data['attestations'][0]['miner_id'], 'api_miner_001')
        mock_get.assert_called_once_with('https://test-api.com/attestations', timeout=30)

    @patch('rustchain_export.requests.get')
    def test_fetch_attestation_data_failure(self, mock_get):
        """Test API fetch with network error"""
        mock_get.side_effect = Exception('Connection timeout')

        data = fetch_attestation_data('https://broken-api.com/data')

        self.assertIsNone(data)

    def test_query_database_all_data(self):
        """Test database query without filters"""
        results = query_database(self.db_path)

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]['miner_id'], 'miner_001')
        self.assertEqual(results[1]['hardware_type'], 'PowerPC G5')

    def test_query_database_with_date_filter(self):
        """Test database query with date range filtering"""
        results = query_database(
            self.db_path,
            start_date='2024-01-16',
            end_date='2024-01-17'
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['miner_id'], 'miner_002')
        self.assertEqual(results[1]['miner_id'], 'miner_003')

    def test_query_database_with_miner_filter(self):
        """Test database query filtered by specific miner"""
        results = query_database(self.db_path, miner_id='miner_001')

        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result['miner_id'], 'miner_001')

    def test_query_database_with_status_filter(self):
        """Test database query filtered by verification status"""
        results = query_database(self.db_path, status='verified')

        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result['verification_status'], 'verified')

    def test_query_database_combined_filters(self):
        """Test database query with multiple filters"""
        results = query_database(
            self.db_path,
            miner_id='miner_001',
            status='verified',
            start_date='2024-01-15'
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['miner_id'], 'miner_001')
        self.assertEqual(results[0]['verification_status'], 'verified')

    def test_query_database_invalid_path(self):
        """Test database query with invalid database path"""
        with self.assertRaises(Exception):
            query_database('/nonexistent/database.db')

    @patch('builtins.open', new_callable=mock_open)
    def test_export_to_csv(self, mock_file):
        """Test CSV export functionality"""
        test_data = [
            {
                'miner_id': 'test_miner',
                'timestamp': '2024-01-15 10:30:00',
                'hardware_type': 'PowerPC G4',
                'verification_status': 'verified'
            }
        ]

        export_to_csv(test_data, 'test_export.csv')

        mock_file.assert_called_once_with('test_export.csv', 'w', newline='')
        handle = mock_file()

        # Check that CSV data was written
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn('miner_id', written_data)
        self.assertIn('test_miner', written_data)

    @patch('builtins.open', new_callable=mock_open)
    def test_export_to_json(self, mock_file):
        """Test JSON export functionality"""
        test_data = [
            {
                'miner_id': 'json_miner',
                'verification_status': 'verified',
                'block_height': 1500
            }
        ]

        export_to_json(test_data, 'test_export.json')

        mock_file.assert_called_once_with('test_export.json', 'w')
        handle = mock_file()

        # Verify JSON was written
        written_calls = handle.write.call_args_list
        self.assertTrue(len(written_calls) > 0)

    def test_export_to_json_empty_data(self):
        """Test JSON export with empty dataset"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
            export_to_json([], tmp.name)

        with open(tmp.name, 'r') as f:
            data = json.load(f)

        self.assertEqual(data, [])
        os.unlink(tmp.name)

    @patch('rustchain_export.pd')
    def test_export_to_parquet_success(self, mock_pandas):
        """Test successful Parquet export"""
        mock_df = MagicMock()
        mock_pandas.DataFrame.return_value = mock_df

        test_data = [{'miner_id': 'parquet_test', 'block_height': 2000}]

        export_to_parquet(test_data, 'test_export.parquet')

        mock_pandas.DataFrame.assert_called_once_with(test_data)
        mock_df.to_parquet.assert_called_once_with('test_export.parquet', index=False)

    @patch('rustchain_export.pd', None)
    def test_export_to_parquet_no_pandas(self):
        """Test Parquet export when pandas is not available"""
        test_data = [{'miner_id': 'test'}]

        with self.assertRaises(ImportError) as context:
            export_to_parquet(test_data, 'test.parquet')

        self.assertIn('pandas', str(context.exception))

    def test_real_csv_export_integration(self):
        """Integration test: query database and export to real CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            csv_path = tmp.name

        # Query test data
        results = query_database(self.db_path, status='verified')

        # Export to CSV
        export_to_csv(results, csv_path)

        # Verify CSV contents
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['miner_id'], 'miner_001')
        self.assertEqual(rows[1]['miner_id'], 'miner_002')

        os.unlink(csv_path)

    @patch('rustchain_export.query_database')
    @patch('rustchain_export.export_to_csv')
    def test_main_function_csv_export(self, mock_export_csv, mock_query):
        """Test main function with CSV export"""
        mock_query.return_value = [{'miner_id': 'test', 'status': 'verified'}]

        test_args = [
            '--database', self.db_path,
            '--format', 'csv',
            '--output', 'main_test'
        ]

        with patch('sys.argv', ['rustchain_export.py'] + test_args):
            main()

        mock_query.assert_called_once()
        mock_export_csv.assert_called_once_with(
            [{'miner_id': 'test', 'status': 'verified'}],
            'main_test.csv'
        )

    @patch('rustchain_export.query_database')
    @patch('rustchain_export.export_to_json')
    def test_main_function_json_export(self, mock_export_json, mock_query):
        """Test main function with JSON export"""
        mock_query.return_value = [{'data': 'test'}]

        test_args = [
            '--database', self.db_path,
            '--format', 'json',
            '--miner-id', 'specific_miner'
        ]

        with patch('sys.argv', ['rustchain_export.py'] + test_args):
            main()

        mock_query.assert_called_once()
        args = mock_query.call_args[1]
        self.assertEqual(args['miner_id'], 'specific_miner')
        mock_export_json.assert_called_once()

    def test_date_range_validation_in_query(self):
        """Test that date filtering works correctly with edge cases"""
        # Test exact date match
        results = query_database(
            self.db_path,
            start_date='2024-01-16',
            end_date='2024-01-16'
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['miner_id'], 'miner_002')

        # Test no results in range
        results = query_database(
            self.db_path,
            start_date='2024-01-01',
            end_date='2024-01-10'
        )
        self.assertEqual(len(results), 0)

    def test_database_schema_compatibility(self):
        """Test that query works with expected database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(attestations)")
            columns = [row[1] for row in cursor.fetchall()]

        expected_columns = [
            'id', 'miner_id', 'timestamp', 'hardware_type', 'cpu_model',
            'architecture', 'verification_status', 'attestation_hash',
            'block_height', 'reward_multiplier', 'created_at'
        ]

        for col in expected_columns:
            self.assertIn(col, columns)


if __name__ == '__main__':
    unittest.main()
