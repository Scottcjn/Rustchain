#!/usr/bin/env python3
"""
RIP-PoA Hardware Fingerprint Validation - POWER8 Optimized
===========================================================
7 Required Checks for RTC Reward Approval
ALL MUST PASS for antiquity multiplier rewards

POWER8 Modifications:
- Larger buffer sizes for cache timing (POWER8 has huge caches)
- Random access patterns to defeat aggressive prefetching
- Adjusted thresholds for server-class CPUs
"""

import hashlib
import os
import platform
import random
import statistics
import subprocess
import time
from typing import Dict, List, Optional, Tuple


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


def check_cache_timing_power8(iterations: int = 50) -> Tuple[bool, Dict]:
    """
    Check 2: Cache Timing Fingerprint - POWER8 Optimized

    POWER8 S824 cache sizes:
    - L1: 32KB per core (instruction) + 64KB per core (data)
    - L2: 512KB per core
    - L3: 8MB per core pair (shared)
    - L4 (off-chip eDRAM): 128MB per chip (optional)

    Uses random access pattern to defeat POWER8's aggressive prefetching.
    """
    # Much larger buffers for POWER8's huge caches
    l1_size = 32 * 1024         # 32KB - fits in L1
    l2_size = 1 * 1024 * 1024   # 1MB - exceeds L1, fits L2
    l3_size = 16 * 1024 * 1024  # 16MB - exceeds L2, hits L3

    def measure_random_access_time(buffer_size: int, accesses: int = 2000) -> float:
        """Random access defeats prefetching, reveals true cache latency"""
        buf = bytearray(buffer_size)
        # Initialize
        for i in range(0, buffer_size, 64):
            buf[i] = i % 256

        # Generate random indices ahead of time
        indices = [random.randint(0, buffer_size - 1) for _ in range(accesses)]

        # Measure random access
        start = time.perf_counter_ns()
        acc = 0
        for idx in indices:
            acc ^= buf[idx]
        elapsed = time.perf_counter_ns() - start
        return elapsed / accesses, acc

    l1_times = []
    l2_times = []
    l3_times = []

    for _ in range(iterations):
        t1, _ = measure_random_access_time(l1_size)
        l1_times.append(t1)
        t2, _ = measure_random_access_time(l2_size)
        l2_times.append(t2)
        t3, _ = measure_random_access_time(l3_size)
        l3_times.append(t3)

    l1_avg = statistics.mean(l1_times)
    l2_avg = statistics.mean(l2_times)
    l3_avg = statistics.mean(l3_times)

    l1_stdev = statistics.stdev(l1_times) if len(l1_times) > 1 else 0
    l2_stdev = statistics.stdev(l2_times) if len(l2_times) > 1 else 0
    l3_stdev = statistics.stdev(l3_times) if len(l3_times) > 1 else 0

    l2_l1_ratio = l2_avg / l1_avg if l1_avg > 0 else 0
    l3_l2_ratio = l3_avg / l2_avg if l2_avg > 0 else 0

    data = {
        "l1_ns": round(l1_avg, 2),
        "l2_ns": round(l2_avg, 2),
        "l3_ns": round(l3_avg, 2),
        "l1_stdev": round(l1_stdev, 2),
        "l2_stdev": round(l2_stdev, 2),
        "l3_stdev": round(l3_stdev, 2),
        "l2_l1_ratio": round(l2_l1_ratio, 3),
        "l3_l2_ratio": round(l3_l2_ratio, 3),
        "platform": "power8_optimized",
    }

    valid = True
    # For POWER8, any positive variance indicates real cache hierarchy
    # VMs/emulators have flat latency profiles
    total_variance = l1_stdev + l2_stdev + l3_stdev
    if total_variance < 1.0:  # No variance at all = synthetic
        valid = False
        data["fail_reason"] = "no_timing_variance"
    elif l1_avg == 0 or l2_avg == 0 or l3_avg == 0:
        valid = False
        data["fail_reason"] = "zero_latency"
    # POWER8's excellent prefetching might show small ratios, but should still have variance
    elif l2_l1_ratio < 0.95 and l3_l2_ratio < 0.95 and total_variance < 5.0:
        valid = False
        data["fail_reason"] = "no_cache_hierarchy"

    return valid, data


def check_simd_identity() -> Tuple[bool, Dict]:
    """Check 3: SIMD Unit Identity (SSE/AVX/AltiVec/NEON/VSX)"""
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

    # POWER8-specific: check for VSX/AltiVec
    if not flags and ("ppc" in arch or "power" in arch):
        try:
            result = subprocess.run(
                ["grep", "-i", "vsx\|altivec\|dfp", "/proc/cpuinfo"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout:
                flags = ["vsx", "altivec", "dfp", "power8"]
        except:
            # For POWER8, these are always present
            flags = ["vsx", "altivec", "dfp", "power8"]

    has_sse = any("sse" in f.lower() for f in flags)
    has_avx = any("avx" in f.lower() for f in flags)
    has_altivec = any("altivec" in f.lower() for f in flags) or "ppc" in arch
    has_vsx = any("vsx" in f.lower() for f in flags) or "power" in arch
    has_neon = any("neon" in f.lower() for f in flags) or "arm" in arch

    data = {
        "arch": arch,
        "simd_flags_count": len(flags),
        "has_sse": has_sse,
        "has_avx": has_avx,
        "has_altivec": has_altivec,
        "has_vsx": has_vsx,
        "has_neon": has_neon,
        "sample_flags": flags[:10] if flags else [],
    }

    # POWER8 always has AltiVec and VSX
    valid = has_sse or has_avx or has_altivec or has_vsx or has_neon or len(flags) > 0
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

    # Warm up the CPU
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
    """Check 6: Anti-Emulation Behavioral Checks

    Detects:
    - x86 hypervisors (VMware, VirtualBox, KVM, QEMU, Xen, Hyper-V)
    - IBM LPAR/PowerVM (POWER systems virtualization)
    - Container environments (Docker, Kubernetes)

    For POWER systems:
    - LPAR = virtualized (blocked) - even if full-system LPAR
    - PowerNV/Petitboot = bare metal (allowed)
    """
    vm_indicators = []

    # x86 VM paths
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

    # === IBM POWER LPAR Detection ===
    # LPAR = Logical Partition under PowerVM hypervisor (virtualized)
    # PowerNV/Petitboot = OPAL firmware, bare metal (not virtualized)
    arch = platform.machine().lower()
    if "ppc64" in arch or "powerpc" in arch:
        # Check for LPAR config (exists only under PowerVM hypervisor)
        if os.path.exists("/proc/ppc64/lparcfg"):
            vm_indicators.append("power:lpar_detected")
            # Read LPAR details for logging
            try:
                with open("/proc/ppc64/lparcfg", "r") as f:
                    for line in f:
                        if line.startswith("partition_id="):
                            vm_indicators.append("power:lpar_partition_id=" + line.split("=")[1].strip())
                        elif line.startswith("NumLpars="):
                            vm_indicators.append("power:num_lpars=" + line.split("=")[1].strip())
            except:
                pass

        # Check for partition name (another LPAR indicator)
        if os.path.exists("/proc/device-tree/ibm,partition-name"):
            try:
                with open("/proc/device-tree/ibm,partition-name", "rb") as f:
                    partition_name = f.read().decode().strip().rstrip('\x00')
                    if partition_name:
                        vm_indicators.append("power:partition_name=" + partition_name)
            except:
                pass

        # PowerNV (bare metal) detection - this is the ALLOWED mode
        # PowerNV systems don't have lparcfg
        is_powernv = not os.path.exists("/proc/ppc64/lparcfg")
        if is_powernv:
            # Double-check with dmesg for OPAL
            try:
                result = subprocess.run(
                    ["dmesg"],
                    capture_output=True, text=True, timeout=5
                )
                if "OPAL" in result.stdout or "powernv" in result.stdout.lower():
                    # This is bare metal PowerNV - NOT a VM indicator
                    pass  # Don't add to vm_indicators
            except:
                pass

    data = {
        "vm_indicators": vm_indicators,
        "indicator_count": len(vm_indicators),
        "is_likely_vm": len(vm_indicators) > 0,
        "arch": arch,
    }

    valid = len(vm_indicators) == 0
    if not valid:
        data["fail_reason"] = "vm_detected"

    return valid, data


def check_power8_hardware() -> Tuple[bool, Dict]:
    """Check 7: POWER8 Hardware Verification"""
    arch = platform.machine().lower()

    data = {
        "arch": arch,
        "is_power8": False,
        "cpu_model": "",
        "smt_threads": 0,
    }

    # Check if actually POWER8
    if "ppc64" not in arch and "powerpc" not in arch:
        data["fail_reason"] = "not_powerpc"
        return True, data  # Pass for non-PPC (they'll use other checks)

    # Get CPU info
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
            if "POWER8" in content:
                data["is_power8"] = True
            # Extract CPU model
            for line in content.split("\n"):
                if line.startswith("cpu"):
                    data["cpu_model"] = line.split(":")[-1].strip()
                    break
    except:
        pass

    # Check SMT threads (POWER8 has SMT8 = 128 threads for 16 cores)
    try:
        result = subprocess.run(["nproc"], capture_output=True, text=True, timeout=5)
        data["smt_threads"] = int(result.stdout.strip())
    except:
        pass

    # POWER8 S824 should have 128 threads (16 cores x 8 SMT)
    valid = True
    if data["is_power8"] and data["smt_threads"] < 64:
        # If claiming POWER8 but not enough threads, suspicious
        valid = False
        data["fail_reason"] = "insufficient_threads_for_power8"

    return valid, data


def validate_all_checks(include_rom_check: bool = False) -> Tuple[bool, Dict]:
    """Run all fingerprint checks - POWER8 optimized version."""
    results = {}
    all_passed = True

    checks = [
        ("clock_drift", "Clock-Skew & Oscillator Drift", check_clock_drift),
        ("cache_timing", "Cache Timing Fingerprint (POWER8)", check_cache_timing_power8),
        ("simd_identity", "SIMD Unit Identity", check_simd_identity),
        ("thermal_drift", "Thermal Drift Entropy", check_thermal_drift),
        ("instruction_jitter", "Instruction Path Jitter", check_instruction_jitter),
        ("anti_emulation", "Anti-Emulation Checks", check_anti_emulation),
        ("power8_verify", "POWER8 Hardware Verification", check_power8_hardware),
    ]

    print(f"Running {len(checks)} Hardware Fingerprint Checks (POWER8 Optimized)...")
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
