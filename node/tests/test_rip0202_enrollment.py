#!/usr/bin/env python3
"""Unit tests for RIP-202 Phase B1 (rip0202_enrollment). Pure — no node deps."""

import sqlite3
import importlib.util
import os

import pytest

# Load the module under test. It lives at node/rip0202_enrollment.py while this
# test lives at node/tests/ — so search the test dir AND its parent (and handle
# a flat layout). Pick the first candidate that exists.
_here = os.path.dirname(os.path.abspath(__file__))
_candidates = [
    os.path.join(_here, "rip0202_enrollment.py"),          # flat layout
    os.path.join(_here, os.pardir, "rip0202_enrollment.py"),  # node/tests -> node
]
_mod_path = next((p for p in _candidates if os.path.exists(p)), _candidates[-1])
_spec = importlib.util.spec_from_file_location("rip0202_enrollment", _mod_path)
enr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enr)


# --- stub the injected consensus deps (so the test has zero node deps) -------

STUB_WEIGHTS = {
    "PowerPC": {"G4": 2.5, "G5": 2.0, "default": 1.5},
    "ARM": {"aarch64": 0.0005, "default": 0.0005},
    "x86": {"modern": 0.8, "retro": 1.4, "default": 1.0},
}


def stub_derive(device, fingerprint, fingerprint_passed):
    """Deterministic stand-in for derive_verified_device: echoes device family/arch."""
    return {
        "device_family": device.get("family", "x86"),
        "device_arch": device.get("arch", "modern"),
    }


def _db():
    """In-memory sqlite with the epoch_enroll_state schema ensured."""
    conn = sqlite3.connect(":memory:")
    enr.ensure_epoch_enroll_state_schema(conn)
    return conn


def att(miner, family="PowerPC", arch="G4", passed=True, ts=1000, fp=None):
    return {
        "miner": miner,
        "device": {"family": family, "arch": arch},
        "fingerprint": fp or {"simd": "x"},
        "fingerprint_passed": passed,
        "timestamp": ts,
    }


# --- weight derivation -------------------------------------------------------

def test_eligible_weight_units():
    e = enr.derive_block_enrollment([att("alice", "PowerPC", "G4")], stub_derive, STUB_WEIGHTS)
    assert e["alice"] == 2_500_000  # 2.5 * 1e6


def test_failed_fingerprint_excluded():
    e = enr.derive_block_enrollment([att("vm", passed=False)], stub_derive, STUB_WEIGHTS)
    assert e["vm"] == 0
    assert "vm" not in enr.eligible_miners(e)


def test_near_zero_weight_rounds_to_excluded():
    # A weight below 1e-6 (a VM-ish ~1e-9) must round to 0 units -> excluded.
    tbl = {"x86": {"modern": 1e-9, "default": 1e-9}}
    e = enr.derive_block_enrollment([att("ghost", "x86", "modern", passed=True)], stub_derive, tbl)
    assert e["ghost"] == 0
    assert enr.eligible_miners(e) == []


def test_penalty_arch_still_eligible():
    # 0.0005 (ARM NAS penalty) is a real, fingerprint-passed weight -> eligible (500u).
    e = enr.derive_block_enrollment([att("nas", "ARM", "aarch64")], stub_derive, STUB_WEIGHTS)
    assert e["nas"] == 500
    assert "nas" in enr.eligible_miners(e)


def test_default_fallback_weight():
    e = enr.derive_block_enrollment([att("u", "PowerPC", "unknown_arch")], stub_derive, STUB_WEIGHTS)
    assert e["u"] == 1_500_000  # PowerPC default 1.5


# --- determinism (the consensus-critical property) ---------------------------

def test_order_independent():
    a = [att("a", "PowerPC", "G4"), att("b", "PowerPC", "G5"), att("c", "ARM", "aarch64")]
    e1 = enr.derive_block_enrollment(a, stub_derive, STUB_WEIGHTS)
    e2 = enr.derive_block_enrollment(list(reversed(a)), stub_derive, STUB_WEIGHTS)
    assert e1 == e2
    assert enr.enrollment_snapshot_hash(e1) == enr.enrollment_snapshot_hash(e2)


def test_duplicate_miner_resolved_deterministically():
    # Same miner twice (different ts) -> latest timestamp wins, deterministically.
    a = [att("dup", "PowerPC", "G4", ts=100), att("dup", "PowerPC", "G5", ts=200)]
    e = enr.derive_block_enrollment(a, stub_derive, STUB_WEIGHTS)
    assert e["dup"] == 2_000_000  # G5 (ts=200) wins
    # reversed input -> identical result
    assert enr.derive_block_enrollment(list(reversed(a)), stub_derive, STUB_WEIGHTS) == e


def test_snapshot_hash_excludes_zero_weight():
    eligible_only = {"a": 2_500_000}
    with_excluded = {"a": 2_500_000, "vm": 0}
    assert enr.enrollment_snapshot_hash(eligible_only) == enr.enrollment_snapshot_hash(with_excluded)


def test_snapshot_hash_sensitive_to_set():
    h1 = enr.enrollment_snapshot_hash({"a": 2_500_000})
    h2 = enr.enrollment_snapshot_hash({"a": 2_500_000, "b": 2_000_000})
    assert h1 != h2


# --- sealing (INV-2 / INV-3) -------------------------------------------------

def test_seal_writes_state():
    conn = _db()
    e = {"a": 2_500_000}
    assert enr.seal_epoch_enrollment(conn, 42, e, finalized_at=999) is True
    assert enr.is_epoch_finalized(conn, 42) is True
    row = conn.execute("SELECT finalized, snapshot_hash, finalized_at FROM epoch_enroll_state WHERE epoch=42").fetchone()
    assert row[0] == 1 and row[1] == enr.enrollment_snapshot_hash(e) and row[2] == 999


def test_inv2_refuses_empty_snapshot():
    conn = _db()
    assert enr.seal_epoch_enrollment(conn, 7, {}, finalized_at=1) is False
    assert enr.is_epoch_finalized(conn, 7) is False


def test_inv2_refuses_all_excluded_snapshot():
    conn = _db()
    assert enr.seal_epoch_enrollment(conn, 8, {"vm1": 0, "vm2": 0}, finalized_at=1) is False
    assert enr.is_epoch_finalized(conn, 8) is False


def test_is_finalized_missing_table_is_false():
    conn = sqlite3.connect(":memory:")  # no epoch_enroll_state table created
    assert enr.is_epoch_finalized(conn, 1) is False


def test_is_finalized_rejects_non_one():
    conn = sqlite3.connect(":memory:")
    conn.execute(enr.EPOCH_ENROLL_STATE_SCHEMA)
    conn.execute("INSERT INTO epoch_enroll_state (epoch, finalized) VALUES (5, 0)")
    conn.execute("INSERT INTO epoch_enroll_state (epoch, finalized) VALUES (6, -1)")
    assert enr.is_epoch_finalized(conn, 5) is False
    assert enr.is_epoch_finalized(conn, 6) is False


# --- loop-2 hardening: determinism on ts-tie, validation, immutability -------

def test_same_timestamp_tie_is_deterministic():
    # Two DIFFERENT attestations for one miner with the SAME timestamp must
    # resolve identically regardless of input order (content-digest tiebreaker).
    a1 = att("dup", "PowerPC", "G4", ts=500)
    a2 = att("dup", "PowerPC", "G5", ts=500)  # same ts, different arch
    e_fwd = enr.derive_block_enrollment([a1, a2], stub_derive, STUB_WEIGHTS)
    e_rev = enr.derive_block_enrollment([a2, a1], stub_derive, STUB_WEIGHTS)
    assert e_fwd == e_rev
    assert enr.enrollment_snapshot_hash(e_fwd) == enr.enrollment_snapshot_hash(e_rev)


def test_non_mapping_and_minerless_skipped():
    items = [att("a", "PowerPC", "G4"), None, 42, {"device": {}}, {"miner": ""}]
    e = enr.derive_block_enrollment(items, stub_derive, STUB_WEIGHTS)
    assert list(e) == ["a"]


def test_fingerprint_passed_must_be_true():
    for bad in (1, "true", "1", "yes"):
        e = enr.derive_block_enrollment(
            [att("m", "PowerPC", "G4", passed=bad)], stub_derive, STUB_WEIGHTS)
        assert e["m"] == 0  # only literal True counts


def test_malformed_timestamp_does_not_crash():
    a = att("m", "PowerPC", "G4")
    a["timestamp"] = None
    e = enr.derive_block_enrollment([a], stub_derive, STUB_WEIGHTS)
    assert e["m"] == 2_500_000


def test_non_dict_device_fingerprint_failclosed():
    # Malformed device/fingerprint must EXCLUDE (fail closed), not get a default weight.
    a = {"miner": "m", "device": "notadict", "fingerprint": 5, "fingerprint_passed": True, "timestamp": 1}
    e = enr.derive_block_enrollment([a], stub_derive, STUB_WEIGHTS)
    assert e["m"] == 0
    assert enr.eligible_miners(e) == []


def test_missing_device_or_fingerprint_excluded():
    a = {"miner": "m", "fingerprint_passed": True, "timestamp": 1}  # no device/fingerprint
    assert enr.derive_block_enrollment([a], stub_derive, STUB_WEIGHTS)["m"] == 0


def test_inf_weight_excluded_no_crash():
    tbl = {"x86": {"modern": float("inf"), "default": float("inf")}}
    e = enr.derive_block_enrollment([att("a", "x86", "modern")], stub_derive, tbl)
    assert e["a"] == 0  # +inf must not OverflowError, must exclude


def test_nonstring_miner_excluded():
    # miner=1 (int) and miner="1" (str) must NOT collide; non-str miner is skipped.
    items = [att("1", "PowerPC", "G4"), {**att("x", "PowerPC", "G5"), "miner": 1}]
    e = enr.derive_block_enrollment(items, stub_derive, STUB_WEIGHTS)
    assert list(e) == ["1"]  # only the genuine string id survives


def test_raising_derive_fn_contained():
    def boom(device, fingerprint, passed):
        raise RuntimeError("derive blew up")
    a = [att("a", "PowerPC", "G4"), att("b", "PowerPC", "G5")]
    e = enr.derive_block_enrollment(a, boom, STUB_WEIGHTS)
    assert e == {"a": 0, "b": 0}  # contained per-attestation, excluded, no crash


def test_empty_derived_identity_excluded():
    # derive_fn returning {} (no family) must EXCLUDE, not get the 1.0 default.
    e = enr.derive_block_enrollment([att("a", "PowerPC", "G4")], lambda d, f, p: {}, STUB_WEIGHTS)
    assert e["a"] == 0


def test_unknown_family_excluded():
    e = enr.derive_block_enrollment(
        [att("a", "PowerPC", "G4")],
        lambda d, f, p: {"device_family": "Martian", "device_arch": "x"},
        STUB_WEIGHTS,
    )
    assert e["a"] == 0  # family not in table -> fail closed


def test_non_dict_derive_return_excluded():
    e = enr.derive_block_enrollment([att("a", "PowerPC", "G4")], lambda d, f, p: None, STUB_WEIGHTS)
    assert e["a"] == 0


def test_threshold_rejects_bool():
    with pytest.raises(ValueError):
        enr.eligible_miners({"a": 5}, threshold_units=True)


def test_threshold_embedded_in_hash():
    e = {"a": 2_500_000, "b": 500}
    # different thresholds -> different eligible set -> different hash
    h1 = enr.enrollment_snapshot_hash(e, threshold_units=1)
    h2 = enr.enrollment_snapshot_hash(e, threshold_units=1000)
    assert h1 != h2


def test_nan_and_negative_weight_excluded():
    tbl = {"x86": {"modern": float("nan"), "neg": -1.0, "default": float("nan")}}
    e_nan = enr.derive_block_enrollment([att("a", "x86", "modern")], stub_derive, tbl)
    e_neg = enr.derive_block_enrollment([att("b", "x86", "neg")], stub_derive, tbl)
    assert e_nan["a"] == 0 and e_neg["b"] == 0


def test_threshold_must_be_positive():
    e = {"vm": 0}
    for bad in (0, -1, 1.0, None):
        with pytest.raises(ValueError):
            enr.eligible_miners(e, threshold_units=bad)
        with pytest.raises(ValueError):
            enr.seal_epoch_enrollment(_db(), 1, e, 1, threshold_units=bad)


def test_seal_is_immutable():
    conn = _db()
    assert enr.seal_epoch_enrollment(conn, 3, {"a": 2_500_000}, finalized_at=10) is True
    # second seal of the same epoch (different snapshot) must be refused
    assert enr.seal_epoch_enrollment(conn, 3, {"b": 2_000_000}, finalized_at=20) is False
    row = conn.execute("SELECT snapshot_hash, finalized_at FROM epoch_enroll_state WHERE epoch=3").fetchone()
    assert row[0] == enr.enrollment_snapshot_hash({"a": 2_500_000}) and row[1] == 10


def test_seal_rejects_malformed_epoch_or_finalized_at():
    conn = _db()
    assert enr.seal_epoch_enrollment(conn, None, {"a": 2_500_000}, finalized_at=1) is False
    assert enr.seal_epoch_enrollment(conn, 1, {"a": 2_500_000}, finalized_at=None) is False


def test_seal_upgrades_preexisting_finalized_zero():
    # A pre-existing UNsealed (finalized=0) row must be upgradable, not stranded.
    conn = _db()
    conn.execute("INSERT INTO epoch_enroll_state (epoch, finalized) VALUES (9, 0)")
    assert enr.seal_epoch_enrollment(conn, 9, {"a": 2_500_000}, finalized_at=5) is True
    assert enr.is_epoch_finalized(conn, 9) is True


def test_seal_missing_table_fails_closed():
    conn = sqlite3.connect(":memory:")  # schema NOT ensured
    assert enr.seal_epoch_enrollment(conn, 1, {"a": 2_500_000}, finalized_at=1) is False


def test_seal_rejects_float_epoch():
    conn = _db()
    assert enr.seal_epoch_enrollment(conn, 1.9, {"a": 2_500_000}, finalized_at=1) is False
    assert enr.seal_epoch_enrollment(conn, True, {"a": 2_500_000}, finalized_at=1) is False
    assert enr.is_epoch_finalized(conn, 1) is False


def test_empty_inputs():
    assert enr.derive_block_enrollment([], stub_derive, STUB_WEIGHTS) == {}
    assert enr.eligible_miners({}) == []
    assert enr.enrollment_snapshot_hash({}) == enr.enrollment_snapshot_hash({"vm": 0})



def test_inf_timestamp_does_not_crash():
    a = att("m", "PowerPC", "G4")
    a["timestamp"] = float("inf")  # int(inf) raises OverflowError -> must be caught
    e = enr.derive_block_enrollment([a], stub_derive, STUB_WEIGHTS)
    assert e["m"] == 2_500_000


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
