// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import json
import csv
import os
import tempfile
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
sys.path.append('.')

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from export_pipeline import ExportPipeline, ExportFormat


class TestExportPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.temp_dir, 'test.db')
        self.pipeline = ExportPipeline(self.test_db)
        self.setup_test_database()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.unlink(self.test_db)
        for file in os.listdir(self.temp_dir):
            os.unlink(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    def setup_test_database(self):
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()

            # Create attestations table
            cursor.execute('''
                CREATE TABLE attestations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_id TEXT NOT NULL,
                    attestation_data TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    hardware_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create blocks table
            cursor.execute('''
                CREATE TABLE blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT,
                    merkle_root TEXT,
                    timestamp TEXT NOT NULL,
                    miner_id TEXT,
                    nonce INTEGER,
                    difficulty REAL,
                    height INTEGER
                )
            ''')

            # Create miners table
            cursor.execute('''
                CREATE TABLE miners (
                    id TEXT PRIMARY KEY,
                    public_key TEXT,
                    hardware_fingerprint TEXT,
                    last_seen TEXT,
                    total_blocks INTEGER DEFAULT 0,
                    hardware_type TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')

            # Insert test data
            now = datetime.now()
            yesterday = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            test_attestations = [
                ('miner_001', '{"cpu":"PowerPC G4","ram":"2GB"}', now.isoformat(), 'verified', 'PowerPC', now.isoformat()),
                ('miner_002', '{"cpu":"68K","ram":"8MB"}', yesterday.isoformat(), 'verified', '68K', yesterday.isoformat()),
                ('miner_003', '{"cpu":"SPARC","ram":"1GB"}', week_ago.isoformat(), 'pending', 'SPARC', week_ago.isoformat())
            ]

            cursor.executemany(
                'INSERT INTO attestations (miner_id, attestation_data, timestamp, status, hardware_type, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                test_attestations
            )

            test_blocks = [
                ('hash001', 'genesis', 'merkle001', now.isoformat(), 'miner_001', 12345, 1.0, 1),
                ('hash002', 'hash001', 'merkle002', yesterday.isoformat(), 'miner_002', 67890, 1.2, 2),
                ('hash003', 'hash002', 'merkle003', week_ago.isoformat(), 'miner_003', 54321, 0.8, 3)
            ]

            cursor.executemany(
                'INSERT INTO blocks (hash, previous_hash, merkle_root, timestamp, miner_id, nonce, difficulty, height) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                test_blocks
            )

            test_miners = [
                ('miner_001', 'pubkey001', 'fp001', now.isoformat(), 5, 'PowerPC', 'active'),
                ('miner_002', 'pubkey002', 'fp002', yesterday.isoformat(), 3, '68K', 'active'),
                ('miner_003', 'pubkey003', 'fp003', week_ago.isoformat(), 1, 'SPARC', 'inactive')
            ]

            cursor.executemany(
                'INSERT INTO miners (id, public_key, hardware_fingerprint, last_seen, total_blocks, hardware_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                test_miners
            )

            conn.commit()

    def test_csv_export_attestations(self):
        output_file = os.path.join(self.temp_dir, 'attestations.csv')
        result = self.pipeline.export_attestations(ExportFormat.CSV, output_file)

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(output_file))

        with open(output_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 3)
        self.assertIn('miner_id', rows[0])
        self.assertIn('attestation_data', rows[0])
        self.assertIn('timestamp', rows[0])
        self.assertEqual(rows[0]['miner_id'], 'miner_001')

    def test_json_export_attestations(self):
        output_file = os.path.join(self.temp_dir, 'attestations.json')
        result = self.pipeline.export_attestations(ExportFormat.JSON, output_file)

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(output_file))

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 3)
        self.assertIn('miner_id', data[0])
        self.assertEqual(data[0]['miner_id'], 'miner_001')

    @unittest.skipUnless(PANDAS_AVAILABLE, "pandas not available")
    def test_parquet_export_attestations(self):
        output_file = os.path.join(self.temp_dir, 'attestations.parquet')
        result = self.pipeline.export_attestations(ExportFormat.PARQUET, output_file)

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(output_file))

        df = pd.read_parquet(output_file)
        self.assertEqual(len(df), 3)
        self.assertIn('miner_id', df.columns)

    def test_date_filtering(self):
        yesterday = datetime.now() - timedelta(days=1)
        start_date = yesterday.strftime('%Y-%m-%d')

        output_file = os.path.join(self.temp_dir, 'filtered.json')
        result = self.pipeline.export_attestations(
            ExportFormat.JSON,
            output_file,
            start_date=start_date
        )

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        # Should filter out week-old record
        self.assertEqual(len(data), 2)

    def test_hardware_type_filtering(self):
        output_file = os.path.join(self.temp_dir, 'powerpc_only.json')
        result = self.pipeline.export_attestations(
            ExportFormat.JSON,
            output_file,
            hardware_type='PowerPC'
        )

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['hardware_type'], 'PowerPC')

    def test_status_filtering(self):
        output_file = os.path.join(self.temp_dir, 'verified_only.json')
        result = self.pipeline.export_attestations(
            ExportFormat.JSON,
            output_file,
            status='verified'
        )

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 2)
        for record in data:
            self.assertEqual(record['status'], 'verified')

    def test_blocks_export(self):
        output_file = os.path.join(self.temp_dir, 'blocks.json')
        result = self.pipeline.export_blocks(ExportFormat.JSON, output_file)

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 3)
        self.assertIn('hash', data[0])
        self.assertIn('height', data[0])

    def test_miners_export(self):
        output_file = os.path.join(self.temp_dir, 'miners.csv')
        result = self.pipeline.export_miners(ExportFormat.CSV, output_file)

        self.assertTrue(result['success'])

        with open(output_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 3)
        self.assertIn('id', rows[0])
        self.assertIn('hardware_type', rows[0])

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            self.pipeline.export_attestations('INVALID', 'test.txt')

    def test_database_error_handling(self):
        # Use non-existent database
        bad_pipeline = ExportPipeline('/nonexistent/path/db.sqlite')
        output_file = os.path.join(self.temp_dir, 'fail.json')

        result = bad_pipeline.export_attestations(ExportFormat.JSON, output_file)

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_file_write_permission_error(self):
        # Try to write to directory without permissions
        restricted_file = '/root/restricted.json'
        result = self.pipeline.export_attestations(ExportFormat.JSON, restricted_file)

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_empty_result_set(self):
        # Filter for non-existent hardware type
        output_file = os.path.join(self.temp_dir, 'empty.json')
        result = self.pipeline.export_attestations(
            ExportFormat.JSON,
            output_file,
            hardware_type='NonExistent'
        )

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 0)

    def test_date_range_filtering(self):
        yesterday = datetime.now() - timedelta(days=1)
        two_days_ago = datetime.now() - timedelta(days=2)

        start_date = two_days_ago.strftime('%Y-%m-%d')
        end_date = yesterday.strftime('%Y-%m-%d')

        output_file = os.path.join(self.temp_dir, 'date_range.json')
        result = self.pipeline.export_attestations(
            ExportFormat.JSON,
            output_file,
            start_date=start_date,
            end_date=end_date
        )

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        # Should only include yesterday's record
        self.assertEqual(len(data), 1)

    def test_export_metadata_inclusion(self):
        output_file = os.path.join(self.temp_dir, 'with_metadata.json')
        result = self.pipeline.export_attestations(ExportFormat.JSON, output_file)

        self.assertTrue(result['success'])
        self.assertIn('records_exported', result)
        self.assertIn('export_time', result)
        self.assertEqual(result['records_exported'], 3)

    @unittest.skipUnless(PANDAS_AVAILABLE, "pandas not available")
    def test_parquet_without_pandas(self):
        # Mock pandas as unavailable
        with patch.dict('sys.modules', {'pandas': None}):
            output_file = os.path.join(self.temp_dir, 'test.parquet')

            with self.assertRaises(ImportError):
                self.pipeline.export_attestations(ExportFormat.PARQUET, output_file)

    def test_complex_attestation_data_parsing(self):
        # Add record with complex JSON data
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            complex_data = json.dumps({
                'cpu': 'PowerPC G5',
                'memory': {'total': '4GB', 'available': '2GB'},
                'hardware_checks': [
                    {'type': 'cpu_id', 'result': 'pass'},
                    {'type': 'cache_timing', 'result': 'pass'}
                ]
            })

            cursor.execute(
                'INSERT INTO attestations (miner_id, attestation_data, timestamp, status, hardware_type) VALUES (?, ?, ?, ?, ?)',
                ('miner_complex', complex_data, datetime.now().isoformat(), 'verified', 'PowerPC')
            )
            conn.commit()

        output_file = os.path.join(self.temp_dir, 'complex.json')
        result = self.pipeline.export_attestations(ExportFormat.JSON, output_file)

        self.assertTrue(result['success'])

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data), 4)
        complex_record = next(r for r in data if r['miner_id'] == 'miner_complex')
        self.assertIn('cpu', json.loads(complex_record['attestation_data']))


if __name__ == '__main__':
    unittest.main()
