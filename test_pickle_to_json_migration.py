"""Test that pickle has been fully removed from proof_of_iron.py.

Updated post vuln-tick 2026-05-14T14:10Z: PR #4530 introduced a dual-read
that fell back to pickle.loads() on legacy BLOBs. That fallback was an RCE
primitive — a poisoned legacy cache row could execute arbitrary code during
_load_features(). These tests now assert:

  1. proof_of_iron.py does not import pickle and does not call pickle.loads/dumps.
  2. _save_features still serializes with json.dumps.
  3. _load_features returns None (cache miss) for legacy pickle BLOBs instead
     of deserializing them.
  4. JSON rows still round-trip cleanly through _load_features.
"""
import os
import sys
import json
import pickle
import sqlite3
import tempfile
import types
import unittest
import importlib.util

import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, 'issue2307_boot_chime', 'src')
PROOF_OF_IRON_PATH = os.path.join(SRC_DIR, 'proof_of_iron.py')


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


def _load_proof_of_iron_module():
    """Load proof_of_iron.py as a top-level module with stub dependencies.

    proof_of_iron.py uses package-relative imports
    (`from .acoustic_fingerprint import ...`). To exercise it directly from
    this top-level test file without polluting global packages, we install
    a fake parent package in sys.modules with the real `src` dir on its
    __path__, plus stub submodules for the heavy audio dependencies.
    """
    pkg_name = '_poi_test_pkg'
    if pkg_name in sys.modules:
        return sys.modules[pkg_name].proof_of_iron

    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [SRC_DIR]
    sys.modules[pkg_name] = pkg

    # Real FingerprintFeatures dataclass is needed by _load_features, so
    # import the real acoustic_fingerprint module under our fake package name.
    af_spec = importlib.util.spec_from_file_location(
        f'{pkg_name}.acoustic_fingerprint',
        os.path.join(SRC_DIR, 'acoustic_fingerprint.py'),
    )
    af_mod = importlib.util.module_from_spec(af_spec)
    sys.modules[f'{pkg_name}.acoustic_fingerprint'] = af_mod
    af_spec.loader.exec_module(af_mod)

    # Stub boot_chime_capture — only BootChimeCapture and CapturedAudio names
    # need to exist; we never instantiate them.
    bcc_stub = types.ModuleType(f'{pkg_name}.boot_chime_capture')
    bcc_stub.BootChimeCapture = type('BootChimeCapture', (), {'__init__': lambda self, *a, **kw: None})
    bcc_stub.CapturedAudio = type('CapturedAudio', (), {})
    sys.modules[f'{pkg_name}.boot_chime_capture'] = bcc_stub

    poi_spec = importlib.util.spec_from_file_location(
        f'{pkg_name}.proof_of_iron', PROOF_OF_IRON_PATH,
    )
    poi_mod = importlib.util.module_from_spec(poi_spec)
    sys.modules[f'{pkg_name}.proof_of_iron'] = poi_mod
    poi_spec.loader.exec_module(poi_mod)
    pkg.proof_of_iron = poi_mod
    return poi_mod


class TestPickleRemoval(unittest.TestCase):
    def test_no_pickle_in_source(self):
        """proof_of_iron.py must not import pickle or call pickle.loads/dumps."""
        with open(PROOF_OF_IRON_PATH, 'r') as f:
            content = f.read()
        self.assertNotIn('import pickle', content,
                         "pickle must not be imported in proof_of_iron.py")
        self.assertNotIn('pickle.loads', content,
                         "pickle.loads must not appear (RCE primitive)")
        self.assertNotIn('pickle.dumps', content,
                         "pickle.dumps must not appear")

    def test_save_uses_json(self):
        """_save_features must serialize with json.dumps."""
        with open(PROOF_OF_IRON_PATH, 'r') as f:
            content = f.read()
        self.assertIn('json.dumps', content,
                      "json.dumps must be used in _save_features")

    def test_json_serialization_roundtrip(self):
        """JSON serialization roundtrip still works."""
        json_data = json.dumps(SAMPLE_FEATURES)
        loaded = json.loads(json_data)
        self.assertEqual(SAMPLE_FEATURES['mfcc_mean'], loaded['mfcc_mean'])
        self.assertEqual(SAMPLE_FEATURES['spectral_centroid'], loaded['spectral_centroid'])

    def test_legacy_pickle_blob_returns_none(self):
        """A legacy pickle BLOB in feature_cache must return None (cache miss),
        not be deserialized. This is the core anti-RCE invariant."""
        poi_mod = _load_proof_of_iron_module()
        ProofOfIron = poi_mod.ProofOfIron

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            # Set up the schema and insert a malicious-shaped pickle BLOB.
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE feature_cache (
                hash TEXT PRIMARY KEY, features BLOB, created_at INTEGER)''')
            pickle_blob = pickle.dumps(SAMPLE_FEATURES)
            c.execute('INSERT INTO feature_cache VALUES (?, ?, ?)',
                     ('legacy_hash', pickle_blob, 1000000000))
            conn.commit()
            conn.close()

            poi = ProofOfIron(db_path=db_path)

            # Contract: legacy pickle BLOBs must NOT be deserialized.
            result = poi._load_features('legacy_hash')
            self.assertIsNone(
                result,
                "Legacy pickle BLOB must be treated as cache miss, not deserialized",
            )

            # Missing hash also returns None.
            missing = poi._load_features('does_not_exist')
            self.assertIsNone(missing)
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_json_row_round_trips_through_load(self):
        """A JSON row written in feature_cache must round-trip through _load_features."""
        poi_mod = _load_proof_of_iron_module()
        ProofOfIron = poi_mod.ProofOfIron

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE feature_cache (
                hash TEXT PRIMARY KEY, features TEXT, created_at INTEGER)''')
            c.execute('INSERT INTO feature_cache VALUES (?, ?, ?)',
                     ('json_hash', json.dumps(SAMPLE_FEATURES), 1234567890))
            conn.commit()
            conn.close()

            poi = ProofOfIron(db_path=db_path)
            result = poi._load_features('json_hash')
            self.assertIsNotNone(result, "JSON row must load successfully")
            self.assertAlmostEqual(result.spectral_centroid, 1000.0)
            self.assertEqual(list(result.mfcc_mean), SAMPLE_FEATURES['mfcc_mean'])
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
