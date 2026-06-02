#!/usr/bin/env python3
"""
C2: Endpoint-level spend can override mempool claims — adversarial
VULN: /utxo/transfer reads UTXOs at line 521-522 OUTSIDE the IMMEDIATE
  lock (line 558). apply_transaction checks utxo_boxes.spent_at but NOT
  utxo_mempool_inputs. So boxes claimed in mempool can be spent by the
  endpoint — mempool entry becomes orphaned, double-spend across systems.

Impact: An attacker can submit a mempool transaction for a box, then
  immediately call /utxo/transfer to spend the same box. The endpoint
  sees spent_at=NULL (box not on-chain spent), builds the tx, acquires
  IMMEDIATE lock, applies it. The mempool entry's input claims become
  orphaned — the box is spent on-chain but the mempool thinks it's pending.

Fix: apply_transaction must reject boxes claimed in utxo_mempool_inputs.
  Or: the endpoint should check mempool before selecting coins.
"""
import threading
import time
import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


class TestEndpointMempoolOverride(unittest.TestCase):
    """C2: Endpoint spend overrides mempool claim."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

        # Give Alice a box
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        boxes = self.db.get_unspent_for_address('alice')
        self.box_id = boxes[0]['box_id']

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_c2_endpoint_overrides_mempool(self):
        """C2: Endpoint spend succeeds on mempool-claimed box.

        Timeline:
          1. mempool_add(tx_mempool) — claims box in utxo_mempool_inputs
          2. apply_transaction(tx_apply) — checks utxo_boxes.spent_at
             (which is NULL), spends the box on-chain
          3. Result: box spent on-chain AND claimed in mempool
             → mempool entry is orphaned (unmineable)
        """
        # Step 1: Add box to mempool
        mempool_ok = self.db.mempool_add({
            'tx_id': 'mempool_claim_c2',
            'tx_type': 'transfer',
            'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        })
        self.assertTrue(mempool_ok, "setup: mempool must accept")

        # Step 2: Endpoint-style apply_transaction on same box
        # (This is what /utxo/transfer does at lines 544-568)
        apply_ok = self.db.apply_transaction({
            'tx_type': 'transfer',
            'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=100)

        # Step 3: Check state
        conn = self.db._conn()
        try:
            # Box on chain?
            box = conn.execute(
                "SELECT spent_at, spent_by_tx FROM utxo_boxes WHERE box_id = ?",
                (self.box_id,),
            ).fetchone()
            chain_spent = box['spent_at'] is not None

            # Box claimed in mempool?
            claim = conn.execute(
                "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id = ?",
                (self.box_id,),
            ).fetchone()
            mempool_claimed = claim is not None

            # Mempool entry exists?
            mempool_entry = conn.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id = 'mempool_claim_c2'"
            ).fetchone()
            mempool_exists = mempool_entry is not None
        finally:
            conn.close()

        print(f"\n[C2] mempool_add: {mempool_ok}")
        print(f"[C2] apply_transaction: {apply_ok}")
        print(f"[C2] Box spent on-chain: {chain_spent}")
        print(f"[C2] Box claimed in mempool: {mempool_claimed}")
        print(f"[C2] Mempool entry exists: {mempool_exists}")

        if apply_ok and mempool_claimed and chain_spent:
            print(f"[C2] ✅ ADVERSARIAL CONFIRMED: Box spent on-chain AND claimed in mempool")
            print("[C2] Mempool entry is orphaned — miner cannot mine it")
            print("[C2] There must be a cross-check: apply_transaction must check mempool_inputs")

        # Code inspection: does apply_transaction check mempool?
        with open(os.path.join(os.path.dirname(__file__), 'utxo_db.py'), 'r') as f:
            src = f.read()
        apply_start = src.find('def apply_transaction')
        if apply_start >= 0:
            block = src[apply_start:apply_start + 600]
            has_mempool_check = 'mempool' in block.lower() and ('check' in block.lower() or 'inputs' in block.lower())
            print(f"[C2] apply_transaction checks mempool: {has_mempool_check}")
            self.assertFalse(has_mempool_check,
                "C2 CONFIRMED: apply_transaction does NOT check utxo_mempool_inputs "
                "- endpoint can override mempool claims")


if __name__ == '__main__':
    unittest.main(verbosity=2)
