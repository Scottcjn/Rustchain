#!/usr/bin/env python3
"""
Regression test: compute_entropy_profile_hash must read the SAME keys that the
real fingerprint producer (node/fingerprint_checks.py) actually emits.

Issue: the entropy profile hash feeds the live anti-Sybil gate
(check_entropy_collision, called from the attestation path in
rustchain_v2_integrated_v2.2.1_rip200.py). On main the consumer reads key names
that the producer never emits:

    consumer key        producer (fingerprint_checks.py) actually emits
    ------------        -----------------------------------------------
    thermal 'ratio'  -> 'drift_ratio'
    cache   'L1'     -> 'l1_ns' / hierarchy ratios 'l2_l1_ratio','l3_l2_ratio'
    cache   'L2'     -> 'l2_ns'
    cache   'cache_hash' -> (no such field)
    jitter  'cv'     -> (no such field; emits int/fp/branch avg_ns + stdevs)
    jitter  'jitter_map' -> (no such field)
    clock   'drift_hash' -> (no such field; emits cv/stdev_ns/drift_stdev)

Effect on REAL hardware: thermal, cache and jitter collapse to constants, so the
entropy_profile_hash is derived almost entirely from clock_cv + simd. Two
fingerprints that differ ONLY in their thermal/cache/jitter entropy (i.e.
genuinely different hardware timing profiles) hash IDENTICALLY -> the anti-Sybil
collision check fires against honest, distinct miners while ignoring 3 of its 5
advertised entropy dimensions.

These tests build fingerprints in the REAL producer shape and fail on main.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = PROJECT_ROOT / "node"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(NODE_PATH))

TEST_DB_PATH = str(PROJECT_ROOT / "tests" / ".test_entropy_profile_schema.db")
os.environ["DB_PATH"] = TEST_DB_PATH
os.environ["RUSTCHAIN_DB_PATH"] = TEST_DB_PATH

from hardware_fingerprint_replay import compute_entropy_profile_hash


def _real_producer_fingerprint(
    *, drift_ratio, l2_l1_ratio, l3_l2_ratio, int_avg_ns, fp_mult=1.7, branch_mult=2.3,
    cv=0.031, simd_tag="avx2"
):
    """Fingerprint shaped exactly like node/fingerprint_checks.py emits."""
    return {
        "checks": {
            "clock_drift": {
                "passed": True,
                "data": {
                    "mean_ns": 12000,
                    "stdev_ns": 372,
                    "cv": cv,
                    "drift_stdev": 41,
                },
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "l1_ns": 5.1,
                    "l2_ns": 14.2,
                    "l3_ns": 44.7,
                    "l2_l1_ratio": l2_l1_ratio,
                    "l3_l2_ratio": l3_l2_ratio,
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {
                    "cold_avg_ns": 8100,
                    "hot_avg_ns": 8900,
                    "cold_stdev": 55,
                    "hot_stdev": 61,
                    "drift_ratio": drift_ratio,
                },
            },
            "instruction_jitter": {
                "passed": True,
                "data": {
                    "int_avg_ns": int_avg_ns,
                    "fp_avg_ns": int(int_avg_ns * fp_mult),
                    "branch_avg_ns": int(int_avg_ns * branch_mult),
                    "int_stdev": 40,
                    "fp_stdev": 70,
                    "branch_stdev": 90,
                },
            },
            "simd_identity": {
                "passed": True,
                "data": {"isa": simd_tag, "vector_width": 256},
            },
        }
    }


def test_thermal_entropy_is_read_from_real_producer_key():
    """Two rigs identical except for thermal drift_ratio must hash differently."""
    a = _real_producer_fingerprint(
        drift_ratio=1.05, l2_l1_ratio=2.78, l3_l2_ratio=3.15, int_avg_ns=9100
    )
    b = _real_producer_fingerprint(
        drift_ratio=1.42, l2_l1_ratio=2.78, l3_l2_ratio=3.15, int_avg_ns=9100
    )
    assert compute_entropy_profile_hash(a) != compute_entropy_profile_hash(b), (
        "thermal drift_ratio does not influence the entropy profile hash "
        "(consumer reads 'ratio', producer emits 'drift_ratio')"
    )


def test_cache_entropy_is_read_from_real_producer_key():
    """Two rigs identical except for cache hierarchy ratios must hash differently."""
    a = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.40, l3_l2_ratio=3.05, int_avg_ns=9100
    )
    b = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=3.90, l3_l2_ratio=4.80, int_avg_ns=9100
    )
    assert compute_entropy_profile_hash(a) != compute_entropy_profile_hash(b), (
        "cache hierarchy ratios do not influence the entropy profile hash "
        "(consumer reads 'L1'/'L2'/'cache_hash', producer emits 'l*_ns'/'l2_l1_ratio')"
    )


def test_jitter_entropy_is_read_from_real_producer_key():
    """Two rigs with different micro-arch jitter ratios must hash differently."""
    a = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.78, l3_l2_ratio=3.15,
        int_avg_ns=9100, fp_mult=1.7, branch_mult=2.3,
    )
    b = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.78, l3_l2_ratio=3.15,
        int_avg_ns=9100, fp_mult=2.4, branch_mult=3.6,
    )
    assert compute_entropy_profile_hash(a) != compute_entropy_profile_hash(b), (
        "instruction jitter does not influence the entropy profile hash "
        "(consumer reads 'cv'/'jitter_map', producer emits '*_avg_ns'/'*_stdev')"
    )


def test_jitter_uses_load_robust_ratio_not_absolute_ns():
    """Same relative jitter but different absolute load must NOT change the hash.

    Raw per-op ns scale with machine load; only the relative timing between op
    classes is a stable hardware characteristic, so it alone must drive the hash.
    """
    light = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.78, l3_l2_ratio=3.15,
        int_avg_ns=8200, fp_mult=1.7, branch_mult=2.3,
    )
    loaded = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.78, l3_l2_ratio=3.15,
        int_avg_ns=15900, fp_mult=1.7, branch_mult=2.3,
    )
    assert compute_entropy_profile_hash(light) == compute_entropy_profile_hash(loaded)


def test_distinct_hardware_not_a_false_collision():
    """Full sanity: two clearly different rigs must not share an entropy hash."""
    rig1 = _real_producer_fingerprint(
        drift_ratio=1.05, l2_l1_ratio=2.40, l3_l2_ratio=3.05,
        int_avg_ns=8200, cv=0.031, simd_tag="avx2",
    )
    rig2 = _real_producer_fingerprint(
        drift_ratio=1.42, l2_l1_ratio=3.90, l3_l2_ratio=4.80,
        int_avg_ns=15900, cv=0.031, simd_tag="avx2",
    )
    assert compute_entropy_profile_hash(rig1) != compute_entropy_profile_hash(rig2), (
        "distinct hardware collapses to the same entropy_profile_hash -> honest "
        "miner falsely blocked as an entropy-sharing Sybil"
    )


def test_same_hardware_still_stable():
    """Same stable characteristics -> same hash (Sybil-on-one-box still caught)."""
    a = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.78, l3_l2_ratio=3.15, int_avg_ns=9100
    )
    b = _real_producer_fingerprint(
        drift_ratio=1.2, l2_l1_ratio=2.78, l3_l2_ratio=3.15, int_avg_ns=9100
    )
    assert compute_entropy_profile_hash(a) == compute_entropy_profile_hash(b)
