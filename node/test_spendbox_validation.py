#!/usr/bin/env python3
"""Test: spend_box() accepts empty/unvalidated box_id"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB
import hashlib

def test_spendbox_empty_id_safe():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    db = UtxoDB(db_path)
    db.init_tables()
    result = db.spend_box("", "tx_123")
    assert result is None, "Empty box_id should return None, not crash"
    print("PASS: Empty box_id handled safely")
    return True

if __name__ == "__main__":
    test_spendbox_empty_id_safe()
    sys.exit(0)
