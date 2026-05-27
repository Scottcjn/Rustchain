#!/usr/bin/env python3
"""
Test: mempool_add() timestamp validation skips ROLLBACK

The _is_nonnegative_int64(timestamp) check returns False
without calling conn.execute("ROLLBACK"), leaving the 
BEGIN IMMEDIATE transaction open.
"""
import sys, os, sqlite3, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT

def test_mempool_rollback_missing():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = UtxoDB(db_path)
    db.init_tables()
    # Create a UTXO first
    box = {
        "box_id": "aa" * 32,
        "value_nrtc": 100 * UNIT,
        "proposition": "00" + "08" + "00" * 20,
        "owner_address": "test",
        "creation_height": 1,
        "transaction_id": "bb" * 32,
        "output_index": 0,
    }
    db.add_box(box)
    # Submit with invalid timestamp -> returns False but db stays locked
    result = db.mempool_add({
        "tx_id": "test_tx",
        "inputs": [{"box_id": "aa" * 32}],
        "outputs": [{"address": "bob", "value_nrtc": 10 * UNIT}],
        "timestamp": -1,  # INVALID: negative timestamp
    })
    assert result == False, "Should reject negative timestamp"
    # If we can still query, the lock was released
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM utxo_boxes").fetchone()[0]
    conn.close()
    assert count > 0, "Database should be accessible after failed mempool_add"
    print(f"PASS: {count} boxes accessible (no lock leak)")
    return True

if __name__ == "__main__":
    test_mempool_rollback_missing()
    sys.exit(0)
