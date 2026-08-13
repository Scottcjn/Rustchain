#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""`/anchor/list` returned 500 because two components disagree on one table.

`rustchain_ergo_anchor.py` writes `rustchain_height / commitment_hash /
ergo_tx_id`. The deployed anchor writer created `rc_slot / commitment / tx_id`,
and that is the schema holding the 629 rows on production. `CREATE TABLE IF NOT
EXISTS` silently does nothing when a table already exists, so the mismatch was
invisible until a query ran:

    sqlite3.OperationalError: no such column: rustchain_height

Every read in that module assumed its own schema, so the whole read path was
broken against the live database, not just the one endpoint that was noticed.

The reads now resolve whichever column is present. These tests run the same
queries against BOTH schemas, because a fix verified against only one of them
would have looked correct while leaving production exactly as broken.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)

# `rustchain_crypto` resolves to a shared test mock that does not define every
# symbol this module imports. Fill in only the missing names rather than
# editing the shared mock or shipping a second copy of it; nothing in these
# tests exercises crypto, they are about SQL-facing behaviour.
try:
    import rustchain_crypto as _rc
except Exception:
    _rc = types.ModuleType("rustchain_crypto")
    sys.modules["rustchain_crypto"] = _rc

if not hasattr(_rc, "blake2b256_hex"):
    _rc.blake2b256_hex = lambda *a, **k: ""
if not hasattr(_rc, "canonical_json"):
    _rc.canonical_json = lambda *a, **k: ""
if not hasattr(_rc, "MerkleTree"):
    class _MerkleTree:  # minimal stand-in; unused by these tests
        def __init__(self, *a, **k):
            pass

    _rc.MerkleTree = _MerkleTree

_spec = importlib.util.spec_from_file_location(
    "ergo_anchor_mod", os.path.join(NODE, "rustchain_ergo_anchor.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["ergo_anchor_mod"] = MOD
_spec.loader.exec_module(MOD)


MODULE_SCHEMA = """
CREATE TABLE ergo_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rustchain_height INTEGER NOT NULL,
    rustchain_hash TEXT NOT NULL,
    commitment_hash TEXT NOT NULL,
    ergo_tx_id TEXT NOT NULL,
    ergo_height INTEGER,
    confirmations INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at INTEGER NOT NULL
)"""

# exactly what production has
PRODUCTION_SCHEMA = """
CREATE TABLE ergo_anchors (
    id INTEGER PRIMARY KEY,
    commitment TEXT UNIQUE,
    miner_count INTEGER,
    miner_data TEXT,
    rc_slot INTEGER,
    ergo_height INTEGER,
    tx_id TEXT,
    status TEXT DEFAULT 'local',
    created_at INTEGER,
    beacon_count INTEGER DEFAULT 0,
    beacon_digest TEXT DEFAULT ''
)"""


class _DB:
    def __init__(self, schema, rows=()):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(schema)
        for r in rows:
            cols = ",".join(r)
            marks = ",".join("?" * len(r))
            self.conn.execute(
                f"INSERT INTO ergo_anchors ({cols}) VALUES ({marks})", tuple(r.values()))
        self.conn.commit()

    def cursor(self):
        return self.conn.cursor()

    def close(self):
        self.conn.close()
        os.unlink(self.tmp.name)


class ColumnResolutionTest(unittest.TestCase):

    def test_resolves_the_modules_own_schema(self):
        db = _DB(MODULE_SCHEMA)
        try:
            cols = MOD._anchor_columns(db.cursor())
            self.assertEqual(cols["height"], "rustchain_height")
            self.assertEqual(cols["tx_id"], "ergo_tx_id")
            self.assertEqual(cols["commitment"], "commitment_hash")
        finally:
            db.close()

    def test_resolves_the_production_schema(self):
        db = _DB(PRODUCTION_SCHEMA)
        try:
            cols = MOD._anchor_columns(db.cursor())
            self.assertEqual(cols["height"], "rc_slot")
            self.assertEqual(cols["tx_id"], "tx_id")
            self.assertEqual(cols["commitment"], "commitment")
        finally:
            db.close()

    def test_an_unknown_schema_still_yields_an_orderable_column(self):
        """A shape we have not seen must not turn a listing into another 500."""
        db = _DB("CREATE TABLE ergo_anchors (id INTEGER PRIMARY KEY, note TEXT)")
        try:
            cols = MOD._anchor_columns(db.cursor())
            self.assertIn(cols["height"], ("created_at", "id", "rowid"))
        finally:
            db.close()

    def test_a_missing_table_does_not_raise(self):
        db = _DB("CREATE TABLE unrelated (id INTEGER)")
        try:
            self.assertIsInstance(MOD._anchor_columns(db.cursor()), dict)
        finally:
            db.close()


class ListQueryWorksOnBothSchemasTest(unittest.TestCase):
    """The query that actually 500'd, run against each schema."""

    def _list(self, db, limit=50, offset=0):
        cur = db.cursor()
        cols = MOD._anchor_columns(cur)
        cur.execute(
            f"SELECT * FROM ergo_anchors ORDER BY {cols['height']} DESC "
            f"LIMIT ? OFFSET ?", (limit, offset))
        return [dict(r) for r in cur.fetchall()]

    def test_production_schema_lists_and_orders(self):
        db = _DB(PRODUCTION_SCHEMA, rows=[
            {"commitment": "c1", "rc_slot": 10, "tx_id": "t1", "created_at": 1},
            {"commitment": "c2", "rc_slot": 30, "tx_id": "t2", "created_at": 2},
            {"commitment": "c3", "rc_slot": 20, "tx_id": "t3", "created_at": 3},
        ])
        try:
            out = self._list(db)
            self.assertEqual([r["rc_slot"] for r in out], [30, 20, 10])
        finally:
            db.close()

    def test_module_schema_lists_and_orders(self):
        db = _DB(MODULE_SCHEMA, rows=[
            {"rustchain_height": 5, "rustchain_hash": "h", "commitment_hash": "c",
             "ergo_tx_id": "t1", "created_at": 1},
            {"rustchain_height": 9, "rustchain_hash": "h", "commitment_hash": "c",
             "ergo_tx_id": "t2", "created_at": 2},
        ])
        try:
            out = self._list(db)
            self.assertEqual([r["rustchain_height"] for r in out], [9, 5])
        finally:
            db.close()

    def test_pending_tx_query_works_on_the_production_schema(self):
        """This read used SELECT ergo_tx_id, a column production does not have."""
        db = _DB(PRODUCTION_SCHEMA, rows=[
            {"commitment": "c1", "rc_slot": 1, "tx_id": "abc", "status": "pending"},
        ])
        try:
            cur = db.cursor()
            cols = MOD._anchor_columns(cur)
            txcol = cols.get("tx_id", "ergo_tx_id")
            cur.execute(
                f"SELECT {txcol} AS ergo_tx_id FROM ergo_anchors "
                f"WHERE status IN ('pending', 'confirming')")
            self.assertEqual([r["ergo_tx_id"] for r in cur.fetchall()], ["abc"])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
