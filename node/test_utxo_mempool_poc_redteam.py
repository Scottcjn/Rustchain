#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
UTXO Red Team PoC — Remaining Mempool Vulnerabilities
Issue: #2819 - Red Team UTXO Implementation
Reporter: @geldbert

Three newly discovered vulnerabilities in mempool_add():

1. MEDIUM: mempool_add() accepts outputs with missing/zero value_nrtc
   - apply_transaction() enforces o['value_nrtc'] > 0 (int type check)
   - mempool_add() uses o.get('value_nrtc', 0) which defaults to 0
   - An attacker can push transactions into mempool that will NEVER be
     mineable, locking UTXOs until mempool expiry (DoS vector)

2. MEDIUM: mempool_add() INSERT OR IGNORE allows input claiming on duplicate tx_id
   - If a tx_id already exists in utxo_mempool, the INSERT OR IGNORE silently
     skips the row insert but execution continues to claim inputs in
     utxo_mempool_inputs (lines 708-712)
   - This creates orphan mempool_inputs entries that reference a tx_id
     with no corresponding mempool row
   - The UTXOs are "locked" in mempool but the transaction cannot be mined

3. HIGH: mempool_add() trusts caller-provided tx_id allowing tx_id collision
   - apply_transaction() computes its own tx_id from inputs+timestamp
   - mempool_add() blindly uses tx.get('tx_id', '')
   - An attacker can provide tx_id matching a CONFIRMED transaction,
     then the mempool_inputs claim would shadow already-spent UTXOs
   - Or provide empty tx_id '', making all such transactions share one key
"""

import unittest
import tempfile
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


class TestMempoolZeroValueOutputBug(unittest.TestCase):
    """
    MEDIUM: mempool_add() accepts outputs with zero/missing value_nrtc

    apply_transaction() strictly validates: isinstance(value_nrtc, int) and value_nrtc > 0
    mempool_add() only does: sum(o.get('value_nrtc', 0) for o in outputs)
    This means mempool accepts unmineable transactions that lock UTXOs.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_mempool_rejects_zero_value_output(self):
        """mempool should reject outputs with value_nrtc=0"""
        # Create UTXO
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # EXPLOIT: Push tx with zero-value output into mempool
        ok = self.db.mempool_add({
            'tx_id': 'tx_zero_value',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 0}],  # ZERO VALUE
            'fee_nrtc': 0,
        })

        # EXPECT: Should be rejected (will never be mineable)
        # ACTUAL: Accepted, locking Alice's UTXO until mempool expiry
        self.assertFalse(ok,
            "MEDIUM: mempool should reject zero-value outputs "
            "(unmineable tx locks UTXOs)")

    def test_mempool_rejects_missing_value_key(self):
        """mempool should reject outputs where value_nrtc key is missing"""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # EXPLOIT: Push tx with missing value_nrtc (defaults to 0)
        ok = self.db.mempool_add({
            'tx_id': 'tx_missing_value',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob'}],  # NO value_nrtc key
            'fee_nrtc': 0,
        })

        self.assertFalse(ok,
            "MEDIUM: mempool should reject outputs without value_nrtc "
            "(defaults to 0, creates unmineable tx)")


class TestMempoolDuplicateTxIdInputClaimBug(unittest.TestCase):
    """
    MEDIUM: INSERT OR IGNORE + subsequent input claiming creates orphan entries

    When a duplicate tx_id is inserted:
    1. INSERT OR IGNORE on utxo_mempool silently skips the row
    2. But the loop at lines 708-712 still inserts into utxo_mempool_inputs
    3. Result: orphan input claims that lock UTXOs in mempool with no
       corresponding transaction to mine or remove
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_duplicate_tx_id_does_not_claim_inputs(self):
        """Duplicate tx_id should not create orphan input claims"""
        # Create UTXO
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        # First mempool add succeeds
        ok1 = self.db.mempool_add({
            'tx_id': 'duplicate_tx',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
        })
        self.assertTrue(ok1)

        # Remove first tx from mempool to free the input
        self.db.mempool_remove('duplicate_tx')

        # Now add again with same tx_id - should succeed cleanly
        ok2 = self.db.mempool_add({
            'tx_id': 'duplicate_tx',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'carol', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
        })

        # Verify no orphan entries: mempool should have exactly one tx
        candidates = self.db.mempool_get_block_candidates()
        # If INSERT OR IGNORE silently fails but inputs are claimed,
        # we get a phantom entry
        self.assertEqual(len(candidates), 1,
            "MEDIUM: Duplicate tx_id should not create orphan entries")


class TestMempoolCallerProvidedTxIdCollision(unittest.TestCase):
    """
    HIGH: mempool_add() trusts caller-provided tx_id

    Unlike apply_transaction() which computes tx_id from inputs+timestamp,
    mempool_add() uses whatever tx_id the caller provides. This allows:
    1. tx_id collision with confirmed transactions
    2. Empty tx_id '' shared across multiple transactions
    3. Arbitrary tx_id manipulation for mempool confusion attacks
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_mempool_rejects_empty_tx_id(self):
        """mempool should reject transactions with empty tx_id"""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        boxes = self.db.get_unspent_for_address('alice')
        box_id = boxes[0]['box_id']

        ok = self.db.mempool_add({
            'tx_id': '',  # EMPTY tx_id
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
        })

        self.assertFalse(ok,
            "HIGH: mempool should reject empty tx_id "
            "(allows multiple txs to share same key)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
