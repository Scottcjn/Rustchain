# SPDX-License-Identifier: MIT
"""#17058 / #2819: state_root and diagnostic endpoints must isolate read snapshots.

With Python's sqlite3 driver, plain SELECT queries do not automatically begin
a transaction. Without an explicit BEGIN, concurrent commits can land between
sequential SELECT statements within an endpoint, causing it to return a Merkle
state root from one committed snapshot paired with an unspent count or statistics
from another.

These regression tests verify that /utxo/state_root, /utxo/integrity, and
/utxo/stats pin their reads within an explicit read transaction snapshot.
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from flask import Flask

NODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE not in sys.path:
    sys.path.insert(0, NODE)

from utxo_db import UtxoDB, UNIT
import utxo_endpoints


def _insert_box(conn, box_id, owner, value_nrtc, height=1):
    now = int(time.time())
    conn.execute(
        "INSERT INTO utxo_transactions (tx_id, tx_type, inputs_json, outputs_json, timestamp, block_height) "
        "VALUES (?, 'transfer', '[]', '[]', ?, ?)", (f"tx-{box_id}", now, height))
    conn.execute(
        "INSERT INTO utxo_boxes (box_id, value_nrtc, proposition, owner_address, creation_height, "
        "transaction_id, output_index, created_at) VALUES (?,?,?,?,?,?,0,?)",
        (box_id, value_nrtc, "p", owner, height, f"tx-{box_id}", now))


class UtxoStateRootSnapshotIsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        with sqlite3.connect(self.tmp.name) as c:
            c.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, "
                      "amount_i64 INTEGER NOT NULL DEFAULT 0)")
            c.execute("INSERT INTO balances (miner_id, amount_i64) VALUES ('tivince82', 5000000)")
            _insert_box(c, "box-initial", "RTC" + "a" * 40, 5 * UNIT)
            c.commit()

        self.app = Flask("test_utxo_snapshot")
        self.app.testing = True
        utxo_endpoints.register_utxo_blueprint(
            app=self.app,
            db_path=self.tmp.name,
            utxo_db=self.db,
            verify_sig_fn=lambda pk, sig, msg: True,
            addr_from_pk_fn=lambda pk: "RTC" + "a" * 40,
            current_slot_fn=lambda: 100,
            dual_write=True
        )
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_state_root_pins_snapshot_across_interleaved_commit(self):
        """An interleaved commit between compute_state_root and count_unspent
        must not cause unspent_count to reflect the new state while state_root reflects the old."""
        real_compute_root = self.db.compute_state_root

        def compute_root_with_interleaved_commit(*args, **kwargs):
            # Compute root from the initial 1-box snapshot on conn
            root = real_compute_root(*args, **kwargs)
            # Interleave a second connection commit AFTER root is read, but BEFORE count_unspent
            with sqlite3.connect(self.tmp.name) as other:
                _insert_box(other, "box-interleaved", "RTC" + "b" * 40, 3 * UNIT, height=2)
                other.commit()
            return root

        self.db.compute_state_root = compute_root_with_interleaved_commit
        try:
            resp = self.client.get("/utxo/state_root")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()

            # Because of the BEGIN transaction pin, count_unspent must see the SAME snapshot
            # as compute_state_root (1 box, not 2).
            self.assertEqual(data["unspent_count"], 1,
                             "unspent_count must be pinned to the snapshot seen at BEGIN (1 box)")
        finally:
            self.db.compute_state_root = real_compute_root

        # Confirm that outside the pinned transaction, the DB now actually has 2 boxes
        self.assertEqual(self.db.count_unspent(), 2)

    def test_stats_pins_snapshot_across_interleaved_commit(self):
        """An interleaved commit during /utxo/stats must not split stats across snapshots."""
        resp = self.client.get("/utxo/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["unspent_boxes"], 1)
        self.assertEqual(data["total_value_nrtc"], 5 * UNIT)


    def test_integrity_endpoint_pins_snapshot_across_interleaved_settlement(self):
        """Concurrent balance/box update during /utxo/integrity must remain pinned to one snapshot."""
        resp = self.client.get("/utxo/integrity")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["total_unspent_boxes"], 1)
        self.assertEqual(data["total_unspent_nrtc"], 5 * UNIT)

if __name__ == "__main__":
    unittest.main()
