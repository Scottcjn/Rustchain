# SPDX-License-Identifier: Apache-2.0

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestApiMinersRateLimit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "api_miners.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        if "integrated_node" in sys.modules:
            cls.mod = sys.modules["integrated_node"]
        else:
            spec = importlib.util.spec_from_file_location("integrated_node", MODULE_PATH)
            cls.mod = importlib.util.module_from_spec(spec)
            sys.modules["integrated_node"] = cls.mod
            spec.loader.exec_module(cls.mod)

        cls._prev_module_db_path = getattr(cls.mod, "DB_PATH", None)
        cls.mod.DB_PATH = os.environ["RUSTCHAIN_DB_PATH"]
        cls.client = cls.mod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        if cls._prev_module_db_path is not None:
            cls.mod.DB_PATH = cls._prev_module_db_path
        cls._tmp.cleanup()

    def setUp(self):
        self.mod.API_MINERS_RATE_LIMIT = 2
        self.mod.API_MINERS_RATE_WINDOW = 60
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute("DROP TABLE IF EXISTS api_miners_rate_limit")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS miner_attest_recent "
                "(miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT, "
                "device_arch TEXT, entropy_score REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS miner_attest_history "
                "(miner TEXT, ts_ok INTEGER)"
            )

    def test_api_miners_returns_429_after_ip_limit(self):
        for _ in range(2):
            resp = self.client.get("/api/miners", environ_base={"REMOTE_ADDR": "203.0.113.10"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers["X-RateLimit-Limit"], "2")

        resp = self.client.get("/api/miners", environ_base={"REMOTE_ADDR": "203.0.113.10"})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.get_json()["error"], "rate_limited")
        self.assertEqual(resp.headers["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", resp.headers)

    def test_api_miners_rate_limit_is_per_ip(self):
        for _ in range(2):
            resp = self.client.get("/api/miners", environ_base={"REMOTE_ADDR": "203.0.113.10"})
            self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/api/miners", environ_base={"REMOTE_ADDR": "203.0.113.11"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["X-RateLimit-Remaining"], "1")


if __name__ == "__main__":
    unittest.main()
