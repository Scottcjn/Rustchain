#!/usr/bin/env python3
"""
B3: Concurrent mempool_add + apply_transaction for same box — TOCTOU race
VULN: mempool_add() checks utxo_mempool_inputs while apply_transaction()
  checks utxo_boxes.spent_at. They use separate BEGIN IMMEDIATE connections,
  so SQLite serialization doesn't help — the two operations check DIFFERENT
  tables. Both succeed for the same box: mempool claims it AND the block
  spends it.
Impact: Box is simultaneously claimed in mempool and spent on-chain. Block
  application succeeds, mempool entry becomes stale/unmineable. The box is
  double-spent in the logical sense — available to both subsystems.
Fix: apply_transaction() (or block production) must cross-check
  utxo_mempool_inputs before spending. See A4 for the sequential version.
"""
import threading
import time
import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


class TestConcurrentApplyVsMempool(unittest.TestCase):
    """B3: Concurrent mempool_add + apply_transaction for same box."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        # Create one box for the race
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

    def test_b3_concurrent_mempool_vs_apply(self):
        """B3: mempool_add + apply_transaction on same box concurrently.

        Timeline:
          1. Thread A (mempool_add): BEGIN IMMEDIATE → checks mempool_inputs
             for box → empty → claims box in utxo_mempool_inputs → COMMIT
          2. Thread B (apply_transaction): BEGIN IMMEDIATE → checks
             utxo_boxes.spent_at for box → NULL (not spent on chain yet) →
             UPDATE spent_at → COMMIT
          Result: Both return True — same box claimed by both systems
        """
        results = {"mempool_ok": None, "apply_ok": None, "error": None}

        def mempool_add_thread():
            try:
                ok = self.db.mempool_add({
                    'tx_id': 'mempool_tx_b3',
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
                    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                })
                results["mempool_ok"] = ok
            except Exception as e:
                results["error"] = f"mempool error: {e}"

        def apply_thread():
            try:
                ok = self.db.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
                    'outputs': [{'address': 'carol', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': int(time.time()),
                }, block_height=100)
                results["apply_ok"] = ok
            except Exception as e:
                results["error"] = f"apply error: {e}"

        t_mempool = threading.Thread(target=mempool_add_thread)
        t_apply = threading.Thread(target=apply_thread)

        # Fire both simultaneously
        t_mempool.start()
        t_apply.start()
        t_mempool.join()
        t_apply.join()

        mempool_ok = results["mempool_ok"]
        apply_ok = results["apply_ok"]

        print(f"\n[B3] mempool_add: {mempool_ok} | apply_transaction: {apply_ok}")
        if results["error"]:
            print(f"[B3] Error: {results['error']}")

        # Check post-race state
        conn = self.db._conn()
        try:
            # Is box claimed in mempool?
            claim = conn.execute(
                "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id = ?",
                (self.box_id,),
            ).fetchone()
            # Is box spent on chain?
            box = conn.execute(
                "SELECT spent_at, spent_by_tx FROM utxo_boxes WHERE box_id = ?",
                (self.box_id,),
            ).fetchone()

            mempool_claimed = claim is not None
            chain_spent = box['spent_at'] is not None

            print(f"[B3] mempool claim: {mempool_claimed} (by {claim['tx_id'] if claim else 'N/A'})")
            print(f"[B3] chain spent: {chain_spent} (by tx {box['spent_by_tx'][:12] if box['spent_by_tx'] else 'N/A'})")

            if mempool_ok and apply_ok:
                print(f"[B3] ✅ RACE CONFIRMED: Both systems accepted same box")
                print(f"[B3] mempool thinks box is pending, chain already spent it")
                print(f"[B3] Root cause: different tables checked under separate IMMEDIATE locks")
                print(f"[B3] mempool_add checks utxo_mempool_inputs")
                print(f"[B3] apply_transaction checks utxo_boxes.spent_at")
                print(f"[B3] No cross-check between the two systems")
                print(f"[B3] Fix: apply_transaction must reject if box is in utxo_mempool_inputs")
        finally:
            conn.close()

        self.assertTrue(
            mempool_ok is not None and apply_ok is not None,
            "B3 must complete without exception"
        )
        # Document the finding: both succeed when they shouldn't
        if mempool_ok and apply_ok:
            self.fail(
                "B3 RACE CONFIRMED: Both mempool_add AND apply_transaction succeeded "
                "for the same box. This is a concurrent double-spend."
            )
        # If one was rejected due to timing (SQLite serialization happened to order them),
        # the vulnerability still exists — just need tighter timing
        print(f"[B3] Finding: cross-system coordination gap documented. "
              f"mempool={mempool_ok}, apply={apply_ok}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
