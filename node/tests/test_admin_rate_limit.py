# SPDX-License-Identifier: MIT
import importlib.util
import gc
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
MODULE_NAME = "rustchain_integrated_rate_limit_test"
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _load_integrated_module():
    if "integrated_node" in sys.modules:
        return sys.modules["integrated_node"]
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(MODULE_NAME, None)
        raise
    return mod


def _cleanup_tempdir(tempdir):
    gc.collect()
    try:
        tempdir.cleanup()
    except OSError:
        pass


class TestAdminRateLimit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        os.environ["RUSTCHAIN_DB_PATH"] = str(Path(cls._tmp.name) / "admin_rate_limit.db")
        cls.mod = _load_integrated_module()
        cls.mod.DB_PATH = os.environ["RUSTCHAIN_DB_PATH"]
        cls.mod.app.config["DB_PATH"] = os.environ["RUSTCHAIN_DB_PATH"]
        cls.mod.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        _cleanup_tempdir(cls._tmp)

    def setUp(self):
        self.mod.ADMIN_RATE_LIMIT_MAX = 2
        self.mod.ADMIN_RATE_LIMIT_WINDOW = 60
        self.mod._ADMIN_RATE_LIMIT_BUCKETS.clear()

    def test_admin_endpoint_rejects_repeated_failed_key_attempts(self):
        statuses = []
        with mock.patch.object(self.mod.time, "time", return_value=1000):
            with self.mod.app.test_client() as client:
                for _ in range(3):
                    response = client.get(
                        "/pending/list",
                        headers={"X-Admin-Key": "wrong-admin-key"},
                        environ_base={"REMOTE_ADDR": "198.51.100.42"},
                    )
                    statuses.append((response.status_code, response.get_json(), response.headers))

        self.assertEqual(statuses[0][0], 401)
        self.assertEqual(statuses[1][0], 401)
        self.assertEqual(statuses[2][0], 429)
        self.assertEqual(statuses[2][1]["code"], "ADMIN_RATE_LIMIT")
        self.assertEqual(statuses[2][2]["Retry-After"], "60")

    def test_public_health_endpoint_is_not_admin_rate_limited(self):
        with mock.patch.object(self.mod.time, "time", return_value=1000):
            with self.mod.app.test_client() as client:
                responses = [
                    client.get("/health", environ_base={"REMOTE_ADDR": "198.51.100.43"})
                    for _ in range(4)
                ]

        self.assertTrue(all(response.status_code == 200 for response in responses))

    def test_dynamic_admin_route_variants_share_rate_limit_bucket(self):
        paths = [
            "/withdraw/history/miner-a",
            "/withdraw/history/miner-b",
            "/withdraw/history/miner-c",
        ]
        statuses = []
        with mock.patch.object(self.mod.time, "time", return_value=1000):
            with self.mod.app.test_client() as client:
                for path in paths:
                    response = client.get(
                        path,
                        headers={"X-Admin-Key": "wrong-admin-key"},
                        environ_base={"REMOTE_ADDR": "198.51.100.44"},
                    )
                    statuses.append(response.status_code)

        self.assertEqual(statuses, [401, 401, 429])

    def test_registered_admin_extension_routes_are_limited(self):
        self.assertTrue(self.mod._is_admin_rate_limited_path("/wallet/link-coinbase"))
        self.assertTrue(self.mod._is_admin_rate_limited_path("/api/bridge/void"))
        self.assertTrue(self.mod._is_admin_rate_limited_path("/api/lock/release"))
        self.assertTrue(self.mod._is_admin_rate_limited_path("/api/bridge/lock/abc123/confirm"))
        self.assertTrue(self.mod._is_admin_rate_limited_path("/genesis/export"))
        self.assertFalse(self.mod._is_admin_rate_limited_path("/wallet/swap-info"))

    def test_dynamic_admin_route_bucket_keys_are_normalized(self):
        self.assertEqual(
            self.mod._admin_rate_limit_bucket_path("/api/miner/alice/attestations"),
            "/api/miner/:miner_id/attestations",
        )
        self.assertEqual(
            self.mod._admin_rate_limit_bucket_path("/withdraw/history/miner-a"),
            "/withdraw/history/:miner_pk",
        )
        self.assertEqual(
            self.mod._admin_rate_limit_bucket_path("/api/bridge/lock/abc123/confirm"),
            "/api/bridge/lock/:lock_id/confirm",
        )
        self.assertEqual(
            self.mod._admin_rate_limit_bucket_path("/api/bridge/lock/def456/release"),
            "/api/bridge/lock/:lock_id/release",
        )


if __name__ == "__main__":
    unittest.main()
