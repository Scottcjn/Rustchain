import sqlite3
import unittest
from node.bridge_api import void_bridge_transfer, generate_bridge_tx_hash, LockType

class TestBridgeVoid(unittest.TestCase):
    def setUp(self):
        # Use in-memory database for testing
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        
        # Setup full schema based on bridge_api.py
        self.cursor.execute("""
            CREATE TABLE bridge_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                direction TEXT NOT NULL,
                source_chain TEXT NOT NULL,
                dest_chain TEXT NOT NULL,
                source_address TEXT NOT NULL,
                dest_address TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                amount_rtc REAL NOT NULL,
                bridge_type TEXT NOT NULL,
                bridge_fee_i64 INTEGER,
                external_tx_hash TEXT,
                external_confirmations INTEGER,
                required_confirmations INTEGER,
                status TEXT NOT NULL,
                lock_epoch INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                expires_at INTEGER,
                completed_at INTEGER,
                tx_hash TEXT UNIQUE NOT NULL,
                voided_by TEXT,
                voided_reason TEXT,
                failure_reason TEXT,
                memo TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE lock_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bridge_transfer_id INTEGER,
                miner_id TEXT,
                amount_i64 INTEGER,
                lock_type TEXT,
                locked_at INTEGER,
                unlock_at INTEGER,
                status TEXT,
                created_at INTEGER,
                released_by TEXT,
                unlocked_at INTEGER
            )
        """)
        self.conn.commit()

    def test_void_releases_bridge_lock(self):
        # 1. Create a bridge transfer
        tx_hash = "test_bridge_hash_123"
        self.cursor.execute("""
            INSERT INTO bridge_transfers 
            (direction, source_chain, dest_chain, source_address, dest_address, 
             amount_i64, amount_rtc, bridge_type, status, lock_epoch, 
             created_at, updated_at, tx_hash) 
            VALUES ('deposit', 'rustchain', 'solana', 'RTC1', 'SOL1', 1000, 0.001, 'bottube', 'locked', 1, 100, 100, ?)
        """, (tx_hash,))
        transfer_id = self.cursor.lastrowid
        
        # 2. Create a BRIDGE lock
        self.cursor.execute(
            "INSERT INTO lock_ledger (bridge_transfer_id, lock_type, status) VALUES (?, ?, 'locked')",
            (transfer_id, "bridge_deposit")
        )
        self.conn.commit()
        
        # 3. Void the transfer
        success, result = void_bridge_transfer(self.conn, tx_hash, "test reason", "admin")
        self.assertTrue(success)
        
        # 4. Verify lock is released
        row = self.cursor.execute("SELECT status FROM lock_ledger WHERE bridge_transfer_id = ?", (transfer_id,)).fetchone()
        self.assertEqual(row[0], "released")

    def test_void_does_not_release_settlement_lock(self):
        # 1. Create a bridge transfer
        tx_hash = "test_settle_hash_456"
        self.cursor.execute("""
            INSERT INTO bridge_transfers 
            (direction, source_chain, dest_chain, source_address, dest_address, 
             amount_i64, amount_rtc, bridge_type, status, lock_epoch, 
             created_at, updated_at, tx_hash) 
            VALUES ('deposit', 'rustchain', 'solana', 'RTC2', 'SOL2', 1000, 0.001, 'bottube', 'locked', 1, 100, 100, ?)
        """, (tx_hash,))
        transfer_id = self.cursor.lastrowid
        
        # 2. Create an EPOCH SETTLEMENT lock (Should NOT be released by bridge void)
        self.cursor.execute(
            "INSERT INTO lock_ledger (bridge_transfer_id, lock_type, status) VALUES (?, ?, 'locked')",
            (transfer_id, "epoch_settlement")
        )
        self.conn.commit()
        
        # 3. Void the transfer
        success, result = void_bridge_transfer(self.conn, tx_hash, "test reason", "admin")
        self.assertTrue(success)
        
        # 4. Verify lock is STILL LOCKED
        row = self.cursor.execute("SELECT status FROM lock_ledger WHERE bridge_transfer_id = ?", (transfer_id,)).fetchone()
        self.assertEqual(row[0], "locked", "Settlement lock should not be released by bridge void!")

    def tearDown(self):
        self.conn.close()

if __name__ == "__main__":
    unittest.main()
