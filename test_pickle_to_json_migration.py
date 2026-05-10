"""Test that pickle to json migration in proof_of_iron.py works correctly."""
import os
import sys
import json
import sqlite3
import tempfile
import unittest

# Add the project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'issue2307_boot_chime', 'src'))

class TestPickleToJsonMigration(unittest.TestCase):
    def test_json_serialization_roundtrip(self):
        """Test that features can be serialized to JSON and deserialized correctly."""
        import numpy as np
        
        # Simulate the data structure used in proof_of_iron.py
        features_data = {
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
        
        # Test JSON roundtrip
        json_data = json.dumps(features_data)
        loaded = json.loads(json_data)
        
        self.assertEqual(features_data['mfcc_mean'], loaded['mfcc_mean'])
        self.assertEqual(features_data['spectral_centroid'], loaded['spectral_centroid'])
        self.assertEqual(features_data['chroma_mean'], loaded['chroma_mean'])
        print("✓ JSON serialization roundtrip test passed")
    
    def test_sqlite_json_storage(self):
        """Test that JSON data can be stored and retrieved from SQLite."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE feature_cache (
                    hash TEXT PRIMARY KEY,
                    features TEXT,
                    created_at INTEGER
                )
            ''')
            conn.commit()
            
            # Insert JSON data
            features_data = json.dumps({
                'mfcc_mean': [0.1, 0.2, 0.3],
                'mfcc_std': [0.01, 0.02, 0.03],
                'spectral_centroid': 1000.0,
                'spectral_bandwidth': 500.0,
                'spectral_rolloff': 2000.0,
                'zero_crossing_rate': 0.1,
                'chroma_mean': [0.5] * 12,
                'temporal_envelope': [0.1, 0.2, 0.3],
                'peak_frequencies': [440.0, 880.0],
                'harmonic_structure': True,
            })
            
            c.execute('INSERT INTO feature_cache (hash, features, created_at) VALUES (?, ?, ?)',
                     ('test_hash', features_data, 1234567890))
            conn.commit()
            
            # Retrieve and parse
            c.execute('SELECT features FROM feature_cache WHERE hash = ?', ('test_hash',))
            row = c.fetchone()
            loaded = json.loads(row[0])
            
            self.assertEqual(loaded['spectral_centroid'], 1000.0)
            self.assertEqual(len(loaded['mfcc_mean']), 3)
            print("✓ SQLite JSON storage test passed")
        finally:
            os.unlink(db_path)
    
    def test_no_pickle_import_in_proof_of_iron(self):
        """Verify that pickle is no longer imported in proof_of_iron.py."""
        with open('issue2307_boot_chime/src/proof_of_iron.py', 'r') as f:
            content = f.read()
        
        # Check that pickle is not imported
        self.assertNotIn('import pickle', content, "pickle should not be imported")
        self.assertIn('import json', content, "json should be imported")
        self.assertIn('json.dumps', content, "json.dumps should be used")
        self.assertIn('json.loads', content, "json.loads should be used")
        print("✓ No pickle import test passed")

if __name__ == "__main__":
    unittest.main()
