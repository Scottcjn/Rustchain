# SPDX-License-Identifier: MIT
import pytest

from node.utxo_db import (
    SQLITE_INT64_MAX,
    UtxoDB,
    address_to_proposition,
    compute_box_id,
)


SEED_TX_ID = "00" * 32
OWNER = "RTC_TEST"
VALUE_NRTC = 1_000_000_000


def _seed_box(db: UtxoDB):
    proposition = address_to_proposition(OWNER)
    box_id = compute_box_id(VALUE_NRTC, proposition, 0, SEED_TX_ID, 0)
    conn = db._conn()
    try:
        conn.execute(
            """INSERT INTO utxo_boxes
               (box_id, value_nrtc, proposition, owner_address,
                creation_height, transaction_id, output_index,
                created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (box_id, VALUE_NRTC, proposition, OWNER, 0, SEED_TX_ID, 0, 1234567890),
        )
        conn.commit()
    finally:
        conn.close()
    return box_id


def _transfer_tx(box_id, timestamp):
    return {
        "tx_type": "transfer",
        "inputs": [{"box_id": box_id, "spending_proof": "test"}],
        "outputs": [{"address": "RTC_DEST", "value_nrtc": VALUE_NRTC}],
        "fee_nrtc": 0,
        "timestamp": timestamp,
    }


@pytest.mark.parametrize("bad_timestamp", [10**20, -1, "123", True])
def test_apply_transaction_rejects_invalid_timestamps_without_sqlite_overflow(
    tmp_path, bad_timestamp
):
    db = UtxoDB(str(tmp_path / "utxo.sqlite3"))
    db.init_tables()
    box_id = _seed_box(db)

    assert db.apply_transaction(_transfer_tx(box_id, bad_timestamp), block_height=1) is False
    assert db.get_box(box_id)["spent_at"] is None


def test_apply_transaction_accepts_sqlite_int64_timestamp_boundary(tmp_path):
    db = UtxoDB(str(tmp_path / "utxo.sqlite3"))
    db.init_tables()
    box_id = _seed_box(db)

    assert db.apply_transaction(_transfer_tx(box_id, SQLITE_INT64_MAX), block_height=1)
