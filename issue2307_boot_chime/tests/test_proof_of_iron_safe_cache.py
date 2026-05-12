# SPDX-License-Identifier: MIT

import os
import pickle
import sqlite3
import sys
import tempfile
from pathlib import Path
from contextlib import closing

import numpy as np


src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from acoustic_fingerprint import FingerprintFeatures
    from proof_of_iron import ProofOfIron
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.acoustic_fingerprint import FingerprintFeatures
    from src.proof_of_iron import ProofOfIron


def _feature_data():
    return {
        "mfcc_mean": [1.0, 2.0],
        "mfcc_std": [0.1, 0.2],
        "spectral_centroid": 100.0,
        "spectral_bandwidth": 200.0,
        "spectral_rolloff": 300.0,
        "zero_crossing_rate": 0.05,
        "chroma_mean": [0.3, 0.4],
        "temporal_envelope": [0.5, 0.6],
        "peak_frequencies": [440.0, 880.0],
        "harmonic_structure": {"h1": 1.0},
    }


def _insert_feature_cache(db_path, features_hash, payload):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE feature_cache (
                hash TEXT PRIMARY KEY,
                features BLOB,
                created_at INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO feature_cache (hash, features, created_at) VALUES (?, ?, 0)",
            (features_hash, payload),
        )
        conn.commit()


def _loader(db_path):
    proof = ProofOfIron.__new__(ProofOfIron)
    proof.db_path = db_path
    return proof


class _Exploit:
    def __reduce__(self):
        return (os.system, ("echo unsafe",))


def test_load_features_rejects_pickle_globals_without_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "features.db")
        _insert_feature_cache(db_path, "evil", pickle.dumps(_Exploit()))

        loaded = _loader(db_path)._load_features("evil")

        assert loaded is None


def test_load_features_migrates_legacy_plain_pickle_dict_to_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "features.db")
        _insert_feature_cache(db_path, "legacy", pickle.dumps(_feature_data()))

        loaded = _loader(db_path)._load_features("legacy")

        assert isinstance(loaded, FingerprintFeatures)
        np.testing.assert_allclose(loaded.mfcc_mean, np.array([1.0, 2.0]))

        with closing(sqlite3.connect(db_path)) as conn:
            stored = conn.execute(
                "SELECT features FROM feature_cache WHERE hash = ?",
                ("legacy",),
            ).fetchone()[0]
        assert isinstance(stored, str)
        assert stored.startswith("{")
