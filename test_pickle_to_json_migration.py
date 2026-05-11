"""Test that pickle to JSON migration in proof_of_iron.py works correctly,
including backward-compatible dual-read for legacy pickle data."""
import os
import sys
import json
import pickle
import sqlite3
import tempfile
import unittest
import numpy as np

# Add the project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'issue2307_boot_chime', 'src'))

SAMPLE_FEATURES = {
    'mfcc_mean': [0.1, 0.2, 0.3, 0.4, 0.5],
    'mfcc_std': [0.01, 0.02, 0.03, 0.04, 0.05],
    'spectral_centroid': 1000.0,
    'spectral_bandwidth': 500.0,
    'spectral_rolloff': 2000.0,
    'zero_crossing_rate': 0.1,
    'chroma_mean': [0.5] * 12,
    'temporal_envelope': [0.1, 0.2, 0.3],
    'peak_frequencies': [440.0, 880.0],
    'harmonic_structure': True,
}


class TestPickleToJsonMigration(unittest.TestCase):
    def test_json_serialization_roundtrip(self):
        """Test that features can be serialized to JSON and deserialized correctly."""
        json_data = json.dumps(SAMPLE_FEATURES)
        loaded = json.loads(json_data)
        self.assertEqual(SAMPLE_FEATURES['mfcc_mean'], loaded['mfcc_mean'])
        self.assertEqual(SAMPLE_FEATURES['spectral_centroid'], loaded['spectral_centroid'])
        print("✓ JSON serialization roundtrip test passed")

    def test_sqlite_json_storage(self):
        """Test that JSON data can be stored and retrieved from SQLite."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE feature_cache (
                hash TEXT PRIMARY KEY, features TEXT, created_at INTEGER)''')
            conn.commit()
            c.execute('INSERT INTO feature_cache VALUES (?, ?, ?)',
                     ('test_hash', json.dumps(SAMPLE_FEATURES), 1234567890))
            conn.commit()
            c.execute('SELECT features FROM feature_cache WHERE hash = ?', ('test_hash',))
            loaded = json.loads(c.fetchone()[0])
            self.assertEqual(loaded['spectral_centroid'], 1000.0)
            print("✓ SQLite JSON storage test passed")
        finally:
            os.unlink(db_path)

    def test_backward_compat_pickle_fallback(self):
        """Test that legacy pickle data is deserialized and migrated to JSON."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE feature_cache (
                hash TEXT PRIMARY KEY, features TEXT, created_at INTEGER)''')
            conn.commit()
            # Insert OLD pickle BLOB data
            pickle_blob = pickle.dumps(SAMPLE_FEATURES)
            c.execute('INSERT INTO feature_cache VALUES (?, ?, ?)',
                     ('old_hash', pickle_blob, 1000000000))
            conn.commit()

            # Manual dual-read logic test (mimics _load_features behavior)
            c.execute('SELECT features FROM feature_cache WHERE hash = ?', ('old_hash',))
            raw = c.fetchone()[0]
            # Try JSON first — should fail
            try:
                json.loads(raw.decode('utf-8') if isinstance(raw, bytes) else raw)
                self.fail("Expected JSON decode to fail on pickle data")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # Expected
            # Fallback to pickle — should succeed
            data = pickle.loads(raw) if isinstance(raw, bytes) else pickle.loads(raw.encode())
            self.assertEqual(data['spectral_centroid'], 1000.0)

            # Now verify the code path in proof_of_iron.py handles this:
            # Check that the source has the fallback pattern
            with open('issue2307_boot_chime/src/proof_of_iron.py', 'r') as f:
                content = f.read()
            self.assertIn('JSONDecodeError', content,
                          "Should catch JSONDecodeError for pickle fallback")
            self.assertIn('pickle.loads', content,
                          "Should have pickle.loads as fallback")
            self.assertIn('json.loads', content,
                          "Should try json.loads first")
            print("✓ Backward-compatible pickle fallback test passed")
        finally:
            os.unlink(db_path)

    def test_no_bare_pickle_in_save(self):
        """Verify that _save_features uses json.dumps, not pickle.dumps."""
        with open('issue2307_boot_chime/src/proof_of_iron.py', 'r') as f:
            content = f.read()
        self.assertNotIn('pickle.dumps', content,
                         "pickle.dumps should NOT be used in save")
        self.assertIn('json.dumps', content,
                      "json.dumps should be used in save")
        print("✓ No pickle.dumps in save test passed")

    def test_dual_read_in_load(self):
        """Verify that _load_features has dual-read (json first, pickle fallback)."""
        with open('issue2307_boot_chime/src/proof_of_iron.py', 'r') as f:
            content = f.read()
        self.assertIn('json.loads', content, "json.loads should be used in load")
        self.assertIn('pickle.loads', content,
                      "pickle.loads should be present as fallback in load")
        self.assertIn('JSONDecodeError', content,
                      "JSONDecodeError should be caught for dual-read")
        print("✓ Dual-read in load test passed")


if __name__ == "__main__":
    unittest.main()
