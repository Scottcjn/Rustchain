# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from node.ergo_raw_tx import RawTxBuilder, encode_coll_byte, encode_int_reg


def test_encode_coll_byte_handles_empty_and_short_payloads():
    assert encode_coll_byte("") == "0e00"
    assert encode_coll_byte("deadbeef") == "0e04deadbeef"


def test_encode_coll_byte_uses_extended_length_at_128_bytes():
    one_byte_short = "aa" * 127
    boundary_payload = "bb" * 128

    assert encode_coll_byte(one_byte_short) == "0e7f" + one_byte_short
    assert encode_coll_byte(boundary_payload) == "0e8001" + boundary_payload


def test_encode_coll_byte_rejects_odd_length_hex_strings():
    with pytest.raises(ValueError):
        encode_coll_byte("abc")


def test_encode_int_reg_zigzags_signed_values():
    assert encode_int_reg(0) == "0400"
    assert encode_int_reg(1) == "0402"
    assert encode_int_reg(-1) == "0401"
    assert encode_int_reg(-2) == "0403"


def test_encode_int_reg_uses_varint_encoding_for_larger_values():
    assert encode_int_reg(63) == "047e"
    assert encode_int_reg(64) == "048001"


def test_encode_int_reg_handles_multi_byte_varint_values():
    assert encode_int_reg(2**21) == "0480808002"


def test_compute_commitment_is_stable_for_equivalent_miner_dicts():
    builder = RawTxBuilder()
    miners = [
        {"miner": "alice", "device_arch": "x86", "ts_ok": 100},
        {"miner": "bob", "device_arch": "arm", "ts_ok": 95},
    ]
    same_miners_with_reordered_keys = [
        {"ts_ok": 100, "device_arch": "x86", "miner": "alice"},
        {"ts_ok": 95, "miner": "bob", "device_arch": "arm"},
    ]
    different_miners = [
        {"miner": "alice", "device_arch": "x86", "ts_ok": 100},
        {"miner": "carol", "device_arch": "arm", "ts_ok": 95},
    ]

    commitment = builder.compute_commitment(miners)

    assert len(commitment) == 64
    assert commitment == builder.compute_commitment(same_miners_with_reordered_keys)
    assert commitment != builder.compute_commitment(different_miners)


def test_compute_commitment_handles_empty_miner_list():
    builder = RawTxBuilder()

    commitment = builder.compute_commitment([])

    assert len(commitment) == 64
    assert commitment == builder.compute_commitment([])
