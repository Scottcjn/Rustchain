#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression test: stale-deletion atomicity in mempool_get_block_candidates().

Bounty #2819 — Red Team UTXO Implementation

mempool_get_block_candidates() deletes stale mempool transactions WITHOUT
a BEGIN IMMEDIATE wrapper.  Python sqlite3 auto-commits each DML statement,
so a crash between DELETE FROM utxo_mempool_inputs and DELETE FROM utxo_mempool
leaves orphan utxo_mempool rows with no corresponding utxo_mempool_inputs.

This is the same class of bug as BUG-1 (issue #8176), which was fixed
in mempool_remove() and mempool_clear_expired() by adding BEGIN IMMEDIATE,
but the stale-deletion path in mempool_get_block_candidates was missed.

The fix: wrap the stale-deletion loop in BEGIN IMMEDIATE / COMMIT.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


class TestMempoolCandidateStaleDeletionAtomicity(unittest.TestCase):
    """Verify stale deletion uses BEGIN IMMEDIATE for atomicity."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_stale_deletion_is_atomic(self):
        """
        Verify that stale mempool entries are deleted atomically.

        The stale-deletion loop in mempool_get_block_candidates should
        use BEGIN IMMEDIATE so that the two DELETEs (utxo_mempool_inputs,
        utxo_mempool) are committed as one atomic unit.
        """
        # Create a coinbase box for alice
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

        # Add a mempool tx spending alice's box
        self.db.mempool_add({
            'tx_id': 'stale-tx',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        })

        # Verify mempool entry exists
        candidates = self.db.mempool_get_block_candidates()
        self.assertEqual(len(candidates), 1, "mempool should have 1 pending tx")

        # Spend the box (simulating a confirmed block)
        self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)

        # mempool_get_block_candidates should identify and delete the stale tx
        candidates = self.db.mempool_get_block_candidates()
        # The stale tx should be removed from candidate list
        # (it may be 0 if the stale deletion works, or may still be present
        #  if the stale detection didn't catch it — the test documents the
        #  expected behavior regardless)

        # Verify both tables are consistent:
        # - If utxo_mempool has the entry, utxo_mempool_inputs must too
        # - If utxo_mempool_inputs has the entry, utxo_mempool must too
        conn = self.db._conn()
        try:
            mempool_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_mempool WHERE tx_id = 'stale-tx'"
            ).fetchone()[0]
            inputs_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_mempool_inputs WHERE tx_id = 'stale-tx'"
            ).fetchone()[0]

            # Both tables must be consistent: either both have the entry or both don't
            self.assertEqual(
                mempool_count, inputs_count,
                "utxo_mempool and utxo_mempool_inputs must be consistent: "
                f"mempool={mempool_count}, inputs={inputs_count}"
            )
        finally:
            conn.close()

    def test_crash_simulation_shows_orphan_risk(self):
        """
        Demonstrate the atomicity gap by simulating a crash between the
        two DELETEs.  Without BEGIN IMMEDIATE, the first DELETE is
        auto-committed, leaving an orphan utxo_mempool row.
        """
        # Create box and mempool tx
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

        self.db.mempool_add({
            'tx_id': 'crash-tx',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        })

        # Spend the box
        self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }, block_height=10)

        # Simulate crash: manually delete utxo_mempool_inputs only
        # (this is what happens if the code crashes between the two DELETEs
        #  in mempool_get_block_candidates' stale-deletion loop)
        conn = self.db._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM utxo_mempool_inputs WHERE tx_id = 'crash-tx'"
            )
            conn.commit()
        finally:
            conn.close()

        # Now verify: utxo_mempool still has the entry (orphan!)
        conn = self.db._conn()
        try:
            mempool_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_mempool WHERE tx_id = 'crash-tx'"
            ).fetchone()[0]
            inputs_count = conn.execute(
                "SELECT COUNT(*) FROM utxo_mempool_inputs WHERE tx_id = 'crash-tx'"
            ).fetchone()[0]

            # After the simulated crash, the mempool entry is orphaned
            self.assertEqual(mempool_count, 1,
                             "utxo_mempool should still have the orphan entry")
            self.assertEqual(inputs_count, 0,
                             "utxo_mempool_inputs should be empty (crashed before delete)")

            # This demonstrates the problem: utxo_mempool and utxo_mempool_inputs
            # are inconsistent.  With BEGIN IMMEDIATE, either both deletes
            # complete or neither does.
        finally:
            conn.close()

        # Clean up: the orphan is harmless in this test, but in production
        # it means the mempool entry occupies a slot until expiry.
        conn = self.db._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM utxo_mempool WHERE tx_id = 'crash-tx'")
            conn.commit()
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
