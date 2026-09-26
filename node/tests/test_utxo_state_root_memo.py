# SPDX-License-Identifier: MIT
"""State root memoization keyed by a DB-level UTXO state version.

/utxo/state_root, /utxo/stats and /utxo/integrity are unauthenticated. Each
used to run compute_state_root() -- an O(N) scan + JSON + SHA-256 per unspent
box -- on every request. The root is now memoized in utxo_state_memo, keyed by
utxo_state_version, which triggers on utxo_boxes bump inside the mutating
transaction. These tests pin:

* a second read with no intervening mutation does not rescan (fails on the
  pre-memo code, which rescanned on every request);
* every utxo_boxes mutation path bumps the version, and the next read
  recomputes to exactly what a fresh compute_state_root() returns;
* mempool-only changes and rolled-back mutations do not change the version;
* reads pinned in one snapshot stay consistent while another connection
  commits;
* the full recompute on /utxo/integrity is admin-only (?force=1).
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest import mock

from flask import Flask

NODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE not in sys.path:
    sys.path.insert(0, NODE)

import state_pruning  # noqa: E402
import utxo_endpoints  # noqa: E402
import utxo_genesis_migration  # noqa: E402
from utxo_db import SCHEMA_SQL, UNIT, UtxoDB  # noqa: E402

ADDR_A = "RTC" + "a" * 40
ADDR_B = "RTC" + "b" * 40


class _Base(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = UtxoDB(self.path)
        self.db.init_tables()
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, "
                      "amount_i64 INTEGER NOT NULL DEFAULT 0)")
        self._coinbase(ADDR_A, 5 * UNIT, 1)
        self._coinbase(ADDR_B, 7 * UNIT, 2)

        self.app = Flask("test_utxo_state_root_memo")
        self.app.testing = True
        utxo_endpoints.register_utxo_blueprint(
            app=self.app, utxo_db=self.db, db_path=self.path,
            verify_sig_fn=lambda *a: True,
            addr_from_pk_fn=lambda pk: ADDR_A,
            current_slot_fn=lambda: 100,
            dual_write=False,
        )
        self.client = self.app.test_client()

        self.scans = 0
        real = UtxoDB.compute_state_root

        def counting(db_self, *a, **kw):
            self.scans += 1
            return real(db_self, *a, **kw)

        patcher = mock.patch.object(UtxoDB, "compute_state_root", counting)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._real_root = lambda: real(self.db)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.path + suffix)
            except OSError:
                pass

    # -- helpers ---------------------------------------------------------
    def _coinbase(self, addr, value, height):
        self.assertTrue(self.db.apply_transaction({
            "tx_type": "mining_reward", "inputs": [],
            "outputs": [{"address": addr, "value_nrtc": value}],
            "fee_nrtc": 0, "timestamp": int(time.time()) + height,
            "_allow_minting": True,
        }, block_height=height))

    def _version(self):
        with sqlite3.connect(self.path) as c:
            return UtxoDB.get_state_version(c)

    def _root(self):
        r = self.client.get("/utxo/state_root")
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def _assert_fresh(self, data):
        """Endpoint output must equal a fresh full computation."""
        self.assertEqual(data["state_root"], self._real_root())
        self.assertEqual(data["unspent_count"], self.db.count_unspent())


class StateRootMemoHitTest(_Base):
    def test_second_read_does_not_rescan(self):
        """Fails on the pre-memo code: every request rescanned the UTXO set."""
        first = self._root()
        self.assertEqual(self.scans, 1)
        second = self._root()
        self.assertEqual(self.scans, 1, "second read with no mutation must hit the memo")
        self.assertEqual(first["state_root"], second["state_root"])
        self.assertEqual(first["unspent_count"], second["unspent_count"])
        self._assert_fresh(second)

    def test_stats_and_integrity_share_the_memo(self):
        self._root()
        self.assertEqual(self.scans, 1)
        stats = self.client.get("/utxo/stats").get_json()
        integ = self.client.get("/utxo/integrity").get_json()
        self.assertEqual(self.scans, 1, "stats/integrity must be served from the memo")
        root = self._real_root()
        self.assertEqual(stats["state_root"], root)
        self.assertEqual(integ["state_root"], root)
        self.assertEqual(stats["unspent_boxes"], 2)
        self.assertEqual(stats["total_value_nrtc"], 12 * UNIT)
        self.assertEqual(stats["spent_boxes"], 0)
        self.assertEqual(integ["total_unspent_nrtc"], 12 * UNIT)
        self.assertEqual(integ["total_unspent_boxes"], 2)
        self.assertFalse(integ["full_recompute"])


class MutationPathsBumpVersionTest(_Base):
    def _check_mutation(self, mutate, expect_count_change=True):
        before = self._root()
        v0 = self._version()
        mutate()
        scans0 = self.scans  # the mutator itself may verify (e.g. genesis)
        self.assertGreater(self._version(), v0, "mutation must bump utxo_state_version")
        after = self._root()
        self.assertEqual(self.scans, scans0 + 1, "next read must recompute once")
        self._assert_fresh(after)
        if expect_count_change:
            self.assertNotEqual(
                (before["state_root"], before["unspent_count"]),
                (after["state_root"], after["unspent_count"]))
        # and the recomputed value is memoized again
        self._root()
        self.assertEqual(self.scans, scans0 + 1)

    def test_apply_transaction_coinbase(self):
        self._check_mutation(lambda: self._coinbase(ADDR_A, 3 * UNIT, 3))

    def test_apply_transaction_transfer(self):
        box = self.db.get_unspent_for_address(ADDR_A)[0]

        def transfer():
            self.assertTrue(self.db.apply_transaction({
                "tx_type": "transfer",
                "inputs": [{"box_id": box["box_id"], "spending_proof": "sig"}],
                "outputs": [{"address": ADDR_B, "value_nrtc": 5 * UNIT}],
                "fee_nrtc": 0,
            }, block_height=4))
        self._check_mutation(transfer)

    def test_add_box(self):
        def add():
            with sqlite3.connect(self.path) as c:
                c.execute("INSERT INTO utxo_transactions (tx_id, tx_type, inputs_json, "
                          "outputs_json, timestamp) VALUES ('t-add','x','[]','[]',0)")
            self.db.add_box({
                "box_id": "f" * 64, "value_nrtc": UNIT, "proposition": "00",
                "owner_address": ADDR_A, "creation_height": 9,
                "transaction_id": "t-add", "output_index": 0,
            })
        self._check_mutation(add)

    def test_spend_box(self):
        box = self.db.get_unspent_for_address(ADDR_B)[0]
        self._check_mutation(lambda: self.db.spend_box(box["box_id"], "spender"))

    def test_raw_sql_writer_like_node_dual_write(self):
        # The node's dual-write mirror and any future writer use raw SQL.
        def raw():
            with sqlite3.connect(self.path) as c:
                c.execute("UPDATE utxo_boxes SET value_nrtc = value_nrtc + 1 "
                          "WHERE owner_address = ?", (ADDR_A,))
        self._check_mutation(raw)

    def test_rollback_restoring_spent_at(self):
        box = self.db.get_unspent_for_address(ADDR_B)[0]
        self.db.spend_box(box["box_id"], "spender")

        def restore():
            with sqlite3.connect(self.path) as c:
                c.execute("UPDATE utxo_boxes SET spent_at = NULL, spent_by_tx = NULL "
                          "WHERE box_id = ?", (box["box_id"],))
        self._check_mutation(restore)

    def test_state_pruning_delete_updates_spent_count(self):
        box = self.db.get_unspent_for_address(ADDR_A)[0]
        self.db.spend_box(box["box_id"], "spender")
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE blocks (height INTEGER)")
            c.execute("INSERT INTO blocks VALUES (1000)")
        self.assertEqual(self.client.get("/utxo/stats").get_json()["spent_boxes"], 1)
        v0 = self._version()
        res = state_pruning.prune_state(self.path, retain_blocks=10, dry_run=False)
        self.assertEqual(res.spent_utxo_rows, 1)
        self.assertGreater(self._version(), v0)
        stats = self.client.get("/utxo/stats").get_json()
        self.assertEqual(stats["spent_boxes"], 0)
        self.assertEqual(stats["state_root"], self._real_root())

    def test_genesis_migration_and_rollback(self):
        # Genesis only runs on an empty UTXO set; clearing it is itself a
        # (raw DELETE) mutation path.
        def clear():
            with sqlite3.connect(self.path) as c:
                c.execute("DELETE FROM utxo_boxes")
                c.execute("DELETE FROM utxo_transactions")
                c.execute("INSERT INTO balances VALUES ('gen-wallet', 3000000)")
        self._check_mutation(clear)

        def genesis():
            res = utxo_genesis_migration.migrate(self.path)
            self.assertNotIn("error", res)
        self._check_mutation(genesis)
        with mock.patch.dict(os.environ, {"RC_ADMIN_KEY": "k"}):
            self._check_mutation(
                lambda: utxo_genesis_migration.rollback_genesis(self.path, admin_key="k"))

    def test_mempool_only_change_does_not_bump(self):
        self._root()
        v0, scans0 = self._version(), self.scans
        box = self.db.get_unspent_for_address(ADDR_A)[0]
        self.assertTrue(self.db.mempool_add({
            "tx_id": "ab" * 32,
            "inputs": [{"box_id": box["box_id"]}],
            "outputs": [{"address": ADDR_B, "value_nrtc": 5 * UNIT}],
            "fee_nrtc": 0,
        }))
        self.assertEqual(self._version(), v0)
        self._root()
        self.assertEqual(self.scans, scans0)

    def test_rolled_back_mutation_leaves_version(self):
        self._root()
        v0 = self._version()
        c = sqlite3.connect(self.path)
        try:
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE utxo_boxes SET value_nrtc = 1")
            # Summary inside the uncommitted write sees its own bump, but must
            # NOT persist a memo for a state that is about to be rolled back.
            inner = self.db.state_summary(conn=c)
            self.assertEqual(inner["version"], v0 + 2)
            self.assertFalse(inner["cached"])
            c.rollback()
        finally:
            c.close()
        self.assertEqual(self._version(), v0)
        self._assert_fresh(self._root())


class SnapshotConsistencyTest(_Base):
    def test_pinned_reader_ignores_concurrent_commit(self):
        reader = sqlite3.connect(self.path)
        try:
            reader.execute("BEGIN")
            s1 = self.db.state_summary(conn=reader)
            # another connection commits a new box while reader is pinned
            self._coinbase(ADDR_A, 9 * UNIT, 7)
            s2 = self.db.state_summary(conn=reader)
            self.assertEqual(s1["version"], s2["version"])
            self.assertEqual(s1["state_root"], s2["state_root"])
            self.assertEqual(s2["unspent_count"], 2)
            self.assertEqual(s2["total_unspent_nrtc"], 12 * UNIT)
        finally:
            reader.rollback()
            reader.close()
        # A fresh reader sees the new state, root and count together.
        s3 = self.db.state_summary()
        self.assertGreater(s3["version"], s1["version"])
        self.assertEqual(s3["unspent_count"], 3)
        self.assertEqual(s3["state_root"], self._real_root())
        self.assertNotEqual(s3["state_root"], s1["state_root"])

    def test_stale_reader_cannot_overwrite_newer_memo(self):
        reader = sqlite3.connect(self.path)
        try:
            reader.execute("BEGIN")
            reader.execute("SELECT 1 FROM utxo_boxes").fetchall()  # pin snapshot
            self._coinbase(ADDR_A, 9 * UNIT, 7)
            fresh = self.db.state_summary()  # stores memo @ new version
            stale = self.db.state_summary(conn=reader)  # old snapshot, miss
            self.assertLess(stale["version"], fresh["version"])
        finally:
            reader.rollback()
            reader.close()
        scans0 = self.scans
        again = self.db.state_summary()
        self.assertTrue(again["cached"])
        self.assertEqual(self.scans, scans0)
        self.assertEqual(again["state_root"], fresh["state_root"])


class SchemaAndFallbackTest(_Base):
    def test_existing_db_without_memo_schema(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(path) as c:  # pre-upgrade production shape
                c.executescript(SCHEMA_SQL)
            db = UtxoDB(path)
            s0 = db.state_summary()  # no memo schema yet -> full compute, no crash
            self.assertIsNone(s0["version"])
            self.assertTrue(db.ensure_state_memo_schema())
            self.assertTrue(db.ensure_state_memo_schema())  # idempotent
            db.init_tables()  # also idempotent over it
            s1 = db.state_summary()
            self.assertEqual(s1["version"], 0)
            self.assertFalse(s1["cached"])
            self.assertTrue(db.state_summary()["cached"])
        finally:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(path + suffix)
                except OSError:
                    pass

    def test_missing_trigger_disables_memo(self):
        self._root()
        with sqlite3.connect(self.path) as c:
            c.execute("DROP TRIGGER trg_utxo_boxes_state_version_upd")
            c.execute("UPDATE utxo_boxes SET value_nrtc = value_nrtc + 1")
        scans0 = self.scans
        data = self._root()
        self.assertEqual(self.scans, scans0 + 1, "untrusted memo must not be served")
        self._assert_fresh(data)


class IntegrityForceTest(_Base):
    def test_force_requires_admin(self):
        with mock.patch.dict(os.environ, {"RC_ADMIN_KEY": "sekret"}):
            r = self.client.get("/utxo/integrity?force=1")
            self.assertEqual(r.status_code, 401)
            r = self.client.get("/utxo/integrity?force=1",
                                headers={"X-Admin-Key": "wrong"})
            self.assertEqual(r.status_code, 401)
            self._root()
            scans0 = self.scans
            r = self.client.get("/utxo/integrity?force=1",
                                headers={"X-Admin-Key": "sekret"})
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertTrue(data["full_recompute"])
            self.assertEqual(self.scans, scans0 + 1)
            self.assertEqual(data["state_root"], self._real_root())

    def test_force_denied_when_admin_key_unset(self):
        with mock.patch.dict(os.environ, {"RC_ADMIN_KEY": ""}):
            r = self.client.get("/utxo/integrity?force=1",
                                headers={"X-Admin-Key": ""})
            self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
