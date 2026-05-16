# SPDX-License-Identifier: MIT
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
        with db._conn() as conn:
            for tx in rows:
                conn.execute(
                    """INSERT INTO utxo_mempool
                       (tx_id, tx_data_json, fee_nrtc, submitted_at, expires_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        tx["tx_id"],
                        json.dumps(tx),
                        tx["fee_nrtc"],
                        now,
                        now + 3600,
                    ),
                )
            conn.commit()

        candidates = db.mempool_get_block_candidates()
        assert [tx["tx_id"] for tx in candidates] == [
            "tx_high_fee",
            "tx_a",
            "tx_b",
        ]
    finally:
        os.unlink(tmp.name)
