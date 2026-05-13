# SPDX-License-Identifier: MIT
"""Test that proof_of_iron.py stores and reads feature cache as JSON only."""
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
            conn.close()
            print("✓ SQLite JSON storage test passed")
        finally:
            os.unlink(db_path)

    def test_legacy_pickle_cache_is_rejected_without_execution(self):
        """Test that legacy pickle data is not deserialized by the live path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE feature_cache (
                hash TEXT PRIMARY KEY, features TEXT, created_at INTEGER)''')
            conn.commit()
            class Exploit:
                def __reduce__(self):
                    return (
                        eval,
                        (
                            '__import__("os").environ.__setitem__('
                            '"PROOF_OF_IRON_PICKLE_RCE_TEST", "1")',
                        ),
                    )

            pickle_blob = pickle.dumps(Exploit())
            c.execute('INSERT INTO feature_cache VALUES (?, ?, ?)',
                     ('old_hash', pickle_blob, 1000000000))
            conn.commit()
            conn.close()

            os.environ.pop("PROOF_OF_IRON_PICKLE_RCE_TEST", None)

            from issue2307_boot_chime.src.proof_of_iron import ProofOfIron
            poi = ProofOfIron(db_path=db_path)
            self.assertIsNone(poi._load_features('old_hash'))
            self.assertNotIn("PROOF_OF_IRON_PICKLE_RCE_TEST", os.environ)
            print("✓ Legacy pickle cache rejection test passed")
        finally:
            os.environ.pop("PROOF_OF_IRON_PICKLE_RCE_TEST", None)
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

    def test_json_only_load(self):
        """Verify that _load_features uses JSON without pickle fallback."""
        with open('issue2307_boot_chime/src/proof_of_iron.py', 'r') as f:
            content = f.read()
        self.assertIn('json.loads', content, "json.loads should be used in load")
        self.assertNotIn('pickle.loads', content,
                         "pickle.loads should not be present as fallback in load")
        self.assertIn('JSONDecodeError', content,
                      "JSONDecodeError should be caught for invalid JSON cache rows")
        print("✓ JSON-only load test passed")


if __name__ == "__main__":
    unittest.main()
