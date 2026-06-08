import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestWalletTxEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_wallet_tx_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
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
        cls._tmp.cleanup()

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.mod.DB_PATH = self.db_path
        self.mod.app.config["DB_PATH"] = self.db_path

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except (FileNotFoundError, PermissionError):
            pass

    def _create_pending_ledger(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE pending_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    epoch INTEGER NOT NULL,
                    from_miner TEXT NOT NULL,
                    to_miner TEXT NOT NULL,
                    amount_i64 INTEGER NOT NULL,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER NOT NULL,
                    confirms_at INTEGER NOT NULL,
                    tx_hash TEXT,
                    voided_reason TEXT,
                    confirmed_at INTEGER
                )
                """
            )

    def test_wallet_tx_returns_pending_ledger_status_as_json(self):
        tx_hash = "09db0d0ace4ab297a54f4e2e392e69e7"
        self._create_pending_ledger()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason, status,
                 created_at, confirms_at, tx_hash)
                VALUES (100, 7, 'founder_community', 'pqmfei', 5000000,
                        'signed_transfer:bonus', 'pending', 100, 200, ?)
                """,
                (tx_hash,),
            )

        resp = self.client.get(f"/wallet/tx/{tx_hash}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertTrue(body["ok"])
        self.assertEqual(body["tx_hash"], tx_hash)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["confirmations"], 0)
        self.assertEqual(body["from_miner"], "founder_community")
        self.assertEqual(body["to_miner"], "pqmfei")
        self.assertEqual(body["amount_i64"], 5_000_000)
        self.assertEqual(body["amount_rtc"], 5.0)

    def test_wallet_tx_handles_legacy_pending_ledger_schema(self):
        tx_hash = "legacytx123"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE pending_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    epoch INTEGER NOT NULL,
                    from_miner TEXT NOT NULL,
                    to_miner TEXT NOT NULL,
                    amount_i64 INTEGER NOT NULL,
                    tx_hash TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, tx_hash)
                VALUES (150, 8, 'alice', 'bob', 1000000, ?)
                """,
                (tx_hash,),
            )

        resp = self.client.get(f"/wallet/tx/{tx_hash}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertTrue(body["ok"])
        self.assertEqual(body["tx_hash"], tx_hash)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["confirmations"], 0)
        self.assertIsNone(body["confirmed_at"])
        self.assertEqual(body["amount_rtc"], 1.0)

    def test_wallet_tx_falls_back_to_confirmed_ledger_reason(self):
        tx_hash = "abc123def456"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    epoch INTEGER,
                    miner_id TEXT NOT NULL,
                    delta_i64 INTEGER NOT NULL,
                    reason TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason)
                VALUES (300, 9, 'alice', -2500000, ?)
                """,
                (f"transfer_out:bob:{tx_hash}",),
            )
            conn.execute(
                """
                INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason)
                VALUES (300, 9, 'bob', 2500000, ?)
                """,
                (f"transfer_in:alice:{tx_hash}",),
            )

        resp = self.client.get(f"/wallet/tx/{tx_hash}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertTrue(body["ok"])
        self.assertEqual(body["tx_hash"], tx_hash)
        self.assertEqual(body["status"], "confirmed")
        self.assertEqual(body["confirmations"], 1)
        self.assertEqual(body["from_miner"], "alice")
        self.assertEqual(body["to_miner"], "bob")
        self.assertEqual(body["amount_rtc"], 2.5)

    def test_wallet_tx_missing_hash_returns_json_404(self):
        resp = self.client.get("/wallet/tx/notfound123")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.content_type, "application/json")
        self.assertEqual(
            resp.get_json(),
            {
                "ok": False,
                "tx_hash": "notfound123",
                "status": "not_found",
                "error": "transaction not found",
            },
        )


if __name__ == "__main__":
    unittest.main()
