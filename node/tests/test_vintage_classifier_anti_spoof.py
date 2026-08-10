import pytest
from node.arch_cross_validation import validate_arch_consistency, score_cpu_brand_consistency, score_clock_consistency


def test_honest_tsc_less_486_passes():
    """Requirement 1: Genuine 486 has no RDTSC, cv=0. Must pass with score >= 0.8."""
    fingerprint = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_sse": False, "has_sse2": False, "has_avx": False}},
            "clock_drift": {"passed": False, "data": {"cv": 0}},  # TSC-less 486
            "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 20.0}}, "tone_ratios": [1.5]}},
            "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 5.0}}
        }
    }
    device_info = {"cpu_brand": "Am486DX4-100"}
    score, details = validate_arch_consistency(fingerprint, "i486", device_info)
    assert score >= 0.8
    assert "tsc_less_vintage_expected" in details["issues"] or details["scores"]["clock_consistency"] == 1.0


def test_spoofed_vintage_on_modern_hardware_fails():
    """Requirement 2: Claiming vintage 486 on modern x86 with SSE2/AVX flags fails with low score."""
    fingerprint = {
        "checks": {
            "simd_identity": {"passed": True, "data": {"has_sse2": True, "has_avx2": True, "simd_type": "sse_avx"}},
            "clock_drift": {"passed": True, "data": {"cv": 0.001}},
        }
    }
    score, details = validate_arch_consistency(fingerprint, "i486")
    assert score < 0.4
    assert any("disqualifying_feature" in issue for issue in details["issues"])


def test_anchored_pentium_brand_matching():
    """Requirement 3: Pentium III must NOT match Pentium P5 vintage tier."""
    score_p3, issues_p3 = score_cpu_brand_consistency("vintage_x86", {"cpu_brand": "Intel Pentium III 800MHz"})
    assert score_p3 < 1.0
    assert any("cpu_brand" in issue for issue in issues_p3)

    score_p5, issues_p5 = score_cpu_brand_consistency("vintage_x86", {"cpu_brand": "Intel Pentium 200 MMX"})
    assert score_p5 == 1.0


def test_failed_check_data_ignored():
    """Requirement 2: Checks with passed=False are ignored as evidence."""
    fingerprint = {
        "checks": {
            "simd_identity": {"passed": False, "data": {"has_sse2": True}},  # Failed check
        }
    }
    score, details = validate_arch_consistency(fingerprint, "vintage_x86")
    assert "disqualifying_feature:has_sse2" not in details["issues"]
