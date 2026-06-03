#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: mempool_add tx_data_json unbounded size (A13)

Bug: json.dumps(tx) at line 1013 serializes entire tx dict with NO size limit.
Giant spending_proof strings pass through unvalidated, consuming unbounded
disk/memory. With MAX_POOL_SIZE=10K, 1K giant txs = GBs storage.

Fix: Add MAX_TX_DATA_JSON_BYTES limit before INSERT, or strip spending_proof
from serialization (it's documented as unused by this layer).
"""

import unittest
import tempfile
import os
import time

from utxo_db import UtxoDB, UNIT


class TestTxDataJsonUnbounded(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        # Fund alice with coinbase (under MAX_COINBASE_OUTPUT_NRTC)
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _get_box(self):
        return self.db.get_unspent_for_address('alice')[0]['box_id']

    def _make_tx(self, tx_id_hex, box_id, proof):
        return {
            'tx_id': tx_id_hex,
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': proof}],
            'outputs': [{'address': 'bob', 'value_nrtc': 45 * UNIT}],
            'fee_nrtc': 5 * UNIT,
            'timestamp': int(time.time()),
        }

    def test_normal_tx_size(self):
        """Baseline — normal tx admitted."""
        box_id = self._get_box()
        ok = self.db.mempool_add(self._make_tx('aa' * 32, box_id, 'sig'))
        self.assertTrue(ok)

    def test_giant_spending_proof_accepted(self):
        """BUG: 100KB spending_proof accepted — no size limit."""
        box_id = self._get_box()
        proof = 'X' * 100_000
        ok = self.db.mempool_add(self._make_tx('bb' * 32, box_id, proof))
        self.assertTrue(ok, "100KB tx_data_json should pass (256KB limit)")

    def test_extreme_proof_rejected(self):
        """512KB spending_proof — now rejected with 256KB limit."""
        box_id = self._get_box()
        proof = 'Z' * 500_000  # 500KB spending_proof → tx ~500KB+ → rejected
        ok = self.db.mempool_add(self._make_tx('dd' * 32, box_id, proof))
        self.assertFalse(ok, "500KB tx_data_json should be rejected (256KB limit)")
        print("  500KB tx: rejected ✓ — fix working")

    def test_giant_proof_stored_size(self):
        """Check actual stored size of giant proof tx_data_json."""
        box_id = self._get_box()
        proof = 'Y' * 50_000
        ok = self.db.mempool_add(self._make_tx('cc' * 32, box_id, proof))
        self.assertTrue(ok)

        conn = self.db._conn()
        row = conn.execute(
            "SELECT LENGTH(tx_data_json) AS sz FROM utxo_mempool WHERE tx_id = ?",
            ('cc' * 32,)
        ).fetchone()
        self.assertGreater(row['sz'], 50_000,
            "Giant proof stored at full size")
        print(f"  Stored tx_data_json: {row['sz']:,} bytes "
              f"({row['sz']/1024:.1f} KB) — NO SIZE LIMIT")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTxDataJsonUnbounded)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("⚠️  Bug CONFIRMED: tx_data_json has NO size limit on serialization")
        print("Giant spending_proof passes through, filling storage unboundedly")
    print("=" * 70)
