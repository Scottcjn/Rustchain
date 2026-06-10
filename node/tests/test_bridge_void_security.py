import sqlite3
import unittest
from node.bridge_api import void_bridge_transfer, get_bridge_transfer_by_hash, create_bridge_transfer, BridgeTransferRequest

class TestBridgeVoidSecurity(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE bridge_transfers (id INTEGER PRIMARY KEY, tx_hash TEXT, direction TEXT, source_chain TEXT, dest_chain TEXT, source_address TEXT, dest_address TEXT, amount_i64 INTEGER, amount_rtc REAL, bridge_type TEXT, bridge_fee_i64 INTEGER, external_tx_hash TEXT, external_confirmations INTEGER, required_confirmations INTEGER, status TEXT, lock_epoch INTEGER, created_at INTEGER, updated_at INTEGER, expires_at INTEGER, completed_at INTEGER, voided_by TEXT, voided_reason TEXT, failure_reason TEXT, memo TEXT)")
        self.conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
        self.conn.execute("CREATE TABLE lock_ledger (id INTEGER PRIMARY KEY, bridge_transfer_id INTEGER, miner_id TEXT, amount_i64 INTEGER, lock_type TEXT, locked_at INTEGER, unlock_at INTEGER, status TEXT, created_at INTEGER, released_by TEXT, unlocked_at INTEGER, release_tx_hash TEXT)")
        # Setup initial balance for the test miner
        self.conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES ('RTC123', 1000000000)")
        self.conn.commit()
        
    def test_void_only_releases_bridge_locks(self):
        # 1. Create a bridge transfer
        req = BridgeTransferRequest("deposit", "rustchain", "solana", "RTC123", "SOL456", 10.0)
        success, result = create_bridge_transfer(self.conn, req)
        transfer_id = result["bridge_transfer_id"]
        tx_hash = result["tx_hash"]
        
        # 2. Add a legitimate bridge lock
        self.conn.execute("INSERT INTO lock_ledger (bridge_transfer_id, lock_type, status) VALUES (?, 'bridge_deposit', 'locked')", (transfer_id,))
        
        # 3. Add a SENSITIVE lock (e.g., epoch settlement) with the SAME transfer ID
        # In a real system, transfer_id might be reused or shifted, but let's simulate a clash
        self.conn.execute("INSERT INTO lock_ledger (bridge_transfer_id, lock_type, status) VALUES (?, 'epoch_settlement', 'locked')", (transfer_id,))
        self.conn.commit()
        
        # 4. Void the transfer
        ok, res = void_bridge_transfer(self.conn, tx_hash, "test reason", "admin")
        self.assertTrue(ok)
        
        # 5. Verify that ONLY the bridge_transfer lock was released
        cursor = self.conn.cursor()
        
        # Bridge lock should be released
        bridge_lock = cursor.execute("SELECT status FROM lock_ledger WHERE lock_type = 'bridge_deposit'").fetchone()
        self.assertEqual(bridge_lock[0], 'released')
        
        # Epoch lock MUST still be locked
        epoch_lock = cursor.execute("SELECT status FROM lock_ledger WHERE lock_type = 'epoch_settlement'").fetchone()
        self.assertEqual(epoch_lock[0], 'locked', "CRITICAL: void_bridge_transfer released a non-bridge lock!")
        
    def tearDown(self):
        self.conn.close()

if __name__ == "__main__":
    unittest.main()
