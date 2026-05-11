# SPDX-License-Identifier: MIT
import os
import tempfile
import unittest
import sqlite3

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import migrate

class TestGenesisMathBug(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        
        # Setup account balances using the OLD schema (miner_pk, balance_rtc)
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE balances (miner_pk TEXT, balance_rtc REAL)")
        # 10 RTC = 1_000_000_000 nanoRTC
        conn.execute("INSERT INTO balances VALUES ('alice', ?)", (10.0,))
        conn.commit()
        conn.close()
        
    def tearDown(self):
        os.unlink(self.db_path)

    def test_genesis_math_bug_fixed(self):
        """Fallback migration must use UNIT (100_000_000) not 1_000_000 as multiplier.

        Previously the fallback query used balance_rtc * 1_000_000, which produced
        amounts 100x too small, destroying user funds during migration. The fix
        uses the correct UNIT constant (100_000_000 nanoRTC per RTC).
        """
        result = migrate(self.db_path, dry_run=False)
        self.assertTrue(result['integrity']['ok'])

        db = UtxoDB(self.db_path)
        alice_balance = db.get_balance('alice')

        # 10 RTC must migrate to exactly 10 * UNIT = 1_000_000_000 nanoRTC
        self.assertEqual(alice_balance, 10 * UNIT)

if __name__ == '__main__':
    unittest.main()
