#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-202 B0 canonical block-format contract — unit tests."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (os.path.dirname(_HERE), _HERE):  # ../ (repo node/) first, then . (flat staging)
    if os.path.exists(os.path.join(_d, "rip0202_block_format.py")):
        sys.path.insert(0, _d)
        break
import rip0202_block_format as b0  # noqa: E402


# ---- record construction / fail-closed validation -------------------------
DEV = {"machine": "x86_64", "cpu_brand": "Intel i7"}
FP = {"simd_identity": {"data": {}}, "clock_drift": {"data": {"cv": 0.0931}}}


def test_build_valid_record():
    r = b0.build_b0_attestation("miner-a", DEV, FP, True, 1000)
    assert set(r) == set(b0.B0_ATTESTATION_FIELDS)
    assert r["miner"] == "miner-a" and r["fingerprint_passed"] is True


@pytest.mark.parametrize("kwargs", [
    {"miner": ""}, {"miner": 1}, {"device": "x"}, {"fingerprint": None},
    {"fingerprint_passed": 1}, {"fingerprint_passed": "true"},
    {"timestamp": "10"}, {"timestamp": True},
])
def test_build_rejects_malformed(kwargs):
    base = dict(miner="m", device=DEV, fingerprint=FP, fingerprint_passed=True, timestamp=1)
    base.update(kwargs)
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation(**base)


def test_build_rejects_non_finite_float():
    for bad in ({"x": float("nan")}, {"nested": {"y": float("inf")}}, {"arr": [1.0, float("-inf")]}):
        with pytest.raises(b0.B0FormatError):
            b0.build_b0_attestation("m", DEV, bad, True, 1)


# ---- canonical hash determinism -------------------------------------------
def _att(miner, ts=1000, passed=True, fp=None):
    return b0.build_b0_attestation(miner, DEV, fp or FP, passed, ts)


def test_empty_hash_sentinel():
    assert b0.canonical_b0_attestations_hash([]) == "0" * 64


def test_hash_deterministic_and_order_independent():
    a, b, c = _att("c", 3), _att("a", 1), _att("b", 2)
    h1 = b0.canonical_b0_attestations_hash([a, b, c])
    h2 = b0.canonical_b0_attestations_hash([c, b, a])  # shuffled
    h3 = b0.canonical_b0_attestations_hash([b, c, a])
    assert h1 == h2 == h3 and len(h1) == 64


def test_hash_rejects_duplicate_miner():
    """One miner, one record per block (loop-3): a dup miner is rejected, not
    silently resolved — cross-block dups are B2's job (max src_height)."""
    x = b0.build_b0_attestation("dup", DEV, {"k": 1}, True, 5)
    y = b0.build_b0_attestation("dup", DEV, {"k": 2}, True, 5)
    with pytest.raises(b0.B0FormatError):
        b0.canonical_b0_attestations_hash([x, y])


def test_hash_ignores_incidental_extra_keys():
    a = _att("m", 1)
    a_extra = dict(a)
    a_extra["_debug"] = "ignore me"  # not a pinned field
    assert b0.canonical_b0_attestations_hash([a]) == b0.canonical_b0_attestations_hash([a_extra])


def test_float_round_trip_stable_hash():
    """The cross-arch claim: a committed float hashes identically after a
    JSON deserialise/serialise round-trip (CPython short-repr is stable)."""
    fp = {"clock_drift": {"data": {"cv": 0.09313725490196078, "lat": [1.5, 2.25, 0.125]}}}
    a = b0.build_b0_attestation("m", DEV, fp, True, 1)
    a_round = json.loads(json.dumps(a))  # simulate commit -> deserialize on apply
    assert b0.canonical_b0_attestations_hash([a]) == b0.canonical_b0_attestations_hash([a_round])


def test_passed_flag_changes_hash():
    assert b0.canonical_b0_attestations_hash([_att("m", 1, passed=True)]) != \
           b0.canonical_b0_attestations_hash([_att("m", 1, passed=False)])


# ---- slot -> epoch --------------------------------------------------------
def test_slot_to_epoch():
    assert b0.slot_to_epoch(0) == 0
    assert b0.slot_to_epoch(143) == 0
    assert b0.slot_to_epoch(144) == 1
    assert b0.slot_to_epoch(289) == 2


@pytest.mark.parametrize("bad", [-1, True, "5", 1.0, None])
def test_slot_to_epoch_rejects_bad(bad):
    with pytest.raises(b0.B0FormatError):
        b0.slot_to_epoch(bad)


def test_block_epoch_reads_committed_slot():
    assert b0.block_epoch({"height": 200, "slot": 288}) == 2


def test_block_epoch_fails_closed_without_slot():
    """No wall-clock fallback: a header without a committed slot must raise."""
    for hdr in ({"height": 200}, {"slot": "288"}, {"slot": True}):
        with pytest.raises(b0.B0FormatError):
            b0.block_epoch(hdr)


def test_block_version_constant():
    assert b0.B0_BLOCK_VERSION == 2


# ---- tri-brain fixes: JSON-safety, hash validation, blocks_per_epoch guard ----
def test_build_rejects_non_string_mapping_key():
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", {1: "x"}, FP, True, 1)        # non-str key in device
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", DEV, {"a": {2: "y"}}, True, 1)  # nested non-str key


@pytest.mark.parametrize("bad", [("t",), {1, 2}, b"bytes"])
def test_build_rejects_non_json_safe_types(bad):
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", {"k": bad}, FP, True, 1)


def test_hash_rejects_malformed_record():
    good = _att("m", 1)
    for bad in ({"miner": "m"},                       # missing device/fingerprint/...
                {"miner": "", "device": {}, "fingerprint": {}, "fingerprint_passed": True, "timestamp": 1},
                {"miner": "m", "device": "x", "fingerprint": {}, "fingerprint_passed": True, "timestamp": 1}):
        with pytest.raises(b0.B0FormatError):
            b0.canonical_b0_attestations_hash([good, bad])


def test_assert_blocks_per_epoch():
    b0.assert_blocks_per_epoch(b0.BLOCKS_PER_EPOCH)   # match -> no raise
    with pytest.raises(b0.B0FormatError):
        b0.assert_blocks_per_epoch(b0.BLOCKS_PER_EPOCH + 1)


@pytest.mark.parametrize("bad", [True, 1.0, 0, -5])
def test_slot_to_epoch_rejects_bad_blocks_per_epoch(bad):
    with pytest.raises(b0.B0FormatError):
        b0.slot_to_epoch(144, blocks_per_epoch=bad)


def test_hash_rejects_non_mapping_items():
    """Loop-2: a non-dict in the list raises B0FormatError (documented contract),
    not a raw AttributeError/TypeError."""
    good = _att("m", 1)
    for bad in (None, "str", 5, ["x"]):
        with pytest.raises(b0.B0FormatError):
            b0.canonical_b0_attestations_hash([good, bad])


# ---- tri-brain loop-3 fixes: size/depth caps, concrete-dict, dup-miner ----
def test_build_rejects_oversized_evidence():
    big = {"blob": "x" * (b0.MAX_EVIDENCE_FIELD_BYTES + 10)}
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", big, FP, True, 1)


def test_build_rejects_excessive_nesting_depth():
    d = cur = {}
    for _ in range(b0.MAX_EVIDENCE_DEPTH + 5):
        cur["n"] = {}
        cur = cur["n"]
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", {"deep": d}, FP, True, 1)


def test_build_rejects_non_dict_mapping():
    import types
    proxy = types.MappingProxyType({"k": 1})  # a Mapping, NOT a dict
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", {"nested": proxy}, FP, True, 1)


def test_build_rejects_dict_and_list_subclasses():
    """Exact-type check: a dict/list SUBCLASS (isinstance-true but not concrete)
    is rejected, so it can't pass validation and then yield different data via an
    overridden __deepcopy__/__iter__ (validate-then-substitute bypass)."""
    class SneakyDict(dict):
        pass

    class SneakyList(list):
        pass

    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", {"nested": SneakyDict({"k": 1})}, FP, True, 1)
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("m", {"arr": SneakyList([1, 2])}, FP, True, 1)


# ---- tri-brain loop-4 fixes: deep-copy (TOCTOU) + miner-id length ----
def test_build_deepcopies_evidence_no_aliasing():
    """Loop-4: mutating the caller's nested evidence after build must NOT change
    the built record (no shallow-copy aliasing / validate->hash TOCTOU)."""
    dev = {"nested": {"k": "orig"}, "arr": [1, 2]}
    rec = b0.build_b0_attestation("m", dev, FP, True, 1)
    dev["nested"]["k"] = "mutated"
    dev["arr"].append(999)
    assert rec["device"]["nested"]["k"] == "orig"
    assert rec["device"]["arr"] == [1, 2]


def test_build_rejects_overlong_miner_id():
    with pytest.raises(b0.B0FormatError):
        b0.build_b0_attestation("x" * (b0.MAX_MINER_ID_LEN + 1), DEV, FP, True, 1)
    # at-limit is accepted
    assert b0.build_b0_attestation("x" * b0.MAX_MINER_ID_LEN, DEV, FP, True, 1)["miner"]
