#!/usr/bin/env python3
"""
RIP-PoA: Proof-of-Antiquity Hardware Attestation
=================================================
Comprehensive hardware proof system that validates:
1. CPU timing characteristics (PowerPC vs x86 vs ARM)
2. RAM access patterns (vintage vs modern)
3. Hardware entropy quality
4. Architecture-specific fingerprints
"""

import hashlib
import math
import statistics
from typing import Dict, Tuple, Optional

# Expected CPU timing profiles (microseconds per 10k hash ops)
CPU_TIMING_PROFILES = {
    "ppc_g4": {"mean": 8500, "variance_min": 200, "variance_max": 800},
    "ppc_g5": {"mean": 5000, "variance_min": 150, "variance_max": 600},
    "x86_vintage": {"mean": 3000, "variance_min": 100, "variance_max": 400},
    "x86_modern": {"mean": 500, "variance_min": 10, "variance_max": 100},
    "arm_vintage": {"mean": 2000, "variance_min": 80, "variance_max": 300},
    "arm_modern": {"mean": 300, "variance_min": 5, "variance_max": 50},
}

# Antiquity tiers based on hardware characteristics
ANTIQUITY_TIERS = {
    "classic": 2.5,      # Pre-2006: PowerPC G4, 68k Mac, VAX, PDP
    "vintage": 2.0,      # 2006-2010: PowerPC G5, early Core 2
    "heritage": 1.5,     # 2010-2015: Sandy Bridge, early ARM
    "modern": 1.0,       # 2015+: Modern x86, ARM64
}


def calculate_shannon_entropy(data: bytes) -> float:
    """Calculate Shannon entropy of byte sequence"""
    if not data:
        return 0.0

    freq = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1

    entropy = 0.0
    length = len(data)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)

    return entropy


def analyze_cpu_timing(signals: Dict) -> Dict:
    """Analyze CPU timing characteristics from attestation signals"""
    timing = signals.get("cpu_timing", {})
    samples = timing.get("samples", [])

    if not samples or len(samples) < 10:
        return {
            "valid": False,
            "reason": "insufficient_timing_samples",
            "tier": "modern",
            "confidence": 0.0
        }

    mean = timing.get("mean") or statistics.mean(samples)
    variance = timing.get("variance") or (statistics.variance(samples) if len(samples) > 1 else 0)

    # Match against known profiles
    best_match = None
    best_score = float('inf')

    for arch, profile in CPU_TIMING_PROFILES.items():
        mean_diff = abs(mean - profile["mean"])
        variance_in_range = (
            profile["variance_min"] <= variance <= profile["variance_max"]
        )

        if variance_in_range:
            score = mean_diff
            if score < best_score:
                best_score = score
                best_match = arch

    if not best_match:
        return {
            "valid": False,
            "reason": "timing_profile_mismatch",
            "mean": mean,
            "variance": variance,
            "tier": "modern",
            "confidence": 0.0
        }

    # Determine antiquity tier
    tier = "modern"
    if "ppc_g4" in best_match or "68k" in best_match:
        tier = "classic"
    elif "ppc_g5" in best_match or "x86_vintage" in best_match:
        tier = "vintage"
    elif "heritage" in best_match or ("arm" in best_match and "vintage" in best_match):
        tier = "heritage"

    # Confidence based on how well it matches
    confidence = 1.0 - min(best_score / CPU_TIMING_PROFILES[best_match]["mean"], 1.0)

    return {
        "valid": True,
        "profile": best_match,
        "tier": tier,
        "mean": mean,
        "variance": variance,
        "confidence": confidence
    }


def analyze_ram_patterns(signals: Dict) -> Dict:
    """Analyze RAM access patterns"""
    ram = signals.get("ram_timing", {})

    if not ram:
        return {"valid": False, "reason": "no_ram_data"}

    seq = ram.get("sequential_ns", 0)
    rand = ram.get("random_ns", 0)
    cache_rate = ram.get("cache_hit_rate", 0)

    if seq == 0 or rand == 0:
        return {"valid": False, "reason": "incomplete_ram_data"}

    # Vintage indicators
    is_slow = seq > 200
    ratio = rand / seq if seq > 0 else 0
    poor_cache = cache_rate < 0.7

    vintage_score = sum([is_slow, ratio > 3.0, poor_cache])

    return {
        "valid": True,
        "sequential_ns": seq,
        "random_ns": rand,
        "cache_hit_rate": cache_rate,
        "vintage_indicators": vintage_score,
        "confidence": vintage_score / 3.0
    }


def calculate_entropy_score(signals: Dict) -> float:
    """Calculate hardware entropy score from attestation signals (0.0 to 1.0)"""
    score = 0.0

    # 1. Shannon entropy of provided samples (40%)
    entropy_data = signals.get("entropy_samples", "")
    if entropy_data:
        try:
            if isinstance(entropy_data, str):
                entropy_data = bytes.fromhex(entropy_data.replace(":", ""))
            shannon = calculate_shannon_entropy(entropy_data)
            score += (shannon / 8.0) * 0.4
        except:
            pass

    # 2. CPU timing profile match (30%)
    cpu_analysis = analyze_cpu_timing(signals)
    if cpu_analysis.get("valid"):
        score += cpu_analysis.get("confidence", 0) * 0.3

    # 3. RAM pattern analysis (20%)
    ram_analysis = analyze_ram_patterns(signals)
    if ram_analysis.get("valid"):
        score += ram_analysis.get("confidence", 0) * 0.2

    # 4. MAC diversity (10%)
    macs = signals.get("macs", [])
    if len(macs) >= 1:
        score += 0.1

    return min(score, 1.0)


def validate_hardware_proof(signals: Dict, claimed_arch: str) -> Tuple[bool, Dict]:
    """Comprehensive hardware proof validation"""
    analysis = {
        "entropy_score": 0.0,
        "cpu_timing": {},
        "ram_patterns": {},
        "antiquity_tier": "modern",
        "tier_confidence": 0.0,
        "warnings": []
    }

    # Calculate overall entropy score
    analysis["entropy_score"] = calculate_entropy_score(signals)

    # Analyze CPU timing
    cpu_result = analyze_cpu_timing(signals)
    analysis["cpu_timing"] = cpu_result

    if not cpu_result.get("valid"):
        analysis["warnings"].append("cpu_timing_invalid")

    # Analyze RAM patterns
    ram_result = analyze_ram_patterns(signals)
    analysis["ram_patterns"] = ram_result

    if not ram_result.get("valid"):
        analysis["warnings"].append("ram_timing_missing")

    # Determine antiquity tier
    if cpu_result.get("valid"):
        analysis["antiquity_tier"] = cpu_result["tier"]
        analysis["tier_confidence"] = cpu_result["confidence"]

        # Cross-check claimed arch with detected profile
        detected_profile = cpu_result.get("profile", "")
        if claimed_arch.startswith("ppc") and "ppc" not in detected_profile:
            analysis["warnings"].append("arch_timing_mismatch")
            analysis["tier_confidence"] *= 0.5

    # Validation thresholds
    min_entropy = 0.3
    min_confidence = 0.4

    is_valid = (
        analysis["entropy_score"] >= min_entropy and
        (not cpu_result.get("valid") or cpu_result.get("confidence", 0) >= min_confidence)
    )

    if not is_valid:
        analysis["warnings"].append("insufficient_proof_quality")

    return is_valid, analysis


def get_antiquity_multiplier(tier: str) -> float:
    """Get reward multiplier for antiquity tier"""
    return ANTIQUITY_TIERS.get(tier, 1.0)


def server_side_validation(data: Dict) -> Tuple[bool, Dict]:
    """Server-side validation for /attest/submit endpoint"""
    device = data.get("device", {})
    signals = data.get("signals", {})

    claimed_arch = device.get("arch", "unknown")
    claimed_family = device.get("family", "unknown")

    # Validate hardware proof
    is_valid, analysis = validate_hardware_proof(signals, claimed_arch)

    # Determine final tier and multiplier
    tier = analysis.get("antiquity_tier", "modern")
    multiplier = get_antiquity_multiplier(tier)

    result = {
        "accepted": is_valid,
        "entropy_score": analysis["entropy_score"],
        "antiquity_tier": tier,
        "reward_multiplier": multiplier,
        "confidence": analysis.get("tier_confidence", 0.0),
        "warnings": analysis.get("warnings", [])
    }

    if not is_valid:
        result["reason"] = "hardware_proof_insufficient"

    return is_valid, result
