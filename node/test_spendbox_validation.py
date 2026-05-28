#!/usr/bin/env python3
"""Vulnerability: spend_box() lacks input validation on box_id parameter."""
import sys, os, tempfile, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT

def run():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = UtxoDB(db_path)
    db.init_tables()
    
    # Create a real box
    box = {
        "box_id": "aa" * 32, "value_nrtc": 100 * UNIT,
        "proposition": "0008" + "00" * 20, "owner_address": "alice",
        "creation_height": 1, "transaction_id": "bb" * 32, "output_index": 0,
    }
    db.add_box(box)
    
    # Test: empty string should NOT spend anything
    result = db.spend_box("", "tx1")
    assert result is None, "Empty box_id should return None"
    
    # Test: original box still unspent
    b = db.get_box("aa" * 32)
    assert b is not None and b["spent_at"] is None, "Box should remain unspent"
    
    print("PASS: spend_box handles empty/malformed box_id safely")
    return True

if __name__ == "__main__":
    run()
    sys.exit(0)
