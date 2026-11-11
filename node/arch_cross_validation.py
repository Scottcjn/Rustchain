#!/usr/bin/env python3
"""
RIP-PoA Architecture Cross-Validation
=====================================
Server-side verification that a miner's claimed `device_arch` matches their fingerprint data.
If someone claims G4 but their cache timing profile looks like Zen 4, they get flagged.

Implements: https://github.com/Scottcjn/rustchain-bounties/issues/17
Bounty: 50 RTC
"""

import json
import os
import statistics
from typing import Dict, List, Optional, Tuple, Any

# ─────────────────────────────────────────────────────────────────
# Architecture Profile Database
# ─────────────────────────────────────────────────────────────────
ARCHITECTURE_PROFILES = {
    "g4": {
        "simd_type": "altivec",
        "simd_detect": "has_altivec",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": False},
        "cv_range": (0.0001, 0.15),
        "thermal_drift_range": (0.5, 15.0),
        "clock_drift_magnitude": "medium",
        "expected_cpu_brands": ["motorola", "freescale", "nxp"],
        "disqualifying_features": ["has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.8,
        "cache_tone_max": 8.0,
    },
    "g5": {
        "simd_type": "altivec",
        "simd_detect": "has_altivec",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": True},
        "cv_range": (0.0001, 0.12),
        "thermal_drift_range": (0.3, 12.0),
        "clock_drift_magnitude": "low",
        "expected_cpu_brands": ["motorola", "ibm"],
        "disqualifying_features": ["has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.7,
        "cache_tone_max": 10.0,
    },
    "g3": {
        "simd_type": "none",
        "simd_detect": None,
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": False, "4096KB": False},
        "cv_range": (0.0001, 0.20),
        "thermal_drift_range": (0.3, 18.0),
        "clock_drift_magnitude": "high",
        "expected_cpu_brands": ["motorola", "freescale"],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.5,
        "cache_tone_max": 6.0,
    },
    "modern_x86": {
        "simd_type": "sse_avx",
        "simd_detect": "has_sse2",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": True},
        "cv_range": (0.0001, 0.008),
        "thermal_drift_range": (0.1, 5.0),
        "clock_drift_magnitude": "very_low",
        "expected_cpu_brands": ["intel", "amd"],
        "disqualifying_features": ["has_altivec", "has_neon"],
        "cache_tone_min": 0.5,
        "cache_tone_max": 5.0,
        "required_features": ["has_sse2"],
    },
    "apple_silicon": {
        "simd_type": "neon",
        "simd_detect": "has_neon",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": True},
        "cv_range": (0.0001, 0.006),
        "thermal_drift_range": (0.1, 4.0),
        "clock_drift_magnitude": "very_low",
        "expected_cpu_brands": ["apple"],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512"],
        "cache_tone_min": 0.4,
        "cache_tone_max": 4.0,
        "required_features": ["has_neon"],
    },
    "arm64": {
        "simd_type": "neon",
        "simd_detect": "has_neon",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": True},
        "cv_range": (0.0001, 0.01),
        "thermal_drift_range": (0.1, 6.0),
        "clock_drift_magnitude": "low",
        "expected_cpu_brands": [],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512"],
        "cache_tone_min": 0.4,
        "cache_tone_max": 6.0,
    },
    "retro_x86": {
        "simd_type": "sse_avx",
        "simd_detect": "has_sse",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": False, "4096KB": False},
        "cv_range": (0.0001, 0.015),
        "thermal_drift_range": (0.2, 8.0),
        "clock_drift_magnitude": "low",
        "expected_cpu_brands": ["intel", "amd", "via"],
        "disqualifying_features": ["has_altivec", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.5,
        "cache_tone_max": 5.0,
    },
    "vintage_x86": {
        "simd_type": "none",
        "simd_detect": None,
        "cache_sizes": {"4KB": True, "32KB": False, "256KB": False, "1024KB": False, "4096KB": False},
        "cv_range": (0.0001, 0.03),
        "thermal_drift_range": (0.5, 15.0),
        "clock_drift_magnitude": "high",
        "expected_cpu_brands": ["intel", "amd", "cyrix", "nexgen"],
        "disqualifying_features": ["has_altivec", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.3,
        "cache_tone_max": 4.0,
    },
    "power8": {
        "simd_type": "altivec",
        "simd_detect": "has_altivec",
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": True},
        "cv_range": (0.0001, 0.01),
        "thermal_drift_range": (0.1, 5.0),
        "clock_drift_magnitude": "low",
        "expected_cpu_brands": ["ibm"],
        "disqualifying_features": ["has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.5,
        "cache_tone_max": 6.0,
    },
    "sparc": {
        "simd_type": "none",
        "simd_detect": None,
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": True},
        "cv_range": (0.0001, 0.02),
        "thermal_drift_range": (0.3, 10.0),
        "clock_drift_magnitude": "medium",
        "expected_cpu_brands": ["sun", "oracle"],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.5,
        "cache_tone_max": 7.0,
    },
    "68k": {
        "simd_type": "none",
        "simd_detect": None,
        "cache_sizes": {"4KB": True, "32KB": False, "256KB": False, "1024KB": False, "4096KB": False},
        "cv_range": (0.0001, 0.25),
        "thermal_drift_range": (1.0, 20.0),
        "clock_drift_magnitude": "very_high",
        "expected_cpu_brands": ["motorola"],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.2,
        "cache_tone_max": 3.0,
    },
    "amiga_68k": {
        "simd_type": "none",
        "simd_detect": None,
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": False, "1024KB": False, "4096KB": False},
        "cv_range": (0.0001, 0.25),
        "thermal_drift_range": (1.0, 20.0),
        "clock_drift_magnitude": "very_high",
        "expected_cpu_brands": ["motorola"],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.2,
        "cache_tone_max": 3.5,
    },
    "riscv": {
        "simd_type": "none",
        "simd_detect": None,
        "cache_sizes": {"4KB": True, "32KB": True, "256KB": True, "1024KB": True, "4096KB": False},
        "cv_range": (0.0001, 0.015),
        "thermal_drift_range": (0.2, 8.0),
        "clock_drift_magnitude": "low",
        "expected_cpu_brands": [],
        "disqualifying_features": ["has_altivec", "has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512", "has_neon"],
        "cache_tone_min": 0.4,
        "cache_tone_max": 6.0,
    },
}

ARCH_ALIASES = {
    "powerpc": "g3", "ppc": "g3", "powerpc g4": "g4", "power macintosh": "g4", "powerbook": "g4",
    "imac": "g3", "powerpc g5": "g5", "power mac g5": "g5", "xserve g5": "g5",
    "apple m1": "apple_silicon", "apple m2": "apple_silicon", "apple m3": "apple_silicon",
    "m1": "apple_silicon", "m2": "apple_silicon", "m3": "apple_silicon",
    "apple_silicon": "apple_silicon",
    "aarch64": "arm64", "arm64": "arm64", "arm": "arm64",
    "x86_64": "modern_x86", "x86-64": "modern_x86", "amd64": "modern_x86",
    "i386": "vintage_x86", "i486": "vintage_x86",
    "i686": "retro_x86", "pentium": "retro_x86", "pentium 4": "retro_x86", "core 2": "retro_x86",
    "sparc": "sparc", "sun": "sparc",
    "68k": "68k", "m68k": "68k", "motorola 68k": "68k",
    "amiga": "amiga_68k",
    "power8": "power8", "power9": "power8", "powerpc 970": "g5",
    "riscv": "riscv", "rv64": "riscv",
}


def normalize_arch(arch: str) -> Optional[str]:
    if not arch or not isinstance(arch, str):
        return None
    arch_lower = arch.lower().strip()
    if arch_lower in ARCH_ALIASES:
        return ARCH_ALIASES[arch_lower]
    if arch_lower in ARCHITECTURE_PROFILES:
        return arch_lower
    for key in ARCHITECTURE_PROFILES:
        if key in arch_lower or arch_lower in key:
            return key
    return None


def extract_simd_features(simd_data: Dict) -> Dict[str, bool]:
    if not simd_data or not isinstance(simd_data, dict):
        return {}
    data = simd_data.get("data", simd_data) if isinstance(simd_data, dict) else {}
    if not isinstance(data, dict):
        data = simd_data
    features = {}
    for feat in ["has_sse", "has_sse2", "has_sse3", "has_sse4", "has_avx", "has_avx2", "has_avx512",
                 "has_x87", "has_mmx", "has_neon", "has_altivec"]:
        if data.get(feat) is not None:
            features[feat] = bool(data.get(feat))
    simd_type = data.get("simd_type", "")
    if simd_type:
        features["simd_type"] = simd_type
    return features


def extract_cache_features(cache_data: Dict) -> Dict[str, Any]:
    if not cache_data or not isinstance(cache_data, dict):
        return {}
    data = cache_data.get("data", cache_data) if isinstance(cache_data, dict) else {}
    if not isinstance(data, dict):
        data = cache_data
    features = {}
    latencies = data.get("latencies", {})
    if isinstance(latencies, dict):
        for level in ["4KB", "32KB", "256KB", "1024KB", "4096KB", "16384KB"]:
            key = f"{level}_present"
            features[key] = level in latencies and "error" not in latencies.get(level, {})
        tone_ratios = data.get("tone_ratios", [])
        if tone_ratios and len(tone_ratios) > 0:
            features["cache_tone_mean"] = statistics.mean(tone_ratios)
            features["cache_tone_stdev"] = statistics.stdev(tone_ratios) if len(tone_ratios) > 1 else 0
        else:
            features["cache_tone_mean"] = 0
            features["cache_tone_stdev"] = 0
    return features


def extract_clock_features(clock_data: Dict) -> Dict[str, Any]:
    if not clock_data or not isinstance(clock_data, dict):
        return {}
    data = clock_data.get("data", clock_data) if isinstance(clock_data, dict) else {}
    if not isinstance(data, dict):
        data = clock_data
    return {
        "cv": data.get("cv", 0),
        "samples": data.get("samples", 0),
        "drift_stdev": data.get("drift_stdev", 0),
        "mean_ns": data.get("mean_ns", 0),
    }


def extract_thermal_features(thermal_data: Dict) -> Dict[str, Any]:
    if not thermal_data or not isinstance(thermal_data, dict):
        return {}
    data = thermal_data.get("data", thermal_data) if isinstance(thermal_data, dict) else {}
    if not isinstance(data, dict):
        data = thermal_data
    return {
        "thermal_drift_pct": data.get("thermal_drift_pct", 0),
        "recovery_pct": data.get("recovery_pct", 0),
    }


def extract_all_features(fingerprint: Dict) -> Dict[str, Any]:
    all_features = {}
    checks = fingerprint.get("checks", {}) if isinstance(fingerprint, dict) else {}
    if not checks and isinstance(fingerprint, dict):
        checks = {k: v for k, v in fingerprint.items()
                  if k in ("clock_drift", "cache_timing", "simd_identity", "thermal_drift",
                           "instruction_jitter", "anti_emulation")}
    if isinstance(checks, dict):
        for check_name, check_value in checks.items():
            if isinstance(check_value, dict):
                # A wrapped check nests its payload under "data"; a flat check IS
                # the payload (no "data" key). Fall back to the value itself so
                # the flat-fingerprint branch above is not silently emptied —
                # matching the X.get("data", X) pattern the extract_* helpers use.
                data = check_value.get("data", check_value)
                if isinstance(data, dict):
                    all_features[check_name] = data
            elif isinstance(check_value, bool):
                all_features[check_name] = {"passed": check_value}
    return all_features


def score_simd_consistency(claimed_arch: str, simd_features: Dict) -> Tuple[float, List[str]]:
    profile_key = normalize_arch(claimed_arch)
    if not profile_key or profile_key not in ARCHITECTURE_PROFILES:
        return 0.5, ["unknown_architecture"]
    profile = ARCHITECTURE_PROFILES[profile_key]
    disqualifying = profile.get("disqualifying_features", [])
    required = profile.get("required_features", [])
    issues = []
    score = 1.0
    for feat in disqualifying:
        if simd_features.get(feat, False):
            issues.append(f"disqualifying_feature:{feat}")
            score -= 0.5
    for feat in required:
        if not simd_features.get(feat, False):
            issues.append(f"missing_required:{feat}")
            score -= 0.2
    expected = profile.get("simd_type", "none")
    if expected == "altivec" and not simd_features.get("has_altivec"):
        issues.append("expected_altivec_missing")
        score -= 0.3
    elif expected == "sse_avx" and not (simd_features.get("has_sse2") or simd_features.get("has_sse")):
        issues.append("expected_sse_missing")
        score -= 0.3
    elif expected == "neon" and not simd_features.get("has_neon"):
        issues.append("expected_neon_missing")
        score -= 0.3
    return max(0.0, min(1.0, score)), issues


def score_cache_consistency(claimed_arch: str, cache_features: Dict, clock_cv: float = 0) -> Tuple[float, List[str]]:
    profile_key = normalize_arch(claimed_arch)
    if not profile_key or profile_key not in ARCHITECTURE_PROFILES:
        return 0.5, ["unknown_architecture"]
    profile = ARCHITECTURE_PROFILES[profile_key]
    expected_cache = profile.get("cache_sizes", {})
    tone_min = profile.get("cache_tone_min", 0.3)
    tone_max = profile.get("cache_tone_max", 6.0)
    issues = []
    score = 1.0
    tone_mean = cache_features.get("cache_tone_mean", 0)
    if tone_mean > 0:
        if tone_mean < tone_min:
            issues.append(f"cache_tone_too_low:{tone_mean:.2f}")
            score -= 0.3
        elif tone_mean > tone_max:
            issues.append(f"cache_tone_too_high:{tone_mean:.2f}")
            score -= 0.3
    for level, expected_present in expected_cache.items():
        key = f"{level}_present"
        actually_present = cache_features.get(key, False)
        if expected_present and not actually_present:
            issues.append(f"expected_cache_{level}_not_detected")
            score -= 0.05
        elif not expected_present and actually_present:
            issues.append(f"unexpected_cache_{level}_detected")
            score -= 0.15
    return max(0.0, min(1.0, score)), issues


def score_clock_consistency(claimed_arch: str, clock_features: Dict) -> Tuple[float, List[str]]:
    profile_key = normalize_arch(claimed_arch)
    if not profile_key or profile_key not in ARCHITECTURE_PROFILES:
        return 0.5, ["unknown_architecture"]
    profile = ARCHITECTURE_PROFILES[profile_key]
    cv_range = profile.get("cv_range", (0.0001, 1.0))
    drift_magnitude = profile.get("clock_drift_magnitude", "medium")
    issues = []
    score = 1.0
    cv = clock_features.get("cv", 0)
    if cv == 0:
        # Bounty #16271 Req #1: Honest TSC-less vintage x86 (386/486) has no RDTSC
        if (claimed_arch or "").strip().lower() in ("386", "486", "i386", "i486", "vintage_x86"):
            return 1.0, []
        issues.append("no_clock_cv_data")
        return 0.3, issues
    cv_min, cv_max = cv_range
    if cv < cv_min:
        issues.append(f"cv_too_low:{cv:.6f}")
        score -= 0.4
    elif cv > cv_max:
        issues.append(f"cv_too_high:{cv:.6f}")
        score -= 0.3
    if drift_magnitude in ("very_high", "high"):
        if cv < 0.01:
            issues.append(f"vintage_arch_{claimed_arch}_too_stable:{cv:.6f}")
            score -= 0.3
    elif drift_magnitude in ("very_low", "low"):
        if cv > 0.03:
            issues.append(f"modern_arch_{claimed_arch}_too_noisy:{cv:.6f}")
            score -= 0.3
    elif drift_magnitude == "medium":
        # G4 class: very low cv suggests modern VM or clock-locked environment
        if cv < 0.005:
            issues.append(f"vintage_arch_{claimed_arch}_too_stable:{cv:.6f}")
            score -= 0.3
    return max(0.0, min(1.0, score)), issues


def score_thermal_consistency(claimed_arch: str, thermal_features: Dict) -> Tuple[float, List[str]]:
    profile_key = normalize_arch(claimed_arch)
    if not profile_key or profile_key not in ARCHITECTURE_PROFILES:
        return 0.5, ["unknown_architecture"]
    profile = ARCHITECTURE_PROFILES[profile_key]
    drift_range = profile.get("thermal_drift_range", (0.1, 20.0))
    issues = []
    score = 1.0
    drift_pct = abs(thermal_features.get("thermal_drift_pct", 0))
    drift_min, drift_max = drift_range
    if drift_pct < drift_min:
        issues.append(f"thermal_drift_too_low:{drift_pct:.2f}")
        score -= 0.2
    elif drift_pct > drift_max:
        issues.append(f"thermal_drift_too_high:{drift_pct:.2f}")
        score -= 0.2
    return max(0.0, min(1.0, score)), issues


def score_cpu_brand_consistency(claimed_arch: str, device_info: Dict) -> Tuple[float, List[str]]:
    profile_key = normalize_arch(claimed_arch)
    if not profile_key or profile_key not in ARCHITECTURE_PROFILES:
        return 0.5, ["unknown_architecture"]
    profile = ARCHITECTURE_PROFILES[profile_key]
    expected_brands = profile.get("expected_cpu_brands", [])
    if not expected_brands:
        return 1.0, []
    issues = []
    score = 1.0
    cpu_brand = ""
    for key in ["cpu_brand", "processor", "cpu_model", "brand"]:
        val = device_info.get(key, "")
        if val and isinstance(val, str):
            cpu_brand = val.lower()
            break
    if cpu_brand:
        brand_matches = any(brand.lower() in cpu_brand for brand in expected_brands)
        if not brand_matches:
            issues.append(f"cpu_brand_mismatch:brand={cpu_brand}")
            score -= 0.3
    return max(0.0, min(1.0, score)), issues


def validate_arch_consistency(
    fingerprint: Dict,
    claimed_arch: str,
    device_info: Optional[Dict] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Main architecture cross-validation function.
    Compares a miner's claimed `device_arch` against their fingerprint data.
    Returns (arch_validation_score: float, details: dict)

    Score interpretation:
      1.0       = Perfect match
      0.8-0.99  = Minor anomalies, acceptable
      0.5-0.79  = Some inconsistencies, review recommended
      0.3-0.49  = Major inconsistencies, likely spoofing
      0.0-0.29  = Clear spoofing detected
    """
    device_info = device_info or {}
    details = {
        "claimed_arch": claimed_arch,
        "normalized_arch": normalize_arch(claimed_arch),
        "scores": {},
        "issues": [],
        "overall_flags": [],
    }
    all_features = extract_all_features(fingerprint)
    simd_data = all_features.get("simd_identity", {})
    cache_data = all_features.get("cache_timing", {})
    clock_data = all_features.get("clock_drift", {})
    thermal_data = all_features.get("thermal_drift", {})
    simd_features = extract_simd_features(simd_data)
    cache_features = extract_cache_features(cache_data)
    clock_features = extract_clock_features(clock_data)
    thermal_features = extract_thermal_features(thermal_data)
    simd_score, simd_issues = score_simd_consistency(claimed_arch, simd_features)
    cache_score, cache_issues = score_cache_consistency(claimed_arch, cache_features, clock_cv=clock_features.get("cv", 0))
    clock_score, clock_issues = score_clock_consistency(claimed_arch, clock_features)
    thermal_score, thermal_issues = score_thermal_consistency(claimed_arch, thermal_features)
    brand_score, brand_issues = score_cpu_brand_consistency(claimed_arch, device_info)
    details["scores"] = {
        "simd_consistency": round(simd_score, 3),
        "cache_consistency": round(cache_score, 3),
        "clock_consistency": round(clock_score, 3),
        "thermal_consistency": round(thermal_score, 3),
        "cpu_brand_consistency": round(brand_score, 3),
    }
    all_issues = simd_issues + cache_issues + clock_issues + thermal_issues + brand_issues
    details["issues"] = all_issues
    weights = {"simd_consistency": 0.30, "cache_consistency": 0.25, "clock_consistency": 0.20,
               "thermal_consistency": 0.15, "cpu_brand_consistency": 0.10}
    overall_score = sum(details["scores"][key] * weights[key] for key in weights)
    overall_score = round(overall_score, 3)
    details["overall_score"] = overall_score
    if overall_score < 0.3:
        details["overall_flags"].append("CRITICAL: strong arch spoofing detected")
    elif overall_score < 0.5:
        details["overall_flags"].append("WARNING: major arch inconsistencies")
    elif overall_score < 0.7:
        details["overall_flags"].append("REVIEW: some arch inconsistencies")
    if overall_score >= 0.9:
        details["interpretation"] = "EXCELLENT: fingerprint data strongly matches claimed arch"
    elif overall_score >= 0.8:
        details["interpretation"] = "GOOD: minor anomalies within tolerance"
    elif overall_score >= 0.7:
        details["interpretation"] = "ACCEPTABLE: some inconsistencies, review recommended"
    elif overall_score >= 0.5:
        details["interpretation"] = "SUSPICIOUS: significant arch mismatch"
    elif overall_score >= 0.3:
        details["interpretation"] = "LIKELY_SPOOFED: major inconsistencies detected"
    else:
        details["interpretation"] = "CONFIRMED_SPOOFED: clear arch mismatch"
    return overall_score, details



# ─────────────────────────────────────────────────────────────────
# Bounty #16271: Hardened x86 Vintage-Arch Reward Validation (Anti-Spoof)
# ─────────────────────────────────────────────────────────────────
import re as _re

X86_VINTAGE_TIER_PROFILES = {
    "386": {"family": 3, "max_simd": "none", "rank": 60, "multiplier": 2.5},
    "486": {"family": 4, "max_simd": "none", "rank": 50, "multiplier": 2.0},
    "pentium": {"family": 5, "max_simd": "none", "rank": 40, "multiplier": 1.6},
    "pentium_mmx": {"family": 5, "max_simd": "mmx", "rank": 35, "multiplier": 1.5},
    "pentium_pro": {"family": 6, "max_simd": "none", "rank": 32, "multiplier": 1.5},
    "pentium_ii": {"family": 6, "max_simd": "mmx", "rank": 30, "multiplier": 1.4},
    "pentium_iii": {"family": 6, "max_simd": "sse", "rank": 25, "multiplier": 1.3},
    "pentium_m_banias": {"family": 6, "max_simd": "sse2", "rank": 20, "multiplier": 1.25},
    "pentium_m_dothan": {"family": 6, "max_simd": "sse2", "rank": 18, "multiplier": 1.2},
    "pentium_m_yonah": {"family": 6, "max_simd": "sse3", "rank": 15, "multiplier": 1.15},
    "pentium_m": {"family": 6, "max_simd": "sse2", "rank": 15, "multiplier": 1.15},
}

_SIMD_GENERATION_ORDER = {
    "none": 0,
    "mmx": 1,
    "sse": 2,
    "sse2": 3,
    "sse3": 4,
    "ssse3": 5,
    "sse4": 6,
    "avx": 7,
    "modern_non_x86": 99,
}

# Anchored, case-insensitive brand patterns (order matters: specific subtypes before general 'pentium')
_ANCHORED_X86_BRAND_PATTERNS = [
    (_re.compile(r"\b(?:i?386|am386[a-z0-9/-]*|cx386[a-z0-9/-]*)\b", _re.IGNORECASE), "386", 3),
    (_re.compile(r"\b(?:i?486(?:\s*dx/?[24]?)?|am486[a-z0-9/-]*|am5x86[a-z0-9/-]*|cx486[a-z0-9/-]*|cyrix\s+cx486[a-z0-9/-]*)\b", _re.IGNORECASE), "486", 4),
    (_re.compile(r"\bpentium(?:\(r\))?\s+(?:iii|3)\b", _re.IGNORECASE), "pentium_iii", 6),
    (_re.compile(r"\b(?:mobile\s+)?pentium(?:\(r\))?\s+(?:ii|2)\b", _re.IGNORECASE), "pentium_ii", 6),
    (_re.compile(r"\bpentium(?:\(r\))?\s+pro\b", _re.IGNORECASE), "pentium_pro", 6),
    (_re.compile(r"\bpentium(?:\(r\))?\s+m\b", _re.IGNORECASE), "pentium_m", 6),
    (_re.compile(r"\bpentium(?:\(r\))?(?:\s+w/\s+|\s+with\s+|\s+)mmx\b", _re.IGNORECASE), "pentium_mmx", 5),
    # Reject Pentium 4 / D / Dual-Core / Extreme / Celeron / Xeon / Core before plain family-5 Pentium
    (_re.compile(r"\bpentium(?:\(r\))?\s+(?:4|iv|d|dual[-\s]core|extreme|g\d+|n\d+|j\d+|silver|gold)\b", _re.IGNORECASE), "modern_x86", None),
    (_re.compile(r"\b(?:core(?:\(tm\))?\s*(?:2|i[3579]|ultra)|ryzen|epyc|threadripper|xeon|apple\s+m[1-9])\b", _re.IGNORECASE), "modern_x86", None),
    # Classic P5 Pentium (e.g. "Pentium 200", "Pentium 75 - 200", "Pentium 60/66", "Intel Pentium")
    (_re.compile(r"\bpentium(?:\(r\))?(?:\s+(?:60/66|75\s*-\s*200|\d{2,3}(?:\s*mhz)?))?(?!\s*(?:iii|ii|iv|pro|mmx|m\b|4|d\b|dual|extreme|g\d|n\d|j\d|silver|gold))\b", _re.IGNORECASE), "pentium", 5),
]


def classify_anchored_x86_vintage_brand(cpu_brand: str, cpu_family: Any = None) -> Optional[str]:
    """
    Anchored, case-insensitive classification of a vintage x86 CPU brand + family.
    Returns canonical vintage tier key (e.g. '486', 'pentium', 'pentium_mmx', 'pentium_iii')
    or None if the brand/family is modern, mismatched, or unverified.
    """
    if not cpu_brand or not isinstance(cpu_brand, str):
        return None
    brand_clean = cpu_brand.strip()
    if not brand_clean:
        return None

    parsed_family: Optional[int] = None
    if cpu_family is not None and not isinstance(cpu_family, bool):
        try:
            parsed_family = int(str(cpu_family).strip())
        except (ValueError, TypeError):
            parsed_family = None

    for pattern, tier_arch, expected_family in _ANCHORED_X86_BRAND_PATTERNS:
        if pattern.search(brand_clean):
            if tier_arch == "modern_x86":
                return None
            if expected_family is not None:
                if parsed_family is None or parsed_family != expected_family:
                    return None
            return tier_arch
    return None


def _is_positive_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and val > 0


def has_validated_measurement_evidence(fingerprint: Dict) -> bool:
    """
    Requirement #2 (#16271): Corroboration must come from a check that explicitly
    `passed is True` with real numeric measurements (and server-consistent ratios),
    never from an unvalidated dict, boolean-only metric, or legacy array shape.
    """
    if not isinstance(fingerprint, dict):
        return False
    checks = fingerprint.get("checks")
    if not isinstance(checks, dict):
        return False

    # 1. Cache timing: requires explicit passed=True and positive l1_ns & l2_ns with consistent l2_l1_ratio
    cache_chk = checks.get("cache_timing")
    if isinstance(cache_chk, dict) and cache_chk.get("passed") is True:
        cdata = cache_chk.get("data")
        if isinstance(cdata, dict):
            l1 = cdata.get("l1_ns")
            l2 = cdata.get("l2_ns")
            ratio = cdata.get("l2_l1_ratio")
            if _is_positive_number(l1) and _is_positive_number(l2):
                expected_ratio = l2 / l1
                if ratio is None or (_is_positive_number(ratio) and abs(float(ratio) - expected_ratio) <= 0.5):
                    return True
            latencies = cdata.get("latencies")
            tone_ratios = cdata.get("tone_ratios")
            if isinstance(latencies, dict) and isinstance(tone_ratios, list) and len(tone_ratios) > 0:
                if all(_is_positive_number(r) for r in tone_ratios):
                    return True

    # 2. Thermal drift: requires explicit passed=True and positive numeric drift/stdev measurement
    thermal_chk = checks.get("thermal_drift")
    if isinstance(thermal_chk, dict) and thermal_chk.get("passed") is True:
        tdata = thermal_chk.get("data")
        if isinstance(tdata, dict):
            if _is_positive_number(tdata.get("thermal_drift_pct")) or _is_positive_number(tdata.get("drift_stdev")):
                return True

    # 3. Instruction jitter: requires explicit passed=True and positive numeric jitter measurement
    jitter_chk = checks.get("instruction_jitter")
    if isinstance(jitter_chk, dict) and jitter_chk.get("passed") is True:
        jdata = jitter_chk.get("data")
        if isinstance(jdata, dict):
            if _is_positive_number(jdata.get("jitter_ns")) or _is_positive_number(jdata.get("cv")):
                return True

    return False


def _detect_highest_observed_simd_generation(fingerprint: Dict) -> Tuple[int, List[str]]:
    """
    Inspect all SIMD-bearing checks (even failed checks and aliases like `simd_bias`
    or `device_age_oracle.flags_sample`) to extract negative/contradictory SIMD evidence.
    """
    highest = 0
    contradictions: List[str] = []
    if not isinstance(fingerprint, dict):
        return highest, contradictions
    checks = fingerprint.get("checks")
    if not isinstance(checks, dict):
        return highest, contradictions

    for chk_name, chk_obj in checks.items():
        if not isinstance(chk_obj, dict):
            continue
        data = chk_obj.get("data")
        if not isinstance(data, dict):
            continue

        if data.get("has_altivec") is True or data.get("has_neon") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["modern_non_x86"])
            contradictions.append(f"{chk_name}:non_x86_simd")
        if data.get("has_avx512") is True or data.get("has_avx2") is True or data.get("has_avx") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["avx"])
            contradictions.append(f"{chk_name}:avx")
        if data.get("has_sse4") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["sse4"])
        if data.get("has_sse3") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["sse3"])
        if data.get("has_sse2") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["sse2"])
        if data.get("has_sse") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["sse"])
        if data.get("has_mmx") is True:
            highest = max(highest, _SIMD_GENERATION_ORDER["mmx"])

        for flag_list_key in ("sample_flags", "flags_sample", "flags"):
            raw_flags = data.get(flag_list_key)
            if isinstance(raw_flags, list):
                for flg in raw_flags:
                    if not isinstance(flg, str):
                        continue
                    fl = flg.strip().lower()
                    if fl in ("avx", "avx2", "avx512", "avx512f"):
                        highest = max(highest, _SIMD_GENERATION_ORDER["avx"])
                    elif fl in ("sse4", "sse4_1", "sse4_2", "sse4.1", "sse4.2", "sse4a"):
                        highest = max(highest, _SIMD_GENERATION_ORDER["sse4"])
                    elif fl in ("ssse3",):
                        highest = max(highest, _SIMD_GENERATION_ORDER["ssse3"])
                    elif fl in ("sse3", "pni"):
                        highest = max(highest, _SIMD_GENERATION_ORDER["sse3"])
                    elif fl == "sse2":
                        highest = max(highest, _SIMD_GENERATION_ORDER["sse2"])
                    elif fl in ("sse", "xmm"):
                        highest = max(highest, _SIMD_GENERATION_ORDER["sse"])
                    elif fl == "mmx":
                        highest = max(highest, _SIMD_GENERATION_ORDER["mmx"])
                    elif fl in ("neon", "altivec", "asimd"):
                        highest = max(highest, _SIMD_GENERATION_ORDER["modern_non_x86"])

    return highest, contradictions


def validate_x86_vintage_reward_tier(
    claimed_arch: str,
    fingerprint: Dict,
    device_info: Optional[Dict] = None,
    measurement_report_verified: bool = True,
) -> Dict[str, str]:
    """
    Harden x86 vintage-arch reward validation (#16271) for the enroll-weight path:
    1. Does NOT gate 386/486 on `fingerprint_passed` or `clock_drift` (honest TSC-less vintage keeps tier).
    2. Requires explicitly passed measurement-bearing evidence + complete `device_age_oracle` & `simd_identity`.
    3. Uses anchored, case-insensitive brand + cpu_family matching.
    4. Does NOT mutate `device_info` (zero blast radius outside enroll-weight).
    5. Disambiguates tiers downward only (`pentium_mmx` -> `pentium` if brand is plain Pentium;
       `pentium_m_banias` -> `pentium_m_yonah` when undifferentiated Pentium M).
    """
    base_family = "x86"
    if isinstance(device_info, dict) and isinstance(device_info.get("device_family"), str):
        base_family = device_info["device_family"]

    claimed_norm = (claimed_arch or "").strip().lower()
    if claimed_norm in ("i386",):
        claimed_norm = "386"
    elif claimed_norm in ("i486",):
        claimed_norm = "486"

    if claimed_norm not in X86_VINTAGE_TIER_PROFILES:
        return {"device_family": base_family, "device_arch": claimed_arch or "default"}

    if not measurement_report_verified:
        return {"device_family": base_family, "device_arch": "default"}

    if not isinstance(fingerprint, dict) or not isinstance(fingerprint.get("checks"), dict):
        return {"device_family": base_family, "device_arch": "default"}

    checks = fingerprint["checks"]

    # Require validated measurement evidence (cache_timing / thermal_drift / instruction_jitter)
    if not has_validated_measurement_evidence(fingerprint):
        return {"device_family": base_family, "device_arch": "default"}

    # Require explicit passed device_age_oracle with flags_sample present
    oracle = checks.get("device_age_oracle")
    if not isinstance(oracle, dict) or oracle.get("passed") is not True:
        return {"device_family": base_family, "device_arch": "default"}
    oracle_data = oracle.get("data")
    if not isinstance(oracle_data, dict) or not isinstance(oracle_data.get("flags_sample"), list):
        return {"device_family": base_family, "device_arch": "default"}

    # Require explicit passed simd_identity with complete observation (sample_flags covers simd_flags_count)
    simd_chk = checks.get("simd_identity")
    if not isinstance(simd_chk, dict) or simd_chk.get("passed") is not True:
        return {"device_family": base_family, "device_arch": "default"}
    simd_data = simd_chk.get("data")
    if not isinstance(simd_data, dict):
        return {"device_family": base_family, "device_arch": "default"}
    sample_flags = simd_data.get("sample_flags")
    flags_count = simd_data.get("simd_flags_count")
    if isinstance(flags_count, int) and isinstance(sample_flags, list):
        if flags_count > len(sample_flags) and len(sample_flags) <= 1:
            return {"device_family": base_family, "device_arch": "default"}

    # Anchored brand + family verification from validated oracle
    cpu_model = oracle_data.get("cpu_model") or ""
    cpu_family = oracle_data.get("cpu_family")
    corroborated_tier = classify_anchored_x86_vintage_brand(cpu_model, cpu_family)
    if not corroborated_tier:
        return {"device_family": base_family, "device_arch": "default"}

    # Check negative/contradictory SIMD evidence across ALL checks
    highest_simd, _ = _detect_highest_observed_simd_generation(fingerprint)
    claimed_profile = X86_VINTAGE_TIER_PROFILES[claimed_norm]
    max_allowed_simd = _SIMD_GENERATION_ORDER[claimed_profile["max_simd"]]
    if highest_simd > max_allowed_simd:
        return {"device_family": base_family, "device_arch": "default"}

    # Tier compatibility & down-only disambiguation (Req #5)
    if claimed_norm in ("386", "486", "pentium_pro", "pentium_ii", "pentium_iii"):
        if corroborated_tier != claimed_norm:
            return {"device_family": base_family, "device_arch": "default"}
        return {"device_family": base_family, "device_arch": claimed_norm}

    if claimed_norm in ("pentium", "pentium_mmx"):
        if corroborated_tier not in ("pentium", "pentium_mmx"):
            return {"device_family": base_family, "device_arch": "default"}
        # Down-only: if miner claims pentium_mmx on plain pentium, downgrade to pentium;
        # if miner claims pentium on pentium_mmx, never inflate (keep pentium).
        if claimed_norm == "pentium_mmx" and corroborated_tier == "pentium":
            return {"device_family": base_family, "device_arch": "pentium"}
        return {"device_family": base_family, "device_arch": claimed_norm}

    if claimed_norm in ("pentium_m", "pentium_m_banias", "pentium_m_dothan", "pentium_m_yonah"):
        if corroborated_tier != "pentium_m":
            return {"device_family": base_family, "device_arch": "default"}
        # Undifferentiated "Intel Pentium M" without clock/model suffix downgrades to lowest subtype
        if not _re.search(r"\d+\s*(?:mhz|ghz)", cpu_model, _re.IGNORECASE):
            return {"device_family": base_family, "device_arch": "pentium_m_yonah"}
        return {"device_family": base_family, "device_arch": claimed_norm}

    return {"device_family": base_family, "device_arch": "default"}


if __name__ == "__main__":
    print("Architecture Cross-Validation Tests")
    print("=" * 60)
    test_cases = [
        {
            "name": "Correct G4 claim",
            "claimed_arch": "g4",
            "fingerprint": {
                "checks": {
                    "simd_identity": {"passed": True, "data": {"has_altivec": True, "has_sse": False, "has_neon": False, "simd_type": "altivec"}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 200}},
                    "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 2.0}, "256KB": {"random_ns": 5.0}, "1024KB": {"random_ns": 10.0}}, "tone_ratios": [2.0, 2.5, 2.0]}},
                    "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 5.0}}
                }
            }
        },
        {
            "name": "G4 claim but x86 fingerprints (spoofing)",
            "claimed_arch": "g4",
            "fingerprint": {
                "checks": {
                    "simd_identity": {"passed": True, "data": {"has_sse2": True, "has_avx": True, "has_altivec": False, "simd_type": "sse_avx"}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.001, "samples": 200}},
                    "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.5}, "256KB": {"random_ns": 3.0}, "4096KB": {"random_ns": 15.0}}, "tone_ratios": [1.5, 2.0, 5.0]}},
                }
            }
        },
        {
            "name": "Modern x86 correct",
            "claimed_arch": "modern_x86",
            "fingerprint": {
                "checks": {
                    "simd_identity": {"passed": True, "data": {"has_sse2": True, "has_avx2": True, "has_altivec": False, "has_neon": False, "simd_type": "sse_avx"}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.002, "samples": 200}},
                    "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.5}, "256KB": {"random_ns": 3.0}, "1024KB": {"random_ns": 8.0}, "4096KB": {"random_ns": 20.0}}, "tone_ratios": [1.5, 2.0, 2.5, 2.5]}},
                }
            }
        },
        {
            "name": "Apple Silicon correct",
            "claimed_arch": "apple_silicon",
            "fingerprint": {
                "checks": {
                    "simd_identity": {"passed": True, "data": {"has_neon": True, "has_altivec": False, "has_sse": False, "simd_type": "neon"}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.003, "samples": 200}},
                    "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 1.0}, "32KB": {"random_ns": 1.2}, "256KB": {"random_ns": 2.5}, "1024KB": {"random_ns": 6.0}, "4096KB": {"random_ns": 12.0}}, "tone_ratios": [1.2, 2.0, 2.4, 2.0]}},
                }
            }
        },
    ]
    for i, tc in enumerate(test_cases):
        score, details = validate_arch_consistency(tc["fingerprint"], tc["claimed_arch"])
        print(f"\nTest {i+1}: {tc['name']}")
        print(f"  Claimed: {tc['claimed_arch']} -> normalized: {details['normalized_arch']}")
        print(f"  Overall score: {score}")
        print(f"  Interpretation: {details.get('interpretation', 'N/A')}")
        print(f"  Sub-scores: simd={details['scores']['simd_consistency']}, "
              f"cache={details['scores']['cache_consistency']}, "
              f"clock={details['scores']['clock_consistency']}")
        if details["issues"]:
            print(f"  Issues: {details['issues']}")
    print("\n" + "=" * 60)
    print("All tests complete.")
