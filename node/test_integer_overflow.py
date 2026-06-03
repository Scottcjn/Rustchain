"""
Test for High Severity Vulnerability #2: Integer Overflow DoS
==============================================================

This test demonstrates an integer overflow vulnerability in utxo_db.py
that can lead to node crash or consensus divergence.

Vulnerability: Missing range checks on fee_nrtc and timestamp fields
allows extremely large values that cause SQLite integer overflow.

Expected: Transaction rejected with invalid fee/timestamp
Actual (with bug): SQLite error → Node crash
"""

import os
import sys
import tempfile
import sqlite3
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from node.utxo_db import UtxoDB, compute_box_id, address_to_proposition

TEST_TX_ID = "00" * 32


def test_fee_overflow():
    """
    Test that extremely large fees are rejected.
    
    Steps:
    1. Create a UTXO box with balance
    2. Attempt to spend it with fee_nrtc = 2^63 - 1
    3. Verify transaction is rejected (not crash)
    """
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize database
        db = UtxoDB(db_path)
        db.init_tables()
        
        # Create a test UTXO
        conn = db._conn()
        test_box_id = compute_box_id(
            1000_000_000,  # 10 RTC
            address_to_proposition('RTC_TEST'),
            0, TEST_TX_ID, 0
        )
        
        conn.execute(
            """INSERT INTO utxo_boxes
               (box_id, value_nrtc, proposition, owner_address,
                creation_height, transaction_id, output_index,
                created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (test_box_id, 1000_000_000, address_to_proposition('RTC_TEST'),
             'RTC_TEST', 0, TEST_TX_ID, 0, 1234567890)
        )
        conn.commit()
        conn.close()
        
        # Attempt malicious transaction with overflow fee
        malicious_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': test_box_id, 'spending_proof': 'test'}],
            'outputs': [
                {'address': 'RTC_ATTACKER', 'value_nrtc': 1_000_000}
            ],
            'fee_nrtc': 2**63 - 1,  # 9,223,372,036,854,775,807
            'timestamp': int(time.time())
        }
        
        print("\n=== Testing Fee Overflow ===")
        print(f"Fee: {malicious_tx['fee_nrtc']}")
        
        try:
            result = db.apply_transaction(malicious_tx, block_height=1)
            print(f"Transaction result: {result}")
            
            if result:
                raise AssertionError("Overflow fee accepted")
            else:
                print("✅ PASS: Transaction rejected safely")
                return
                
        except sqlite3.IntegrityError as e:
            raise AssertionError(f"Database error (DoS): {e}") from e
        except Exception as e:
            raise AssertionError(f"Unexpected error (DoS): {e}") from e
            
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_timestamp_overflow():
    """
    Test that extremely large timestamps are rejected.
    """
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        db = UtxoDB(db_path)
        db.init_tables()
        
        # Create test UTXO
        conn = db._conn()
        test_box_id = compute_box_id(
            1000_000_000,
            address_to_proposition('RTC_TEST'),
            0, TEST_TX_ID, 0
        )
        
        conn.execute(
            """INSERT INTO utxo_boxes
               (box_id, value_nrtc, proposition, owner_address,
                creation_height, transaction_id, output_index,
                created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (test_box_id, 1000_000_000, address_to_proposition('RTC_TEST'),
             'RTC_TEST', 0, TEST_TX_ID, 0, 1234567890)
        )
        conn.commit()
        conn.close()
        
        # Malicious transaction with overflow timestamp
        malicious_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': test_box_id, 'spending_proof': 'test'}],
            'outputs': [
                {'address': 'RTC_ATTACKER', 'value_nrtc': 500_000_000}
            ],
            'fee_nrtc': 0,
            'timestamp': 10**20  # Extremely large
        }
        
        print("\n=== Testing Timestamp Overflow ===")
        print(f"Timestamp: {malicious_tx['timestamp']}")
        
        try:
            result = db.apply_transaction(malicious_tx, block_height=1)
            
            if result:
                raise AssertionError("Overflow timestamp accepted")
            else:
                print("✅ PASS: Transaction rejected safely")
                return
                
        except Exception as e:
            raise AssertionError(f"Error (DoS): {e}") from e
            
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_negative_fee():
    """
    Test that negative fees are rejected.
    """
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        db = UtxoDB(db_path)
        db.init_tables()
        
        # Create test UTXO
        conn = db._conn()
        test_box_id = compute_box_id(
            1000_000_000,
            address_to_proposition('RTC_TEST'),
            0, TEST_TX_ID, 0
        )
        
        conn.execute(
            """INSERT INTO utxo_boxes
               (box_id, value_nrtc, proposition, owner_address,
                creation_height, transaction_id, output_index,
                created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (test_box_id, 1000_000_000, address_to_proposition('RTC_TEST'),
             'RTC_TEST', 0, TEST_TX_ID, 0, 1234567890)
        )
        conn.commit()
        conn.close()
        
        # Malicious transaction with negative fee
        malicious_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': test_box_id, 'spending_proof': 'test'}],
            'outputs': [
                {'address': 'RTC_ATTACKER', 'value_nrtc': 2_000_000_000}
            ],
            'fee_nrtc': -1_000_000_000,  # Negative fee = fund creation
            'timestamp': int(time.time())
        }
        
        print("\n=== Testing Negative Fee ===")
        print(f"Fee: {malicious_tx['fee_nrtc']}")
        
        try:
            result = db.apply_transaction(malicious_tx, block_height=1)
            
            if result:
                raise AssertionError("Negative fee accepted (fund creation)")
            else:
                print("✅ PASS: Negative fee rejected")
                return
                
        except Exception as e:
            raise AssertionError(f"Error: {e}") from e
            
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == '__main__':
    def run_test(fn):
        try:
            fn()
            return True
        except AssertionError as exc:
            print(f"🔴 BUG: {exc}")
            return False

    print("=" * 60)
    print("Testing Integer Overflow Protection")
    print("=" * 60)
    
    result1 = run_test(test_fee_overflow)
    result2 = run_test(test_timestamp_overflow)
    result3 = run_test(test_negative_fee)
    
    print("\n" + "=" * 60)
    if result1 and result2 and result3:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("🔴 SOME TESTS FAILED")
        sys.exit(1)
