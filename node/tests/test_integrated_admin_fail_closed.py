# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


class TestIntegratedAdminFailClosed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._import_tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._import_tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_admin_fail_closed_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

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
        cls.mod.DB_PATH = None
        sys.modules.pop(cls.mod.__name__, None)
        del cls.mod
        cls._import_tmp.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "admin_fail_closed.db")
        self._prev_module_db = self.mod.DB_PATH
        self._prev_admin_env = os.environ.get("RC_ADMIN_KEY")
        self.mod.DB_PATH = self.db_path
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
        self._init_db()
        self.client = self.mod.app.test_client()

    def tearDown(self):
        self.mod.DB_PATH = self._prev_module_db
        if self._prev_admin_env is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = self._prev_admin_env
        self._tmp.cleanup()

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            db.executescript(
                """
                CREATE TABLE balances (
                    miner_id TEXT PRIMARY KEY,
                    amount_i64 INTEGER DEFAULT 0,
                    balance_rtc REAL DEFAULT 0
                );
                CREATE TABLE ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    epoch INTEGER NOT NULL,
                    miner_id TEXT NOT NULL,
                    delta_i64 INTEGER NOT NULL,
                    reason TEXT
                );
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
                    voided_by TEXT,
                    voided_reason TEXT,
                    confirmed_at INTEGER
                );
                CREATE UNIQUE INDEX idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);
                """
            )
            db.execute(
                "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
                ("alice", 10_000_000, 10.0),
            )
            db.execute(
                "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
                ("bob", 0, 0.0),
            )

    def test_wallet_transfer_rejects_empty_header_when_admin_key_unset(self):
        os.environ.pop("RC_ADMIN_KEY", None)

        resp = self.client.post(
            "/wallet/transfer",
            json={"from_miner": "alice", "to_miner": "bob", "amount_rtc": 1},
        )

        self.assertEqual(resp.status_code, 401)
        with closing(sqlite3.connect(self.db_path)) as db:
            pending_count = db.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0]
        self.assertEqual(pending_count, 0)

    def test_pending_confirm_rejects_empty_header_when_admin_key_unset(self):
        os.environ.pop("RC_ADMIN_KEY", None)

        resp = self.client.post("/pending/confirm", json={})

        self.assertEqual(resp.status_code, 401)

    def test_pending_integrity_rejects_empty_header_when_admin_key_unset(self):
        os.environ.pop("RC_ADMIN_KEY", None)

        resp = self.client.get("/pending/integrity")

        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
