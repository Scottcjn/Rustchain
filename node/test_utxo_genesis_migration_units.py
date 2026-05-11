"""
Regression tests for UTXO genesis migration account-unit conversion.

Account-model balances use amount_i64 at 6 decimals (micro-RTC), while UTXO
boxes use nanoRTC at 8 decimals. The genesis migration must convert before
creating boxes and before comparing integrity totals.
"""

import os
import sqlite3
import tempfile
import unittest

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import ACCOUNT_UNIT, load_account_balances, migrate


class TestGenesisMigrationUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def test_amount_i64_balances_convert_from_micro_rtc_to_nrtc(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL
            )
        """)
        conn.executemany(
            "INSERT INTO balances VALUES (?, ?)",
            [
                ("alice", 1 * ACCOUNT_UNIT),
                ("bob", 2 * ACCOUNT_UNIT + 500_000),
            ],
        )
        conn.commit()
        conn.close()

        balances = load_account_balances(self.db_path)
        self.assertEqual(balances, [
            ("alice", 1 * UNIT),
            ("bob", 250_000_000),
        ])

        result = migrate(self.db_path, dry_run=False)
        db = UtxoDB(self.db_path)

        self.assertEqual(result["total_nrtc"], 350_000_000)
        self.assertEqual(db.get_balance("alice"), 1 * UNIT)
        self.assertEqual(db.get_balance("bob"), 250_000_000)
        self.assertTrue(result["integrity"]["ok"])
        self.assertTrue(result["integrity"]["models_agree"])
        self.assertEqual(result["integrity"]["expected_total_nrtc"], 350_000_000)

    def test_legacy_balance_rtc_fallback_converts_to_nrtc(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE balances (
                miner_pk TEXT PRIMARY KEY,
                balance_rtc REAL NOT NULL
            )
        """)
        conn.execute("INSERT INTO balances VALUES (?, ?)", ("alice", 10.0))
        conn.commit()
        conn.close()

        result = migrate(self.db_path, dry_run=False)
        db = UtxoDB(self.db_path)

        self.assertEqual(result["total_nrtc"], 10 * UNIT)
        self.assertEqual(db.get_balance("alice"), 10 * UNIT)
        self.assertTrue(result["integrity"]["models_agree"])


if __name__ == '__main__':
    unittest.main()
