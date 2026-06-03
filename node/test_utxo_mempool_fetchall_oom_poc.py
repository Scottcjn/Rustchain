#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
A5: mempool_get_block_candidates() fetchall() loads all tx_data_json into memory
=================================================================================
VULN: utxo_db.py:1055 — `.fetchall()` loads ALL mempool rows into Python memory.
Combined with NO MAX_TX_DATA_JSON_BYTES limit (A3), an attacker can fill the
mempool with garbage-padded txs, causing OOM on block candidate selection.

Root cause:
1. mempool_add() line 1001: json.dumps(tx) stored directly — no size cap
2. mempool_get_block_candidates() line 1055: .fetchall() → all tx_data_json in RAM
3. Processing loop iterates ALL rows before hitting max_count (line 1091)

At MAX_POOL_SIZE=10000 and each tx carrying 500KB garbage → ~5GB memory spike.

Fix:
- Add MAX_TX_DATA_JSON_BYTES cap in mempool_add() (e.g., 64KB)
- Use server-side cursor / LIMIT+OFFSET in mempool_get_block_candidates()
- Strip non-essential fields before json.dumps()

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT, MAX_COINBASE_OUTPUT_NRTC


def _make_box(db, value_unit: float, address: str = 'fund'):
    """Create a single unspent box with value_unit * UNIT nanoRTC."""
    nrtc = int(value_unit * UNIT)
    if nrtc > MAX_COINBASE_OUTPUT_NRTC:
        raise ValueError(f"nrtc {nrtc} exceeds MAX_COINBASE_OUTPUT_NRTC")
    return db.apply_transaction({
        'tx_type': 'mining_reward', 'inputs': [],
        'outputs': [{'address': address, 'value_nrtc': nrtc}],
        'fee_nrtc': 0, 'timestamp': int(time.time()),
        '_allow_minting': True,
    }, block_height=1)


def _get_box_id(db):
    """Get first unspent box_id."""
    conn = db._conn()
    try:
        row = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE spent_at IS NULL LIMIT 1"
        ).fetchone()
        return row['box_id'] if row else None
    finally:
        conn.close()


class TestMempoolFetchallOOM(unittest.TestCase):
    """mempool_get_block_candidates loads all tx_data_json into memory."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        # Fund 10 RTC box
        ok = _make_box(self.db, 10, 'alice')
        self.assertTrue(ok, "setUp: mining_reward")

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test1_garbage_survives_storage(self):
        """Garbage-padded tx stored at full size — no truncation."""
        box_id = _get_box_id(self.db)
        self.assertIsNotNone(box_id, "No unspent box found")

        garbage_kb = 100
        garbage = "Y" * (garbage_kb * 1024)
        tx = {
            'tx_id': f'garbage_test_{int(time.time())}',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': ''}],
            'outputs': [{'address': 'bob', 'value_nrtc': 10 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            'padding': garbage,              # ← injected garbage, no size limit
            'extra_array': list(range(5000)),
        }

        result = self.db.mempool_add(tx)
        self.assertTrue(result, "mempool_add should accept garbage-padded tx")

        conn = self.db._conn()
        try:
            row = conn.execute(
                "SELECT length(tx_data_json) AS sz FROM utxo_mempool LIMIT 1"
            ).fetchone()
            stored = row['sz']
        finally:
            conn.close()

        expected_min = garbage_kb * 1024
        self.assertGreater(
            stored, expected_min,
            f"Stored tx_data_json ({stored}B) should include padding ({expected_min}B)"
        )
        print(f"  Stored tx_data_json: {stored} bytes ({stored/1024:.0f} KB)")
        print(f"  Padding alone: {garbage_kb} KB")
        print(f"  ➡ NO size limit — garbage survives storage")

    def test2_fetchall_memory_spike(self):
        """Memory spike from fetchall() scales with stored garbage size."""
        # Create 5 distinct boxes
        for i in range(5):
            addr = f"funder_{i}"
            ok = _make_box(self.db, 10, addr)
            self.assertTrue(ok, f"create box for {addr}")

        # Get 5 box IDs
        box_ids = []
        conn = self.db._conn()
        try:
            rows = conn.execute(
                "SELECT box_id FROM utxo_boxes WHERE spent_at IS NULL LIMIT 5"
            ).fetchall()
            box_ids = [r['box_id'] for r in rows]
        finally:
            conn.close()

        self.assertEqual(len(box_ids), 5, "Need 5 boxes")

        # Submit 5 txs with ~100KB garbage each
        for i, bid in enumerate(box_ids):
            garbage = "G" * (100 * 1024)
            tx = {
                'tx_id': f'oom_demo_{i}',
                'tx_type': 'transfer',
                'inputs': [{'box_id': bid, 'spending_proof': ''}],
                'outputs': [{'address': 'bob', 'value_nrtc': 10 * UNIT}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()),
                'padding': garbage,
            }
            ok = self.db.mempool_add(tx)
            self.assertTrue(ok, f"mempool_add tx {i}")

        # Measure memory during mempool_get_block_candidates
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()

        candidates = self.db.mempool_get_block_candidates(max_count=100)

        after = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = after[1] / (1024 * 1024)
        delta_mb = (after[0] - before[0]) / (1024 * 1024)

        print(f"  Candidates returned: {len(candidates)}")
        print(f"  Memory delta (current): {delta_mb:.2f} MB")
        print(f"  Peak memory delta: {peak_mb:.2f} MB")
        print(f"  Each tx ~100KB garbage")

        # Show per-tx stored size
        conn = self.db._conn()
        try:
            rows = conn.execute(
                "SELECT tx_id, length(tx_data_json) AS sz FROM utxo_mempool"
            ).fetchall()
        finally:
            conn.close()

        for tx_id, sz in rows:
            print(f"    {tx_id}: {sz} bytes ({sz/1024:.0f} KB)")

        # Scale estimate
        per_tx_kb = 100
        pool_max = 10000
        print(f"\n  ⚠ SCALE: {pool_max} mempool entries × {per_tx_kb}KB = "
              f"{pool_max * per_tx_kb / 1024:.0f} MB loaded by fetchall()")

    def test3_no_size_limit_confirmed(self):
        """Confirm no MAX_TX_DATA_JSON_BYTES in mempool_add source."""
        import inspect
        source = inspect.getsource(UtxoDB.mempool_add)
        self.assertNotIn("MAX_TX_DATA", source,
                         "No MAX_TX_DATA_JSON_BYTES should exist")
        print("  ✅ No MAX_TX_DATA_JSON_BYTES limit in mempool_add()")


if __name__ == '__main__':
    unittest.main(verbosity=2)
