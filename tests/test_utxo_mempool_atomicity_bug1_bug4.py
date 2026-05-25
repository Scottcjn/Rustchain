"""Tests for UTXO mempool atomicity fixes (BUG-1 + BUG-4 from PR #6146 review)

BUG-1: mempool_remove() must atomically delete from both utxo_mempool
       and utxo_mempool_inputs within a single BEGIN IMMEDIATE transaction.
BUG-4: apply_transaction() must proactively evict mempool txs whose
       inputs (including data_inputs) reference boxes that were just spent.
"""
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
    """Directly insert a mempool tx (for unit-testing the helper)."""
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


# --------- BUG-1: mempool_remove atomicity ---------

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


# --------- BUG-4: stale data_input eviction ---------

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

    def test_apply_transaction_evicts_stale_mempool_tx_via_input(self, db):
        """Regression test: apply_transaction() should evict mempool txs
        whose claimed inputs reference a box that was just spent.
        Uses real mempool_add() + apply_transaction() flow."""
        # First, use apply_transaction to create a real UTXO  that we can spend
        result = db.apply_transaction({
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": "addr1", "value_nrtc": 10000}],
            "fee_nrtc": 0,
            "data_inputs": [],
            "_allow_minting": True,
        }, block_height=1)
        assert result, "minting should succeed"

        # Find the actual box_id created by the mint
        conn = db._conn()
        try:
            row = conn.execute(
                "SELECT box_id FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL ORDER BY box_id ASC LIMIT 1",
                ("addr1",),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "should have a box for addr1"
        box_w = row["box_id"]

        # Add a mempool tx that claims this box as input
        ok = db.mempool_add({
            "tx_id": "tx_m",
            "tx_type": "transfer",
            "inputs": [{"box_id": box_w, "spending_proof": "proof_w"}],
            "outputs": [{"address": "addr3", "value_nrtc": 9900}],
            "fee_nrtc": 100,
        })
        assert ok, "mempool_add should succeed"

        # Verify tx_m is in the mempool
        conn = db._conn()
        try:
            mp_row = conn.execute("SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_m",)).fetchone()
        finally:
            conn.close()
        assert mp_row is not None, "tx_m should be in mempool before spend"

        # Spend box_w via apply_transaction
        result = db.apply_transaction({
            "tx_type": "transfer",
            "inputs": [{"box_id": box_w, "spending_proof": "proof_spend"}],
            "outputs": [{"address": "addr_new", "value_nrtc": 9900}],
            "fee_nrtc": 100,
            "data_inputs": [],
        }, block_height=2)
        assert result is True, "apply_transaction should succeed"

        # BUG-4 regression: tx_m should have been evicted
        conn = db._conn()
        try:
            mp_row = conn.execute("SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_m",)).fetchone()
            inp_row = conn.execute("SELECT tx_id FROM utxo_mempool_inputs WHERE tx_id=?", ("tx_m",)).fetchone()
        finally:
            conn.close()
        assert mp_row is None, "BUG-4: stale mempool tx should be evicted after its input is spent"
        assert inp_row is None, "BUG-4: stale mempool input rows should be cleaned up"

    def test_apply_transaction_preserves_unrelated_mempool_txs(self, db):
        """Spending a box should only evict mempool txs that depend on it,
        not unrelated mempool txs."""
        # Create two boxes via minting
        db.apply_transaction({
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": "addr1", "value_nrtc": 10000}],
            "fee_nrtc": 0,
            "data_inputs": [],
            "_allow_minting": True,
        }, block_height=1)
        db.apply_transaction({
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": "addr2", "value_nrtc": 20000}],
            "fee_nrtc": 0,
            "data_inputs": [],
            "_allow_minting": True,
        }, block_height=1)

        # Find actual box_ids
        conn = db._conn()
        try:
            box_a_row = conn.execute("SELECT box_id FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL ORDER BY box_id ASC LIMIT 1", ("addr1",)).fetchone()
            box_b_row = conn.execute("SELECT box_id FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL ORDER BY box_id ASC LIMIT 1", ("addr2",)).fetchone()
        finally:
            conn.close()
        box_a = box_a_row["box_id"]
        box_b = box_b_row["box_id"]

        # tx_m2 claims box_b (unrelated to the spend of box_a)
        ok = db.mempool_add({
            "tx_id": "tx_m2",
            "tx_type": "transfer",
            "inputs": [{"box_id": box_b, "spending_proof": "p2"}],
            "outputs": [{"address": "addr5", "value_nrtc": 19900}],
            "fee_nrtc": 100,
        })
        assert ok

        # Spend box_a (not box_b)
        result = db.apply_transaction({
            "tx_type": "transfer",
            "inputs": [{"box_id": box_a, "spending_proof": "p3"}],
            "outputs": [{"address": "addr_new", "value_nrtc": 9900}],
            "fee_nrtc": 100,
            "data_inputs": [],
        }, block_height=2)
        assert result

        conn = db._conn()
        try:
            m2 = conn.execute("SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_m2",)).fetchone()
        finally:
            conn.close()

        assert m2 is not None, "tx_m2 should remain (its input box_b was not spent)"