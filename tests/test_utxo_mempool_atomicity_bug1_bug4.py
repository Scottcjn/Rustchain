"""Tests for UTXO mempool atomicity fixes (BUG-1 + BUG-4 from PR #6146 review)"""
import json
import time
import pytest
from node.utxo_db import UtxoDB

@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_utxo.db")
    instance = UtxoDB(db_path)
    instance.init_tables()
    return instance

def _add_box(db, box_id, value, addr="addr1", height=1, tx_idx=0):
    db.add_box({
        "box_id": box_id,
        "value_nrtc": value,
        "proposition": addr,
        "owner_address": addr,
        "creation_height": height,
        "transaction_id": f"tx_genesis_{box_id}",
        "output_index": tx_idx,
    })

def _add_mempool_tx(db, tx_id, box_ids, fee=100):
    now = int(time.time())
    conn = db._conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, expires_at, submitted_at) VALUES (?,?,?,?,?)",
            (tx_id, json.dumps({"tx_id": tx_id}), fee, now + 3600, now),
        )
        for bid in box_ids:
            conn.execute(
                "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?,?)",
                (bid, tx_id),
            )
        conn.commit()
    finally:
        conn.close()

class TestMempoolRemoveAtomicityBug1:
    def test_mempool_remove_deletes_both_tables(self, db):
        _add_box(db, "box1", 1000)
        _add_mempool_tx(db, "tx1", ["box1"])
        db.mempool_remove("tx1")
        conn = db._conn()
        try:
            p = conn.execute("SELECT * FROM utxo_mempool WHERE tx_id=?", ("tx1",)).fetchone()
            i = conn.execute("SELECT * FROM utxo_mempool_inputs WHERE tx_id=?", ("tx1",)).fetchone()
        finally:
            conn.close()
        assert p is None
        assert i is None

    def test_mempool_remove_nonexistent_is_safe(self, db):
        db.mempool_remove("nonexistent_tx")

class TestStaleDataInputEvictionBug4:
    def test_evict_stale_data_input_txs(self, db):
        _add_box(db, "box_a", 1000)
        _add_box(db, "box_b", 2000, "addr2")
        _add_mempool_tx(db, "tx_stale", ["box_a", "box_b"], 50)
        evicted = db._evict_stale_data_input_txs(["box_b"])
        assert evicted == 1
        conn = db._conn()
        try:
            p = conn.execute("SELECT * FROM utxo_mempool WHERE tx_id=?", ("tx_stale",)).fetchone()
            rows = conn.execute("SELECT * FROM utxo_mempool_inputs WHERE tx_id=?", ("tx_stale",)).fetchall()
        finally:
            conn.close()
        assert p is None
        assert len(rows) == 0

    def test_evict_no_stale_when_not_in_mempool(self, db):
        assert db._evict_stale_data_input_txs(["nope"]) == 0

    def test_evict_empty_list(self, db):
        assert db._evict_stale_data_input_txs([]) == 0
