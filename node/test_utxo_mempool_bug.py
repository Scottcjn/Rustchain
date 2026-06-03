#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Test case for UTXO Mempool Empty Outputs Bug
Issue: #2819 - Red Team UTXO Implementation

This test demonstrates that mempool_add() also accepts empty outputs.
"""

import unittest
import tempfile
import os
import sys
import time

sys.path.insert(0, '/tmp/Rustchain_utxo/node')

from utxo_db import UtxoDB, UNIT


class TestUTXOMempoolEmptyOutputsBug(unittest.TestCase):
    """
    MEDIUM: mempool_add() accepts empty outputs,    Bounty: #2819 - Red Team UTXO Implementation
    Severity: MEDIUM (50 RTC)
    Reporter: XiaZong (RTC0816b68b604630945c94cde35da4641a926aa4fd)
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_mempool_empty_outputs_rejected(self):
        """
        MEDIUM: mempool should reject empty outputs.
        Steps:
        1. Create UTXO with 100 RTC
        2. Try to add tx with outputs=[] to mempool
        3. Verify transaction is rejected
        4. Verify mempool is empty
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
        self.assertEqual(alice_before, 100 * UNIT)

        # Get the UTXO
        boxes = self.db.get_unspent_for_address('alice')
        self.assertEqual(len(boxes), 1)
        box_id = boxes[0]['box_id']

        # Step 2: EXPLOIT - Try to add tx with empty outputs to mempool
        ok = self.db.mempool_add({
            'tx_id': 'malicious_tx_001',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [],  # EMPTY - This should be rejected!
            'fee_nrtc': 0,
        })

        # Step 3: Transaction MUST be rejected
        self.assertFalse(ok,
            "MEDIUM: Empty outputs should be rejected from mempool!")

        # Step 4: Verify mempool is empty
        candidates = self.db.mempool_get_block_candidates()
        self.assertEqual(len(candidates), 0,
            "Mempool should be empty if transaction is rejected")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUTXOMempoolEmptyOutputsBug)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.failures:
        print("⚠️  VULNERABILITY CONFIRMED!")
        print("⚠️  Test FAILED - Empty outputs accepted by mempool (BUG!)")
        print("=" * 70)
        print("\nThis allows DoS via mempool flooding.")
        print("\nFix: Add empty outputs check in mempool_add()")
    else:
        print("✅ Test PASSED - Empty outputs rejected from mempool (FIXED)")
        print("=" * 70)
