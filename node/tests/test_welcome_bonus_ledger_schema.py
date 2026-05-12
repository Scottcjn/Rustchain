# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


def load_node_module():
    os.environ.setdefault("RC_ADMIN_KEY", "test-admin-key-000000000000000000")
    spec = importlib.util.spec_from_file_location("rustchain_welcome_bonus_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWelcomeBonusLedgerSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_node_module()

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db_path = self.mod.DB_PATH
        self.mod.DB_PATH = self.db_path

    def tearDown(self):
        self.mod.DB_PATH = self.original_db_path
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _seed_current_schema(self, miner="RTC-new-miner"):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE miner_attest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner TEXT NOT NULL,
                    ts_ok INTEGER NOT NULL
                );

                CREATE TABLE balances (
                    miner_id TEXT PRIMARY KEY,
                    amount_i64 INTEGER DEFAULT 0,
                    balance_rtc REAL DEFAULT 0
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
            conn.execute(
                "INSERT INTO miner_attest_history (miner, ts_ok) VALUES (?, 100)",
                (miner,),
            )
            conn.execute(
                "INSERT INTO balances (miner_id, amount_i64, balance_rtc) VALUES (?, ?, ?)",
                (self.mod.WELCOME_BONUS_SOURCE, 2_000_000, 2.0),
            )
            conn.commit()

    def _seed_legacy_schema(self, miner="RTC-legacy-miner"):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE miner_attest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner TEXT NOT NULL,
                    ts_ok INTEGER NOT NULL
                );

                CREATE TABLE balances (
                    miner_pk TEXT PRIMARY KEY,
                    balance_rtc REAL DEFAULT 0
                );

                CREATE TABLE ledger (
                    from_miner TEXT,
                    to_miner TEXT,
                    amount_i64 INTEGER,
                    memo TEXT,
                    ts INTEGER
                );
                """
            )
            conn.execute(
                "INSERT INTO miner_attest_history (miner, ts_ok) VALUES (?, 100)",
                (miner,),
            )
            conn.execute(
                "INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
                (self.mod.WELCOME_BONUS_SOURCE, 2.0),
            )
            conn.commit()

    def test_welcome_bonus_uses_current_account_ledger_schema(self):
        miner = "RTC-new-miner"
        self._seed_current_schema(miner)

        self.mod._check_welcome_bonus(miner)
        self.mod._check_welcome_bonus(miner)

        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = dict(
                (miner_id, (amount_i64, balance_rtc))
                for miner_id, amount_i64, balance_rtc in conn.execute(
                    "SELECT miner_id, amount_i64, balance_rtc FROM balances"
                ).fetchall()
            )
            ledger_rows = conn.execute(
                "SELECT miner_id, delta_i64, reason FROM ledger ORDER BY delta_i64"
            ).fetchall()

        bonus_i64 = int(self.mod.WELCOME_BONUS_RTC * self.mod.ACCOUNT_UNIT)
        self.assertEqual(
            rows,
            {
                self.mod.WELCOME_BONUS_SOURCE: (2_000_000 - bonus_i64, 1.5),
                miner: (bonus_i64, self.mod.WELCOME_BONUS_RTC),
            },
        )
        self.assertEqual(
            ledger_rows,
            [
                (self.mod.WELCOME_BONUS_SOURCE, -bonus_i64, "welcome_bonus:0.5_rtc"),
                (miner, bonus_i64, "welcome_bonus:0.5_rtc"),
            ],
        )

    def test_welcome_bonus_preserves_legacy_transfer_ledger_schema(self):
        miner = "RTC-legacy-miner"
        self._seed_legacy_schema(miner)

        self.mod._check_welcome_bonus(miner)
        self.mod._check_welcome_bonus(miner)

        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = dict(
                conn.execute("SELECT miner_pk, balance_rtc FROM balances").fetchall()
            )
            ledger_rows = conn.execute(
                "SELECT from_miner, to_miner, amount_i64, memo FROM ledger"
            ).fetchall()

        bonus_i64 = int(self.mod.WELCOME_BONUS_RTC * self.mod.ACCOUNT_UNIT)
        self.assertEqual(
            rows,
            {
                self.mod.WELCOME_BONUS_SOURCE: 1.5,
                miner: self.mod.WELCOME_BONUS_RTC,
            },
        )
        self.assertEqual(
            ledger_rows,
            [
                (
                    self.mod.WELCOME_BONUS_SOURCE,
                    miner,
                    bonus_i64,
                    "welcome_bonus:0.5_rtc",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
