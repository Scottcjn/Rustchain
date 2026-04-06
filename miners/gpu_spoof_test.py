#!/usr/bin/env python3
"""
GPU Spoof Detection Test — Can PPA Catch a Fake H100?
=====================================================

Simulates an adversary who claims to have an H100 GPU but actually has
different hardware (e.g., RTX 4070). The test:

1. Runs a real GPU fingerprint on whatever GPU is installed
2. Generates a "claimed H100" profile with known H100 characteristics
3. Compares the real fingerprint against the H100 claim
4. Reports which channels expose the lie

This demonstrates PPA's ability to detect GPU hardware spoofing —
the Tier 1 threat from RIP-0308.

Usage:
    python3 gpu_spoof_test.py

Author: Elyan Labs (RIP-0308: Proof of Physical AI)
"""

import json
import sys
import os

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gpu_fingerprint import run_gpu_fingerprint

# ---------------------------------------------------------------------------
# Known H100 Reference Profile
# ---------------------------------------------------------------------------
# These are published/expected characteristics of a genuine NVIDIA H100 SXM5.
# An attacker claiming H100 would need ALL of these to match simultaneously.
# ---------------------------------------------------------------------------

H100_REFERENCE = {
    "gpu_name": "NVIDIA H100 80GB HBM3",
    "vram_mb": 81920,  # 80 GB HBM3
    "compute_capability": "9.0",  # Hopper architecture

    # 8a: Memory — H100 has 3.35 TB/s HBM3 bandwidth
    # Working set transitions: L1 (256KB/SM) → L2 (50MB) → HBM3 (80GB)
    "expected_memory": {
        "hbm_bandwidth_gbps": 3350,
        "l2_cache_mb": 50,
        "spread_min": 500,  # Massive spread due to HBM3
    },

    # 8b: Compute — H100 FP16:FP32 ratio with tensor cores
    # H100 FP32: 67 TFLOPS, FP16 tensor: 989 TFLOPS (w/ sparsity: 1979)
    # Expected FP16:FP32 ratio: ~14.7x (tensor) or ~2x (CUDA cores only)
    "expected_compute": {
        "fp16_to_fp32_ratio_min": 8.0,   # Tensor core dominant
        "fp16_to_fp32_ratio_max": 20.0,
        "fp32_tflops_min": 50.0,
        "fp32_tflops_max": 70.0,
        "bf16_supported": True,
    },

    # 8e: Bus — H100 SXM5 uses NVLink, PCIe variant uses Gen5 x16
    # SXM: NVLink 4.0 = 900 GB/s bidirectional
    # PCIe: Gen5 x16 = ~64 GB/s unidirectional
    "expected_bus": {
        "pcie_h2d_gbps_min": 25.0,  # PCIe Gen5 x16
        "pcie_h2d_gbps_max": 64.0,
        "asymmetry_max": 0.15,  # Gen5 is more symmetric
    },

    # 8d: Thermal — H100 SXM TDP = 700W, PCIe TDP = 350W
    "expected_thermal": {
        "tdp_watts": 700,  # SXM variant
        "ramp_rate_min": 0.3,  # Massive heatsink = slow ramp
        "ramp_rate_max": 1.5,
        "temp_range_min": 5,
    },
}

# Additional GPU profiles for cross-reference
GPU_PROFILES = {
    "H100_SXM": {
        "fp16_fp32_ratio": (10.0, 20.0),
        "fp32_tflops": (50.0, 70.0),
        "pcie_h2d_gbps": (25.0, 64.0),
        "vram_mb": 81920,
        "compute_cap": "9.0",
    },
    "A100_SXM": {
        "fp16_fp32_ratio": (2.0, 4.0),
        "fp32_tflops": (15.0, 20.0),
        "pcie_h2d_gbps": (20.0, 32.0),
        "vram_mb": (40960, 81920),  # 40GB or 80GB variant
        "compute_cap": "8.0",
    },
    "V100_SXM": {
        "fp16_fp32_ratio": (1.8, 2.5),
        "fp32_tflops": (12.0, 16.0),
        "pcie_h2d_gbps": (10.0, 16.0),
        "vram_mb": (16384, 32768),  # 16GB or 32GB
        "compute_cap": "7.0",
    },
    "RTX_4090": {
        "fp16_fp32_ratio": (3.5, 5.5),
        "fp32_tflops": (70.0, 83.0),
        "pcie_h2d_gbps": (20.0, 28.0),
        "vram_mb": 24576,
        "compute_cap": "8.9",
    },
    "RTX_4070_Laptop": {
        "fp16_fp32_ratio": (3.5, 5.0),
        "fp32_tflops": (15.0, 25.0),
        "pcie_h2d_gbps": (8.0, 14.0),
        "vram_mb": 8192,
        "compute_cap": "8.9",
    },
    "T4": {
        "fp16_fp32_ratio": (6.0, 10.0),
        "fp32_tflops": (7.0, 9.0),
        "pcie_h2d_gbps": (10.0, 14.0),
        "vram_mb": 16384,
        "compute_cap": "7.5",
    },
    "RTX_5070": {
        "fp16_fp32_ratio": (2.5, 3.5),
        "fp32_tflops": (25.0, 40.0),
        "pcie_h2d_gbps": (20.0, 30.0),
        "vram_mb": 12288,
        "compute_cap": "12.0",
    },
    "RTX_3090": {
        "fp16_fp32_ratio": (1.8, 2.5),
        "fp32_tflops": (30.0, 36.0),
        "pcie_h2d_gbps": (20.0, 28.0),
        "vram_mb": 24576,
        "compute_cap": "8.6",
    },
    "MI300X": {
        "fp16_fp32_ratio": (4.0, 8.0),
        "fp32_tflops": (80.0, 164.0),
        "pcie_h2d_gbps": (30.0, 64.0),
        "vram_mb": 196608,
        "compute_cap": "N/A",  # AMD, no CUDA compute cap
    },
    "L40S": {
        "fp16_fp32_ratio": (3.5, 5.5),
        "fp32_tflops": (60.0, 91.0),
        "pcie_h2d_gbps": (20.0, 32.0),
        "vram_mb": 49152,
        "compute_cap": "8.9",
    },
}


def identify_gpu(fingerprint: dict) -> dict:
    """Identify the most likely real GPU from fingerprint data."""
    channels = fingerprint["channels"]
    results = {}

    # Extract key metrics
    fp_ratio = channels[1]["data"]["asymmetry_ratios"].get("fp16_to_fp32", 0)
    fp32_tflops = channels[1]["data"]["throughput"].get("fp32", {}).get("tflops", 0)
    h2d_gbps = channels[4]["data"]["peak_h2d_gbps"]
    vram = fingerprint["vram_mb"]
    compute_cap = fingerprint["compute_capability"]

    for gpu_name, profile in GPU_PROFILES.items():
        score = 0
        checks = []

        # FP16:FP32 ratio
        ratio_range = profile["fp16_fp32_ratio"]
        if ratio_range[0] <= fp_ratio <= ratio_range[1]:
            score += 25
            checks.append(f"FP16:FP32 ratio {fp_ratio:.2f} in range [{ratio_range[0]}-{ratio_range[1]}]")
        else:
            checks.append(f"FP16:FP32 ratio {fp_ratio:.2f} OUTSIDE [{ratio_range[0]}-{ratio_range[1]}]")

        # FP32 TFLOPS
        tflops_range = profile["fp32_tflops"]
        if tflops_range[0] <= fp32_tflops <= tflops_range[1]:
            score += 25
            checks.append(f"FP32 {fp32_tflops:.1f} TFLOPS in range")
        else:
            checks.append(f"FP32 {fp32_tflops:.1f} TFLOPS OUTSIDE [{tflops_range[0]}-{tflops_range[1]}]")

        # PCIe bandwidth
        bw_range = profile["pcie_h2d_gbps"]
        if bw_range[0] <= h2d_gbps <= bw_range[1]:
            score += 25
            checks.append(f"PCIe {h2d_gbps:.1f} GB/s in range")
        else:
            checks.append(f"PCIe {h2d_gbps:.1f} GB/s OUTSIDE [{bw_range[0]}-{bw_range[1]}]")

        # Compute capability
        if compute_cap == profile["compute_cap"]:
            score += 25
            checks.append(f"Compute cap {compute_cap} matches")
        else:
            checks.append(f"Compute cap {compute_cap} != {profile['compute_cap']}")

        results[gpu_name] = {"score": score, "checks": checks}

    return results


def run_spoof_test(claimed_gpu: str = "H100_SXM"):
    """Run a full spoof detection test."""
    print("=" * 70)
    print("  GPU SPOOF DETECTION TEST — Proof of Physical AI")
    print(f"  Adversary claims: {claimed_gpu}")
    print("=" * 70)
    print()

    # Step 1: Real fingerprint
    print("[1/3] Running real GPU fingerprint...")
    fp = run_gpu_fingerprint(samples=100)
    real_gpu = fp.gpu_name
    real_vram = fp.vram_mb
    real_cap = fp.compute_capability

    # Step 2: Compare against claimed profile
    print()
    print("=" * 70)
    print(f"  SPOOF ANALYSIS: Claimed={claimed_gpu}, Actual={real_gpu}")
    print("=" * 70)
    print()

    channels = [ch if isinstance(ch, dict) else ch for ch in fp.channels]
    claimed = GPU_PROFILES.get(claimed_gpu, GPU_PROFILES["H100_SXM"])

    violations = []
    passes = []

    # Check 1: Compute capability
    if real_cap != claimed.get("compute_cap", "9.0"):
        violations.append(
            f"COMPUTE CAPABILITY: Real={real_cap}, Claimed={claimed['compute_cap']}. "
            f"Cannot be software-spoofed — it's a hardware register."
        )
    else:
        passes.append(f"Compute capability matches ({real_cap})")

    # Check 2: VRAM
    claimed_vram = claimed.get("vram_mb", 81920)
    if isinstance(claimed_vram, tuple):
        vram_match = claimed_vram[0] <= real_vram <= claimed_vram[1]
    else:
        vram_match = abs(real_vram - claimed_vram) < claimed_vram * 0.1
    if not vram_match:
        violations.append(
            f"VRAM: Real={real_vram}MB, Claimed={claimed_vram}MB. "
            f"An RTX 4070 has 8GB, not 80GB."
        )
    else:
        passes.append(f"VRAM plausible ({real_vram}MB)")

    # Check 3: FP16:FP32 ratio (silicon-level)
    fp_ratio = channels[1]["data"]["asymmetry_ratios"].get("fp16_to_fp32", 0)
    ratio_range = claimed["fp16_fp32_ratio"]
    if not (ratio_range[0] <= fp_ratio <= ratio_range[1]):
        violations.append(
            f"FP16:FP32 RATIO: Real={fp_ratio:.2f}x, Expected=[{ratio_range[0]}-{ratio_range[1]}x]. "
            f"Tensor core architecture mismatch — unfakeable without the actual silicon."
        )
    else:
        passes.append(f"FP16:FP32 ratio in range ({fp_ratio:.2f}x)")

    # Check 4: FP32 throughput
    fp32_tflops = channels[1]["data"]["throughput"].get("fp32", {}).get("tflops", 0)
    tflops_range = claimed["fp32_tflops"]
    if not (tflops_range[0] <= fp32_tflops <= tflops_range[1]):
        violations.append(
            f"FP32 THROUGHPUT: Real={fp32_tflops:.1f} TFLOPS, Expected=[{tflops_range[0]}-{tflops_range[1]}]. "
            f"Physical compute capacity cannot be inflated by software."
        )
    else:
        passes.append(f"FP32 throughput in range ({fp32_tflops:.1f} TFLOPS)")

    # Check 5: PCIe bandwidth
    h2d_gbps = channels[4]["data"]["peak_h2d_gbps"]
    bw_range = claimed["pcie_h2d_gbps"]
    if not (bw_range[0] <= h2d_gbps <= bw_range[1]):
        violations.append(
            f"PCIe BANDWIDTH: Real={h2d_gbps:.1f} GB/s, Expected=[{bw_range[0]}-{bw_range[1]}]. "
            f"Bus speed reveals PCIe generation and lane width."
        )
    else:
        passes.append(f"PCIe bandwidth in range ({h2d_gbps:.1f} GB/s)")

    # Check 6: Thermal ramp (physical heat curve)
    temp_range = channels[3]["data"].get("temp_range_c", 0)
    ramp_rate = channels[3]["data"].get("ramp_rate_c_per_s", 0)
    if claimed_gpu.startswith("H100") and ramp_rate > 2.0:
        violations.append(
            f"THERMAL RAMP: Real={ramp_rate:.1f}°C/s (small cooler), "
            f"H100 SXM has massive heatsink = slower ramp (<1.5°C/s). Physical mismatch."
        )
    else:
        passes.append(f"Thermal ramp plausible ({ramp_rate:.1f}°C/s)")

    # Step 3: Verdict
    print("VIOLATIONS (spoof detected):")
    if violations:
        for i, v in enumerate(violations, 1):
            print(f"  ✗ [{i}] {v}")
    else:
        print("  (none)")

    print()
    print("CONSISTENT (could match claim):")
    if passes:
        for p in passes:
            print(f"  ✓ {p}")
    else:
        print("  (none)")

    print()
    print("=" * 70)
    spoofed = len(violations) > 0
    if spoofed:
        print(f"  VERDICT: SPOOF DETECTED — {len(violations)} violations found")
        print(f"  Real hardware: {real_gpu} ({real_vram}MB, sm_{real_cap})")
        print(f"  Claimed hardware: {claimed_gpu}")
        print(f"  The physics don't lie. {len(violations)} channels expose the fraud.")
    else:
        print(f"  VERDICT: Claim is PLAUSIBLE — hardware matches {claimed_gpu} profile")
    print("=" * 70)

    # Also show what the GPU actually matches
    print()
    print("GPU IDENTIFICATION (what does the fingerprint actually match?):")
    id_results = identify_gpu(fp.to_dict())
    sorted_ids = sorted(id_results.items(), key=lambda x: -x[1]["score"])
    for gpu_name, result in sorted_ids:
        marker = "◀ BEST MATCH" if result["score"] == sorted_ids[0][1]["score"] and result["score"] > 50 else ""
        print(f"  {gpu_name}: {result['score']}% match {marker}")
        for check in result["checks"]:
            print(f"    {'✓' if 'in range' in check or 'matches' in check else '✗'} {check}")
        print()

    return {
        "claimed": claimed_gpu,
        "actual": real_gpu,
        "spoofed": spoofed,
        "violations": len(violations),
        "violation_details": violations,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GPU Spoof Detection Test")
    parser.add_argument("--claim", default="H100_SXM", choices=list(GPU_PROFILES.keys()),
                        help="GPU the adversary claims to have")
    args = parser.parse_args()

    result = run_spoof_test(claimed_gpu=args.claim)

    if result["spoofed"]:
        print(f"\n🚨 SPOOF CAUGHT: {result['violations']} physical violations detected.")
        sys.exit(1)
    else:
        print(f"\n✅ Claim appears legitimate.")
        sys.exit(0)
