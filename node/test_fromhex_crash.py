#!/usr/bin/env python3
"""
Test: bytes.fromhex() crash when given invalid hex input

Vulnerability: compute_box_id() and compute_tx_id() in utxo_db.py
call bytes.fromhex() without try/except ValueError.

Reproduces: UTXO Red Team bounty #2819
Severity: Medium (50 RTC)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import compute_box_id, compute_tx_id

def test_fromhex_invalid_proposition():
    """CRASH: proposition with non-hex chars causes ValueError"""
    try:
        compute_box_id(
            value_nrtc=1000,
            proposition="ZZZZ_INVALID_HEX!!!",  # Invalid hex!
            creation_height=1,
            transaction_id="abc123",
            output_index=0
        )
        # If we reach here, the function survived
        return True
    except ValueError as e:
        print(f"CRASH REPRODUCED: {e}")
        return False  # Crash = vulnerability confirmed

def test_fromhex_invalid_tx_id():
    """CRASH: transaction_id with garbage causes ValueError"""
    try:
        compute_box_id(
            value_nrtc=1000,
            proposition="aabb",
            creation_height=1,
            transaction_id="GGGG_!!invalid!!",  # Invalid hex!
            output_index=0
        )
        return True
    except ValueError as e:
        print(f"CRASH REPRODUCED: {e}")
        return False

if __name__ == "__main__":
    ok1 = test_fromhex_invalid_proposition()
    ok2 = test_fromhex_invalid_tx_id()
    if not ok1 or not ok2:
        print("\nVULNERABILITY CONFIRMED: bytes.fromhex crashes on invalid input")
        sys.exit(1)
    print("\nFunction is safe (fix verified)")
    sys.exit(0)
