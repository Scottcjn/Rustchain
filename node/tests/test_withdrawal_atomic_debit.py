# SPDX-License-Identifier: MIT
import base64
import importlib.util
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestWithdrawalAtomicDebit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_withdraw_atomic_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.UNIT = getattr(cls.mod, "UNIT", 1_000_000)

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
        try:
            cls._tmp.cleanup()
        except OSError:
            pass

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.mod.DB_PATH = self.db_path
        self._orig_verify = self.mod.verify_sr25519_signature
        self._create_schema()

    def tearDown(self):
        self.mod.verify_sr25519_signature = self._orig_verify
        try:
            os.unlink(self.db_path)
        except (FileNotFoundError, PermissionError):
            pass

    def _create_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL NOT NULL DEFAULT 0)"
            )
            conn.execute(
                "CREATE TABLE withdrawal_nonces (miner_pk TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL, PRIMARY KEY (miner_pk, nonce))"
            )
            conn.execute(
                "CREATE TABLE withdrawal_limits (miner_pk TEXT NOT NULL, date TEXT NOT NULL, total_withdrawn REAL DEFAULT 0, PRIMARY KEY (miner_pk, date))"
            )
            conn.execute(
                "CREATE TABLE miner_keys (miner_pk TEXT PRIMARY KEY, pubkey_sr25519 TEXT NOT NULL, registered_at INTEGER NOT NULL)"
            )
            conn.execute(
                """
                CREATE TABLE withdrawals (
                    withdrawal_id TEXT PRIMARY KEY,
                    miner_pk TEXT NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL,
                    destination TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE fee_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    miner_pk TEXT,
                    fee_rtc REAL NOT NULL,
                    fee_urtc INTEGER NOT NULL,
                    destination TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute("INSERT INTO balances VALUES ('miner-test', 50.01)")
            conn.execute("INSERT INTO balances VALUES ('founder_community', 0)")
            conn.execute(
                "INSERT INTO miner_keys VALUES ('miner-test', ?, ?)",
                ("00" * 32, int(time.time())),
            )

    def _payload(self, nonce):
        return {
            "miner_pk": "miner-test",
            "amount": 50.0,
            "destination": "rtc-destination",
            "signature": base64.b64encode(b"\x00" * 64).decode("ascii"),
            "nonce": nonce,
        }

    def test_concurrent_withdrawals_cannot_overdraw_balance(self):
        def slow_valid_signature(*_args, **_kwargs):
            time.sleep(0.05)
            return True

        self.mod.verify_sr25519_signature = slow_valid_signature
        results = []
        lock = threading.Lock()

        def post_withdrawal(nonce):
            with self.mod.app.test_client() as client:
                resp = client.post("/withdraw/request", json=self._payload(nonce))
            with lock:
                results.append((resp.status_code, resp.get_json()))

        t1 = threading.Thread(target=post_withdrawal, args=("nonce-1",))
        t2 = threading.Thread(target=post_withdrawal, args=("nonce-2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        statuses = sorted(status for status, _body in results)
        self.assertEqual(statuses, [200, 400])

        with sqlite3.connect(self.db_path) as conn:
            balance = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = 'miner-test'"
            ).fetchone()[0]
            founder_balance = conn.execute(
                "SELECT balance_rtc FROM balances WHERE miner_pk = 'founder_community'"
            ).fetchone()[0]
            withdrawal_count = conn.execute("SELECT COUNT(*) FROM withdrawals").fetchone()[0]

        self.assertGreaterEqual(balance, 0)
        self.assertAlmostEqual(balance, 0.0, places=6)
        self.assertAlmostEqual(founder_balance, self.mod.WITHDRAWAL_FEE, places=6)
        self.assertEqual(withdrawal_count, 1)


if __name__ == "__main__":
    unittest.main()
