"""
Test for Critical Vulnerability #1: Genesis Migration Race Condition
======================================================================

This test demonstrates a race condition in utxo_genesis_migration.py
that can lead to fund duplication (all account balances doubled).

Vulnerability: check_existing_genesis() is called outside the transaction,
allowing multiple nodes to pass the check simultaneously and create
duplicate genesis boxes.

Expected: Genesis boxes created only once
Actual (with bug): Genesis boxes created twice (or more)
"""

import os
import sys
import tempfile
import threading
import time
import sqlite3

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from node.utxo_genesis_migration import migrate, rollback_genesis
from node.utxo_db import UtxoDB


def test_genesis_migration_race():
    """
    Test that demonstrates the race condition in genesis migration.
    
    Steps:
    1. Create a test database with account balances
    2. Run migrate() in two threads simultaneously
    3. Verify that genesis boxes are duplicated
    """
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize account balances
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL
            )
        """)
        
        # Insert test balances
        test_balances = [
            ('miner_001', 100_000_000),  # 1 RTC
            ('miner_002', 200_000_000),  # 2 RTC
            ('miner_003', 300_000_000),  # 3 RTC
        ]
        conn.executemany(
            "INSERT INTO balances VALUES (?, ?)",
            test_balances
        )
        conn.commit()
        conn.close()
        
        # Initialize UTXO tables
        utxo_db = UtxoDB(db_path)
        utxo_db.init_tables()
        
        # Track results from threads
        results = []
        
        def run_migration():
            """Run migration in a thread"""
            try:
                result = migrate(db_path, dry_run=False)
                results.append(result)
            except Exception as e:
                results.append({'error': str(e)})
        
        # Start two threads simultaneously
        t1 = threading.Thread(target=run_migration)
        t2 = threading.Thread(target=run_migration)
        
        t1.start()
        time.sleep(0.05)  # Small delay to let first thread check
        t2.start()
        
        t1.join()
        t2.join()
        
        # Check results
        print("\n=== Migration Results ===")
        for i, result in enumerate(results, 1):
            print(f"Thread {i}: {result}")
        
        # Count genesis boxes
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_boxes WHERE creation_height = 0"
        ).fetchone()['n']
        conn.close()
        
        print(f"\nGenesis boxes created: {count}")
        print(f"Expected: {len(test_balances)}")
        
        # BUG: If count > len(test_balances), we have duplication
        if count > len(test_balances):
            print("🔴 CRITICAL BUG DETECTED: Genesis boxes duplicated!")
            print(f"   Duplication factor: {count / len(test_balances):.2f}x")
            raise AssertionError("Genesis boxes duplicated")
        print("✅ PASS: Genesis migration is atomic")
            
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_genesis_migration_rollback():
    """
    Test that rollback is atomic and complete.
    """
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Setup
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL
            )
        """)
        conn.execute("INSERT INTO balances VALUES (?, ?)", ("miner_001", 100_000_000))
        conn.commit()
        conn.close()
        
        # Run migration
        migrate(db_path, dry_run=False)
        
        # Rollback
        deleted = rollback_genesis(db_path)
        
        # Verify rollback
        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_boxes WHERE creation_height = 0"
        ).fetchone()[0]
        conn.close()
        
        print(f"Genesis boxes after rollback: {count}")
        
        if count != 0:
            print("🔴 BUG: Rollback incomplete!")
            raise AssertionError("Rollback left genesis boxes behind")
        print("✅ PASS: Rollback is complete")
            
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Genesis Migration Race Condition")
    print("=" * 60)
    
    # Test 1: Race condition
    test_genesis_migration_race()
    
    print("\n" + "=" * 60)
    print("Testing Genesis Migration Rollback")
    print("=" * 60)
    
    # Test 2: Rollback
    test_genesis_migration_rollback()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    sys.exit(0)
