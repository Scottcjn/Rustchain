#!/usr/bin/env python3
"""
Tests for RIP-201 Bucket Normalization Spoofing Fix
=====================================================

Proves the four defences required by bounty #554:

1. CPU brand cross-validation -- Intel Xeon + G4 is REJECTED.
2. SIMD evidence -- missing AltiVec for PowerPC claims is REJECTED.
3. Cache-timing profile -- mismatch for PowerPC claims is REJECTED.
4. Server-side bucket classification -- modern x86 cannot spoof into
   ANY vintage bucket.

Uses only stdlib unittest; no client code is executed locally.
"""

import sqlite3
import unittest
import sys
import os

# Ensure the parent directory is on the path so we can import the fix.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rip201_bucket_fix import (
    validate_cpu_brand_vs_arch,
    validate_simd_evidence,
    validate_cache_timing,
    classify_reward_bucket,
    get_verified_multiplier,
    log_bucket_classification,
    BucketClassification,
    _brand_looks_modern_x86,
    _brand_looks_powerpc,
    _infer_arch_from_features,
    _arch_to_bucket,
)


# ── Helpers ──────────────────────────────────────────────────────

def _make_fingerprint(
    has_altivec=False,
    has_sse2=False,
    has_avx=False,
    has_avx2=False,
    has_avx512=False,
    has_neon=False,
    simd_type="",
    vec_perm_result=None,
    altivec_ops=None,
    cv=0.05,
    tone_ratios=None,
    latency_keys=None,
    thermal_drift_pct=5.0,
):
    """Build a fingerprint dict matching the Rustchain schema."""
    simd = {
        "has_altivec": has_altivec,
        "has_sse2": has_sse2,
        "has_avx": has_avx,
        "has_avx2": has_avx2,
        "has_avx512": has_avx512,
        "has_neon": has_neon,
        "simd_type": simd_type,
    }
    if vec_perm_result is not None:
        simd["vec_perm_result"] = vec_perm_result
    if altivec_ops is not None:
        simd["altivec_ops"] = altivec_ops

    latencies = {}
    if latency_keys is None:
        latency_keys = ["4KB", "32KB", "256KB", "1024KB"]
    for k in latency_keys:
        latencies[k] = {"random_ns": 2.0}

    return {
        "checks": {
            "simd_identity": {"passed": True, "data": simd},
            "clock_drift": {"passed": True, "data": {"cv": cv, "samples": 200}},
            "cache_timing": {
                "passed": True,
                "data": {
                    "latencies": latencies,
                    "tone_ratios": tone_ratios or [2.0, 2.5, 2.0],
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {"thermal_drift_pct": thermal_drift_pct},
            },
        }
    }


def _g4_fingerprint():
    """Fingerprint matching a genuine PowerPC G4."""
    return _make_fingerprint(
        has_altivec=True,
        simd_type="altivec",
        vec_perm_result=0xDEAD,
        altivec_ops=42,
        cv=0.05,
        tone_ratios=[2.0, 2.5, 2.0],
        latency_keys=["4KB", "32KB", "256KB", "1024KB"],
        thermal_drift_pct=5.0,
    )


def _modern_x86_fingerprint():
    """Fingerprint matching a modern Intel/AMD x86-64 system."""
    return _make_fingerprint(
        has_sse2=True,
        has_avx=True,
        has_avx2=True,
        simd_type="sse_avx",
        cv=0.002,
        tone_ratios=[1.5, 2.0, 2.5, 2.5],
        latency_keys=["4KB", "32KB", "256KB", "1024KB", "4096KB"],
    )


# =================================================================
# Test suite
# =================================================================

class TestBrandCrossValidation(unittest.TestCase):
    """Defence 1: CPU brand string vs claimed arch."""

    def test_intel_xeon_claiming_g4_rejected(self):
        """Bounty requirement: Intel Xeon + G4 claim is REJECTED."""
        passed, reason = validate_cpu_brand_vs_arch(
            "Intel(R) Xeon(R) Platinum 8380 CPU @ 2.30GHz",
            "g4",
        )
        self.assertFalse(passed)
        self.assertIn("brand_is_modern_x86", reason)

    def test_amd_epyc_claiming_g4_rejected(self):
        """Bounty requirement: AMD EPYC + G4 claim is REJECTED."""
        passed, reason = validate_cpu_brand_vs_arch(
            "AMD EPYC 7763 64-Core Processor",
            "g4",
        )
        self.assertFalse(passed)
        self.assertIn("brand_is_modern_x86", reason)

    def test_intel_core_i9_claiming_g5_rejected(self):
        passed, reason = validate_cpu_brand_vs_arch(
            "Intel(R) Core(TM) i9-13900K",
            "g5",
        )
        self.assertFalse(passed)

    def test_amd_ryzen_claiming_sparc_rejected(self):
        passed, reason = validate_cpu_brand_vs_arch(
            "AMD Ryzen 9 7950X 16-Core Processor",
            "sparc",
        )
        self.assertFalse(passed)

    def test_intel_xeon_claiming_68k_rejected(self):
        passed, reason = validate_cpu_brand_vs_arch(
            "Intel(R) Xeon(R) E5-2670 v3 @ 2.30GHz",
            "68k",
        )
        self.assertFalse(passed)

    def test_genuine_powerpc_g4_accepted(self):
        """Bounty requirement: Real PowerPC G4 is ACCEPTED."""
        passed, reason = validate_cpu_brand_vs_arch(
            "PowerPC G4 7447A @ 1.42GHz",
            "g4",
        )
        self.assertTrue(passed)

    def test_amigaone_g4_accepted(self):
        passed, reason = validate_cpu_brand_vs_arch(
            "AmigaOne G4 7447 @ 1GHz",
            "g4",
        )
        self.assertTrue(passed)

    def test_ibm_power8_accepted(self):
        passed, reason = validate_cpu_brand_vs_arch(
            "IBM POWER8 @ 3.5GHz",
            "power8",
        )
        self.assertTrue(passed)

    def test_modern_x86_claiming_modern_x86_accepted(self):
        """Honest x86 miners are not blocked."""
        passed, reason = validate_cpu_brand_vs_arch(
            "Intel(R) Core(TM) i7-12700K",
            "modern_x86",
        )
        self.assertTrue(passed)

    def test_missing_arch_rejected(self):
        passed, reason = validate_cpu_brand_vs_arch("anything", "")
        self.assertFalse(passed)

    def test_empty_brand_powerpc_claim_rejected(self):
        """Empty brand + PowerPC claim: rejected (no positive evidence)."""
        passed, reason = validate_cpu_brand_vs_arch("", "g4")
        # Empty string is not modern_x86, so brand_looks_modern_x86 = False
        # But also not powerpc brand, so should fail for powerpc archs.
        self.assertFalse(passed)
        self.assertIn("brand_not_powerpc", reason)

    def test_unknown_brand_non_powerpc_non_x86_passes(self):
        """Unknown brand claiming arm64 should pass (no brand gate for ARM)."""
        passed, reason = validate_cpu_brand_vs_arch(
            "Qualcomm Snapdragon 8 Gen 3", "arm64",
        )
        self.assertTrue(passed)


class TestSIMDEvidence(unittest.TestCase):
    """Defence 2: SIMD evidence for PowerPC claims."""

    def test_g4_with_altivec_accepted(self):
        """Bounty requirement: Real G4 + valid AltiVec evidence ACCEPTED."""
        simd = {
            "data": {
                "has_altivec": True,
                "simd_type": "altivec",
                "vec_perm_result": 0xCAFE,
            }
        }
        passed, reason = validate_simd_evidence("g4", simd)
        self.assertTrue(passed)

    def test_g4_missing_altivec_rejected(self):
        """Bounty requirement: Missing AltiVec for G4 is REJECTED."""
        simd = {"data": {"has_altivec": False, "simd_type": "none"}}
        passed, reason = validate_simd_evidence("g4", simd)
        self.assertFalse(passed)
        self.assertIn("altivec_missing", reason)

    def test_g4_with_sse2_and_altivec_rejected(self):
        """x86 SIMD features alongside AltiVec = spoofing."""
        simd = {
            "data": {
                "has_altivec": True,
                "has_sse2": True,
                "simd_type": "altivec",
                "vec_perm_result": 0xBEEF,
            }
        }
        passed, reason = validate_simd_evidence("g4", simd)
        self.assertFalse(passed)
        self.assertIn("x86_simd_with_altivec", reason)

    def test_g4_with_avx_and_altivec_rejected(self):
        simd = {
            "data": {
                "has_altivec": True,
                "has_avx": True,
                "simd_type": "altivec",
                "vec_perm_result": 1,
            }
        }
        passed, reason = validate_simd_evidence("g4", simd)
        self.assertFalse(passed)

    def test_g4_altivec_but_no_evidence_rejected(self):
        """has_altivec=True but no vec_perm, no altivec_ops, no simd_type."""
        simd = {"data": {"has_altivec": True}}
        passed, reason = validate_simd_evidence("g4", simd)
        self.assertFalse(passed)
        self.assertIn("insufficient_altivec_evidence", reason)

    def test_g4_altivec_with_ops_count_accepted(self):
        """altivec_ops count alone is sufficient evidence."""
        simd = {
            "data": {
                "has_altivec": True,
                "altivec_ops": 128,
            }
        }
        passed, reason = validate_simd_evidence("g4", simd)
        self.assertTrue(passed)

    def test_g5_missing_simd_data_rejected(self):
        passed, reason = validate_simd_evidence("g5", {})
        self.assertFalse(passed)

    def test_g5_none_simd_data_rejected(self):
        passed, reason = validate_simd_evidence("g5", None)
        self.assertFalse(passed)

    def test_g3_no_altivec_needed(self):
        """G3 does not have AltiVec -- SIMD check is skipped."""
        passed, reason = validate_simd_evidence("g3", {})
        self.assertTrue(passed)

    def test_modern_x86_simd_check_not_required(self):
        passed, reason = validate_simd_evidence("modern_x86", {})
        self.assertTrue(passed)

    def test_power8_requires_altivec(self):
        simd = {"data": {"has_altivec": False}}
        passed, reason = validate_simd_evidence("power8", simd)
        self.assertFalse(passed)


class TestCacheTimingValidation(unittest.TestCase):
    """Defence 3: Cache-timing profile for PowerPC claims."""

    def test_g4_valid_cache_profile_accepted(self):
        cache = {
            "data": {
                "latencies": {
                    "4KB": {"random_ns": 1.0},
                    "32KB": {"random_ns": 2.0},
                    "256KB": {"random_ns": 5.0},
                    "1024KB": {"random_ns": 10.0},
                },
                "tone_ratios": [2.0, 2.5, 2.0],
            }
        }
        clock = {"data": {"cv": 0.05}}
        passed, reason = validate_cache_timing("g4", cache, clock)
        self.assertTrue(passed)

    def test_g4_clock_cv_too_low_rejected(self):
        """Bounty requirement: cache timing mismatch REJECTED.
        Modern x86 CV (~0.002) is way below G4 minimum (0.008)."""
        cache = {"data": {"latencies": {"4KB": {"random_ns": 1.0}}, "tone_ratios": [2.0]}}
        clock = {"data": {"cv": 0.002}}
        passed, reason = validate_cache_timing("g4", cache, clock)
        self.assertFalse(passed)
        self.assertIn("clock_cv_too_low", reason)

    def test_g4_large_l3_rejected(self):
        """G4 should NOT have a 4096 KB L3 cache."""
        cache = {
            "data": {
                "latencies": {
                    "4KB": {"random_ns": 1.0},
                    "32KB": {"random_ns": 2.0},
                    "256KB": {"random_ns": 5.0},
                    "4096KB": {"random_ns": 20.0},
                },
                "tone_ratios": [2.0, 2.5],
            }
        }
        clock = {"data": {"cv": 0.05}}
        passed, reason = validate_cache_timing("g4", cache, clock)
        self.assertFalse(passed)
        self.assertIn("unexpected_large_cache", reason)

    def test_g4_tone_ratio_too_low_rejected(self):
        cache = {
            "data": {
                "latencies": {"4KB": {"random_ns": 1.0}},
                "tone_ratios": [0.3, 0.4],
            }
        }
        clock = {"data": {"cv": 0.05}}
        passed, reason = validate_cache_timing("g4", cache, clock)
        self.assertFalse(passed)
        self.assertIn("tone_ratio_too_low", reason)

    def test_g5_allows_large_l3(self):
        """G5 can have a large L3 -- should not be rejected."""
        cache = {
            "data": {
                "latencies": {
                    "4KB": {"random_ns": 1.0},
                    "32KB": {"random_ns": 2.0},
                    "4096KB": {"random_ns": 20.0},
                },
                "tone_ratios": [2.0, 2.5],
            }
        }
        clock = {"data": {"cv": 0.08}}
        passed, reason = validate_cache_timing("g5", cache, clock)
        self.assertTrue(passed)

    def test_modern_x86_cache_check_skipped(self):
        """Non-PowerPC arches are not subject to cache profile checks."""
        passed, reason = validate_cache_timing("modern_x86", {}, {})
        self.assertTrue(passed)

    def test_g3_cv_too_high_rejected(self):
        clock = {"data": {"cv": 0.50}}
        cache = {"data": {"latencies": {"4KB": {"random_ns": 1.0}}, "tone_ratios": [2.0]}}
        passed, reason = validate_cache_timing("g3", cache, clock)
        self.assertFalse(passed)
        self.assertIn("clock_cv_too_high", reason)


class TestServerSideBucketClassification(unittest.TestCase):
    """Defence 4: Server-side classification from verified features."""

    def test_intel_xeon_spoofing_g4_downgraded_to_modern_x86(self):
        """Bounty requirement: Modern x86 cannot spoof into ANY vintage bucket.
        Intel Xeon claiming G4 gets downgraded to modern_x86 at 1.0x."""
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "g4",
            "Intel(R) Xeon(R) Platinum 8380 CPU @ 2.30GHz",
            fp,
        )
        self.assertTrue(result.downgraded)
        self.assertEqual(result.bucket, "modern_x86")
        self.assertEqual(result.multiplier, 1.0)
        self.assertGreater(len(result.rejection_reasons), 0)

    def test_amd_epyc_spoofing_g4_downgraded(self):
        """Bounty requirement: AMD EPYC + G4 REJECTED / downgraded."""
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "g4",
            "AMD EPYC 7763 64-Core Processor",
            fp,
        )
        self.assertTrue(result.downgraded)
        self.assertEqual(result.bucket, "modern_x86")
        self.assertEqual(result.multiplier, 1.0)

    def test_genuine_g4_full_multiplier(self):
        """Bounty requirement: Real PowerPC G4 with valid evidence ACCEPTED."""
        fp = _g4_fingerprint()
        result = classify_reward_bucket(
            "g4",
            "PowerPC G4 7447A @ 1.42GHz",
            fp,
        )
        self.assertFalse(result.downgraded)
        self.assertEqual(result.bucket, "vintage_powerpc_g4")
        self.assertEqual(result.multiplier, 2.5)

    def test_x86_spoofing_g5_downgraded(self):
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "g5",
            "Intel(R) Core(TM) i7-12700K",
            fp,
        )
        self.assertTrue(result.downgraded)
        self.assertEqual(result.multiplier, 1.0)

    def test_x86_spoofing_68k_downgraded(self):
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "68k",
            "AMD Ryzen 9 7950X",
            fp,
        )
        self.assertTrue(result.downgraded)
        self.assertEqual(result.multiplier, 1.0)

    def test_x86_spoofing_sparc_downgraded(self):
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "sparc",
            "Intel(R) Xeon(R) Gold 6248R",
            fp,
        )
        self.assertTrue(result.downgraded)
        self.assertEqual(result.multiplier, 1.0)

    def test_x86_spoofing_power8_downgraded(self):
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "power8",
            "Intel(R) Xeon(R) E5-2690 v4",
            fp,
        )
        self.assertTrue(result.downgraded)
        self.assertEqual(result.multiplier, 1.0)

    def test_honest_modern_x86_unchanged(self):
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "modern_x86",
            "Intel(R) Core(TM) i7-12700K",
            fp,
        )
        self.assertFalse(result.downgraded)
        self.assertEqual(result.multiplier, 1.0)

    def test_inferred_arch_matches_evidence(self):
        """Server-side inference should detect modern_x86 from SSE2/AVX."""
        fp = _modern_x86_fingerprint()
        inferred = _infer_arch_from_features(
            fp["checks"]["simd_identity"],
            fp["checks"]["cache_timing"],
            "Intel(R) Xeon(R) Platinum 8380",
        )
        self.assertEqual(inferred, "modern_x86")

    def test_inferred_arch_detects_g4_from_altivec(self):
        fp = _g4_fingerprint()
        inferred = _infer_arch_from_features(
            fp["checks"]["simd_identity"],
            fp["checks"]["cache_timing"],
            "PowerPC G4 7447A",
        )
        self.assertIn("powerpc", inferred)


class TestGetVerifiedMultiplier(unittest.TestCase):
    """Integration test for the drop-in multiplier function."""

    def test_spoofed_g4_gets_1x(self):
        """Intel Xeon spoofing G4 gets 1.0x multiplier after verification."""
        mult = get_verified_multiplier(
            miner_id="miner_xeon_spoof",
            claimed_arch="g4",
            cpu_brand="Intel(R) Xeon(R) Platinum 8380 CPU @ 2.30GHz",
            fingerprint=_modern_x86_fingerprint(),
            chain_age_years=0.0,
        )
        self.assertEqual(mult, 1.0)

    def test_genuine_g4_gets_2_5x_at_year_0(self):
        mult = get_verified_multiplier(
            miner_id="miner_real_g4",
            claimed_arch="g4",
            cpu_brand="PowerPC G4 7447A @ 1.42GHz",
            fingerprint=_g4_fingerprint(),
            chain_age_years=0.0,
        )
        self.assertEqual(mult, 2.5)

    def test_genuine_g4_decays_over_time(self):
        mult = get_verified_multiplier(
            miner_id="miner_real_g4",
            claimed_arch="g4",
            cpu_brand="PowerPC G4 7447A @ 1.42GHz",
            fingerprint=_g4_fingerprint(),
            chain_age_years=5.0,
        )
        # At year 5 with DECAY_RATE=0.06: bonus = 1.5 * (1 - 0.3) = 1.05
        # multiplier = 1.0 + 1.05 = 2.05
        self.assertAlmostEqual(mult, 2.05, places=2)
        self.assertGreater(mult, 1.0)
        self.assertLess(mult, 2.5)

    def test_with_audit_db(self):
        """Ensure audit logging works with an in-memory database."""
        db = sqlite3.connect(":memory:")
        mult = get_verified_multiplier(
            miner_id="miner_audit_test",
            claimed_arch="g4",
            cpu_brand="Intel(R) Xeon(R) Platinum 8380",
            fingerprint=_modern_x86_fingerprint(),
            chain_age_years=0.0,
            db=db,
        )
        self.assertEqual(mult, 1.0)
        row = db.execute(
            "SELECT * FROM rip201_bucket_audit WHERE miner = ?",
            ("miner_audit_test",),
        ).fetchone()
        self.assertIsNotNone(row)
        db.close()


class TestBrandDetectionHelpers(unittest.TestCase):
    """Unit tests for brand-detection helpers."""

    def test_intel_xeon_is_modern_x86(self):
        self.assertTrue(_brand_looks_modern_x86("Intel(R) Xeon(R) Platinum 8380"))

    def test_amd_epyc_is_modern_x86(self):
        self.assertTrue(_brand_looks_modern_x86("AMD EPYC 7763"))

    def test_amd_ryzen_is_modern_x86(self):
        self.assertTrue(_brand_looks_modern_x86("AMD Ryzen 9 7950X"))

    def test_powerpc_g4_is_not_modern_x86(self):
        self.assertFalse(_brand_looks_modern_x86("PowerPC G4 7447A"))

    def test_motorola_is_powerpc(self):
        self.assertTrue(_brand_looks_powerpc("Motorola PowerPC 7450"))

    def test_ibm_is_powerpc(self):
        self.assertTrue(_brand_looks_powerpc("IBM POWER8"))

    def test_intel_is_not_powerpc(self):
        self.assertFalse(_brand_looks_powerpc("Intel(R) Xeon(R) Platinum 8380"))


class TestArchToBucket(unittest.TestCase):
    """Verify arch -> bucket mapping."""

    def test_g4_maps_to_vintage_powerpc_g4(self):
        self.assertEqual(_arch_to_bucket("g4"), "vintage_powerpc_g4")

    def test_unknown_maps_to_modern_x86(self):
        self.assertEqual(_arch_to_bucket("whateverXYZ"), "modern_x86")

    def test_case_insensitive(self):
        self.assertEqual(_arch_to_bucket("G4"), "vintage_powerpc_g4")
        self.assertEqual(_arch_to_bucket("G5"), "vintage_powerpc_g5")


class TestEdgeCases(unittest.TestCase):
    """Edge cases and regression guards."""

    def test_empty_fingerprint_downgrades_powerpc_claim(self):
        """Empty fingerprint + G4 claim should be downgraded."""
        result = classify_reward_bucket("g4", "PowerPC G4 7447A", {})
        # Missing SIMD data -> simd check fails -> downgrade.
        self.assertTrue(result.downgraded)

    def test_none_fingerprint_downgrades(self):
        result = classify_reward_bucket("g4", "PowerPC G4 7447A", {"checks": {}})
        self.assertTrue(result.downgraded)

    def test_via_nano_claiming_g4_rejected(self):
        """VIA Nano is x86 -- should not get PowerPC bucket."""
        passed, _ = validate_cpu_brand_vs_arch("VIA Nano U3500", "g4")
        self.assertFalse(passed)

    def test_multiple_rejection_reasons_accumulated(self):
        """When both brand and SIMD fail, both reasons should appear."""
        fp = _modern_x86_fingerprint()
        result = classify_reward_bucket(
            "g4",
            "Intel(R) Xeon(R) Platinum 8380",
            fp,
        )
        # Should have at least brand + SIMD reasons.
        self.assertGreaterEqual(len(result.rejection_reasons), 2)


if __name__ == "__main__":
    unittest.main()
