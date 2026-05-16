# SPDX-License-Identifier: MIT
from contextlib import closing
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utxo_db import UtxoDB, UNIT, address_to_proposition, compute_box_id


def _seed_box(db, owner, value_nrtc, index):
    tx_id = f"{index:064x}"
    box_id = compute_box_id(
        value_nrtc,
        address_to_proposition(owner),
        1,
        tx_id,
        0,
    )
    db.add_box(
        {
            "box_id": box_id,
            "value_nrtc": value_nrtc,
            "proposition": address_to_proposition(owner),
            "owner_address": owner,
            "creation_height": 1,
            "transaction_id": tx_id,
            "output_index": 0,
        }
    )
    return box_id


def _tx(tx_id, box_id, fee_nrtc):
    return {
        "tx_id": tx_id,
        "tx_type": "transfer",
        "inputs": [{"box_id": box_id, "spending_proof": "sig"}],
        "outputs": [{"address": f"{tx_id}_receiver", "value_nrtc": UNIT}],
        "fee_nrtc": fee_nrtc,
    }


def _insert_mempool_rows(db, rows):
    now = 1_700_000_000
    expires_at = int(time.time()) + 3600
    with closing(db._conn()) as conn:
        for offset, tx in enumerate(rows):
            submitted_at = tx.get("submitted_at", now + offset)
            conn.execute(
                """INSERT INTO utxo_mempool
                   (tx_id, tx_data_json, fee_nrtc, submitted_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    tx["tx_id"],
                    json.dumps(tx),
                    tx["fee_nrtc"],
                    submitted_at,
                    expires_at,
                ),
            )
        conn.commit()


def test_mempool_candidates_use_deterministic_fee_time_txid_order():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        db = UtxoDB(tmp.name)
        db.init_tables()
        box_a = _seed_box(db, "alice", 2 * UNIT, 1)
        box_b = _seed_box(db, "bob", 2 * UNIT, 2)
        box_c = _seed_box(db, "carol", 2 * UNIT, 3)

        now = int(time.time())
        rows = [
            _tx("tx_b", box_b, 10),
            _tx("tx_high_fee", box_c, 20),
            _tx("tx_a", box_a, 10),
        ]
        for tx in rows:
            tx["submitted_at"] = now
        _insert_mempool_rows(db, rows)

        candidates = db.mempool_get_block_candidates()
        assert [tx["tx_id"] for tx in candidates] == [
            "tx_high_fee",
            "tx_a",
            "tx_b",
        ]
    finally:
        os.unlink(tmp.name)


def test_mempool_candidates_can_use_fifo_policy():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        db = UtxoDB(tmp.name)
        db.init_tables()
        box_a = _seed_box(db, "alice", 2 * UNIT, 1)
        box_b = _seed_box(db, "bob", 2 * UNIT, 2)
        box_c = _seed_box(db, "carol", 2 * UNIT, 3)

        _insert_mempool_rows(
            db,
            [
                {**_tx("tx_middle_fee", box_a, 10), "submitted_at": 30},
                {**_tx("tx_high_fee", box_b, 100), "submitted_at": 40},
                {**_tx("tx_earliest", box_c, 1), "submitted_at": 20},
            ],
        )

        candidates = db.mempool_get_block_candidates(ordering_policy="fifo")
        assert [tx["tx_id"] for tx in candidates] == [
            "tx_earliest",
            "tx_middle_fee",
            "tx_high_fee",
        ]
    finally:
        os.unlink(tmp.name)
