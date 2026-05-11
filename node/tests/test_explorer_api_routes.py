import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestExplorerApiRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        spec = importlib.util.spec_from_file_location("rustchain_integrated_explorer_api_test", MODULE_PATH)
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

    def test_blocks_endpoint_returns_recent_blocks(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE blocks (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    merkle_root TEXT NOT NULL,
                    state_root TEXT NOT NULL,
                    producer TEXT NOT NULL,
                    tx_count INTEGER NOT NULL,
                    body_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO blocks
                (height, block_hash, prev_hash, timestamp, merkle_root, state_root,
                 producer, tx_count, body_json, created_at)
                VALUES (1, 'hash1', 'prev0', 100, 'm1', 's1', 'miner1', 1, '{"tx_count": 1}', 110)
                """
            )
            conn.execute(
                """
                INSERT INTO blocks
                (height, block_hash, prev_hash, timestamp, merkle_root, state_root,
                 producer, tx_count, body_json, created_at)
                VALUES (2, 'hash2', 'hash1', 200, 'm2', 's2', 'miner2', 0, '{"tx_count": 0}', 210)
                """
            )

        resp = self.client.get("/api/blocks?limit=1")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["blocks"][0]["height"], 2)
        self.assertEqual(body["blocks"][0]["hash"], "hash2")
        self.assertEqual(body["blocks"][0]["block_hash"], "hash2")
        self.assertEqual(body["blocks"][0]["tx_count"], 0)
        self.assertEqual(body["blocks"][0]["body"], {"tx_count": 0})

    def test_transactions_endpoint_combines_recent_ledgers(self):
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
                    confirmed_at INTEGER
                )
                """
            )
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
                INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason, status,
                 created_at, confirms_at, tx_hash)
                VALUES (200, 7, 'alice', 'bob', 1500000, 'signed_transfer:coffee',
                        'pending', 205, 300, 'tx_pending')
                """
            )
            conn.execute(
                """
                INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason)
                VALUES (100, 6, 'carol', 2500000, 'transfer_in:dave:tx_confirmed')
                """
            )

        resp = self.client.get("/api/transactions?limit=10")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertTrue(body["ok"])
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["transactions"][0]["source"], "pending_ledger")
        self.assertEqual(body["transactions"][0]["tx_hash"], "tx_pending")
        self.assertEqual(body["transactions"][0]["from"], "alice")
        self.assertEqual(body["transactions"][0]["to"], "bob")
        self.assertEqual(body["transactions"][0]["status"], "pending")
        self.assertEqual(body["transactions"][0]["amount_rtc"], 1.5)

        self.assertEqual(body["transactions"][1]["source"], "ledger")
        self.assertEqual(body["transactions"][1]["tx_hash"], "tx_confirmed")
        self.assertEqual(body["transactions"][1]["miner_id"], "carol")
        self.assertEqual(body["transactions"][1]["counterparty"], "dave")
        self.assertEqual(body["transactions"][1]["direction"], "received")
        self.assertEqual(body["transactions"][1]["amount_rtc"], 2.5)

    def test_explorer_endpoints_return_empty_without_tables(self):
        blocks_resp = self.client.get("/api/blocks")
        tx_resp = self.client.get("/api/transactions")

        self.assertEqual(blocks_resp.status_code, 200)
        self.assertEqual(blocks_resp.get_json(), {"ok": True, "blocks": [], "count": 0, "total": 0})

        self.assertEqual(tx_resp.status_code, 200)
        self.assertEqual(tx_resp.get_json(), {"ok": True, "transactions": [], "count": 0, "total": 0})

    def test_explorer_endpoints_reject_invalid_pagination(self):
        blocks_resp = self.client.get("/api/blocks?limit=bad")
        tx_resp = self.client.get("/api/transactions?offset=bad")

        self.assertEqual(blocks_resp.status_code, 400)
        self.assertEqual(blocks_resp.get_json(), {"ok": False, "error": "limit must be an integer"})

        self.assertEqual(tx_resp.status_code, 400)
        self.assertEqual(tx_resp.get_json(), {"ok": False, "error": "offset must be an integer"})


if __name__ == "__main__":
    unittest.main()
