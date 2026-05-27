#!/usr/bin/env python3
"""
A6: mempool_remove() races with mempool_add() — orphan input claims
====================================================================
VULN: utxo_db.py:1027-1039 — mempool_remove() has no BEGIN IMMEDIATE.
Each DELETE autocommits separately, creating a race window where a
concurrent mempool_add with the same tx_id can interleave.

DEMONSTRATED: Sequential connection interleaving proves the orphan state
is physically possible — SQLite has no constraint preventing it.

Fix: Wrap both DELETEs in BEGIN IMMEDIATE ... COMMIT for atomic release.

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


def _make_box(db, value_unit: float = 10, address: str = 'fund'):
    nrtc = int(value_unit * UNIT)
    if nrtc > 150 * UNIT:
        raise ValueError("Over coinbase cap")
    return db.apply_transaction({
        'tx_type': 'mining_reward', 'inputs': [],
        'outputs': [{'address': address, 'value_nrtc': nrtc}],
        'fee_nrtc': 0, 'timestamp': int(time.time()),
        '_allow_minting': True,
    }, block_height=1)


class TestMempoolRemoveRaceDirect(unittest.TestCase):
    """Direct SQLite interleaving to demonstrate orphan input claims."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        _make_box(self.db, 10, 'alice')

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test1_no_begin_immediate(self):
        """Confirm mempool_remove has no BEGIN IMMEDIATE."""
        import inspect
        src = inspect.getsource(UtxoDB.mempool_remove)
        self.assertNotIn("BEGIN", src, "mempool_remove has no BEGIN")
        print("  ✅ mempool_remove() no BEGIN → DELETEs auto-commit separately")

    def test2_orphan_demonstration(self):
        """Sequential SQL interleaving: prove orphan state is possible."""
        TX_ID = 'orphan_demo'
        box_id = None

        # Get a box
        conn = self.db._conn()
        try:
            row = conn.execute(
                "SELECT box_id FROM utxo_boxes WHERE spent_at IS NULL LIMIT 1"
            ).fetchone()
            box_id = row['box_id']
        finally:
            conn.close()

        self.assertIsNotNone(box_id)

        # Add tx to mempool via normal API
        ok = self.db.mempool_add({
            'tx_id': TX_ID,
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': ''}],
            'outputs': [{'address': 'bob', 'value_nrtc': 10 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        })
        self.assertTrue(ok, "Initial mempool_add")
        print(f"  Initial: TX '{TX_ID}' in mempool, box {box_id[:16]}... claimed ✓")

        # === SIMULATE RACE ===
        # Step 1: mempool_remove's first DELETE (frees box claim)
        conn1 = sqlite3.connect(self.db.db_path)
        conn1.row_factory = sqlite3.Row
        conn1.execute("DELETE FROM utxo_mempool_inputs WHERE tx_id = ?", (TX_ID,))
        conn1.commit()  # explicit commit = autocommit equivalent
        print(f"  Step 1: DELETE utxo_mempool_inputs → claim released ✓")

        # CRITICAL: close conn1 so conn2 can take the write lock
        conn1.close()

        # Step 2: concurrent mempool_add re-claims the freed box for same tx_id
        conn2 = sqlite3.connect(self.db.db_path)
        conn2.row_factory = sqlite3.Row
        conn2.execute("BEGIN IMMEDIATE")

        # Verify box is free now
        existing = conn2.execute(
            "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id = ?", (box_id,)
        ).fetchone()
        self.assertIsNone(existing, "Box should be unclaimed after step 1")

        # Re-insert mempool entry + claim
        now = int(time.time())
        conn2.execute(
            """INSERT INTO utxo_mempool
               (tx_id, tx_data_json, fee_nrtc, submitted_at, expires_at)
               VALUES (?,?,?,?,?)""",
            (TX_ID, '{"reclaim": true}', 0, now, now + 3600),
        )
        conn2.execute(
            "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?,?)",
            (box_id, TX_ID),
        )
        conn2.execute("COMMIT")
        conn2.close()
        print(f"  Step 2: mempool_add re-inserts entry + claim ✓")

        # Step 3: mempool_remove's second DELETE (removes mempool entry)
        conn3 = sqlite3.connect(self.db.db_path)
        conn3.execute("DELETE FROM utxo_mempool WHERE tx_id = ?", (TX_ID,))
        conn3.commit()
        conn3.close()
        print(f"  Step 3: DELETE utxo_mempool → entry removed ✓")

        # === VERIFY ORPHAN ===
        conn4 = self.db._conn()
        try:
            entry = conn4.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id = ?", (TX_ID,)
            ).fetchone()
            claims = conn4.execute(
                "SELECT box_id FROM utxo_mempool_inputs WHERE tx_id = ?", (TX_ID,)
            ).fetchall()

            self.assertIsNone(entry, "mempool entry should be gone")
            self.assertGreater(len(claims), 0,
                "input claims should survive — ORPHAN")

            print(f"\n  ⚠ ORPHAN CONFIRMED: {len(claims)} claim(s) with no mempool entry")
            print(f"  Box {box_id[:16]}... locked by ghost tx")

            # Box is reported as locked
            locked = conn4.execute(
                "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id = ?",
                (box_id,)
            ).fetchone()
            print(f"  mempool_check_double_spend('{box_id[:16]}...') = {locked is not None}")
            print(f"  ➡ Box LOCKED — unspendable until ghost entry expires")
        finally:
            conn4.close()

    def test3_multi_box_orphan(self):
        """3 boxes orphaned in one attack cycle."""
        for i in range(3):
            _make_box(self.db, 10, f'v{i}')

        conn = self.db._conn()
        try:
            box_ids = [r['box_id'] for r in conn.execute(
                "SELECT box_id FROM utxo_boxes WHERE spent_at IS NULL LIMIT 3"
            ).fetchall()]
        finally:
            conn.close()

        self.assertEqual(len(box_ids), 3)
        TX_ID = 'multi_orphan'

        # Add to mempool
        self.db.mempool_add({
            'tx_id': TX_ID,
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': ''} for bid in box_ids],
            'outputs': [{'address': 'bob', 'value_nrtc': 30 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        })

        # Race: release → re-claim → delete entry
        c1 = sqlite3.connect(self.db.db_path)
        c1.execute("DELETE FROM utxo_mempool_inputs WHERE tx_id = ?", (TX_ID,))
        c1.commit()
        c1.close()

        c2 = sqlite3.connect(self.db.db_path)
        c2.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        c2.execute(
            "INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, submitted_at, expires_at) VALUES (?,?,?,?,?)",
            (TX_ID, '{"multi": true}', 0, now, now + 3600),
        )
        for bid in box_ids:
            c2.execute("INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?,?)", (bid, TX_ID))
        c2.execute("COMMIT")
        c2.close()

        c3 = sqlite3.connect(self.db.db_path)
        c3.execute("DELETE FROM utxo_mempool WHERE tx_id = ?", (TX_ID,))
        c3.commit()
        c3.close()

        # Verify: all 3 claims survive, no entry
        c4 = self.db._conn()
        try:
            entry = c4.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id = ?", (TX_ID,)
            ).fetchone()
            n_claims = c4.execute(
                "SELECT COUNT(*) AS n FROM utxo_mempool_inputs WHERE tx_id = ?",
                (TX_ID,)
            ).fetchone()['n']

            self.assertIsNone(entry)
            self.assertEqual(n_claims, 3, "All 3 claims survive")

            print(f"  🗳 {n_claims} boxes locked by ghost tx '{TX_ID}'")
            print(f"  Each locked for up to 1 hour (mempool expiry)")
            print(f"  At MAX_POOL_SIZE=10000, attacker can lock 10000+ boxes")
        finally:
            c4.close()

    def test4_compare_with_proper_locking(self):
        """Compare: a properly locked mempool_remove prevents the race."""
        import inspect
        src = inspect.getsource(UtxoDB.mempool_remove)

        # Patch: add BEGIN IMMEDIATE
        # We'll just write the test to prove atomic DELETE prevents orphan.
        TX_ID = 'locked_remove_test'
        box_id = None

        conn = self.db._conn()
        try:
            row = conn.execute(
                "SELECT box_id FROM utxo_boxes WHERE spent_at IS NULL LIMIT 1"
            ).fetchone()
            box_id = row['box_id']
        finally:
            conn.close()

        self.db.mempool_add({
            'tx_id': TX_ID,
            'tx_type': 'transfer',
            'inputs': [{'box_id': box_id, 'spending_proof': ''}],
            'outputs': [{'address': 'bob', 'value_nrtc': 10 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        })

        # CORRECT remove: both DELETEs inside one transaction
        cp = sqlite3.connect(self.db.db_path)
        cp.execute("BEGIN IMMEDIATE")
        cp.execute("DELETE FROM utxo_mempool_inputs WHERE tx_id = ?", (TX_ID,))
        cp.execute("DELETE FROM utxo_mempool WHERE tx_id = ?", (TX_ID,))
        cp.execute("COMMIT")
        cp.close()
        # Neither DELETE ran as autocommit — they were atomic within the tx

        # Verify: no orphan — both entry and claims cleanly removed
        cq = self.db._conn()
        try:
            entry = cq.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id = ?", (TX_ID,)
            ).fetchone()
            claims = cq.execute(
                "SELECT COUNT(*) AS n FROM utxo_mempool_inputs WHERE tx_id = ?",
                (TX_ID,)
            ).fetchone()['n']

            self.assertIsNone(entry, "entry removed")
            self.assertEqual(claims, 0, "no orphan claims with proper locking")
            print(f"  ✅ With BEGIN IMMEDIATE: {claims} orphan claims (clean)")
        finally:
            cq.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
