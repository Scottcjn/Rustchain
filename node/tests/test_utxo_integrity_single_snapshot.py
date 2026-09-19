# SPDX-License-Identifier: MIT
"""#2819 (robin1121): the integrity report must describe ONE snapshot.

compute_state_root() opened its own connection, so the totals and the root
beside them could come from two different database states (and models_agree
was decided across them). These tests pin the totals, the root and the caller's
view to a single connection. The mixing is made deterministic with an
uncommitted write: a box visible only inside one transaction must appear in
both the totals and the root computed for that same connection, or in neither.
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

NODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE not in sys.path:
    sys.path.insert(0, NODE)

from utxo_db import UtxoDB, UNIT


def _insert_box(conn, box_id, owner, value_nrtc, height=1):
    now = int(time.time())
    conn.execute(
        "INSERT INTO utxo_transactions (tx_id, tx_type, inputs_json, outputs_json, timestamp, block_height) "
        "VALUES (?, 'transfer', '[]', '[]', ?, ?)", (f"tx-{box_id}", now, height))
    conn.execute(
        "INSERT INTO utxo_boxes (box_id, value_nrtc, proposition, owner_address, creation_height, "
        "transaction_id, output_index, created_at) VALUES (?,?,?,?,?,?,0,?)",
        (box_id, value_nrtc, "p", owner, height, f"tx-{box_id}", now))


class IntegritySingleSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        with sqlite3.connect(self.tmp.name) as c:
            c.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, "
                      "amount_i64 INTEGER NOT NULL DEFAULT 0)")
            _insert_box(c, "box-committed", "RTC" + "a" * 40, 5 * UNIT)
            c.commit()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_totals_and_root_come_from_the_callers_snapshot(self):
        conn = sqlite3.connect(self.tmp.name)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            _insert_box(conn, "box-uncommitted", "RTC" + "b" * 40, 7 * UNIT, height=2)

            result = self.db.integrity_check(conn=conn)
            root_same_conn = self.db.compute_state_root(conn=conn)

            # Everything must describe the caller's view: 2 boxes, 12 RTC, and a
            # root over both. Pre-fix the root was computed on a second
            # connection, which could not see box-uncommitted.
            self.assertEqual(result["total_unspent_boxes"], 2)
            self.assertEqual(result["total_unspent_nrtc"], 12 * UNIT)
            self.assertEqual(result["state_root"], root_same_conn)
            self.assertNotEqual(result["state_root"], self.db.compute_state_root(),
                                "root must reflect the caller's snapshot, not a fresh one")
            self.assertEqual(self.db.count_unspent(conn=conn), 2)
        finally:
            conn.rollback()
            conn.close()

    def test_models_agree_is_decided_on_one_snapshot(self):
        """expected_total is compared against totals from the same connection."""
        conn = sqlite3.connect(self.tmp.name)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            _insert_box(conn, "box-settlement", "RTC" + "c" * 40, 3 * UNIT, height=3)
            # An account model that already includes the in-flight 3 RTC agrees
            # only if the UTXO side is read from this same snapshot.
            res = self.db.integrity_check(expected_total=8 * UNIT, conn=conn)
            self.assertTrue(res["ok"])
            self.assertTrue(res.get("models_agree"))
        finally:
            conn.rollback()
            conn.close()

    def test_default_behaviour_unchanged_without_a_connection(self):
        res = self.db.integrity_check()
        self.assertEqual(res["total_unspent_boxes"], 1)
        self.assertEqual(res["state_root"], self.db.compute_state_root())
        self.assertEqual(self.db.count_unspent(), 1)


if __name__ == "__main__":
    unittest.main()


class IntegrityRaceTest(unittest.TestCase):
    """A settlement committing BETWEEN the totals read and the root read must not
    split the report across two states (the original robin1121 defect)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        with sqlite3.connect(self.tmp.name) as c:
            _insert_box(c, "box-1", "RTC" + "a" * 40, 5 * UNIT)
            c.commit()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_concurrent_commit_between_reads_does_not_split_the_report(self):
        real_root = self.db.compute_state_root

        def root_with_interleaved_commit(*a, **kw):
            # Simulate an epoch settlement committing on another connection
            # after the totals were read but before the root is computed.
            with sqlite3.connect(self.tmp.name) as other:
                _insert_box(other, "box-race", "RTC" + "d" * 40, 9 * UNIT, height=9)
                other.commit()
            self.db.compute_state_root = real_root      # only interleave once
            return real_root(*a, **kw)

        self.db.compute_state_root = root_with_interleaved_commit
        try:
            res = self.db.integrity_check()
        finally:
            self.db.compute_state_root = real_root

        # The report must be internally consistent: the root must be the root OF
        # the box set whose totals it reports (1 box / 5 RTC), not of the set
        # after the interleaved commit.
        self.assertEqual(res["total_unspent_boxes"], 1)
        self.assertEqual(res["total_unspent_nrtc"], 5 * UNIT)
        after = self.db.compute_state_root()   # old API only: root of the 2-box set now
        self.assertNotEqual(res["state_root"], after,
                            "root reflects the post-commit set while the totals beside it "
                            "reflect the pre-commit set (report split across two snapshots)")
