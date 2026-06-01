# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from node.ergo_raw_tx import RawTxBuilder, encode_coll_byte, encode_int_reg


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *, get_response=None, post_responses=None):
        self.headers = {}
        self.get_response = get_response
        self.post_responses = list(post_responses or [])

    def get(self, *_args, **_kwargs):
        return self.get_response

    def post(self, *_args, **_kwargs):
        return self.post_responses.pop(0)


def test_encode_coll_byte_handles_empty_and_short_payloads():
    assert encode_coll_byte("") == "0e00"
    assert encode_coll_byte("deadbeef") == "0e04deadbeef"


def test_encode_coll_byte_uses_extended_length_at_128_bytes():
    one_byte_short = "aa" * 127
    boundary_payload = "bb" * 128

    assert encode_coll_byte(one_byte_short) == "0e7f" + one_byte_short
    assert encode_coll_byte(boundary_payload) == "0e8001" + boundary_payload


def test_encode_coll_byte_uses_multi_byte_varint_lengths():
    payload = "cc" * 16_384

    assert encode_coll_byte(payload) == "0e808001" + payload


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


def test_get_unspent_box_ignores_non_list_json():
    builder = RawTxBuilder()
    builder.session = FakeSession(get_response=FakeResponse({"box": {"value": 9_000_000}}))

    assert builder.get_unspent_box() is None


def test_get_unspent_box_skips_malformed_entries():
    valid_box = {"box": {"value": 3_000_000, "boxId": "box-1"}}
    builder = RawTxBuilder()
    builder.session = FakeSession(
        get_response=FakeResponse(["not-a-box", {"box": "not-an-object"}, valid_box])
    )

    assert builder.get_unspent_box() == valid_box


def test_get_current_height_defaults_for_non_object_json():
    builder = RawTxBuilder()
    builder.session = FakeSession(get_response=FakeResponse(["not", "an", "object"]))

    assert builder.get_current_height() == 0


def test_anchor_miners_rejects_non_object_signed_transaction(monkeypatch):
    builder = RawTxBuilder()
    builder.session = FakeSession(post_responses=[FakeResponse(["signed"]), FakeResponse("tx-id")])
    monkeypatch.setattr(
        builder,
        "get_recent_miners",
        lambda limit=10: [{"miner": "alice", "device_arch": "x86", "ts_ok": 1}],
    )
    monkeypatch.setattr(
        builder,
        "get_unspent_box",
        lambda min_value=3000000: {
            "box": {"value": 4_000_000, "boxId": "box-1", "ergoTree": "tree"}
        },
    )
    monkeypatch.setattr(builder, "get_current_height", lambda: 100)

    assert builder.anchor_miners() == {"success": False, "error": "Sign: invalid response"}
