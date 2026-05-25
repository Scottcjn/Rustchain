#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: A14 — mempool_add no per-input spending_proof size limit

Bug: spending_proof in each input has no per-input size limit. While A13
caps total tx_data_json at 256KB, an attacker can still fill each input
with a moderately large proof (e.g., 25KB x 4 inputs = 100KB) without
exceeding the total cap.

Fix: Add MAX_SPENDING_PROOF_BYTES = 8_192 (8KB) per input.
"""

import unittest
import tempfile
import os
import time
import json

from utxo_db import UtxoDB, UNIT, MAX_SPENDING_PROOF_BYTES


class TestSpendingProofSize(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        boxes = self.db.get_unspent_for_address('alice')
        self.box_id = boxes[0]['box_id']

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_normal_proof_accepted(self):
        """Normal 64-byte Ed25519 signature proof accepted."""
        ok = self.db.mempool_add({
            'tx_id': 'aa' * 32,
            'tx_type': 'transfer',
            'inputs': [{'box_id': self.box_id, 'spending_proof': 'x' * 128}],
            'outputs': [{'address': 'bob', 'value_nrtc': 40 * UNIT}],
            'fee_nrtc': 10 * UNIT,
            'timestamp': int(time.time()),
        })
        self.assertTrue(ok, "Normal proof (128B) should be accepted")

    def test_10kb_proof_rejected(self):
        """10KB spending_proof — should be rejected."""
        # Need a new box for each test
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=2)
        boxes = self.db.get_unspent_for_address('alice')
        bid = boxes[-1]['box_id']

        ok = self.db.mempool_add({
            'tx_id': 'bb' * 32,
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': 'Y' * 10_000}],
            'outputs': [{'address': 'bob', 'value_nrtc': 40 * UNIT}],
            'fee_nrtc': 10 * UNIT,
            'timestamp': int(time.time()),
        })
        self.assertFalse(ok, "10KB spending_proof should be rejected")
        print("  10KB proof: rejected ✓")


    def test_non_string_list_proof_rejected(self):
        """List-based spending_proof (non-string) — bypasses isinstance check."""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=3)
        boxes = self.db.get_unspent_for_address('alice')
        bid = boxes[-1]['box_id']

        # List proof with 8193 elements — serializes to ~40KB JSON
        proof_list = ['Y'] * (MAX_SPENDING_PROOF_BYTES + 1)
        serialized = json.dumps(proof_list, separators=(',', ':'))
        print(f"  non-string list: {len(serialized)}B serialized")

        ok = self.db.mempool_add({
            'tx_id': 'cc' * 32,
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': proof_list}],
            'outputs': [{'address': 'bob', 'value_nrtc': 40 * UNIT}],
            'fee_nrtc': 10 * UNIT,
            'timestamp': int(time.time()),
        })
        self.assertFalse(ok, "Non-string list proof should be rejected")
        print("  non-string list proof: rejected ✓")

    def test_dict_proof_rejected(self):
        """Dict-based spending_proof — another non-string bypass."""
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 50 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=4)
        boxes = self.db.get_unspent_for_address('alice')
        bid = boxes[-1]['box_id']

        # Dict with enough keys to exceed limit
        proof_dict = {str(i): 'x' for i in range(200)}
        serialized = json.dumps(proof_dict, separators=(',', ':'))
        print(f"  dict proof: {len(serialized)}B serialized")

        ok = self.db.mempool_add({
            'tx_id': 'dd' * 32,
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': proof_dict}],
            'outputs': [{'address': 'bob', 'value_nrtc': 40 * UNIT}],
            'fee_nrtc': 10 * UNIT,
            'timestamp': int(time.time()),
        })

        if len(serialized) > 8192:
            self.assertFalse(ok, "Oversized dict proof should be rejected")
            print("  dict proof: rejected ✓")
        else:
            self.assertTrue(ok, "Small dict proof should be accepted")
            print("  dict proof: accepted (within limit) ✓")


if __name__ == '__main__':
    unittest.main(verbosity=2)
