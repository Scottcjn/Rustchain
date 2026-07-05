import os
import sys
import sqlite3
import unittest
import tempfile

# Add node directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib.util
NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
spec = importlib.util.spec_from_file_location("rustchain_integrated_rewards_test", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
migrate_lequangsang_balances = mod.migrate_lequangsang_balances

class TestLequangsangBalanceMigration(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_migration_new_schema(self):
        # Create table in new schema format
        self.cursor.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
        
        # Populate balances
        self.cursor.execute("INSERT INTO balances VALUES ('lequangsang01', 30000000)")
        self.cursor.execute("INSERT INTO balances VALUES ('RTCfe13452d122263caf633ab1876bd9631133b68b', 20000000)")
        self.cursor.execute("INSERT INTO balances VALUES ('RTCfe13452d122263caf633ab1876bd9631133b68b1', 10000000)")
        self.conn.commit()

        # Run migration
        migrate_lequangsang_balances(self.cursor)
        self.conn.commit()

        # Verify balances
        row_target = self.cursor.execute("SELECT amount_i64 FROM balances WHERE miner_id='RTCfe13452d122263caf633ab1876bd9631133b68b1'").fetchone()
        row_src1 = self.cursor.execute("SELECT amount_i64 FROM balances WHERE miner_id='lequangsang01'").fetchone()
        row_src2 = self.cursor.execute("SELECT amount_i64 FROM balances WHERE miner_id='RTCfe13452d122263caf633ab1876bd9631133b68b'").fetchone()

        self.assertEqual(row_target[0], 60000000) # 10M original + 30M + 20M
        self.assertEqual(row_src1[0], 0)
        self.assertEqual(row_src2[0], 0)

    def test_migration_legacy_schema(self):
        # Create table in legacy schema format
        self.cursor.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL)")
        
        # Populate balances
        self.cursor.execute("INSERT INTO balances VALUES ('lequangsang01', 30.0)")
        self.cursor.execute("INSERT INTO balances VALUES ('RTCfe13452d122263caf633ab1876bd9631133b68b', 20.0)")
        self.cursor.execute("INSERT INTO balances VALUES ('RTCfe13452d122263caf633ab1876bd9631133b68b1', 10.0)")
        self.conn.commit()

        # Run migration
        migrate_lequangsang_balances(self.cursor)
        self.conn.commit()

        # Verify balances
        row_target = self.cursor.execute("SELECT balance_rtc FROM balances WHERE miner_pk='RTCfe13452d122263caf633ab1876bd9631133b68b1'").fetchone()
        row_src1 = self.cursor.execute("SELECT balance_rtc FROM balances WHERE miner_pk='lequangsang01'").fetchone()
        row_src2 = self.cursor.execute("SELECT balance_rtc FROM balances WHERE miner_pk='RTCfe13452d122263caf633ab1876bd9631133b68b'").fetchone()

        self.assertAlmostEqual(row_target[0], 60.0) # 10.0 original + 30.0 + 20.0
        self.assertAlmostEqual(row_src1[0], 0.0)
        self.assertAlmostEqual(row_src2[0], 0.0)

if __name__ == '__main__':
    unittest.main()
