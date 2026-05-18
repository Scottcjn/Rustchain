#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Test case for UTXO Empty Outputs Bug in apply_transaction()
Issue: #2819 - Red Team UTXO Implementation

This test demonstrates a CRITICAL vulnerability where empty outputs
result in complete fund destruction.
"""

import unittest
import tempfile
import os
import sys
import time

sys.path.insert(0, '/tmp/Rustchain_utxo/node')

from utxo_db import UtxoDB, UNIT


class TestUTXOEmptyOutputsBug(unittest.TestCase):
    """
    CRITICAL: Empty outputs must be rejected to prevent fund destruction.

    Bounty: #2819 - Red Team UTXO Implementation
    Severity: CRITICAL (200 RTC)
    Reporter: XiaZong (RTC0816b68b604630945c94cde35da4641a926aa4fd)

    Vulnerability:
    When outputs=[] and fee=0, the conservation check:
        if inputs and (output_total + fee) > input_total:
    becomes:
        if inputs and (0 + 0) > input_total:
    which evaluates to False, allowing the transaction to proceed.
    Result: Inputs are spent, no outputs are created → funds destroyed.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_empty_outputs_rejected(self):
        """
        CRITICAL: Empty outputs must be rejected to prevent fund destruction.

        Steps:
        1. Create UTXO with 100 RTC
        2. Try to spend with outputs=[]
        3. Verify transaction is rejected
        4. Verify balance is preserved
        """
        # Step 1: Create initial UTXO with 100 RTC
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok, "Coinbase should succeed")

        # Verify Alice has 100 RTC
        alice_before = self.db.get_balance('alice')
        self.assertEqual(alice_before, 100 * UNIT, "Alice should have 100 RTC")

        # Get the UTXO
        boxes = self.db.get_unspent_for_address('alice')
        self.assertEqual(len(boxes), 1, "Alice should have 1 UTXO")
        box_id = boxes[0]['box_id']

        # Step 2: EXPLOIT - Try to spend with empty outputs
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [],  # EMPTY - This is the vulnerability!
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=2)

        # Step 3: Transaction MUST be rejected
        self.assertFalse(ok,
            "CRITICAL: Empty outputs should be rejected to prevent fund destruction!")

        # Step 4: Balance must be preserved
        alice_after = self.db.get_balance('alice')
        self.assertEqual(alice_after, 100 * UNIT,
            "Balance should not change if transaction is rejected")

        # Verify no funds were destroyed
        total_supply = self.db.get_balance('alice') + \
                      self.db.get_balance('bob') + \
                      self.db.get_balance('charlie')
        self.assertEqual(total_supply, 100 * UNIT,
            "Total supply should remain 100 RTC - no funds destroyed")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUTXOEmptyOutputsBug)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.failures:
        print("⚠️  CRITICAL VULNERABILITY CONFIRMED!")
        print("⚠️  Test FAILED - Empty outputs are accepted (BUG!)")
        print("=" * 70)
        print("\nThis means funds can be destroyed via empty outputs.")
        print("Conservation law is bypassed.")
        print("\nFix: Add 'if not outputs: return False' in apply_transaction()")
    else:
        print("✅ Test PASSED - Empty outputs are rejected (FIXED)")
        print("=" * 70)
