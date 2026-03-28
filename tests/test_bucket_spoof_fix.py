#!/usr/bin/env python3
"""
tests/test_bucket_spoof_fix.py
===============================
Tests for RIP-201 Bucket Normalization Spoofing Fix — Bounty #554

Verifies that classify_miner_bucket() uses server-side arch_cross_validation
results instead of blindly trusting client-reported device_arch.

Attack vector (liu971227-sys / Rustchain#551):
  A modern x86 machine claims device_arch=G4 → gets routed into
  vintage_powerpc bucket → earns 2.5× instead of 1.0× rewards.

Fix:
  run_arch_validation_for_attestation() validates fingerprint vs arch claim,
  stores result in arch_validation_results table, and classify_miner_bucket()
  reads from that table when db+miner_id are provided.

All tests are self-contained (in-memory SQLite, mock fingerprints).
No external services required.
"""

import sqlite3
import sys
import os
import time

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root or tests/ directory
# ---------------------------------------------------------------------------
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)

for _p in [
    os.path.join(_REPO_ROOT, "rips", "python"),
    os.path.join(_REPO_ROOT, "node"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rustchain.fleet_immune_system import (
    ensure_schema,
    classify_miner_bucket,
    store_arch_validation_result,
    run_arch_validation_for_attestation,
    get_validated_bucket,
    ARCH_VALIDATION_SCORE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    ensure_schema(db)
    return db


# Fingerprint helpers — construct realistic check dicts

def _fp_x86_spoof_g4() -> dict:
    """Intel Xeon fingerprint but claiming G4 — classic spoof."""
    return {
        "checks": {
            "simd_identity": {
                "passed": True,
                "data": {
                    "has_altivec": False,
                    "has_sse": True,
                    "has_sse2": True,
                    "has_avx": True,
                    "has_avx2": True,
                    "has_neon": False,
                    "simd_type": "sse_avx",
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.0015, "samples": 200, "mean_ns": 500},
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "latencies": {
                        "4KB":    {"random_ns": 0.8},
                        "32KB":   {"random_ns": 1.2},
                        "256KB":  {"random_ns": 2.5},
                        "1024KB": {"random_ns": 8.0},
                        "4096KB": {"random_ns": 20.0},
                    },
                    "tone_ratios": [1.5, 2.1, 3.2, 2.5],
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {"thermal_drift_pct": 1.2, "recovery_pct": 0.5},
            },
        }
    }


def _fp_real_g4() -> dict:
    """Authentic PowerPC G4 fingerprint profile."""
    return {
        "checks": {
            "simd_identity": {
                "passed": True,
                "data": {
                    "has_altivec": True,
                    "has_sse": False,
                    "has_sse2": False,
                    "has_avx": False,
                    "has_neon": False,
                    "simd_type": "altivec",
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.072, "samples": 200, "mean_ns": 2100},
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "latencies": {
                        "4KB":    {"random_ns": 3.5},
                        "32KB":   {"random_ns": 7.0},
                        "256KB":  {"random_ns": 18.0},
                        "1024KB": {"random_ns": 45.0},
                    },
                    "tone_ratios": [2.0, 2.6, 2.5],
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {"thermal_drift_pct": 6.0, "recovery_pct": 3.0},
            },
        }
    }


def _fp_x86_fake_altivec() -> dict:
    """x86 machine that reports has_altivec=True to fake AltiVec support."""
    return {
        "checks": {
            "simd_identity": {
                "passed": True,
                "data": {
                    # Attacker sets has_altivec True but also exposes SSE
                    "has_altivec": True,
                    "has_sse": True,
                    "has_sse2": True,
                    "has_avx": True,
                    "has_neon": False,
                    "simd_type": "sse_avx",
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.0018, "samples": 200, "mean_ns": 480},
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "latencies": {
                        "4KB":    {"random_ns": 0.9},
                        "32KB":   {"random_ns": 1.3},
                        "256KB":  {"random_ns": 2.8},
                        "1024KB": {"random_ns": 9.0},
                        "4096KB": {"random_ns": 22.0},
                    },
                    "tone_ratios": [1.4, 2.1, 3.2, 2.4],
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {"thermal_drift_pct": 1.0, "recovery_pct": 0.4},
            },
        }
    }


# ---------------------------------------------------------------------------
# Test 1: Intel Xeon + G4 claim → rejected, falls to "modern" bucket
# ---------------------------------------------------------------------------

def test_intel_xeon_g4_spoof_rejected():
    """
    Core exploit scenario: x86 machine claims device_arch=G4.
    The arch cross-validation should detect SSE/AVX (disqualifying for G4)
    and assign "modern" bucket instead of "vintage_powerpc".
    """
    db = make_db()
    miner = "spoof-xeon-001"
    claimed_arch = "g4"
    fingerprint = _fp_x86_spoof_g4()
    device_info = {"cpu_brand": "Intel(R) Xeon(R) Gold 6248R"}

    passed, bucket = run_arch_validation_for_attestation(
        db, miner, claimed_arch, fingerprint, device_info
    )

    assert not passed, (
        f"Validation should have REJECTED Intel Xeon claiming G4, got passed={passed}"
    )
    assert bucket == "modern", (
        f"Spoofing attacker must land in 'modern' bucket, got '{bucket}'"
    )

    # Verify classify_miner_bucket() also returns "modern" via DB lookup
    resolved = classify_miner_bucket(claimed_arch, db=db, miner_id=miner)
    assert resolved == "modern", (
        f"classify_miner_bucket should return 'modern' for rejected miner, got '{resolved}'"
    )

    print("  PASS: Intel Xeon + G4 claim → rejected, lands in 'modern' bucket")


# ---------------------------------------------------------------------------
# Test 2: Real G4 fingerprint + G4 claim → accepted, vintage_powerpc bucket
# ---------------------------------------------------------------------------

def test_real_g4_fingerprint_accepted():
    """
    Legitimate G4 miner with authentic AltiVec fingerprint.
    Should pass validation and land in vintage_powerpc bucket.
    """
    db = make_db()
    miner = "real-g4-powerbook-115"
    claimed_arch = "g4"
    fingerprint = _fp_real_g4()
    device_info = {"cpu_brand": "PowerPC G4 (7450)"}

    passed, bucket = run_arch_validation_for_attestation(
        db, miner, claimed_arch, fingerprint, device_info
    )

    assert passed, (
        f"Authentic G4 fingerprint should PASS validation, got passed={passed}"
    )
    assert bucket == "vintage_powerpc", (
        f"Real G4 must land in 'vintage_powerpc' bucket, got '{bucket}'"
    )

    resolved = classify_miner_bucket(claimed_arch, db=db, miner_id=miner)
    assert resolved == "vintage_powerpc", (
        f"classify_miner_bucket should return 'vintage_powerpc', got '{resolved}'"
    )

    print("  PASS: Real G4 fingerprint + G4 claim → accepted, vintage_powerpc bucket")


# ---------------------------------------------------------------------------
# Test 3: Modern x86 faking AltiVec → rejected
# ---------------------------------------------------------------------------

def test_x86_fake_altivec_rejected():
    """
    Attacker sets has_altivec=True in fingerprint but still exposes SSE/AVX.
    The G4 profile explicitly disqualifies any miner that reports has_sse=True.
    Should be rejected and land in "modern".
    """
    db = make_db()
    miner = "spoof-fake-altivec-002"
    claimed_arch = "g4"
    fingerprint = _fp_x86_fake_altivec()
    device_info = {"cpu_brand": "AMD Ryzen 9 5950X"}

    passed, bucket = run_arch_validation_for_attestation(
        db, miner, claimed_arch, fingerprint, device_info
    )

    assert not passed, (
        f"x86 with fake AltiVec should FAIL validation, got passed={passed}"
    )
    assert bucket == "modern", (
        f"Rejected attacker must land in 'modern' bucket, got '{bucket}'"
    )

    resolved = classify_miner_bucket(claimed_arch, db=db, miner_id=miner)
    assert resolved == "modern", (
        f"classify_miner_bucket should return 'modern', got '{resolved}'"
    )

    print("  PASS: Modern x86 faking AltiVec → rejected, lands in 'modern' bucket")


# ---------------------------------------------------------------------------
# Test 4: No validation record → safe default (modern, no bonus)
# ---------------------------------------------------------------------------

def test_unvalidated_miner_defaults_to_modern():
    """
    A miner that has never been through arch validation (e.g., submitted
    attestation before validation hook was deployed) should default to "modern"
    bucket — never granting an unearned vintage bonus.
    """
    db = make_db()
    # No call to run_arch_validation_for_attestation — miner is unknown

    resolved = classify_miner_bucket("g4", db=db, miner_id="ghost-miner-never-validated")
    assert resolved == "modern", (
        f"Unvalidated miner must default to 'modern', got '{resolved}'"
    )

    # Also verify via get_validated_bucket directly
    bucket = get_validated_bucket(db, "ghost-miner-never-validated", "g4")
    assert bucket == "modern", (
        f"get_validated_bucket should return 'modern' when no record exists, got '{bucket}'"
    )

    print("  PASS: Unvalidated miner → defaults to 'modern' (no unearned bonus)")


# ---------------------------------------------------------------------------
# Test 5: Legacy call path (no db/miner_id) still works unchanged
# ---------------------------------------------------------------------------

def test_legacy_classify_still_works():
    """
    Callers that invoke classify_miner_bucket(arch) without db/miner_id
    must continue to work exactly as before (backwards compatibility).
    """
    # These are the original raw-arch lookups — no validation
    assert classify_miner_bucket("g4") == "vintage_powerpc"
    assert classify_miner_bucket("modern") == "modern"
    assert classify_miner_bucket("apple_silicon") == "apple_silicon"
    assert classify_miner_bucket("totally_unknown_arch") == "modern"

    print("  PASS: Legacy classify_miner_bucket(arch) path still works correctly")


# ---------------------------------------------------------------------------
# Test 6: store_arch_validation_result round-trip
# ---------------------------------------------------------------------------

def test_store_and_retrieve_validation_result():
    """
    Verify that store_arch_validation_result() persists correctly
    and get_validated_bucket() retrieves the right bucket.
    """
    db = make_db()
    miner = "test-store-retrieve"

    # Store a passing result for vintage bucket
    store_arch_validation_result(
        db, miner, "g4",
        validation_score=0.85,
        passed=True,
        validated_bucket="vintage_powerpc",
    )
    bucket = get_validated_bucket(db, miner, "g4")
    assert bucket == "vintage_powerpc", f"Expected vintage_powerpc, got {bucket}"

    # Overwrite with a failing result
    store_arch_validation_result(
        db, miner, "g4",
        validation_score=0.25,
        passed=False,
        validated_bucket="modern",
        rejection_reason="disqualifying_feature:has_sse",
    )
    bucket = get_validated_bucket(db, miner, "g4")
    assert bucket == "modern", f"After rejection, expected 'modern', got {bucket}"

    print("  PASS: store/retrieve validation result round-trip works")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all():
    tests = [
        test_intel_xeon_g4_spoof_rejected,
        test_real_g4_fingerprint_accepted,
        test_x86_fake_altivec_rejected,
        test_unvalidated_miner_defaults_to_modern,
        test_legacy_classify_still_works,
        test_store_and_retrieve_validation_result,
    ]

    print("=" * 65)
    print("RIP-201 Bucket Normalization Spoofing Fix — Bounty #554 Tests")
    print("=" * 65)

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL [{test_fn.__name__}]: {exc}")
            failed += 1
        except Exception as exc:
            print(f"  ERROR [{test_fn.__name__}]: {type(exc).__name__}: {exc}")
            failed += 1

    print("=" * 65)
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")
    print("=" * 65)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
