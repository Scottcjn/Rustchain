#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
UTXO Race Condition & TOCTOU Test Cases
Issue: #2819 - Red Team UTXO Implementation

Tests for race conditions in concurrent apply_transaction calls.
"""

import unittest
import tempfile
import os
import sys
import time
import threading
import queue

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


class TestRaceCondition(unittest.TestCase):
    """
    Test for race conditions between apply_transaction calls.
    
    Scenario: Two concurrent transactions spending the same UTXO.
    Expected: Only one should succeed, one should fail with double-spend.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_concurrent_double_spend_only_one_wins(self):
        """
        HIGH: Race condition test - concurrent double spend
        
        Two threads try to spend the same UTXO simultaneously.
        Only ONE should succeed.
        """
        # Create a UTXO with 100 RTC
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok)

        boxes = self.db.get_unspent_for_address('alice')
        self.assertEqual(len(boxes), 1)
        box_id = boxes[0]['box_id']

        results = queue.Queue()
        errors = queue.Queue()

        def spend_to_bob():
            try:
                ok = self.db.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': box_id, 'spending_proof': 'sig1'}],
                    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': int(time.time()),
                }, block_height=2)
                results.put(('bob', ok))
            except Exception as e:
                errors.put(('bob', str(e)))

        def spend_to_charlie():
            try:
                ok = self.db.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': box_id, 'spending_proof': 'sig2'}],
                    'outputs': [{'address': 'charlie', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': int(time.time()),
                }, block_height=2)
                results.put(('charlie', ok))
            except Exception as e:
                errors.put(('charlie', str(e)))

        # Start both threads simultaneously
        t1 = threading.Thread(target=spend_to_bob)
        t2 = threading.Thread(target=spend_to_charlie)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Collect results
        successes = 0
        failures = 0
        recipients = []
        while not results.empty():
            recipient, ok = results.get()
            recipients.append(recipient)
            if ok:
                successes += 1
            else:
                failures += 1

        # Check errors
        while not errors.empty():
            print(f"Error: {errors.get()}")

        # CRITICAL: Only ONE should succeed
        print(f"Successes: {successes}, Failures: {failures}")
        
        # This assertion may FAIL if there's a race condition
        self.assertEqual(successes, 1, 
            f"CRITICAL: Only ONE double-spend should succeed, got {successes}")
        self.assertEqual(failures, 1,
            f"CRITICAL: ONE double-spend should fail, got {failures}")
        
        # Verify balance: 100 RTC should be with ONE recipient
        bob_bal = self.db.get_balance('bob')
        charlie_bal = self.db.get_balance('charlie')
        self.assertEqual(bob_bal + charlie_bal, 100 * UNIT,
            "Total should be 100 RTC - no double-spend")

    def test_fee_overflow_integer(self):
        """
        MEDIUM: Fee integer overflow test
        
        Large fee values might cause integer overflow.
        """
        # Create UTXO
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # Try with very large fee (near max int64)
        VERY_LARGE_FEE = 2**62
        
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 1}],
            'fee_nrtc': VERY_LARGE_FEE,
            'timestamp': int(time.time()),
        }, block_height=2)
        
        # Should be rejected (fee < 0 check catches negative, but large positive may pass)
        # But conservation check: output_total + fee > input_total should fail
        self.assertFalse(ok, "Transaction with huge fee should be rejected")

    def test_negative_output_value_bypass(self):
        """
        CRITICAL: Negative output value should be rejected
        
        The conservation check: output_total + fee <= input_total
        If output value is negative, output_total decreases, bypassing conservation.
        """
        # Create UTXO
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # EXPLOIT: Negative output value
        # With input=100, output=-50, fee=0:
        # output_total + fee = -50 <= 100 → passes conservation!
        # But output is destroyed, alice gets nothing
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': -50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=2)
        
        # Should be rejected - negative output values should be invalid
        # If this PASSES, there's a vulnerability!
        if ok:
            print("⚠️ VULNERABILITY: Negative output value was accepted!")
            bob_bal = self.db.get_balance('bob')
            alice_bal = self.db.get_balance('alice')
            print(f"Bob: {bob_bal}, Alice: {alice_bal}")
        
        # The existing code has: isinstance(o['value_nrtc'], int) and o['value_nrtc'] > 0
        # So this SHOULD be rejected
        self.assertFalse(ok, 
            "CRITICAL: Negative output values must be rejected!")

    def test_zero_fee_with_max_inputs(self):
        """
        Test conservation with zero fee and many inputs/outputs
        """
        # Create multiple UTXOs
        for i in range(5):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': f'alice_{i}', 'value_nrtc': 20 * UNIT}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()),
                '_allow_minting': True,
            }, block_height=1+i)

        # Spend all with exact value (fee=0)
        all_boxes = []
        for i in range(5):
            boxes = self.db.get_unspent_for_address(f'alice_{i}')
            all_boxes.extend([b['box_id'] for b in boxes])

        # Create transaction with all inputs, outputs = one recipient
        inputs = [{'box_id': bid, 'spending_proof': 'sig'} for bid in all_boxes]
        outputs = [{'address': 'bob', 'value_nrtc': 100 * UNIT}]

        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=10)

        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('bob'), 100 * UNIT)

    def test_race_condition_mempool_vs_apply(self):
        """
        HIGH: Race between mempool_add and apply_transaction
        
        A transaction is in mempool, then someone else spends the UTXO.
        When apply_transaction is called, it should succeed if UTXO still unspent.
        """
        # Create UTXO
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # Add to mempool
        ok = self.db.mempool_add({
            'tx_id': 'test_tx_1',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 99 * UNIT}],
            'fee_nrtc': 1 * UNIT,
            'timestamp': int(time.time()),
        })
        self.assertTrue(ok)

        # Meanwhile, apply_transaction with same UTXO should fail
        # because it's already in mempool_inputs
        # But apply_transaction doesn't check mempool!
        # This is NOT a vulnerability because apply_transaction
        # checks utxo_boxes.spent_at, which is only set when mined
        
        # However, if the tx is mined first, then mempool_add was invalid
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'charlie', 'value_nrtc': 99 * UNIT}],
            'fee_nrtc': 1 * UNIT,
            'timestamp': int(time.time()),
        }, block_height=2)
        
        # This SHOULD succeed (mempool doesn't mark as spent)
        self.assertTrue(ok)
        self.assertEqual(self.db.get_balance('charlie'), 99 * UNIT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
