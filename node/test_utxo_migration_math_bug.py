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

    def test_genesis_math_bug(self):
        # 1. Migrate genesis using fallback query
        result = migrate(self.db_path, dry_run=False)
        
        db = UtxoDB(self.db_path)
        alice_balance = db.get_balance('alice')
        
        # We expected 10 RTC = 1_000_000_000 nanoRTC
        expected_balance = 10 * UNIT
        
        # BUT because of the 1000000 multiplier bug in the fallback query,
        # it gives 10.0 * 1000000 = 10000000 nanoRTC
        # Which is 100x smaller!
        self.assertNotEqual(alice_balance, expected_balance)
        self.assertEqual(alice_balance, 10_000_000)

if __name__ == '__main__':
    unittest.main()
