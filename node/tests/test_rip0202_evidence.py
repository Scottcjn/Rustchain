#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-202 B0-persist attestation-evidence capture — unit tests."""
import os
import sqlite3
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (os.path.dirname(_HERE), _HERE):  # ../ (repo node/) first, then . (flat)
    if os.path.exists(os.path.join(_d, "rip0202_evidence.py")):
        sys.path.insert(0, _d)
        break
import rip0202_evidence as ev  # noqa: E402
import rip0202_block_format as b0  # noqa: E402

DEV = {"machine": "x86_64", "cpu_brand": "Intel i7"}
FP = {"clock_drift": {"data": {"cv": 0.0931}}, "simd_identity": {"data": {}}}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ev.ensure_attestation_evidence_schema(c)
    yield c
    c.close()


def test_schema_idempotent(conn):
    ev.ensure_attestation_evidence_schema(conn)  # second call is a no-op
    cols = [r[1] for r in conn.execute("PRAGMA table_info(attestation_evidence)")]
    assert cols == ["miner", "device_json", "fingerprint_json", "fingerprint_passed", "ts"]


def test_record_and_load_round_trip(conn):
    ev.record_attestation_evidence(conn, "miner-a", DEV, FP, True, 1000)
    recs = ev.load_committed_attestations(conn)
    assert recs == [b0.build_b0_attestation("miner-a", DEV, FP, True, 1000)]


def test_record_fail_closed_on_malformed(conn):
    with pytest.raises(b0.B0FormatError):
        ev.record_attestation_evidence(conn, "", DEV, FP, True, 1)          # empty miner
    with pytest.raises(b0.B0FormatError):
        ev.record_attestation_evidence(conn, "m", {"x": float("nan")}, FP, True, 1)  # non-finite
    assert conn.execute("SELECT COUNT(*) FROM attestation_evidence").fetchone()[0] == 0


def test_upsert_latest_wins(conn):
    ev.record_attestation_evidence(conn, "dup", DEV, {"k": 1}, True, 100)
    ev.record_attestation_evidence(conn, "dup", DEV, {"k": 2}, False, 200)
    rows = conn.execute("SELECT COUNT(*) FROM attestation_evidence").fetchone()[0]
    assert rows == 1
    rec = ev.load_committed_attestations(conn)[0]
    assert rec["fingerprint"] == {"k": 2} and rec["fingerprint_passed"] is False and rec["timestamp"] == 200


def test_load_skips_corrupt_rows(conn):
    ev.record_attestation_evidence(conn, "good", DEV, FP, True, 10)
    # inject a corrupt row directly (simulates legacy/garbage data)
    conn.execute(
        "INSERT INTO attestation_evidence VALUES (?,?,?,?,?)",
        ("bad", "{not json", "{}", 1, 20),
    )
    recs = ev.load_committed_attestations(conn)
    assert [r["miner"] for r in recs] == ["good"]  # corrupt skipped, no crash


def test_load_min_ts_filter(conn):
    ev.record_attestation_evidence(conn, "old", DEV, FP, True, 100)
    ev.record_attestation_evidence(conn, "new", DEV, FP, True, 500)
    recs = ev.load_committed_attestations(conn, min_ts=300)
    assert [r["miner"] for r in recs] == ["new"]


def test_loaded_records_hash_equals_original(conn):
    """Evidence round-trip preserves the B0 attestations hash (storage is
    byte-stable through canonical JSON) — ties B0-persist to the B0 contract."""
    originals = [
        b0.build_b0_attestation("a", DEV, FP, True, 1),
        b0.build_b0_attestation("b", DEV, {"lat": [1.5, 0.125]}, True, 2),
    ]
    for r in originals:
        ev.record_attestation_evidence(conn, r["miner"], r["device"], r["fingerprint"],
                                       r["fingerprint_passed"], r["timestamp"])
    loaded = ev.load_committed_attestations(conn)
    assert b0.canonical_b0_attestations_hash(loaded) == b0.canonical_b0_attestations_hash(originals)


# ---- tri-brain fixes: ts-monotonic upsert + strict load validation ----
def test_older_attestation_does_not_clobber_newer(conn):
    ev.record_attestation_evidence(conn, "m", DEV, {"v": "new"}, True, 200)
    ev.record_attestation_evidence(conn, "m", DEV, {"v": "old"}, True, 100)  # older ts
    rec = ev.load_committed_attestations(conn)[0]
    assert rec["fingerprint"] == {"v": "new"} and rec["timestamp"] == 200


def test_equal_ts_overwrites(conn):
    ev.record_attestation_evidence(conn, "m", DEV, {"v": 1}, True, 100)
    ev.record_attestation_evidence(conn, "m", DEV, {"v": 2}, True, 100)  # same ts -> replace
    assert ev.load_committed_attestations(conn)[0]["fingerprint"] == {"v": 2}


def test_load_skips_out_of_range_passed_and_float_ts(conn):
    ev.record_attestation_evidence(conn, "good", DEV, FP, True, 10)
    conn.execute("INSERT INTO attestation_evidence VALUES (?,?,?,?,?)", ("bad_passed", "{}", "{}", 2, 20))
    conn.execute("INSERT INTO attestation_evidence VALUES (?,?,?,?,?)", ("bad_ts", "{}", "{}", 1, 1.9))
    assert [r["miner"] for r in ev.load_committed_attestations(conn)] == ["good"]
