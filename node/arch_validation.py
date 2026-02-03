#!/usr/bin/env python3
"""
RustChain Server-Side Architecture Cross-Validation
==================================================
Bounty #17 Implementation
"""

import math
import logging
import sqlite3
import argparse
import json
import sys
from typing import Dict, Tuple

# Architecture Profile Database
# values are in bytes for cache sizes
ARCH_PROFILES = {
    "G4": {
        "l1_min": 30 * 1024, "l1_max": 34 * 1024,
        "l2_min": 250 * 1024, "l2_max": 2048 * 1024,
        "l3_min": 0, "l3_max": 2 * 1024 * 1024,
        "simd": "altivec",
        "min_cv": 0.001,
        "drift_typical": 500
    },
    "G5": {
        "l1_min": 30 * 1024, "l1_max": 66 * 1024,
        "l2_min": 500 * 1024, "l2_max": 1024 * 1024,
        "l3_min": 0, "l3_max": 0,
        "simd": "altivec",
        "min_cv": 0.001,
        "drift_typical": 400
    },
    "G3": {
        "l1_min": 30 * 1024, "l1_max": 34 * 1024,
        "l2_min": 500 * 1024, "l2_max": 1024 * 1024,
        "l3_min": 0, "l3_max": 0,
        "simd": None,
        "min_cv": 0.001,
        "drift_typical": 600
    },
    "modern_x86": {
        "l1_min": 30 * 1024, "l1_max": 66 * 1024,
        "l2_min": 250 * 1024, "l2_max": 2048 * 1024,
        "l3_min": 4 * 1024 * 1024, "l3_max": 256 * 1024 * 1024,
        "simd": "sse_avx",
        "min_cv": 0.0001,
        "drift_typical": 100
    },
    "apple_silicon": {
        "l1_min": 120 * 1024, "l1_max": 200 * 1024,
        "l2_min": 4 * 1024 * 1024, "l2_max": 16 * 1024 * 1024,
        "l3_min": 0, "l3_max": 32 * 1024 * 1024,
        "simd": "neon",
        "min_cv": 0.0001,
        "drift_typical": 50
    },
    "retro_x86": {
        "l1_min": 8 * 1024, "l1_max": 34 * 1024,
        "l2_min": 120 * 1024, "l2_max": 512 * 1024,
        "l3_min": 0, "l3_max": 0,
        "simd": "sse",
        "min_cv": 0.0005,
        "drift_typical": 300
    }
}

def migrate_db(db_path: str):
    """Adds arch_validation_score column if it doesn't exist"""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("ALTER TABLE miner_attest_recent ADD COLUMN arch_validation_score REAL DEFAULT 1.0")
            print(f"[DB] Migrated {db_path}: added arch_validation_score")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            pass # Already exists
        else:
            print(f"[DB] Error migrating {db_path}: {e}")
    except Exception as e:
        print(f"[DB] Connection failed for {db_path}: {e}")

def validate_arch_consistency(claimed_arch: str, fingerprint_data: Dict) -> Tuple[float, str]:
    """
    Validates claimed architecture against hardware fingerprint data.
    Returns: (confidence_score, reason)
    Score 1.0 = Perfect match, 0.0 = Hard mismatch.
    """
    if not fingerprint_data or "checks" not in fingerprint_data:
        return 0.5, "missing_fingerprint_data"

    arch = claimed_arch.lower()
    profile = None
    
    # Map claimed arch to profile
    if "g4" in arch: profile = ARCH_PROFILES["G4"]
    elif "g5" in arch: profile = ARCH_PROFILES["G5"]
    elif "g3" in arch: profile = ARCH_PROFILES["G3"]
    elif "apple" in arch or "m1" in arch or "m2" in arch or "m3" in arch: profile = ARCH_PROFILES["apple_silicon"]
    elif "x86_64" in arch or "amd64" in arch: profile = ARCH_PROFILES["modern_x86"]
    elif "i386" in arch or "i686" in arch or "pentium" in arch: profile = ARCH_PROFILES["retro_x86"]
    
    if not profile:
        return 0.5, "unknown_architecture_profile"

    score = 1.0
    penalties = []

    checks = fingerprint_data.get("checks", {})

    # 1. SIMD Identity Check
    simd_data = checks.get("simd_identity", {}).get("data", {})
    if profile["simd"] == "altivec":
        if not simd_data.get("has_altivec"):
            score -= 0.4
            penalties.append("missing_expected_altivec")
    elif profile["simd"] == "sse_avx":
        if not (simd_data.get("has_sse") or simd_data.get("has_avx")):
            score -= 0.4
            penalties.append("missing_expected_x86_simd")
    elif profile["simd"] == "neon":
        if not simd_data.get("has_neon"):
            score -= 0.4
            penalties.append("missing_expected_neon")

    # 2. Cache Timing Profile (Ratio Analysis)
    # We don't have absolute bytes, but we have l1_ns, l2_ns, l3_ns
    # and l2_l1_ratio, l3_l2_ratio.
    # Real hardware has specific jump in latency.
    cache_data = checks.get("cache_timing", {}).get("data", {})
    l2_ratio = cache_data.get("l2_l1_ratio", 0)
    l3_ratio = cache_data.get("l3_l2_ratio", 0)

    # Simple heuristic: VMs often show flat cache (ratio ~1.0)
    if l2_ratio < 1.05 and profile["l2_min"] > 0:
        score -= 0.3
        penalties.append("flat_cache_hierarchy")

    # 3. Clock Drift (CV and stdev)
    clock_data = checks.get("clock_drift", {}).get("data", {})
    cv = clock_data.get("cv", 0)
    drift_stdev = clock_data.get("drift_stdev", 0)

    if cv < profile["min_cv"]:
        score -= 0.2
        penalties.append("timing_too_stable_for_arch")
    
    # 4. Thermal Drift
    thermal_data = checks.get("thermal_drift", {}).get("data", {})
    drift_ratio = thermal_data.get("drift_ratio", 1.0)
    # Vintage silicon usually has more drift (ratio > 1.02)
    if profile == ARCH_PROFILES["G4"] or profile == ARCH_PROFILES["G5"]:
        if drift_ratio < 1.005:
            score -= 0.1
            penalties.append("low_thermal_drift_for_vintage")

    score = max(0.0, score)
    reason = "match" if score > 0.8 else f"mismatch:{','.join(penalties)}"
    
    return round(score, 2), reason

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RustChain Architecture Validation")
    parser.add_argument("--claimed", type=str, help="Claimed architecture")
    parser.add_argument("--fingerprint", type=str, help="Path to fingerprint JSON")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument("--migrate", type=str, help="Path to SQLite DB to migrate")
    args = parser.parse_args()

    if args.migrate:
        migrate_db(args.migrate)
        if not args.claimed: sys.exit(0)

    # Test data or load from file
    if args.fingerprint:
        try:
            with open(args.fingerprint, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading fingerprint: {e}")
            sys.exit(1)
    else:
        # Default test cases
        data = {
            "checks": {
                "simd_identity": {"data": {"has_altivec": True, "has_sse": False}},
                "cache_timing": {"data": {"l2_l1_ratio": 3.5, "l3_l2_ratio": 1.1}},
                "clock_drift": {"data": {"cv": 0.005, "drift_stdev": 450}},
                "thermal_drift": {"data": {"drift_ratio": 1.03}}
            }
        }
    
    claimed = args.claimed if args.claimed else "PowerPC G4"
    score, reason = validate_arch_consistency(claimed, data)
    
    if args.json:
        print(json.dumps({"score": score, "reason": reason, "claimed": claimed}))
    else:
        print(f"Arch: {claimed} -> Score: {score}, Reason: {reason}")
