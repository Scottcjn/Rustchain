#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
A2: apply_transaction() missing MAX_INPUTS boundary check
=========================================================
VULN: apply_transaction() at utxo_db.py:485 has NO limit on number of inputs.

Impact:
  - Block production delay: applying a tx with 10K+ inputs ties up write lock
  - Consensus stall: if mempool candidate has 5K inputs, block application
    blocks other node operations for the duration
  - Direct endpoint DoS: /utxo/transfer with colluded UTXOs → unbounded
    apply_transaction processing

Root cause: Same as A1 — MAX_INPUTS constant doesn't exist.
Fix: Add MAX_INPUTS = 1000 (or align with consensus limit) + reject in
     apply_transaction(). apply_transaction loop at lines 668-676 does
     rowcount check per input, scaling linearly with input count.

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import MAX_INPUTS, MAX_OUTPUTS, UtxoDB, UNIT, coin_select


class TestApplyTransactionNoMaxInputs(unittest.TestCase):
    """
    apply_transaction() rejects transactions over the input-count boundary.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _create_boxes(self, count: int) -> list:
        """Create N unspent UTXOs, return [box_id, ...]."""
        ids = []
        for i in range(count):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': f'a{i}', 'value_nrtc': 1 * UNIT}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()) + i,
                '_allow_minting': True,
            }, block_height=i + 1)
            ids.append(self.db.get_unspent_for_address(f'a{i}')[0]['box_id'])
        return ids

    def test_apply_tx_accepts_inputs_at_limit(self):
        """
        apply_transaction with exactly MAX_INPUTS remains valid.
        """
        box_ids = self._create_boxes(MAX_INPUTS)
        inputs = [{'box_id': bid, 'spending_proof': 'sig'} for bid in box_ids]

        start = time.time()
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': [{'address': 'bob', 'value_nrtc': MAX_INPUTS * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=200)
        elapsed = time.time() - start

        print(f"[A2] apply_tx {MAX_INPUTS} inputs: {ok} ({elapsed:.4f}s)")
        self.assertTrue(ok,
            "apply_transaction should accept transactions at MAX_INPUTS")

        # Verify it actually processed
        bob_bal = self.db.get_balance('bob')
        self.assertEqual(bob_bal, MAX_INPUTS * UNIT,
            "apply_transaction correctly processed all 100 inputs")

    def test_apply_tx_rejects_inputs_over_limit(self):
        """
        500 inputs should be rejected before per-input block application work.
        """
        box_ids = self._create_boxes(500)
        inputs = [{'box_id': bid, 'spending_proof': 'sig'} for bid in box_ids]

        start = time.time()
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': [{'address': 'victim', 'value_nrtc': 500 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=300)
        elapsed = time.time() - start

        qps = 500 / elapsed
        print(f"[A2 perf] 500 inputs: accepted={ok} ({elapsed:.4f}s, rate={qps:.0f}/sec)")
        self.assertFalse(ok)

    def test_max_inputs_constant_exists(self):
        """Verify MAX_INPUTS exists in utxo_db.py."""
        with open(__file__.replace('test_utxo_no_max_inputs_apply_poc.py',
                                   'utxo_db.py'), 'r') as f:
            src = f.read()
        has = 'MAX_INPUTS' in src and 'MAX_INPUT' in src
        print(f"[A2] MAX_INPUTS constant exists: {has}")
        self.assertTrue('MAX_INPUTS' in src)

    def test_max_outputs_exists_inputs_doesnt(self):
        """
        Confirm input and output sides use the same anti-bloat bound.
        """
        self.assertEqual(MAX_OUTPUTS, 100,
            "MAX_OUTPUTS = 100 exists as anti-bloat guard")
        self.assertEqual(MAX_INPUTS, MAX_OUTPUTS)


class TestCoinSelectEnforces20ButDbLayerDoesnt(unittest.TestCase):
    """
    coin_select() caps at 20 inputs via heuristic and the DB layer now has
    a hard consensus-boundary limit as defense in depth.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_coin_select_caps_at_20(self):
        """
        coin_select's 20-input heuristic exists (line 1185) because the
        DB layer provides NO protection against excessive inputs.
        """
        # Create 30 small UTXOs
        for i in range(30):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': f'dust_{i}', 'value_nrtc': 1}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()) + i,
                '_allow_minting': True,
            }, block_height=i + 1)

        all_utxos = []
        for i in range(30):
            all_utxos.extend(self.db.get_unspent_for_address(f'dust_{i}'))

        selected, change = coin_select(all_utxos, target_nrtc=10)
        print(f"[A2 coin_select] {len(all_utxos)} available → "
              f"{len(selected)} selected (≤20 heuristic), change={change}")
        self.assertLessEqual(len(selected), 20,
            "coin_select caps at 20 — but DB layer doesn't")


if __name__ == '__main__':
    unittest.main(verbosity=2)
