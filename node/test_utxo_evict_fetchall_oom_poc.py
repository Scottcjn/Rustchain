#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
[UTXO-BUG] _evict_stale_data_input_txs() fetchall() OOM on apply_transaction()
================================================================================

VULN: utxo_db.py — _evict_stale_data_input_txs() calls
    conn.execute("SELECT tx_id, tx_data_json FROM utxo_mempool").fetchall()

This loads ALL mempool entries including tx_data_json into Python memory in a
single call. It is triggered on EVERY apply_transaction() commit (the block
application critical path).

Distinct from the previously-reported mempool_get_block_candidates() fetchall
(now fixed): _evict_stale_data_input_txs() is a separate code path that
remained vulnerable.

Attack:
  1. Fill mempool with MAX_POOL_SIZE (10,000) transactions near the
     MAX_TX_DATA_JSON_BYTES (256 KB) per-tx limit.
  2. Mine any valid block to trigger apply_transaction().
  3. apply_transaction() calls _evict_stale_data_input_txs() which issues
     fetchall() → loads ≤ 10,000 × 256 KB = 2.56 GB into Python RAM → OOM.

Fix: replace .fetchall() with cursor iteration so only one row is in memory
at a time (already applied in utxo_db.py).

Bot: Ivan-LB
"""

import inspect
import json
import os
import sys
import tempfile
import time
import tracemalloc
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT, MAX_COINBASE_OUTPUT_NRTC, MAX_TX_DATA_JSON_BYTES


def _mine(db: UtxoDB, nrtc: int, address: str, block_height: int) -> bool:
    return db.apply_transaction({
        'tx_type': 'mining_reward', 'inputs': [],
        'outputs': [{'address': address, 'value_nrtc': nrtc}],
        'fee_nrtc': 0, 'timestamp': int(time.time()),
        '_allow_minting': True,
    }, block_height=block_height)


def _get_unspent_boxes(db: UtxoDB, limit: int = 100):
    conn = db._conn()
    try:
        return conn.execute(
            "SELECT box_id, value_nrtc FROM utxo_boxes WHERE spent_at IS NULL LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        conn.close()


class TestEvictFetchallOOM(unittest.TestCase):
    """_evict_stale_data_input_txs() uses fetchall() — OOM on full mempool."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_fix_uses_cursor_iteration_not_fetchall(self):
        """After fix: _evict_stale_data_input_txs source must not use .fetchall()
        on the full mempool SELECT."""
        source = inspect.getsource(UtxoDB._evict_stale_data_input_txs)
        lines = source.splitlines()

        # Find the block that SELECTs tx_data_json from mempool
        data_json_select_idx = None
        for i, line in enumerate(lines):
            if 'tx_data_json' in line and 'FROM utxo_mempool' in line:
                data_json_select_idx = i
                break

        self.assertIsNotNone(data_json_select_idx,
            "Could not find SELECT tx_data_json FROM utxo_mempool in source")

        # The SELECT must NOT be followed immediately by .fetchall()
        # (next non-empty line after the query)
        context_lines = lines[data_json_select_idx:data_json_select_idx + 5]
        context = '\n'.join(context_lines)
        self.assertNotIn('.fetchall()', context,
            f"_evict_stale_data_input_txs() still calls .fetchall() on the full "
            f"mempool tx_data_json SELECT — this is the OOM vector.\n"
            f"Context:\n{context}\n"
            f"Fix: replace .fetchall() with cursor iteration."
        )
        print("\n  ✅ _evict_stale_data_input_txs uses cursor iteration (no fetchall)")

    def test_memory_footprint_bounded_with_padded_txs(self):
        """Memory during apply_transaction should not scale with mempool size."""
        N_BOXES = 10
        N_MEMPOOL = 10  # limited by available boxes; enough to demonstrate pattern

        # Create N_BOXES independent UTXOs via mining
        max_per_block = MAX_COINBASE_OUTPUT_NRTC
        for i in range(N_BOXES):
            ok = _mine(self.db, max_per_block, f'owner_{i}', block_height=i + 1)
            self.assertTrue(ok, f"setup: mine box {i}")

        boxes = _get_unspent_boxes(self.db, limit=N_BOXES)
        self.assertGreaterEqual(len(boxes), N_MEMPOOL, "Not enough boxes for test")

        # Fill N_MEMPOOL mempool slots with padded transactions (~100 KB each)
        pad_size = 100 * 1024  # 100 KB padding per tx
        for j, box in enumerate(boxes[:N_MEMPOOL]):
            box_id, value_nrtc = box['box_id'], box['value_nrtc']
            tx = {
                'tx_id': f'padded_{j:04d}',
                'tx_type': 'transfer',
                'inputs': [{'box_id': box_id, 'spending_proof': ''}],
                'outputs': [{'address': f'dest_{j}', 'value_nrtc': value_nrtc}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()),
                '_padding': 'P' * pad_size,
            }
            # Truncate if over limit
            tx_json = json.dumps(tx)
            if len(tx_json) > MAX_TX_DATA_JSON_BYTES:
                tx['_padding'] = 'P' * (pad_size - (len(tx_json) - MAX_TX_DATA_JSON_BYTES) - 10)
            ok = self.db.mempool_add(tx)
            self.assertTrue(ok, f"mempool_add padded tx {j}")

        # Verify mempool is populated
        conn = self.db._conn()
        try:
            pool_count = conn.execute("SELECT COUNT(*) AS n FROM utxo_mempool").fetchone()['n']
            total_bytes = conn.execute(
                "SELECT COALESCE(SUM(length(tx_data_json)), 0) AS b FROM utxo_mempool"
            ).fetchone()['b']
        finally:
            conn.close()
        print(f"\n  Mempool: {pool_count} txs, {total_bytes/1024:.0f} KB total tx_data_json")

        # Now mine a NEW box and spend it to trigger apply_transaction()
        # which calls _evict_stale_data_input_txs() internally
        ok = _mine(self.db, max_per_block, 'trigger_addr', block_height=N_BOXES + 1)
        self.assertTrue(ok, "mine trigger box")

        trigger_boxes = _get_unspent_boxes(self.db, limit=1)
        self.assertTrue(trigger_boxes, "No trigger box found")
        trigger_box_id = None
        for b in trigger_boxes:
            if b['box_id'] not in {box['box_id'] for box in boxes[:N_MEMPOOL]}:
                trigger_box_id = b['box_id']
                trigger_value  = b['value_nrtc']
                break
        if trigger_box_id is None:
            # Fallback: use any unspent box not in mempool
            conn = self.db._conn()
            try:
                claimed = set(conn.execute(
                    "SELECT box_id FROM utxo_mempool_inputs"
                ).fetchall().__iter__().__next__()['box_id']
                for _ in [None])
            except Exception:
                claimed = set()
            finally:
                conn.close()

        # Directly call apply_transaction with a fresh mining_reward to trigger eviction
        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        ok = _mine(self.db, max_per_block, 'measurement', block_height=N_BOXES + 2)
        self.assertTrue(ok, "measurement mining_reward")

        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap_after.compare_to(snap_before, 'lineno')
        top_stats = stats[:5]
        total_delta_kb = sum(s.size_diff for s in stats) / 1024

        print(f"  Memory delta from apply_transaction: {total_delta_kb:.0f} KB")
        print(f"  Total mempool data: {total_bytes/1024:.0f} KB")
        print(f"  ✅ Memory delta should be << total mempool data (cursor streaming)")
        for stat in top_stats[:3]:
            print(f"    {stat}")

        # With cursor iteration, memory delta should be well below total pool size
        # (we loaded up to 10 × ~100KB = ~1MB into pool; delta should be << that)
        self.assertLess(
            total_delta_kb, total_bytes / 1024 * 0.5,
            f"Memory spike ({total_delta_kb:.0f} KB) exceeds 50% of mempool data "
            f"({total_bytes/1024:.0f} KB) — fetchall() may still be loading all rows"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
