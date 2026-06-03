#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
C16: Multiple mining_reward in the same block — fix verification

Bug: apply_transaction permitted multiple mining_reward transactions at
the same block_height. Each mining_reward with different content could
produce a unique tx_id, allowing multiple coinbase outputs per block.

Fix: Added per-block check — if a mining_reward already exists at the
given block_height, subsequent mining_reward txs are rejected.
"""

import unittest
import tempfile
import os
import time

from utxo_db import UtxoDB, UNIT, MAX_COINBASE_OUTPUT_NRTC


class TestMultipleMiningReward(unittest.TestCase):
    """C16: Multiple mining_reward txs at same block_height — now rejected."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_first_mining_reward_accepted(self):
        """First mining_reward at height 1 — accepted."""
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertTrue(ok, "First mining_reward should succeed")

    def test_second_mining_reward_same_height_rejected(self):
        """FIX: Second mining_reward at SAME height — rejected."""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'bob', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        self.assertFalse(ok,
            "FIX: Second mining_reward at same height should be rejected!")
        print("  ✅ Second mining_reward at height 1: rejected")

    def test_different_heights_accepted(self):
        """Different block heights — both mining_rewards accepted."""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=2)
        self.assertTrue(ok, "Different heights — both should succeed")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMultipleMiningReward)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n" + "=" * 60)
    print("C16 FIXED" if result.wasSuccessful() else "C16 ISSUES")
    print("=" * 60)
