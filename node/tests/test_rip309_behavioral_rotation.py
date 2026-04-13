import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROTATION_PATH = os.path.join(NODE_DIR, "rip_309_measurement_rotation.py")
SOPHIA_PATH = os.path.join(NODE_DIR, "sophia_elya_service.py")


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRip309BehavioralRotation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        cls.rotation = _load_module("rip309_behavioral_rotation_test", ROTATION_PATH)

    def test_behavioral_metric_pool_matches_five_of_ten_design(self):
        pool = self.rotation.get_behavioral_metric_pool()
        self.assertEqual(len(pool), 10)
        self.assertEqual(self.rotation.ACTIVE_BEHAVIORAL_METRIC_COUNT, 5)
        self.assertEqual(len({metric["name"] for metric in pool}), 10)

    def test_behavioral_metric_subset_is_deterministic(self):
        nonce = self.rotation.derive_epoch_nonce("11" * 32)
        first = self.rotation.get_active_behavioral_metrics(nonce)
        second = self.rotation.get_active_behavioral_metrics(nonce)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)
        self.assertEqual(first, sorted(first))

    def test_behavioral_metric_subset_varies_across_epochs(self):
        subsets = set()
        for i in range(8):
            prev_hash = f"{i + 1:064x}"
            nonce = self.rotation.derive_epoch_nonce(prev_hash)
            subsets.add(tuple(self.rotation.get_active_behavioral_metrics(nonce)))

        self.assertGreater(len(subsets), 1, "behavioral rotation should vary across epochs")


class TestSophiaEpochBehavioralRotationExposure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_cwd = os.getcwd()
        os.chdir(cls._tmp.name)
        cls.sophia = _load_module("sophia_epoch_behavioral_rotation_test", SOPHIA_PATH)
        cls.sophia.init_db()
        cls.client = cls.sophia.app.test_client()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._prev_cwd)
        cls._tmp.cleanup()

    def test_epoch_endpoint_exposes_behavioral_rotation(self):
        with patch.object(self.sophia.time, "time", return_value=3600), \
             patch.object(self.sophia, "LAST_HASH_B3", "22" * 32):
            resp = self.client.get("/epoch")

        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        rotation = body["measurement_rotation"]

        self.assertEqual(rotation["behavioral_metric_pool_size"], 10)
        self.assertEqual(rotation["active_behavioral_metric_count"], 5)
        self.assertEqual(len(rotation["active_behavioral_metrics"]), 5)
        self.assertEqual(len(rotation["behavioral_metric_pool"]), 10)
        self.assertEqual(rotation["epoch"], body["epoch"])
        self.assertTrue(rotation["nonce"])


if __name__ == "__main__":
    unittest.main()
