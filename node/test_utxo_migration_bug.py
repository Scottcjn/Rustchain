import os
import tempfile
import time
import unittest
import sqlite3

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import migrate, rollback_genesis, GENESIS_HEIGHT

class TestGenesisDuplication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        
        # Setup account balances
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE balances (miner_id TEXT, amount_i64 INTEGER)")
        conn.execute("INSERT INTO balances VALUES ('alice', ?)", (100 * UNIT,))
        conn.commit()
        conn.close()
        
    def tearDown(self):
        os.unlink(self.db_path)

    def test_genesis_duplication_via_rollback(self):
        # 1. Migrate genesis
        result = migrate(self.db_path, dry_run=False)
        self.assertTrue(result['integrity']['ok'])
        
        db = UtxoDB(self.db_path)
        alice_boxes = db.get_unspent_for_address('alice')
        self.assertEqual(len(alice_boxes), 1)
        alice_box = alice_boxes[0]
        
        # 2. Alice spends her genesis box
        ok = db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_box['box_id'], 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=1)
        self.assertTrue(ok)
        
        self.assertEqual(db.get_balance('alice'), 0)
        self.assertEqual(db.get_balance('bob'), 100 * UNIT)
        
        # 3. Admin rolls back genesis
        # The rollback deletes the genesis box (which is now spent)
        # But leaves Bob's box intact!
        deleted = rollback_genesis(self.db_path)
        self.assertEqual(deleted, 1)
        
        # 4. Admin re-runs migration
        result = migrate(self.db_path, dry_run=False)
        self.assertTrue(result['integrity']['ok'])
        
        # 5. Duplication!
        # Alice has her genesis box back, AND Bob still has his 100 RTC!
        self.assertEqual(db.get_balance('alice'), 100 * UNIT)
        self.assertEqual(db.get_balance('bob'), 100 * UNIT)
        
        # Total supply is now 200 RTC, even though account balance was 100 RTC
        self.assertEqual(db.get_balance('alice') + db.get_balance('bob'), 200 * UNIT)

if __name__ == '__main__':
    unittest.main()
