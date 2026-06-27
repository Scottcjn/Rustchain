# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"
TX_HASH = "0123456789abcdef0123456789abcdef"


class TestWalletTxStatusEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_env = {
            key: os.environ.get(key)
            for key in (
                "RUSTCHAIN_DB_PATH",
                "RC_ADMIN_KEY",
                "RUSTCHAIN_DISABLE_P2P_AUTO_START",
            )
        }
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "test.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_wallet_tx_status_test",
            MODULE_PATH,
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.client = cls.mod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        for key, value in cls._prev_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls._tmp.cleanup()

    def setUp(self):
        with sqlite3.connect(self.mod.DB_PATH) as db:
            db.executescript(
                """
                DROP TABLE IF EXISTS pending_ledger;
                DROP TABLE IF EXISTS ledger;

                CREATE TABLE pending_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER,
                    epoch INTEGER,
                    from_miner TEXT,
                    to_miner TEXT,
                    amount_i64 INTEGER,
                    reason TEXT,
                    status TEXT,
                    created_at INTEGER,
                    confirms_at INTEGER,
                    tx_hash TEXT,
                    voided_by TEXT,
                    voided_reason TEXT,
                    confirmed_at INTEGER
                );

                CREATE TABLE ledger (
                    ts INTEGER,
                    epoch INTEGER,
                    miner_id TEXT,
                    delta_i64 INTEGER,
                    reason TEXT
                );
                """
            )

    def _insert_pending(self, status="pending", tx_hash=TX_HASH, amount=5_000_000):
        with sqlite3.connect(self.mod.DB_PATH) as db:
            db.execute(
                """
                INSERT INTO pending_ledger
                    (ts, epoch, from_miner, to_miner, amount_i64, reason,
                     status, created_at, confirms_at, tx_hash, confirmed_at,
                     voided_by, voided_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1700000000,
                    42,
                    "alice",
                    "bob",
                    amount,
                    "signed_transfer:private memo",
                    status,
                    1700000000,
                    1700003600,
                    tx_hash,
                    1700007200 if status == "confirmed" else None,
                    "admin",
                    "private void reason",
                ),
            )

    def _insert_verified_ledger_pair(self, tx_hash=TX_HASH):
        with sqlite3.connect(self.mod.DB_PATH) as db:
            db.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                (1700007300, 42, "alice", -5_000_000, f"transfer_out:bob:{tx_hash}"),
            )
            db.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                (1700007300, 42, "bob", 5_000_000, f"transfer_in:alice:{tx_hash}"),
            )

    def test_pending_lookup_is_status_only(self):
        self._insert_pending(status="pending")

        response = self.client.get(f"/wallet/tx/{TX_HASH}")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body, {
            "ok": True,
            "tx_hash": TX_HASH,
            "status": "pending",
            "confirmations": 0,
            "block_height": None,
        })
        for private_key in (
            "from_miner",
            "to_miner",
            "from",
            "to",
            "amount_i64",
            "amount_rtc",
            "pending_id",
            "reason",
            "voided_reason",
        ):
            self.assertNotIn(private_key, body)

    def test_confirmed_pending_requires_verified_double_entry(self):
        self._insert_pending(status="confirmed")

        response = self.client.get(f"/wallet/tx/{TX_HASH}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "pending")

        self._insert_verified_ledger_pair()
        response = self.client.get(f"/wallet/tx/{TX_HASH}")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "confirmed")
        self.assertEqual(body["confirmations"], 1)
        self.assertEqual(body["block_height"], 42)

    def test_ledger_only_lookup_requires_balanced_double_entry(self):
        with sqlite3.connect(self.mod.DB_PATH) as db:
            db.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                (1700007300, 42, "bob", 5_000_000, f"transfer_in:alice:{TX_HASH}"),
            )

        response = self.client.get(f"/wallet/tx/{TX_HASH}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["status"], "not_found")

        with sqlite3.connect(self.mod.DB_PATH) as db:
            db.execute("DELETE FROM ledger")

        self._insert_verified_ledger_pair()
        response = self.client.get(f"/wallet/tx/{TX_HASH}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "confirmed")

    def test_duplicate_pending_hash_is_ambiguous(self):
        self._insert_pending(status="pending")
        self._insert_pending(status="voided")

        response = self.client.get(f"/wallet/tx/{TX_HASH}")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json(), {
            "ok": False,
            "error": "ambiguous_transaction",
        })

    def test_rejects_short_or_non_hex_hashes(self):
        for bad_hash in ("abc", "g" * 32, TX_HASH + "00"):
            response = self.client.get(f"/wallet/tx/{bad_hash}")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()["ok"], False)


if __name__ == "__main__":
    unittest.main()
