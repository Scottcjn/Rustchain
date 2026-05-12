import os
import tempfile
import unittest
import sqlite3

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import migrate

class TestGenesisMathFix(unittest.TestCase):
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

    def test_genesis_math_fix(self):
        # 1. Migrate genesis using fallback query
        result = migrate(self.db_path, dry_run=False)
        self.assertTrue(result['integrity']['ok'])

        db = UtxoDB(self.db_path)
        alice_balance = db.get_balance('alice')

        # 10 RTC = 1_000_000_000 nanoRTC
        expected_balance = 10 * UNIT

        # The fix ensures that balance_rtc (REAL) is multiplied by 10^8 (UNIT)
        # instead of 10^6, ensuring correct fund conservation.
        self.assertEqual(alice_balance, expected_balance)
        self.assertEqual(alice_balance, 1_000_000_000)

if __name__ == '__main__':
    unittest.main()
