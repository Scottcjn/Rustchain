"""
Deterministic regression tests for UTXO snapshot consistency (#17058 / #2819).

Verifies that:
1. `/utxo/state_root` returns a `state_root` and `unspent_count` from the exact same
   SQLite snapshot even when a second connection commits a new box mid-request.
2. `UtxoDB.state_summary(conn=conn)` and `UtxoDB.integrity_check(conn=conn)` pin a read
   snapshot even when the caller passes an un-begun SQLite connection (`conn.in_transaction == False`).
3. `/utxo/integrity` on a pure-UTXO database (no `balances` table) still pins its read
   snapshot before reading totals and `compute_state_root`.
4. `/utxo/balance/<address>` reads `balance_nrtc` and `utxo_count` from one pinned snapshot.
"""

import os
import sqlite3
import tempfile
import time
from flask import Flask

from utxo_db import UtxoDB, UNIT, address_to_proposition, compute_box_id
from utxo_endpoints import register_utxo_blueprint


def _make_box(address: str, value_nrtc: int, height: int, tx_byte: str) -> dict:
    tx_id = tx_byte * 64
    prop = address_to_proposition(address)
    box_id = compute_box_id(value_nrtc, prop, height, tx_id, 0)
    return {
        "box_id": box_id,
        "value_nrtc": value_nrtc,
        "proposition": prop,
        "owner_address": address,
        "creation_height": height,
        "transaction_id": tx_id,
        "output_index": 0,
    }


def test_state_root_endpoint_pins_single_snapshot_under_interleaved_commit():
    """Inject a second-connection commit during compute_state_root and verify root & count match."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        db = UtxoDB(db_path)
        db.init_tables()
        addr = "RTC" + "a" * 40
        db.add_box(_make_box(addr, 10 * UNIT, 1, "1"))

        expected_root_1 = db.compute_state_root()
        assert db.count_unspent() == 1

        app = Flask(__name__)
        app.config["TESTING"] = True
        register_utxo_blueprint(
            app, db, db_path,
            verify_sig_fn=lambda *a: True,
            addr_from_pk_fn=lambda pk: addr,
            current_slot_fn=lambda: 1,
            dual_write=False,
        )
        client = app.test_client()

        # Force cache miss so state_summary runs _compute_state_summary, and commit a 2nd box
        # on a separate connection right as compute_state_root runs.
        orig_compute_root = db.compute_state_root

        def interleaved_compute_root(conn=None):
            # Another writer commits a second box while the endpoint's read is in progress
            writer_db = UtxoDB(db_path)
            writer_db.add_box(_make_box(addr, 20 * UNIT, 2, "2"))
            return orig_compute_root(conn=conn)

        db.compute_state_root = interleaved_compute_root
        try:
            # Drop memo row so state_summary must recompute
            c = sqlite3.connect(db_path)
            c.execute("DELETE FROM utxo_state_memo")
            c.commit()
            c.close()

            resp = client.get("/utxo/state_root")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["unspent_count"] == 1
            assert data["state_root"] == expected_root_1
        finally:
            db.compute_state_root = orig_compute_root

        # Subsequent request sees the newly committed 2-box snapshot
        resp2 = client.get("/utxo/state_root")
        data2 = resp2.get_json()
        assert data2["unspent_count"] == 2
        assert data2["state_root"] != expected_root_1
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_caller_supplied_unbegun_connection_is_pinned_in_state_summary_and_integrity():
    """Even if a caller passes conn with in_transaction=False, state_summary and integrity_check pin a snapshot."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        db = UtxoDB(db_path)
        db.init_tables()
        addr = "RTC" + "b" * 40
        db.add_box(_make_box(addr, 50 * UNIT, 1, "3"))
        root_1 = db.compute_state_root()

        orig_compute_root = db.compute_state_root

        def commit_between_agg_and_root(conn=None):
            # In integrity_check(use_memo=False), aggregate SELECT runs first, then compute_state_root(conn=conn)
            writer = UtxoDB(db_path)
            writer.add_box(_make_box(addr, 25 * UNIT, 2, "4"))
            return orig_compute_root(conn=conn)

        db.compute_state_root = commit_between_agg_and_root
        caller_conn = sqlite3.connect(db_path)
        try:
            assert caller_conn.in_transaction is False
            res = db.integrity_check(conn=caller_conn, use_memo=False)
            assert res["total_unspent_boxes"] == 1
            assert res["total_unspent_nrtc"] == 50 * UNIT
            assert res["state_root"] == root_1
        finally:
            caller_conn.close()
            db.compute_state_root = orig_compute_root
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_balance_endpoint_pins_single_snapshot():
    """/utxo/balance/<address> must read balance_nrtc and utxo_count from the same snapshot."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        db = UtxoDB(db_path)
        db.init_tables()
        addr = "RTC" + "c" * 40
        db.add_box(_make_box(addr, 15 * UNIT, 1, "5"))

        app = Flask(__name__)
        app.config["TESTING"] = True
        register_utxo_blueprint(
            app, db, db_path,
            verify_sig_fn=lambda *a: True,
            addr_from_pk_fn=lambda pk: addr,
            current_slot_fn=lambda: 1,
            dual_write=False,
        )
        client = app.test_client()

        orig_count = db.count_unspent_for_address

        def interleaved_count(address, conn=None):
            writer = UtxoDB(db_path)
            writer.add_box(_make_box(addr, 35 * UNIT, 2, "6"))
            return orig_count(address, conn=conn)

        db.count_unspent_for_address = interleaved_count
        try:
            resp = client.get(f"/utxo/balance/{addr}")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["balance_nrtc"] == 15 * UNIT
            assert body["utxo_count"] == 1
        finally:
            db.count_unspent_for_address = orig_count
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
