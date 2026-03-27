#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-201 Fleet Score Manipulation PoC — Bounty #494

Demonstrates four techniques to artificially lower fleet scores
while operating 10+ coordinated miners on shared infrastructure.

Techniques:
1. IP Rotation — unique /24 subnets per miner defeats IP clustering (40%)
2. Fingerprint Variance — minimal valid fingerprints with unique clock_drift
   defeats similarity detection (40%)
3. Timing Stagger — Poisson-distributed attestation timing defeats
   correlation window (20%)
4. Threshold Exploitation — FLEET_DETECTION_MINIMUM=4 gate means
   sub-groups below 4 get score 0.0

All techniques are black-box: no server-side modification required.
"""

import argparse
import importlib.util
import json
import math
import random
import sqlite3
from pathlib import Path


def load_fleet_module():
    """Load fleet_immune_system.py as a module."""
    module_path = (
        Path(__file__).resolve().parent.parent
        / "rips"
        / "python"
        / "rustchain"
        / "fleet_immune_system.py"
    )
    spec = importlib.util.spec_from_file_location(
        "fleet_immune_system_manipulation", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fingerprint generators
# ---------------------------------------------------------------------------

def identical_fleet_fingerprint():
    """Fingerprint that all naive fleet miners would share (worst case)."""
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.052, "samples": 64},
            },
            "cache_timing": {
                "passed": True,
                "data": {"l1_hit_ns": 4.1, "l2_hit_ns": 10.2},
            },
            "thermal_drift": {
                "passed": True,
                "data": {"entropy": 0.61},
            },
            "simd_identity": {
                "passed": True,
                "data": {"profile": "identical-simd"},
            },
        },
        "all_passed": True,
    }


def unique_minimal_fingerprint(miner_index):
    """
    Technique 2: Minimal valid fingerprint with unique clock_drift CV.

    By submitting only anti_emulation + clock_drift (2 checks), the
    similarity engine has fewer dimensions to compare. Each miner gets
    a unique CV value so no two share the same clock_drift_hash.
    """
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {
                    "cv": round(0.03 + miner_index * 0.007, 4),
                    "samples": 64,
                },
            },
        },
        "all_passed": True,
    }


def diverse_full_fingerprint(miner_index):
    """
    Alternative Technique 2b: Full fingerprint but with diverse values.

    Each miner gets unique values across all 4 hashable dimensions so
    similarity never exceeds 1 shared hash (below the 2-match threshold).
    """
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {
                    "cv": round(0.03 + miner_index * 0.007, 4),
                    "samples": 64,
                },
            },
            "cache_timing": {
                "passed": True,
                "data": {
                    "l1_hit_ns": round(3.5 + miner_index * 0.3, 1),
                    "l2_hit_ns": round(9.0 + miner_index * 0.5, 1),
                },
            },
            "thermal_drift": {
                "passed": True,
                "data": {"entropy": round(0.4 + miner_index * 0.05, 2)},
            },
            "simd_identity": {
                "passed": True,
                "data": {"profile": f"simd-variant-{miner_index}"},
            },
        },
        "all_passed": True,
    }


# ---------------------------------------------------------------------------
# Timing generators
# ---------------------------------------------------------------------------

def naive_timing(base_ts, miner_index):
    """All miners attest within seconds (triggers timing correlation)."""
    return base_ts + miner_index * 3  # 3-second gaps


def staggered_timing(base_ts, miner_index, mean_gap=45):
    """
    Technique 3: Poisson-distributed stagger beyond 30s window.

    FLEET_TIMING_WINDOW_S = 30 in the detector. By spacing attestations
    with a mean gap of 45s, the fraction within any 30s window stays
    well below the 60% threshold.
    """
    cumulative = 0
    for _ in range(miner_index):
        cumulative += max(35, random.expovariate(1.0 / mean_gap))
    return base_ts + int(cumulative)


# ---------------------------------------------------------------------------
# IP generators
# ---------------------------------------------------------------------------

def same_subnet_ip(miner_index):
    """All miners on same /24 (triggers IP clustering)."""
    return f"10.0.0.{10 + miner_index}"


def rotated_subnet_ip(miner_index, epoch):
    """
    Technique 1: Each miner on a unique /24 subnet.

    The IP clustering detector groups by subnet_hash of the /24 prefix.
    Different /24s = different groups = no clustering signal.
    """
    return f"198.{51 + miner_index}.{(epoch * 7 + miner_index) % 255}.{10 + miner_index % 200}"


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------

def run_scenario(fleet_mod, name, num_miners, num_epochs,
                 ip_fn, timing_fn, fingerprint_fn):
    """Run a fleet detection scenario and return results."""
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)

    miners = [f"miner-{i}" for i in range(num_miners)]
    epoch_results = []

    for epoch_offset in range(num_epochs):
        epoch = 500 + epoch_offset
        base_ts = 100_000 * epoch

        for i, miner in enumerate(miners):
            fleet_mod.record_fleet_signals_from_request(
                db,
                miner=miner,
                epoch=epoch,
                ip_address=ip_fn(i, epoch) if ip_fn.__code__.co_argcount > 1 else ip_fn(i),
                attest_ts=timing_fn(base_ts, i),
                fingerprint=fingerprint_fn(i),
            )

        scores = fleet_mod.compute_fleet_scores(db, epoch)
        multipliers = {
            m: fleet_mod.apply_fleet_decay(2.5, s)
            for m, s in scores.items()
        }

        max_score = max(scores.values()) if scores else 0
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        all_clean = all(s < 0.3 for s in scores.values())

        epoch_results.append({
            "epoch": epoch,
            "max_score": round(max_score, 4),
            "avg_score": round(avg_score, 4),
            "all_clean": all_clean,
            "scores": {m: round(s, 4) for m, s in scores.items()},
            "multipliers": {m: round(v, 4) for m, v in multipliers.items()},
        })

    return {
        "scenario": name,
        "num_miners": num_miners,
        "num_epochs": num_epochs,
        "epochs": epoch_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="RIP-201 Fleet Score Manipulation PoC (Bounty #494)"
    )
    parser.add_argument(
        "--miners", type=int, default=12,
        help="Number of miners (default: 12)"
    )
    parser.add_argument(
        "--epochs", type=int, default=5,
        help="Consecutive epochs to test (default: 5)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility"
    )
    args = parser.parse_args()
    random.seed(args.seed)

    fleet_mod = load_fleet_module()

    # --- Scenario 1: Baseline (no evasion) ---
    baseline = run_scenario(
        fleet_mod, "baseline_no_evasion", args.miners, args.epochs,
        ip_fn=same_subnet_ip,
        timing_fn=naive_timing,
        fingerprint_fn=lambda i: identical_fleet_fingerprint(),
    )

    # --- Scenario 2: Full manipulation (all 3 techniques) ---
    random.seed(args.seed)
    manipulated = run_scenario(
        fleet_mod, "full_manipulation", args.miners, args.epochs,
        ip_fn=rotated_subnet_ip,
        timing_fn=staggered_timing,
        fingerprint_fn=unique_minimal_fingerprint,
    )

    # --- Scenario 3: Diverse fingerprints only (IP+timing naive) ---
    random.seed(args.seed)
    fp_only = run_scenario(
        fleet_mod, "fingerprint_diversity_only", args.miners, args.epochs,
        ip_fn=same_subnet_ip,
        timing_fn=naive_timing,
        fingerprint_fn=diverse_full_fingerprint,
    )

    # --- Scenario 4: IP rotation only ---
    random.seed(args.seed)
    ip_only = run_scenario(
        fleet_mod, "ip_rotation_only", args.miners, args.epochs,
        ip_fn=rotated_subnet_ip,
        timing_fn=naive_timing,
        fingerprint_fn=lambda i: identical_fleet_fingerprint(),
    )

    report = {
        "tool": "rip201_fleet_score_manipulation",
        "bounty": "#494 — RIP-201 Fleet Score Manipulation (150 RTC)",
        "technique_summary": {
            "1_ip_rotation": "Unique /24 subnet per miner → IP clustering score = 0",
            "2_fingerprint_variance": "Minimal checks + unique clock_drift → similarity score = 0",
            "3_timing_stagger": "Poisson gaps (mean 45s) beyond 30s window → timing score ≈ 0",
            "4_threshold_exploit": "FLEET_DETECTION_MINIMUM=4 means <4 signals → score 0.0",
        },
        "scenarios": [baseline, manipulated, fp_only, ip_only],
        "conclusion": {
            "baseline_detected": not baseline["epochs"][-1]["all_clean"],
            "manipulation_clean": manipulated["epochs"][-1]["all_clean"],
            "sustained_epochs": sum(
                1 for e in manipulated["epochs"] if e["all_clean"]
            ),
        },
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
