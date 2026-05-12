import os
import tempfile
import time
import unittest
import sqlite3

from utxo_db import UtxoDB, UNIT
from utxo_genesis_migration import migrate, rollback_genesis, GENESIS_HEIGHT

class TestGenesisDuplicationFix(unittest.TestCase):
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

    def test_genesis_rollback_prevention_on_spend(self):
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
        
        # 3. Admin attempts to rollback genesis
        # The rollback MUST FAIL because a genesis box has been spent.
        # This prevents the duplication bug.
        with self.assertRaises(ValueError) as cm:
            rollback_genesis(self.db_path)
        self.assertIn("Cannot rollback genesis: some genesis boxes have already been spent", str(cm.exception))
        
        # 4. Verify that no boxes were deleted and balances are intact
        # (Alice's spent box is still marked as spent, Bob's box still exists)
        self.assertEqual(db.get_balance('alice'), 0)
        self.assertEqual(db.get_balance('bob'), 100 * UNIT)
        
        # Total supply remains 100 RTC
        self.assertEqual(db.get_balance('alice') + db.get_balance('bob'), 100 * UNIT)

if __name__ == '__main__':
    unittest.main()
