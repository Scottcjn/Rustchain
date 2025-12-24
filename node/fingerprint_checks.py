#!/usr/bin/env python3
"""
RIP-PoA Hardware Fingerprint Validation
========================================
7 Required Checks for RTC Reward Approval
ALL MUST PASS for antiquity multiplier rewards

Checks:
1. Clock-Skew & Oscillator Drift
2. Cache Timing Fingerprint
3. SIMD Unit Identity
4. Thermal Drift Entropy
5. Instruction Path Jitter
6. Anti-Emulation Behavioral Checks
7. ROM Fingerprint (retro platforms only)
"""

import hashlib
import os
import platform
import statistics
import subprocess
import time
from typing import Dict, List, Optional, Tuple

# Import ROM fingerprint database if available
try:
    from rom_fingerprint_db import (
        identify_rom,
        is_known_emulator_rom,
        compute_file_hash,
        detect_platform_roms,
        get_real_hardware_rom_signature,
    )
    ROM_DB_AVAILABLE = True
except ImportError:
    ROM_DB_AVAILABLE = False

def check_clock_drift(samples: int = 200) -> Tuple[bool, Dict]:
    """Check 1: Clock-Skew & Oscillator Drift"""
    intervals = []
    reference_ops = 5000

    for i in range(samples):
        data = "drift_{}".format(i).encode()
        start = time.perf_counter_ns()
        for _ in range(reference_ops):
            hashlib.sha256(data).digest()
        elapsed = time.perf_counter_ns() - start
        intervals.append(elapsed)
        if i % 50 == 0:
            time.sleep(0.001)

    mean_ns = statistics.mean(intervals)
    stdev_ns = statistics.stdev(intervals)
    cv = stdev_ns / mean_ns if mean_ns > 0 else 0

    drift_pairs = [intervals[i] - intervals[i-1] for i in range(1, len(intervals))]
    drift_stdev = statistics.stdev(drift_pairs) if len(drift_pairs) > 1 else 0

    data = {
        "mean_ns": int(mean_ns),
        "stdev_ns": int(stdev_ns),
        "cv": round(cv, 6),
        "drift_stdev": int(drift_stdev),
    }

    valid = True
    if cv < 0.0001:
        valid = False
        data["fail_reason"] = "synthetic_timing"
    elif drift_stdev == 0:
        valid = False
        data["fail_reason"] = "no_drift"

    return valid, data


def check_cache_timing(iterations: int = 100) -> Tuple[bool, Dict]:
    """Check 2: Cache Timing Fingerprint (L1/L2/L3 Latency)"""
    l1_size = 8 * 1024
    l2_size = 128 * 1024
    l3_size = 4 * 1024 * 1024

    def measure_access_time(buffer_size: int, accesses: int = 1000) -> float:
        buf = bytearray(buffer_size)
        for i in range(0, buffer_size, 64):
            buf[i] = i % 256
        start = time.perf_counter_ns()
        for i in range(accesses):
            _ = buf[(i * 64) % buffer_size]
        elapsed = time.perf_counter_ns() - start
        return elapsed / accesses

    l1_times = [measure_access_time(l1_size) for _ in range(iterations)]
    l2_times = [measure_access_time(l2_size) for _ in range(iterations)]
    l3_times = [measure_access_time(l3_size) for _ in range(iterations)]

    l1_avg = statistics.mean(l1_times)
    l2_avg = statistics.mean(l2_times)
    l3_avg = statistics.mean(l3_times)

    l2_l1_ratio = l2_avg / l1_avg if l1_avg > 0 else 0
    l3_l2_ratio = l3_avg / l2_avg if l2_avg > 0 else 0

    data = {
        "l1_ns": round(l1_avg, 2),
        "l2_ns": round(l2_avg, 2),
        "l3_ns": round(l3_avg, 2),
        "l2_l1_ratio": round(l2_l1_ratio, 3),
        "l3_l2_ratio": round(l3_l2_ratio, 3),
    }

    valid = True
    if l2_l1_ratio < 1.01 and l3_l2_ratio < 1.01:
        valid = False
        data["fail_reason"] = "no_cache_hierarchy"
    elif l1_avg == 0 or l2_avg == 0 or l3_avg == 0:
        valid = False
        data["fail_reason"] = "zero_latency"

    return valid, data


def check_simd_identity() -> Tuple[bool, Dict]:
    """Check 3: SIMD Unit Identity (SSE/AVX/AltiVec/NEON)"""
    flags = []
    arch = platform.machine().lower()

    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "flags" in line.lower() or "features" in line.lower():
                    parts = line.split(":")
                    if len(parts) > 1:
                        flags = parts[1].strip().split()
                        break
    except:
        pass

    if not flags:
        try:
            result = subprocess.run(
                ["sysctl", "-a"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "feature" in line.lower() or "altivec" in line.lower():
                    flags.append(line.split(":")[-1].strip())
        except:
            pass

    has_sse = any("sse" in f.lower() for f in flags)
    has_avx = any("avx" in f.lower() for f in flags)
    has_altivec = any("altivec" in f.lower() for f in flags) or "ppc" in arch
    has_neon = any("neon" in f.lower() for f in flags) or "arm" in arch

    data = {
        "arch": arch,
        "simd_flags_count": len(flags),
        "has_sse": has_sse,
        "has_avx": has_avx,
        "has_altivec": has_altivec,
        "has_neon": has_neon,
        "sample_flags": flags[:10] if flags else [],
    }

    valid = has_sse or has_avx or has_altivec or has_neon or len(flags) > 0
    if not valid:
        data["fail_reason"] = "no_simd_detected"

    return valid, data


def check_thermal_drift(samples: int = 50) -> Tuple[bool, Dict]:
    """Check 4: Thermal Drift Entropy"""
    cold_times = []
    for i in range(samples):
        start = time.perf_counter_ns()
        for _ in range(10000):
            hashlib.sha256("cold_{}".format(i).encode()).digest()
        cold_times.append(time.perf_counter_ns() - start)

    for _ in range(100):
        for __ in range(50000):
            hashlib.sha256(b"warmup").digest()

    hot_times = []
    for i in range(samples):
        start = time.perf_counter_ns()
        for _ in range(10000):
            hashlib.sha256("hot_{}".format(i).encode()).digest()
        hot_times.append(time.perf_counter_ns() - start)

    cold_avg = statistics.mean(cold_times)
    hot_avg = statistics.mean(hot_times)
    cold_stdev = statistics.stdev(cold_times)
    hot_stdev = statistics.stdev(hot_times)
    drift_ratio = hot_avg / cold_avg if cold_avg > 0 else 0

    data = {
        "cold_avg_ns": int(cold_avg),
        "hot_avg_ns": int(hot_avg),
        "cold_stdev": int(cold_stdev),
        "hot_stdev": int(hot_stdev),
        "drift_ratio": round(drift_ratio, 4),
    }

    valid = True
    if cold_stdev == 0 and hot_stdev == 0:
        valid = False
        data["fail_reason"] = "no_thermal_variance"

    return valid, data


def check_instruction_jitter(samples: int = 100) -> Tuple[bool, Dict]:
    """Check 5: Instruction Path Jitter"""
    def measure_int_ops(count: int = 10000) -> float:
        start = time.perf_counter_ns()
        x = 1
        for i in range(count):
            x = (x * 7 + 13) % 65537
        return time.perf_counter_ns() - start

    def measure_fp_ops(count: int = 10000) -> float:
        start = time.perf_counter_ns()
        x = 1.5
        for i in range(count):
            x = (x * 1.414 + 0.5) % 1000.0
        return time.perf_counter_ns() - start

    def measure_branch_ops(count: int = 10000) -> float:
        start = time.perf_counter_ns()
        x = 0
        for i in range(count):
            if i % 2 == 0:
                x += 1
            else:
                x -= 1
        return time.perf_counter_ns() - start

    int_times = [measure_int_ops() for _ in range(samples)]
    fp_times = [measure_fp_ops() for _ in range(samples)]
    branch_times = [measure_branch_ops() for _ in range(samples)]

    int_avg = statistics.mean(int_times)
    fp_avg = statistics.mean(fp_times)
    branch_avg = statistics.mean(branch_times)

    int_stdev = statistics.stdev(int_times)
    fp_stdev = statistics.stdev(fp_times)
    branch_stdev = statistics.stdev(branch_times)

    data = {
        "int_avg_ns": int(int_avg),
        "fp_avg_ns": int(fp_avg),
        "branch_avg_ns": int(branch_avg),
        "int_stdev": int(int_stdev),
        "fp_stdev": int(fp_stdev),
        "branch_stdev": int(branch_stdev),
    }

    valid = True
    if int_stdev == 0 and fp_stdev == 0 and branch_stdev == 0:
        valid = False
        data["fail_reason"] = "no_jitter"

    return valid, data


def check_anti_emulation() -> Tuple[bool, Dict]:
    """Check 6: Anti-Emulation Behavioral Checks"""
    vm_indicators = []

    vm_paths = [
        "/sys/class/dmi/id/product_name",
        "/sys/class/dmi/id/sys_vendor",
        "/proc/scsi/scsi",
    ]

    vm_strings = ["vmware", "virtualbox", "kvm", "qemu", "xen", "hyperv", "parallels"]

    for path in vm_paths:
        try:
            with open(path, "r") as f:
                content = f.read().lower()
                for vm in vm_strings:
                    if vm in content:
                        vm_indicators.append("{}:{}".format(path, vm))
        except:
            pass

    for key in ["KUBERNETES", "DOCKER", "VIRTUAL", "container"]:
        if key in os.environ:
            vm_indicators.append("ENV:{}".format(key))

    try:
        with open("/proc/cpuinfo", "r") as f:
            if "hypervisor" in f.read().lower():
                vm_indicators.append("cpuinfo:hypervisor")
    except:
        pass

    data = {
        "vm_indicators": vm_indicators,
        "indicator_count": len(vm_indicators),
        "is_likely_vm": len(vm_indicators) > 0,
    }

    valid = len(vm_indicators) == 0
    if not valid:
        data["fail_reason"] = "vm_detected"

    return valid, data


def check_rom_fingerprint() -> Tuple[bool, Dict]:
    """
    Check 7: ROM Fingerprint (for retro platforms)

    Detects if running with a known emulator ROM dump.
    Real vintage hardware should have unique/variant ROMs.
    Emulators all use the same pirated ROM packs.
    """
    if not ROM_DB_AVAILABLE:
        # Skip for modern hardware or if DB not available
        return True, {"skipped": True, "reason": "rom_db_not_available_or_modern_hw"}

    arch = platform.machine().lower()
    rom_hashes = {}
    emulator_detected = False
    detection_details = []

    # Check for PowerPC (Mac emulation target)
    if "ppc" in arch or "powerpc" in arch:
        # Try to get real hardware ROM signature
        real_rom = get_real_hardware_rom_signature()
        if real_rom:
            rom_hashes["real_hardware"] = real_rom
        else:
            # Check if running under emulator with known ROM
            platform_roms = detect_platform_roms()
            if platform_roms:
                for platform_name, rom_hash in platform_roms.items():
                    if is_known_emulator_rom(rom_hash, "md5"):
                        emulator_detected = True
                        rom_info = identify_rom(rom_hash, "md5")
                        detection_details.append({
                            "platform": platform_name,
                            "hash": rom_hash,
                            "known_as": rom_info,
                        })

    # Check for 68K (Amiga, Atari ST, old Mac)
    elif "m68k" in arch or "68000" in arch:
        platform_roms = detect_platform_roms()
        for platform_name, rom_hash in platform_roms.items():
            if "amiga" in platform_name.lower():
                if is_known_emulator_rom(rom_hash, "sha1"):
                    emulator_detected = True
                    rom_info = identify_rom(rom_hash, "sha1")
                    detection_details.append({
                        "platform": platform_name,
                        "hash": rom_hash,
                        "known_as": rom_info,
                    })
            elif "mac" in platform_name.lower():
                if is_known_emulator_rom(rom_hash, "apple"):
                    emulator_detected = True
                    rom_info = identify_rom(rom_hash, "apple")
                    detection_details.append({
                        "platform": platform_name,
                        "hash": rom_hash,
                        "known_as": rom_info,
                    })

    # For modern hardware, report "N/A" but pass
    else:
        return True, {
            "skipped": False,
            "arch": arch,
            "is_retro_platform": False,
            "rom_check": "not_applicable_modern_hw",
        }

    data = {
        "arch": arch,
        "is_retro_platform": True,
        "rom_hashes": rom_hashes,
        "emulator_detected": emulator_detected,
        "detection_details": detection_details,
    }

    if emulator_detected:
        data["fail_reason"] = "known_emulator_rom"
        return False, data

    return True, data


def validate_all_checks(include_rom_check: bool = True) -> Tuple[bool, Dict]:
    """Run all 7 fingerprint checks. ALL MUST PASS for RTC approval."""
    results = {}
    all_passed = True

    checks = [
        ("clock_drift", "Clock-Skew & Oscillator Drift", check_clock_drift),
        ("cache_timing", "Cache Timing Fingerprint", check_cache_timing),
        ("simd_identity", "SIMD Unit Identity", check_simd_identity),
        ("thermal_drift", "Thermal Drift Entropy", check_thermal_drift),
        ("instruction_jitter", "Instruction Path Jitter", check_instruction_jitter),
        ("anti_emulation", "Anti-Emulation Checks", check_anti_emulation),
    ]

    # Add ROM check for retro platforms
    if include_rom_check and ROM_DB_AVAILABLE:
        checks.append(("rom_fingerprint", "ROM Fingerprint (Retro)", check_rom_fingerprint))

    print(f"Running {len(checks)} Hardware Fingerprint Checks...")
    print("=" * 50)

    total_checks = len(checks)
    for i, (key, name, func) in enumerate(checks, 1):
        print(f"\n[{i}/{total_checks}] {name}...")
        try:
            passed, data = func()
        except Exception as e:
            passed = False
            data = {"error": str(e)}
        results[key] = {"passed": passed, "data": data}
        if not passed:
            all_passed = False
        print("  Result: {}".format("PASS" if passed else "FAIL"))

    print("\n" + "=" * 50)
    print("OVERALL RESULT: {}".format("ALL CHECKS PASSED" if all_passed else "FAILED"))

    if not all_passed:
        failed = [k for k, v in results.items() if not v["passed"]]
        print("Failed checks: {}".format(failed))

    return all_passed, results


if __name__ == "__main__":
    import json
    passed, results = validate_all_checks()
    print("\n\nDetailed Results:")
    print(json.dumps(results, indent=2, default=str))
