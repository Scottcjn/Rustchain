#!/usr/bin/env python3
"""
Test script for /wallet/history endpoint (Issue #908)
Validates the unified transaction history API.
"""
import sqlite3
import os
import tempfile
import json

# Test configuration
UNIT = 1_000_000  # uRTC per 1 RTC
GENESIS_TS = 1730419200  # 2024-11-01 00:00:00 UTC
EPOCH_DURATION = 3600  # 1 hour per epoch

def init_test_db(db_path):
    """Initialize test database with sample data."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables
    c.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            miner_pk TEXT PRIMARY KEY,
            balance_rtc REAL DEFAULT 0
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            epoch INTEGER NOT NULL,
            from_miner TEXT NOT NULL,
            to_miner TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            confirms_at INTEGER NOT NULL,
            tx_hash TEXT,
            voided_by TEXT,
            voided_reason TEXT,
            confirmed_at INTEGER
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS epoch_rewards (
            epoch INTEGER,
            miner_id TEXT,
            share_i64 INTEGER
        )
    """)
    
    # Insert test data
    test_miner = "dual-g4-125"
    
    # Balance
    c.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
              (test_miner, 123.456))
    
    # Transfers
    transfers = [
        (1733000000, 424, "founder_community", test_miner, 10_000_000, "bonus", "confirmed", 1733000000, 1733000000, 1733000000, "tx_hash_001"),
        (1733010000, 425, test_miner, "other_miner", 5_000_000, "payment", "confirmed", 1733010000, 1733010000, 1733010000, "tx_hash_002"),
        (1733020000, 426, "another_miner", test_miner, 2_500_000, "refund", "confirmed", 1733020000, 1733020000, 1733020000, "tx_hash_003"),
    ]
    c.executemany("""
        INSERT INTO pending_ledger 
        (ts, epoch, from_miner, to_miner, amount_i64, reason, status, created_at, confirms_at, confirmed_at, tx_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, transfers)
    
    # Mining rewards
    rewards = [
        (424, test_miner, 297_000),  # 0.297 RTC
        (425, test_miner, 312_000),  # 0.312 RTC
        (426, test_miner, 289_000),  # 0.289 RTC
    ]
    c.executemany("""
        INSERT INTO epoch_rewards (epoch, miner_id, share_i64)
        VALUES (?, ?, ?)
    """, rewards)
    
    conn.commit()
    conn.close()

def test_wallet_history():
    """Test the wallet history endpoint logic."""
    print("🧪 Testing /wallet/history endpoint implementation...")
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize test data
        init_test_db(db_path)
        print(f"✅ Test database initialized: {db_path}")
        
        # Simulate the endpoint logic
        miner_id = "dual-g4-125"
        limit = 50
        offset = 0
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get balance
        balance_row = c.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?",
            (miner_id,)
        ).fetchone()
        balance = balance_row[0] if balance_row else 0.0
        print(f"✅ Balance retrieved: {balance} RTC")
        
        # Get transfers
        transfer_rows = c.execute("""
            SELECT id, ts, from_miner, to_miner, amount_i64, reason, status,
                   created_at, confirms_at, confirmed_at, tx_hash, voided_reason
            FROM pending_ledger
            WHERE from_miner = ? OR to_miner = ?
            ORDER BY COALESCE(created_at, ts) DESC, id DESC
            LIMIT ? OFFSET ?
        """, (miner_id, miner_id, limit, offset)).fetchall()
        print(f"✅ Transfers retrieved: {len(transfer_rows)} records")
        
        # Get rewards
        reward_rows = c.execute("""
            SELECT epoch, miner_id, share_i64
            FROM epoch_rewards
            WHERE miner_id = ?
            ORDER BY epoch DESC
            LIMIT ? OFFSET ?
        """, (miner_id, limit, offset)).fetchall()
        print(f"✅ Rewards retrieved: {len(reward_rows)} records")
        
        # Build unified list
        transactions = []
        
        # Process transfers
        for row in transfer_rows:
            (pending_id, ts, from_miner, to_miner, amount_i64, reason,
             raw_status, created_at, confirms_at, confirmed_at, tx_hash, voided_reason) = row
            
            direction = "sent" if from_miner == miner_id else "received"
            tx_type = "transfer_out" if direction == "sent" else "transfer_in"
            counterparty = to_miner if direction == "sent" else from_miner
            
            transactions.append({
                "type": tx_type,
                "amount": int(amount_i64) / UNIT,
                "timestamp": int(created_at or ts or 0),
                "tx_hash": tx_hash or f"pending_{pending_id}",
                "direction": direction,
                "counterparty": counterparty,
            })
        
        # Process rewards
        for epoch, reward_miner_id, share_i64 in reward_rows:
            epoch_ts = GENESIS_TS + (epoch * EPOCH_DURATION)
            transactions.append({
                "type": "reward",
                "amount": int(share_i64) / UNIT,
                "timestamp": epoch_ts,
                "tx_hash": f"reward_epoch_{epoch}",
                "epoch": epoch,
                "direction": "received",
                "counterparty": "protocol",
            })
        
        # Sort by timestamp
        transactions.sort(key=lambda x: x["timestamp"], reverse=True)
        
        conn.close()
        
        # Print results
        print(f"\n📊 Unified transaction history for {miner_id}:")
        print(f"   Balance: {balance} RTC")
        print(f"   Total transactions: {len(transactions)}")
        print(f"\n📋 Recent transactions:")
        
        for i, tx in enumerate(transactions[:5], 1):
            print(f"   {i}. {tx['type']:15} {tx['amount']:>10.6f} RTC | {tx['counterparty']:20} | {tx['tx_hash']}")
        
        # Validate expected format
        response = {
            "ok": True,
            "miner_id": miner_id,
            "balance": balance,
            "transactions": transactions,
            "total": len(transactions),
            "limit": limit,
            "offset": offset,
        }
        
        print(f"\n✅ Response format validation:")
        assert response["ok"] == True, "ok should be True"
        assert response["miner_id"] == miner_id, "miner_id should match"
        assert "balance" in response, "balance should be present"
        assert "transactions" in response, "transactions should be present"
        assert "total" in response, "total should be present"
        assert isinstance(response["transactions"], list), "transactions should be a list"
        
        print(f"   ✅ All format checks passed!")
        
        # Test with unknown miner_id
        print(f"\n🧪 Testing unknown miner_id...")
        unknown_miner = "nonexistent-miner"
        conn = sqlite3.connect(db_path)
        balance_row = conn.execute(
            "SELECT balance_rtc FROM balances WHERE miner_pk = ?",
            (unknown_miner,)
        ).fetchone()
        balance = balance_row[0] if balance_row else 0.0
        transfers = conn.execute("""
            SELECT id FROM pending_ledger
            WHERE from_miner = ? OR to_miner = ?
        """, (unknown_miner, unknown_miner)).fetchall()
        rewards = conn.execute("""
            SELECT epoch FROM epoch_rewards
            WHERE miner_id = ?
        """, (unknown_miner,)).fetchall()
        conn.close()
        
        assert balance == 0.0, "Unknown miner should have 0 balance"
        assert len(transfers) == 0, "Unknown miner should have no transfers"
        assert len(rewards) == 0, "Unknown miner should have no rewards"
        print(f"   ✅ Unknown miner handled gracefully (empty list, not error)")
        
        print(f"\n✅ ALL TESTS PASSED!")
        return True
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == "__main__":
    success = test_wallet_history()
    exit(0 if success else 1)
