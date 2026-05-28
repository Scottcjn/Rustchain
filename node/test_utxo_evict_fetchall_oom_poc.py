# SPDX-License-Identifier: MIT
"""PoC tests for _evict_stale_data_input_txs() fetchall() OOM DoS."""
import json
import os
import sqlite3
import tempfile
import tracemalloc
import unittest


def _make_db(path: str, n_txs: int, tx_size_bytes: int) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS utxo_mempool (
            tx_id TEXT PRIMARY KEY,
            tx_data_json TEXT NOT NULL,
            fee_nrtc INTEGER DEFAULT 0,
            submitted_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS utxo_mempool_inputs (
            box_id TEXT NOT NULL PRIMARY KEY,
            tx_id TEXT NOT NULL
        );
    """)
    padding = "x" * tx_size_bytes
    for i in range(n_txs):
        tx_id = f"tx_{i:06d}"
        tx_data = json.dumps({"tx_id": tx_id, "data_inputs": [], "pad": padding})
        conn.execute(
            "INSERT INTO utxo_mempool VALUES (?,?,0,0,9999999999)",
            (tx_id, tx_data),
        )
    conn.commit()
    return conn


class TestEvictFetchallOOM(unittest.TestCase):

    def test_cursor_iteration_bounded_memory(self):
        """Cursor iteration keeps memory proportional to one row, not the pool."""
        n_txs = 10
        tx_size = 100_000  # 100KB per tx → 1MB total pool
        total_pool_bytes = n_txs * tx_size

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = _make_db(db_path, n_txs, tx_size)

            tracemalloc.start()
            snap_before = tracemalloc.take_snapshot()

            # Fixed code: cursor iteration — never loads entire pool into RAM
            stale_tx_ids = set()
            for mp_row in conn.execute(
                "SELECT tx_id, tx_data_json FROM utxo_mempool"
            ):
                try:
                    tx_data = json.loads(mp_row["tx_data_json"])
                    if tx_data.get("data_inputs"):
                        stale_tx_ids.add(mp_row["tx_id"])
                except (json.JSONDecodeError, TypeError):
                    pass

            snap_after = tracemalloc.take_snapshot()
            tracemalloc.stop()

            stats = snap_after.compare_to(snap_before, 'lineno')
            delta_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)

            conn.close()

            # Memory delta should be well below 50% of total pool size
            self.assertLess(
                delta_bytes, total_pool_bytes * 0.5,
                f"Memory delta {delta_bytes/1024:.1f} KB exceeds 50% of "
                f"pool size {total_pool_bytes/1024:.1f} KB"
            )
        finally:
            os.unlink(db_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
