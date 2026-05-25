# SPDX-License-Identifier: MIT
"""
Batch PoC: A9 (address_to_proposition no validation), A10 (hex decode error handling),
A11 (_normalize_outputs no MAX_OUTPUTS_BYTES)

A9: address_to_proposition on L106 accepts ANY string — empty, 10MB, null bytes
A10: proposition_to_address on L112 crashes on odd-length/invalid hex via bytes.fromhex()
A11: _normalize_outputs has no MAX_OUTPUTS_BYTES check on tx_data_json serialization
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from utxo_db import address_to_proposition, proposition_to_address, UtxoDB, P2PK_PREFIX


# --- A9: address_to_proposition no address validation ---

def test_a9_empty_address():
    """Empty string accepted with no validation"""
    result = address_to_proposition("")
    prefix_hex = P2PK_PREFIX.hex()
    assert result.startswith(prefix_hex), "Should at least have prefix"
    print("[A9] Empty address → %s... (len=%d)" % (result[:20], len(result)))


def test_a9_10k_address():
    """10KB address accepted with no length check"""
    huge = "A" * 10000
    result = address_to_proposition(huge)
    print("[A9] 10KB address accepted → len=%d bytes" % len(result))


def test_a9_null_bytes():
    """Null bytes in address accepted"""
    result = address_to_proposition("valid\x00address")
    print("[A9] Address with null byte accepted: %s..." % result[:30])


# --- A10: proposition_to_address no hex decode error handling ---

def test_a10_odd_length():
    """Odd-length hex raises ValueError — no graceful handling"""
    try:
        result = proposition_to_address("aabbc")  # 5 chars, odd
        pytest.fail("Odd-length hex accepted: %s (BUG: should fail)" % result)
    except ValueError as e:
        print("[A10] Odd-length hex raises ValueError: %s (graceful? NO — unhandled)" % e)


def test_a10_invalid_hex():
    """Invalid hex chars raise ValueError — caller must catch"""
    try:
        result = proposition_to_address("zzzzz")
        pytest.fail("Invalid hex accepted: %s (BUG)" % result)
    except ValueError as e:
        print("[A10] Invalid hex raises ValueError: %s" % e)


# --- A11: _normalize_outputs no MAX_OUTPUTS_BYTES check ---

def test_a11_unbounded_output_size():
    """_normalize_outputs accepts oversized tx_data_json"""
    # Build an output with huge tokens_json — must go through apply_transaction path
    # which calls _normalize_outputs. Direct access via UtxoDB test.
    db_path = "/tmp/test_a11_outputs.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    db = UtxoDB(db_path)
    db.init_tables()

    from utxo_db import UNIT
    db.add_box(dict(
        box_id="big_output_source", value_nrtc=100 * UNIT,
        proposition="b0b", owner_address="alice",
        creation_height=1, transaction_id="tx_genesis", output_index=0,
    ))

    # Create output with ~100KB tokens_json (way over any reasonable limit)
    huge_tokens = json.dumps({"data": "X" * 100_000})
    huge_outputs = [dict(
        address="bob", value_nrtc=50 * UNIT,
        tokens_json=huge_tokens
    )]

    try:
        applied = db.apply_transaction(dict(
            tx_id="big_output_tx",
            tx_type="transfer",
            inputs=[{"box_id": "big_output_source", "spending_proof": "sig"}],
            outputs=huge_outputs,
            fee_nrtc=0,
            timestamp=1000,
        ), block_height=200)
        if applied:
            print("[A11] Output with ~100KB tokens_json ACCEPTED — no MAX_OUTPUTS_BYTES check")
        else:
            print("[A11] Output rejected by other validation")
    except Exception as e:
        print("[A11] Exception: %s: %s" % (type(e).__name__, e))

    os.remove(db_path)


def test_a11_oversized_register():
    """registers_json with ~50KB content accepted"""
    db_path = "/tmp/test_a11_register.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    db = UtxoDB(db_path)
    db.init_tables()
    from utxo_db import UNIT
    db.add_box(dict(
        box_id="big_reg_source", value_nrtc=100 * UNIT,
        proposition="b0b", owner_address="alice",
        creation_height=1, transaction_id="tx_gen2", output_index=0,
    ))

    huge_register = json.dumps({"R4": "X" * 50000})
    try:
        applied = db.apply_transaction(dict(
            tx_id="big_reg_tx",
            tx_type="transfer",
            inputs=[{"box_id": "big_reg_source", "spending_proof": "sig"}],
            outputs=[dict(address="bob", value_nrtc=50 * UNIT, registers_json=huge_register)],
            fee_nrtc=0,
            timestamp=1000,
        ), block_height=200)
        if applied:
            print("[A11] Output with 50KB registers_json ACCEPTED — no size check")
        else:
            print("[A11] Output rejected")
    except Exception as e:
        print("[A11] Exception: %s: %s" % (type(e).__name__, e))

    os.remove(db_path)


if __name__ == "__main__":
    tests = [
        ("A9 empty address", test_a9_empty_address),
        ("A9 10KB address", test_a9_10k_address),
        ("A9 null bytes", test_a9_null_bytes),
        ("A10 odd-length hex", test_a10_odd_length),
        ("A10 invalid hex", test_a10_invalid_hex),
        ("A11 unbounded output size", test_a11_unbounded_output_size),
        ("A11 oversized register", test_a11_oversized_register),
    ]
    results = []
    for name, fn in tests:
        try:
            fn()
            results.append((name, "PASS"))
        except Exception as e:
            results.append((name, "EXCEPTION: %s" % e))

    print("\n=== RESULTS ===")
    for name, status in results:
        print("  %s\t%s" % (status, name))
    all_pass = all(s == "PASS" for _, s in results)
    print("\nOVERALL: %s" % ("ALL PASS" if all_pass else "SOME FAILED"))
