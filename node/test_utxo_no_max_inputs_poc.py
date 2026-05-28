#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
A1: mempool_add() missing MAX_INPUTS boundary check
====================================================
VULN: Neither mempool_add() nor apply_transaction() enforces an upper bound
on the number of inputs a transaction can carry.

Impact:
  - DoS via N+1 query attack inside BEGIN IMMEDIATE lock (each input → 1 SELECT)
  - Mempool input table bloat (utxo_mempool_inputs)
  - Validation cost unbounded — attacker controls runtime of critical section

Fix: Add MAX_INPUTS = 1000 (or 100) constant + reject check in both methods.
     (Mirrors existing MAX_OUTPUTS = 100 pattern at utxo_db.py:45)

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import MAX_INPUTS, UtxoDB, UNIT


class TestMempoolNoMaxInputsBoundary(unittest.TestCase):
    """
    Regression tests for the input-count DoS boundary.
    """
    """mempool_add() rejects transactions over the input-count boundary."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _create_unspent_boxes(self, count: int) -> list:
        """Create N unspent UTXOs via mining_reward."""
        box_ids = []
        for i in range(count):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{
                    'address': f'alice_{i}',
                    'value_nrtc': 1 * UNIT,
                }],
                'fee_nrtc': 0,
                'timestamp': int(time.time()) + i,
                '_allow_minting': True,
            }, block_height=i + 1)
            boxes = self.db.get_unspent_for_address(f'alice_{i}')
            box_ids.append(boxes[0]['box_id'])
        return box_ids

    def test_mempool_rejects_inputs_over_limit(self):
        """
        Submits a tx over MAX_INPUTS. It must be rejected before per-input
        mempool checks run under the write lock.
        """
        box_ids = self._create_unspent_boxes(200)
        inputs = [{'box_id': bid, 'spending_proof': 'sig'} for bid in box_ids]

        start = time.time()
        ok = self.db.mempool_add({
            'tx_id': 'big_input_tx',
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': [{
                'address': 'bob',
                'value_nrtc': 200 * UNIT,
            }],
            'fee_nrtc': 0,
        })
        elapsed = time.time() - start

        print(f"[A1] 200-input tx accepted: {ok} ({elapsed:.3f}s, {200/elapsed:.0f} queries/sec)")
        self.assertFalse(ok,
            "CRITICAL: mempool_add should reject excessive inputs "
            "(200 SELECT queries inside BEGIN IMMEDIATE = DoS vector)")

    def test_mempool_rejects_large_input_dos_vector(self):
        """
        Measure the cost — 500-input tx to quantify the DoS surface.
        Each input adds a SELECT query. Attacker can scale to 5000+
        with sufficient UTXO inventory.
        """
        box_ids = self._create_unspent_boxes(500)
        inputs = [{'box_id': bid, 'spending_proof': 'sig'} for bid in box_ids]

        start = time.time()
        ok = self.db.mempool_add({
            'tx_id': 'dos_vector_test',
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': [{
                'address': 'victim',
                'value_nrtc': 500 * UNIT,
            }],
            'fee_nrtc': 0,
        })
        elapsed = time.time() - start

        print(f"[A1 DoS] 500-input tx: accepted={ok}, {elapsed:.3f}s, rate={500/elapsed:.0f} qps")
        self.assertFalse(ok,
            "CRITICAL: 500 inputs should be rejected "
            f"({elapsed:.3f}s of locked DB time is unbounded DoS)")

    def test_apply_transaction_rejects_inputs_over_limit(self):
        """
        Same input cap is enforced during block application.
        """
        box_ids = self._create_unspent_boxes(MAX_INPUTS + 1)
        inputs_payload = [{'box_id': bid, 'spending_proof': 'sig'} for bid in box_ids]
        start = time.time()
        ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': inputs_payload,
            'outputs': [{'address': 'bob', 'value_nrtc': (MAX_INPUTS + 1) * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=MAX_INPUTS + 10)
        elapsed = time.time() - start
        print(f"[A1 apply_tx] {MAX_INPUTS + 1}-input tx accepted: {ok} ({elapsed:.3f}s)")
        self.assertFalse(ok)


class TestDualInputCheckMissing(unittest.TestCase):
    """
    Cross-reference: utxo_endpoints.py may also lack input count checks.
    """

    def test_max_inputs_constant_exists(self):
        """Verify the DB layer has a MAX_INPUTS cap matching MAX_OUTPUTS."""
        with open(__file__.replace('test_utxo_no_max_inputs_poc.py',
                                   'utxo_db.py'), 'r') as f:
            src = f.read()
        has_max_outputs = 'MAX_OUTPUTS' in src
        has_max_inputs = 'MAX_INPUTS' in src or 'MAX_INPUT_COUNT' in src
        print(f"[A1 constants] MAX_OUTPUTS={has_max_outputs}, MAX_INPUTS={has_max_inputs}")
        self.assertTrue(has_max_outputs,
            "MAX_OUTPUTS should exist (checking project baseline)")
        self.assertTrue(has_max_inputs,
            "MAX_INPUTS should exist as the input-side DoS guard")
        self.assertEqual(MAX_INPUTS, 100)


if __name__ == '__main__':
    unittest.main(verbosity=2)
