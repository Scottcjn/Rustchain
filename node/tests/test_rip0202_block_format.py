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


def test_same_miner_same_ts_tiebreak_is_total_order():
    """Two records, same miner+ts, different content -> deterministic order."""
    x = b0.build_b0_attestation("dup", DEV, {"k": 1}, True, 5)
    y = b0.build_b0_attestation("dup", DEV, {"k": 2}, True, 5)
    assert b0.canonical_b0_attestations_hash([x, y]) == b0.canonical_b0_attestations_hash([y, x])


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
