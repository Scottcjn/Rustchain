#!/usr/bin/env python3
"""
B4: Concurrent apply_transaction double-spend for same box
TEST: Two threads call apply_transaction with the same input box.
  Both use BEGIN IMMEDIATE on separate connections — they serialize at
  SQLite level. Thread A acquires lock first, spends the box, commits.
  Thread B's UPDATE ... WHERE spent_at IS NULL affects 0 rows → abort.
  Expected: Thread A succeeds, Thread B fails. No double-spend.
Impact: If this test passes (correct behavior), it validates the
  apply_transaction serialization. If it fails (both succeed), it's
  a critical consensus bug. This test confirms the guard works.
"""
import threading
import time
import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


class TestConcurrentApplyDoubleSpend(unittest.TestCase):
    """B4: Concurrent apply_transaction for same box."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'target', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        boxes = self.db.get_unspent_for_address('target')
        self.box_id = boxes[0]['box_id']

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_b4_concurrent_apply_double_spend(self):
        """B4: Two threads apply_transaction same box concurrently.

        Expected: Thread A succeeds (spends box), Thread B fails
        (box already spent → spent_at not NULL → abort).
        If both succeed → critical consensus bug.
        """
        results = {"a_ok": None, "b_ok": None, "a_err": None, "b_err": None}

        def apply_a():
            try:
                ok = self.db.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
                    'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': int(time.time()),
                }, block_height=100)
                results["a_ok"] = ok
            except Exception as e:
                results["a_err"] = str(e)

        def apply_b():
            try:
                ok = self.db.apply_transaction({
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
                    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                    'timestamp': int(time.time()),
                }, block_height=101)
                results["b_ok"] = ok
            except Exception as e:
                results["b_err"] = str(e)

        t_a = threading.Thread(target=apply_a)
        t_b = threading.Thread(target=apply_b)

        t_a.start()
        t_b.start()
        t_a.join()
        t_b.join()

        print(f"\n[B4] A (apply): {results['a_ok']} | B (apply): {results['b_ok']}")
        if results["a_err"]: print(f"[B4] A error: {results['a_err']}")
        if results["b_err"]: print(f"[B4] B error: {results['b_err']}")

        # Verify chain state
        conn = self.db._conn()
        box = conn.execute(
            "SELECT spent_at, spent_by_tx FROM utxo_boxes WHERE box_id = ?",
            (self.box_id,),
        ).fetchone()
        conn.close()

        print(f"[B4] Box spent: {box['spent_at'] is not None} by tx {(box['spent_by_tx'] or 'N/A')[:12]}")

        # Expected: exactly one succeeds
        successes = sum(1 for r in [results["a_ok"], results["b_ok"]] if r is True)
        self.assertEqual(successes, 1,
            f"B4: Expected 1 success (serialization works), got {successes}. "
            f"Double-spend detected if >1.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
