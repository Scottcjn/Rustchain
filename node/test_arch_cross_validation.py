#!/usr/bin/env python3
"""Unit tests for arch_cross_validation.py"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from arch_cross_validation import (
    validate_arch_consistency, normalize_arch, ARCHITECTURE_PROFILES
)

def test_normalize_arch():
    assert normalize_arch("g4") == "g4"
    assert normalize_arch("PowerPC G4") == "g4"
    assert normalize_arch("power macintosh") == "g4"
    assert normalize_arch("apple m1") == "apple_silicon"
    assert normalize_arch("M1") == "apple_silicon"
    assert normalize_arch("x86_64") == "modern_x86"
    assert normalize_arch("AMD64") == "modern_x86"
    assert normalize_arch("i386") == "vintage_x86"
    assert normalize_arch("ppc") == "g3"
    assert normalize_arch("68k") == "68k"
    assert normalize_arch("unknown_arch") is None
    assert normalize_arch("") is None
    assert normalize_arch(None) is None
    print("  normalize_arch: PASS")

def test_g4_real_hardware():
    fp = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_altivec": True, "has_sse": False, "has_neon": False, "simd_type": "altivec"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 2.0}, "256KB": {"random_ns": 5.0}, "1024KB": {"random_ns": 10.0}}, "tone_ratios": [2.0, 2.5, 2.0]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 5.0}}
        }
    }
    score, details = validate_arch_consistency(fp, "g4")
    assert score >= 0.8, f"G4 real hardware scored too low: {score}"
    print(f"  G4 real hardware: PASS (score={score})")

def test_g4_flat_fingerprint_not_flagged():
    # Same legitimate G4 evidence as test_g4_real_hardware, but in the FLAT
    # form (no "checks" wrapper, no per-check "data" key). extract_all_features
    # explicitly supports this layout, so it must score identically to the
    # wrapped form and NOT be falsely flagged as spoofed.
    wrapped = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_altivec": True, "has_sse": False, "has_neon": False, "simd_type": "altivec"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 2.0}, "256KB": {"random_ns": 5.0}, "1024KB": {"random_ns": 10.0}}, "tone_ratios": [2.0, 2.5, 2.0]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 5.0}}
        }
    }
    flat = {
        "simd_identity": {"has_altivec": True, "has_sse": False, "has_neon": False, "simd_type": "altivec"},
        "clock_drift": {"cv": 0.05, "samples": 200},
        "cache_timing": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 2.0}, "256KB": {"random_ns": 5.0}, "1024KB": {"random_ns": 10.0}}, "tone_ratios": [2.0, 2.5, 2.0]},
        "thermal_drift": {"thermal_drift_pct": 5.0}
    }
    wrapped_score, _ = validate_arch_consistency(wrapped, "g4")
    flat_score, _ = validate_arch_consistency(flat, "g4")
    assert flat_score >= 0.8, f"flat G4 fingerprint falsely flagged: {flat_score}"
    assert flat_score == wrapped_score, f"flat {flat_score} != wrapped {wrapped_score}"
    print(f"  G4 flat fingerprint: PASS (score={flat_score})")

def test_g4_x86_spoofing():
    fp = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_sse2": True, "has_avx2": True, "has_altivec": False, "simd_type": "sse_avx"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.001, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.5}, "256KB": {"random_ns": 3.0}, "4096KB": {"random_ns": 15.0}}, "tone_ratios": [1.5, 2.0, 5.0]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 0.0}}
        }
    }
    score, details = validate_arch_consistency(fp, "g4")
    assert score < 0.7, f"G4/x86 spoofing scored too high: {score}"
    print(f"  G4/x86 spoofing: PASS (score={score})")

def test_modern_x86_real():
    fp = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_sse2": True, "has_avx2": True, "has_altivec": False, "has_neon": False, "simd_type": "sse_avx"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.002, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.5}, "256KB": {"random_ns": 3.0}, "1024KB": {"random_ns": 8.0}, "4096KB": {"random_ns": 20.0}}, "tone_ratios": [1.5, 2.0, 2.5, 2.5]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 1.5}}
        }
    }
    score, details = validate_arch_consistency(fp, "modern_x86")
    assert score >= 0.8, f"modern_x86 real hardware scored too low: {score}"
    print(f"  modern_x86 real: PASS (score={score})")

def test_apple_silicon_real():
    fp = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_neon": True, "has_altivec": False, "has_sse": False, "simd_type": "neon"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.003, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.2}, "256KB": {"random_ns": 2.5}, "1024KB": {"random_ns": 6.0}, "4096KB": {"random_ns": 12.0}}, "tone_ratios": [1.2, 2.0, 2.4, 2.0]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 1.0}}
        }
    }
    score, details = validate_arch_consistency(fp, "apple_silicon")
    assert score >= 0.8, f"apple_silicon real scored too low: {score}"
    print(f"  apple_silicon real: PASS (score={score})")

def test_frozen_profile():
    fp = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_sse2": True, "has_avx2": True, "has_altivec": False, "has_neon": False, "simd_type": "sse_avx"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.0, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.5}, "256KB": {"random_ns": 3.0}, "1024KB": {"random_ns": 8.0}, "4096KB": {"random_ns": 20.0}}, "tone_ratios": [1.5, 2.0, 2.5, 2.5]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 1.5}},
        }
    }
    score, details = validate_arch_consistency(fp, "modern_x86")
    assert details["scores"]["clock_consistency"] == 0.3, f"frozen clock should score 0.3, got {details['scores']['clock_consistency']}"
    assert "no_clock_cv_data" in details["issues"], "Should flag no_clock_cv_data"
    print(f"  frozen profile: PASS (clock_score={details['scores']['clock_consistency']})")

def test_missing_fingerprint():
    fp = {}
    score, details = validate_arch_consistency(fp, "g4")
    # Empty fingerprint should have low scores due to missing evidence
    assert details["overall_score"] < 0.7, f"Empty fingerprint scored too high: {details['overall_score']}"
    print(f"  empty fingerprint: PASS (score={details['overall_score']})")

def test_cpu_brand_consistency():
    fp = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_altivec": True, "has_sse": False, "has_neon": False, "simd_type": "altivec"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 2.0}, "256KB": {"random_ns": 5.0}, "1024KB": {"random_ns": 10.0}}, "tone_ratios": [2.0, 2.5, 2.0]}},
        }
    }
    score_good, _ = validate_arch_consistency(fp, "g4", {"cpu_brand": "Motorola MPC7445"})
    score_bad, details = validate_arch_consistency(fp, "g4", {"cpu_brand": "Intel Core i9-13900K"})
    assert score_good > score_bad, f"G4 with Intel brand should score lower"
    print(f"  cpu_brand consistency: PASS (G4/Motorola={score_good}, G4/Intel={score_bad})")

def test_all_profiles_valid():
    required = ["simd_type", "cache_sizes", "cv_range", "thermal_drift_range", "disqualifying_features", "cache_tone_min", "cache_tone_max"]
    for arch, profile in ARCHITECTURE_PROFILES.items():
        for field in required:
            assert field in profile, f"Profile {arch} missing {field}"
        assert isinstance(profile["cv_range"], tuple) and len(profile["cv_range"]) == 2
    print("  all profiles valid: PASS")

def test_score_interpretation_levels():
    for arch in ["g4", "modern_x86"]:
        fp = {"checks": {"simd_identity": {"passed": True, "data": {"has_sse2": True}}, "clock_drift": {"passed": True, "data": {"cv": 0.002, "samples": 200}}, "cache_timing": {"passed": True, "data": {"tone_ratios": [1.5]}}}}
        score, details = validate_arch_consistency(fp, arch)
        assert "interpretation" in details
    print("  interpretation levels: PASS")


from arch_cross_validation import (
    validate_x86_vintage_reward_tier,
    classify_anchored_x86_vintage_brand,
    has_validated_measurement_evidence,
)


def _make_x86_fp(brand: str, family: int, measurements: bool = True, **extra_checks):
    checks = {
        "device_age_oracle": {
            "passed": True,
            "data": {
                "cpu_model": brand,
                "cpu_family": str(family),
                "arch": "i686",
                "flags_sample": [],
                "mismatch_reasons": [],
                "confidence": 0.85,
            },
        },
    }
    if measurements:
        checks["cache_timing"] = {
            "passed": True,
            "data": {
                "l1_ns": 40.0,
                "l2_ns": 80.0,
                "l3_ns": 240.0,
                "l2_l1_ratio": 2.0,
                "l3_l2_ratio": 3.0,
            },
        }
        checks["simd_identity"] = {
            "passed": True,
            "data": {
                "arch": "i686",
                "simd_flags_count": 1,
                "has_sse": False,
                "has_avx": False,
                "has_altivec": False,
                "has_neon": False,
                "sample_flags": ["fpu"],
            },
        }
    checks.update(extra_checks)
    return {"checks": checks}


def test_bounty_16271_tscless_486_and_386_keep_tier():
    fp_486 = _make_x86_fp(
        "Am486DX4",
        4,
        clock_drift={"passed": False, "data": {"fail_reason": "rdtsc_unavailable", "cv": 0}},
    )
    fp_486["all_passed"] = False
    res_486 = validate_x86_vintage_reward_tier("486", fp_486)
    assert res_486 == {"device_family": "x86", "device_arch": "486"}

    fp_386 = _make_x86_fp("Am386DX", 3)
    res_386 = validate_x86_vintage_reward_tier("386", fp_386)
    assert res_386 == {"device_family": "x86", "device_arch": "386"}


def test_bounty_16271_anchored_brand_and_family_boundaries():
    # Pentium III (family 6) must NOT match family-5 'pentium'
    fp_p3 = _make_x86_fp("Intel Pentium III 800MHz", 6)
    assert validate_x86_vintage_reward_tier("pentium", fp_p3)["device_arch"] == "default"
    assert validate_x86_vintage_reward_tier("pentium_iii", fp_p3)["device_arch"] == "pentium_iii"

    # Pentium 4 / Core i7 must clamp to default
    fp_p4 = _make_x86_fp("Intel(R) Pentium(R) 4 CPU 3.00GHz", 15)
    assert validate_x86_vintage_reward_tier("pentium", fp_p4)["device_arch"] == "default"
    fp_i7 = _make_x86_fp("Intel Core i7-9750H", 6)
    assert validate_x86_vintage_reward_tier("486", fp_i7)["device_arch"] == "default"

    # Mixed-case & literal Linux kernel model names accepted
    for brand, fam, arch in [
        ("pEnTiUm 200", 5, "pentium"),
        ("Pentium 75 - 200", 5, "pentium"),
        ("Pentium 60/66", 5, "pentium"),
        ("486 DX/2", 4, "486"),
        ("Am5x86-WT", 4, "486"),
        ("Cyrix Cx486DX2", 4, "486"),
        ("Pentium III (Coppermine)", 6, "pentium_iii"),
        ("Pentium II (Deschutes)", 6, "pentium_ii"),
    ]:
        fp = _make_x86_fp(brand, fam)
        assert validate_x86_vintage_reward_tier(arch, fp)["device_arch"] == arch


def test_bounty_16271_validated_evidence_and_simd_contradictions():
    # Bare brand without measurements -> clamp
    fp_bare = _make_x86_fp("Am486DX4", 4, measurements=False)
    assert validate_x86_vintage_reward_tier("486", fp_bare)["device_arch"] == "default"

    # Unvalidated cache_timing (missing passed=True or inconsistent ratio) -> clamp
    fp_bad_ratio = _make_x86_fp("Am486DX4", 4)
    fp_bad_ratio["checks"]["cache_timing"]["data"]["l2_l1_ratio"] = 9.5
    assert not has_validated_measurement_evidence(fp_bad_ratio)
    assert validate_x86_vintage_reward_tier("486", fp_bad_ratio)["device_arch"] == "default"

    # Modern SIMD flags (even on failed check or alias) -> clamp
    fp_sse2 = _make_x86_fp(
        "Am486DX4",
        4,
        simd_identity={"passed": False, "data": {"sample_flags": ["sse2"]}},
    )
    assert validate_x86_vintage_reward_tier("486", fp_sse2)["device_arch"] == "default"


def test_bounty_16271_down_only_disambiguation_and_no_blast_radius():
    # Plain Pentium 200 claiming pentium_mmx downgrades to pentium; MMX claiming pentium stays pentium
    fp_p5 = _make_x86_fp("Intel Pentium 200", 5)
    assert validate_x86_vintage_reward_tier("pentium_mmx", fp_p5)["device_arch"] == "pentium"
    fp_mmx = _make_x86_fp("Intel Pentium MMX 233MHz", 5)
    assert validate_x86_vintage_reward_tier("pentium", fp_mmx)["device_arch"] == "pentium"

    # Caller device_info dict is never mutated
    caller_device = {"device_family": "x86", "device_arch": "486"}
    fp_spoof = _make_x86_fp("Intel Core i7-9750H", 6)
    res = validate_x86_vintage_reward_tier("486", fp_spoof, device_info=caller_device)
    assert res["device_arch"] == "default"
    assert caller_device == {"device_family": "x86", "device_arch": "486"}


if __name__ == "__main__":
    print("\n=== arch_cross_validation unit tests ===\n")
    test_normalize_arch()
    test_g4_real_hardware()
    test_g4_flat_fingerprint_not_flagged()
    test_g4_x86_spoofing()
    test_modern_x86_real()
    test_apple_silicon_real()
    test_frozen_profile()
    test_missing_fingerprint()
    test_cpu_brand_consistency()
    test_all_profiles_valid()
    test_score_interpretation_levels()
    print("\n=== ALL TESTS PASSED ===\n")
