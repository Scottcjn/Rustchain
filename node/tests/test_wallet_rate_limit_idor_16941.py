# SPDX-License-Identifier: Apache-2.0

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


class TestWalletRateLimitIDOR16941(unittest.TestCase):
    """Test rate limiting on /wallet/balance and /wallet/history (Issue #16941)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "wallet_test.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

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

        with sqlite3.connect(cls.mod.DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS balances ("
                "miner_id TEXT PRIMARY KEY, "
                "amount_i64 INTEGER"
                ")"
            )
            conn.execute(
                "INSERT OR REPLACE INTO balances (miner_id, amount_i64) "
                "VALUES ('test_miner', 100000000)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ledger ("
                "ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT"
                ")"
            )
            conn.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) "
                "VALUES (1700000000, 100, 'test_miner', 1000000, 'epoch_100_reward')"
            )

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
        self.mod.API_WALLET_RATE_LIMIT = 3
        self.mod.API_WALLET_RATE_WINDOW = 60
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute("DROP TABLE IF EXISTS wallet_rate_limit")

    def test_wallet_balance_rate_limit_enforced(self):
        """Verify /wallet/balance enforces 429 when rate limit is exceeded."""
        ip = "198.51.100.1"
        for i in range(3):
            resp = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("X-RateLimit-Limit"), "3")
            expected_remaining = str(2 - i)
            self.assertEqual(resp.headers.get("X-RateLimit-Remaining"), expected_remaining)

        # 4th request from same IP must be rate-limited (429)
        resp = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip})
        self.assertEqual(resp.status_code, 429)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertEqual(data.get("error"), "rate_limited")
        self.assertEqual(resp.headers.get("X-RateLimit-Remaining"), "0")
        self.assertIn("Retry-After", resp.headers)

    def test_wallet_balance_rate_limit_per_ip(self):
        """Verify rate limits are partitioned per IP address."""
        ip1 = "198.51.100.10"
        ip2 = "198.51.100.11"

        # Exhaust IP1
        for _ in range(3):
            resp = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip1})
            self.assertEqual(resp.status_code, 200)

        # IP1 is blocked
        resp1 = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip1})
        self.assertEqual(resp1.status_code, 429)

        # IP2 is still permitted
        resp2 = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip2})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.headers.get("X-RateLimit-Remaining"), "2")

    def test_api_wallet_alias_rate_limited(self):
        """Verify /api/wallet/<miner_id> alias shares wallet rate limit."""
        ip = "198.51.100.20"
        for _ in range(3):
            resp = self.client.get("/api/wallet/test_miner", environ_base={"REMOTE_ADDR": ip})
            self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/api/wallet/test_miner", environ_base={"REMOTE_ADDR": ip})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.get_json().get("error"), "rate_limited")

    def test_wallet_history_rate_limit_enforced(self):
        """Verify /wallet/history enforces rate limiting."""
        ip = "198.51.100.30"
        for i in range(3):
            resp = self.client.get("/wallet/history?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("X-RateLimit-Limit"), "3")
            self.assertEqual(resp.headers.get("X-RateLimit-Remaining"), str(2 - i))

        resp = self.client.get("/wallet/history?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip})
        self.assertEqual(resp.status_code, 429)
        data = resp.get_json()
        self.assertFalse(data.get("ok"))
        self.assertEqual(data.get("error"), "rate_limited")
        self.assertIn("Retry-After", resp.headers)

    def test_admin_key_bypasses_wallet_rate_limit(self):
        """Admin requests with valid X-Admin-Key bypass public rate limit."""
        ip = "198.51.100.40"
        # Exhaust quota for IP
        for _ in range(3):
            resp = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip})
            self.assertEqual(resp.status_code, 200)

        # Unauthenticated request is 429
        resp = self.client.get("/wallet/balance?miner_id=test_miner", environ_base={"REMOTE_ADDR": ip})
        self.assertEqual(resp.status_code, 429)

        # Admin authenticated request passes 200
        admin_resp = self.client.get(
            "/wallet/balance?miner_id=test_miner",
            headers={"X-Admin-Key": ADMIN_KEY},
            environ_base={"REMOTE_ADDR": ip},
        )
        self.assertEqual(admin_resp.status_code, 200)
        self.assertEqual(admin_resp.get_json().get("miner_id"), "test_miner")

    def test_check_wallet_rate_limit_function_unit(self):
        """Direct unit test of check_wallet_rate_limit logic and reset calculations."""
        ip = "198.51.100.50"
        t0 = 1000

        ok, info = self.mod.check_wallet_rate_limit(ip, endpoint="test_ep", now_ts=t0)
        self.assertTrue(ok)
        self.assertEqual(info["remaining"], 2)

        ok, info = self.mod.check_wallet_rate_limit(ip, endpoint="test_ep", now_ts=t0 + 1)
        self.assertTrue(ok)
        self.assertEqual(info["remaining"], 1)

        ok, info = self.mod.check_wallet_rate_limit(ip, endpoint="test_ep", now_ts=t0 + 2)
        self.assertTrue(ok)
        self.assertEqual(info["remaining"], 0)

        # 4th call within window fails
        ok, info = self.mod.check_wallet_rate_limit(ip, endpoint="test_ep", now_ts=t0 + 3)
        self.assertFalse(ok)
        self.assertEqual(info["remaining"], 0)
        self.assertGreater(info["retry_after"], 0)

        # Advance beyond window (t0 + 100) -> all prior requests pruned -> reset
        ok, info = self.mod.check_wallet_rate_limit(ip, endpoint="test_ep", now_ts=t0 + 100)
        self.assertTrue(ok)
        self.assertEqual(info["remaining"], 2)


if __name__ == "__main__":
    unittest.main()
