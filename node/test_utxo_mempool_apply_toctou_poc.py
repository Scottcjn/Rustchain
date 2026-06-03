#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
A4: TOCTOU — concurrent mempool_add + apply_transaction on same box
=====================================================================
VULN: mempool_add (claim via utxo_mempool_inputs) and apply_transaction
(spend via utxo_boxes.spent_at) use SEPARATE BEGIN IMMEDIATE transactions.
They don't coordinate — both can succeed on the same box.

Flow:
  1. Thread A: mempool_add(tx1 claiming box X) → BEGIN IMMEDIATE
     → checks spent_at IS NULL → passes
     → INSERT INTO utxo_mempool_inputs (box_id=X, tx_id=tx1)
     → COMMIT → returns True
  2. Thread B: apply_transaction(tx2 spending box X) → BEGIN IMMEDIATE
     → checks spent_at IS NULL → still NULL (mempool_inputs != spent_at)
     → UPDATE utxo_boxes SET spent_at=NOW WHERE box_id=X → rowcount=1
     → COMMIT → returns True
  3. Both succeed! Box X is "claimed" in mempool AND "spent" in a block.
     Mempool entry becomes stale/unmineable.

Fix: Add cross-check in apply_transaction: verify no mempool claim exists.
     Or: atomically check mempool_inputs before spending in block context.

PoC uses sequential calls (no threading) to demonstrate the fundamental
API-level gap — the two methods don't guard against each other.

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


class TestConcurrentMempoolVsApplyTocTou(unittest.TestCase):
    """mempool_add and apply_transaction both succeed on same box."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _create_boxes(self, count=3):
        """Create unspent boxes for testing."""
        ids = []
        for i in range(count):
            self.db.apply_transaction({
                'tx_type': 'mining_reward', 'inputs': [],
                'outputs': [{'address': f'u{i}', 'value_nrtc': 100 * UNIT}],
                'fee_nrtc': 0, 'timestamp': int(time.time()) + i,
                '_allow_minting': True,
            }, block_height=i + 1)
            ids.append(self.db.get_unspent_for_address(f'u{i}')[0]['box_id'])
        return ids

    def test_both_succeed_on_same_box(self):
        """
        mempool_add claims box X in mempool_inputs.
        apply_transaction spends box X in utxo_boxes.
        Both return True.
        """
        [bid] = self._create_boxes(1)

        # Step 1: mempool_add claims the box
        mempool_ok = self.db.mempool_add({
            'tx_id': 'mempool_tx',
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        })
        self.assertTrue(mempool_ok,
            "mempool_add claimed box X in mempool_inputs")

        # Verify mempool claims the box
        is_claimed = self.db.mempool_check_double_spend(bid)
        self.assertTrue(is_claimed,
            "Box X is claimed in utxo_mempool_inputs after mempool_add")

        # Step 2: apply_transaction spends the SAME box in utxo_boxes
        apply_ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': 'sig2'}],
            'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=10)
        self.assertTrue(apply_ok,
            "BUG: apply_transaction also spent box X — "
            "mempool_add didn't prevent it")

        # Both succeeded — box is both "claimed" in mempool and "spent" in UTXO
        # The mempool entry is now stale
        print(f"[A4] mempool_add={mempool_ok}, apply_transaction={apply_ok}")
        print(f"[A4] Box claimed in mempool: {is_claimed}")

        # Verify: mempool still has the stale entry
        candidates = self.db.mempool_get_block_candidates()
        print(f"[A4] Mempool candidates count: {len(candidates)}")
        if candidates:
            print(f"[A4] Stale mempool tx still present! tx_id={candidates[0].get('tx_id')}")

        # Verify: balance shows the apply_transaction result
        carol_bal = self.db.get_balance('carol')
        bob_bal = self.db.get_balance('bob')
        print(f"[A4] Carol (apply_tx recipient): {carol_bal} nRTC")
        print(f"[A4] Bob (mempool recipient): {bob_bal} nRTC")
        self.assertEqual(carol_bal, 100 * UNIT,
            "apply_transaction correctly assigned funds to Carol")
        self.assertEqual(bob_bal, 0,
            "mempool recipient Bob gets nothing — stale entry")

    def test_concurrent_threads_demonstration(self):
        """
        Demonstrate the TOCTOU with threads: two concurrent operations
        on the same box from different connections both succeed.
        """
        [bid] = self._create_boxes(1)
        results = {'mempool': None, 'apply': None}
        errors = []

        def do_mempool_add():
            try:
                db2 = UtxoDB(self.tmp.name)
                db2.init_tables()
                ok = db2.mempool_add({
                    'tx_id': 'thread_mempool',
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': bid, 'spending_proof': 'sig1'}],
                    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                })
                results['mempool'] = ok
            except Exception as e:
                errors.append(f"mempool: {e}")
                results['mempool'] = False

        def do_apply_tx():
            try:
                db2 = UtxoDB(self.tmp.name)
                db2.init_tables()
                ok = db2.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': bid, 'spending_proof': 'sig2'}],
                    'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': int(time.time()),
                }, block_height=20)
                results['apply'] = ok
            except Exception as e:
                errors.append(f"apply: {e}")
                results['apply'] = False

        t1 = threading.Thread(target=do_mempool_add)
        t2 = threading.Thread(target=do_apply_tx)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        print(f"[A4 concurrent] mempool_add={results['mempool']}, "
              f"apply_transaction={results['apply']}")

        both_succeeded = results['mempool'] and results['apply']
        print(f"[A4 concurrent] Both succeeded: {both_succeeded}")
        if both_succeeded:
            print("[A4] TOCTOU CONFIRMED: mempool AND block both own the box!")

        if errors:
            for e in errors:
                print(f"[A4 ERROR] {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
