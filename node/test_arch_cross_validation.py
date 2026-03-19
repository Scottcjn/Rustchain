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

if __name__ == "__main__":
    print("\n=== arch_cross_validation unit tests ===\n")
    test_normalize_arch()
    test_g4_real_hardware()
    test_g4_x86_spoofing()
    test_modern_x86_real()
    test_apple_silicon_real()
    test_frozen_profile()
    test_missing_fingerprint()
    test_cpu_brand_consistency()
    test_all_profiles_valid()
    test_score_interpretation_levels()
    print("\n=== ALL TESTS PASSED ===\n")
