#!/usr/bin/env python3
"""
B2: Concurrent mempool_add stress + pool cap overflow via stale count
VULN: mempool_clear_expired() runs OUTSIDE the IMMEDIATE lock, on its own
  connection with no explicit transaction. Between clear_expired() returning
  and the BEGIN IMMEDIATE count check, concurrent adds can fill the gap.
  Under high concurrency, the pool cap can temporarily be exceeded.
  Additionally: mempool_clear_expired() itself lacks BEGIN IMMEDIATE —
  two-step DELETEs (inputs first, then entry) are autocommit, same race
  pattern as B1.
Impact: Pool admission count drift under concurrent load, stale input
  claim releases during expiry race.
Fix: Move mempool_clear_expired() INSIDE the BEGIN IMMEDIATE block in
  mempool_add(), or add IMMEDIATE lock to mempool_clear_expired() itself.
"""
import threading
import time
import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT, MAX_POOL_SIZE


THREAD_COUNT = 50


class TestConcurrentMempoolStress(unittest.TestCase):
    """B2: Stress test mempool under concurrent load."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _create_boxes(self, addr: str, count: int) -> list:
        """Create N unspent boxes for addr."""
        box_ids = []
        for i in range(count):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': addr, 'value_nrtc': 100 * UNIT}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()) + i,
                '_allow_minting': True,
            }, block_height=i + 1)
            boxes = self.db.get_unspent_for_address(addr)
            box_ids.append(boxes[-1]['box_id'])
        return box_ids

    def test_b2_concurrent_pool_stress(self):
        """B2: 50 threads hammer mempool with unique boxes.

        Verify:
        - Each box claimed exactly once (no double-spend)
        - Pool count never exceeds MAX_POOL_SIZE
        - No exceptions under concurrent load
        """
        # Create enough boxes for each thread to have a unique box
        boxes_per_thread = 1
        total_boxes = THREAD_COUNT * boxes_per_thread
        # Create in batches by address
        box_ids = self._create_boxes("stressor", total_boxes)
        self.assertEqual(len(box_ids), total_boxes,
                         f"Created {len(box_ids)}/{total_boxes} boxes")

        results = [{"ok": None, "error": None} for _ in range(THREAD_COUNT)]

        def worker(thread_id: int):
            try:
                bid = box_ids[thread_id]
                ok = self.db.mempool_add({
                    'tx_id': f'stress_tx_{thread_id:04d}',
                    'tx_type': 'transfer',
                    'inputs': [{'box_id': bid, 'spending_proof': 'sig'}],
                    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
                    'fee_nrtc': 0,
                })
                results[thread_id]["ok"] = ok
            except Exception as e:
                results[thread_id]["error"] = str(e)

        threads = []
        start = time.time()
        for i in range(THREAD_COUNT):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        elapsed = time.time() - start

        admitted = sum(1 for r in results if r["ok"] is True)
        rejected = sum(1 for r in results if r["ok"] is False)
        errors = sum(1 for r in results if r["error"] is not None)

        print(f"\n[B2] Stress test: {THREAD_COUNT} threads | {elapsed:.3f}s")
        print(f"[B2] Admitted: {admitted} | Rejected: {rejected} | Errors: {errors}")

        # Check pool count
        conn = self.db._conn()
        pool_count = conn.execute("SELECT COUNT(*) AS n FROM utxo_mempool").fetchone()['n']
        conn.close()
        print(f"[B2] Pool count: {pool_count}/{MAX_POOL_SIZE}")

        # Check box claims — each box claimed at most once
        conn = self.db._conn()
        claim_count = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_mempool_inputs"
        ).fetchone()['n']
        distinct_box_count = conn.execute(
            "SELECT COUNT(DISTINCT box_id) AS n FROM utxo_mempool_inputs"
        ).fetchone()['n']
        conn.close()
        print(f"[B2] Total claims: {claim_count} | Distinct boxes: {distinct_box_count}")

        # Verify no double-spend (each box claimed at most once)
        self.assertEqual(claim_count, distinct_box_count,
                         "B2: Double-spend detected — same box claimed by multiple TXs")
        self.assertLessEqual(pool_count, MAX_POOL_SIZE,
                             f"B2: Pool overflow — {pool_count} > {MAX_POOL_SIZE}")
        self.assertEqual(errors, 0, f"B2: {errors} threads raised exceptions")

        # Check mempool_clear_expired also lacks IMMEDIATE (same B1 pattern)
        self._check_clear_expired_lock()

    def _check_clear_expired_lock(self):
        with open(__file__.replace(self.__class__.__name__ + '.py', 'utxo_db.py')
                  if self.__class__.__name__ + '.py' in __file__
                  else os.path.join(os.path.dirname(__file__), 'utxo_db.py'), 'r') as f:
            src = f.read()
        # Find mempool_clear_expired method
        idx = src.find('def mempool_clear_expired')
        if idx >= 0:
            block = src[idx:idx + 500]
            has_immediate = 'IMMEDIATE' in block or 'BEGIN' in block
            print(f"[B2] mempool_clear_expired() uses explicit transaction: {has_immediate}")
            self.assertFalse(has_immediate,
                "B2: mempool_clear_expired() also lacks BEGIN IMMEDIATE "
                "— same race pattern as B1, called before the pool count check")

    def test_b2_clear_expired_also_has_race(self):
        """B2: mempool_clear_expired() also lacks BEGIN IMMEDIATE.

        Same vulnerability as B1: clears expired entries with no write lock,
        two-step DELETEs (inputs then metadata) in autocommit mode.
        Called BEFORE BEGIN IMMEDIATE in mempool_add() — creates a stale
        count window.
        """
        with open(os.path.join(os.path.dirname(__file__), 'utxo_db.py'), 'r') as f:
            src = f.read()
        idx = src.find('def mempool_clear_expired')
        self.assertGreaterEqual(idx, 0, "mempool_clear_expired not found")
        block = src[idx:idx + 400]
        has_immediate = 'IMMEDIATE' in block or 'BEGIN' in block
        print(f"[B2] mempool_clear_expired IMMEDIATE: {has_immediate}")
        self.assertFalse(has_immediate,
            "B2 CONFIRMED: mempool_clear_expired() lacks BEGIN IMMEDIATE "
            "- stale count window before pool cap check")


if __name__ == '__main__':
    unittest.main(verbosity=2)
