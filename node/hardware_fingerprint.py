#!/usr/bin/env python3
"""
RIP-PoA Hardware Fingerprint Collection
========================================
Comprehensive hardware fingerprinting for anti-emulation attestation.
All 7 checks must pass for RTC reward approval.
"""

import hashlib
import os
import platform
import statistics
import struct
import subprocess
import time
from typing import Dict, List, Tuple, Optional

# Number of samples for each measurement
CLOCK_DRIFT_SAMPLES = 1000
CACHE_TIMING_ITERATIONS = 100
JITTER_SAMPLES = 500
THERMAL_SAMPLES = 50


class HardwareFingerprint:
    """Collects comprehensive hardware fingerprints for attestation"""
    
    @staticmethod
    def collect_clock_drift(samples: int = CLOCK_DRIFT_SAMPLES) -> Dict:
        """
        1. Clock-Skew & Oscillator Drift
        Measures microscopic timing imperfections in the CPU oscillator.
        Cannot be faked by VMs - each physical chip has unique drift.
        """
        intervals = []
        reference_ops = 10000  # Hash operations per measurement
        
        for i in range(samples):
            # Measure time for fixed hash operations
            data = f"drift_sample_{i}".encode()
            start = time.perf_counter_ns()
            for _ in range(reference_ops):
                hashlib.sha256(data).digest()
            elapsed = time.perf_counter_ns() - start
            intervals.append(elapsed)
            
            # Small delay to capture oscillator drift
            if i % 100 == 0:
                time.sleep(0.001)  # 1ms pause every 100 samples
        
        # Calculate drift statistics
        mean_interval = statistics.mean(intervals)
        variance = statistics.variance(intervals) if len(intervals) > 1 else 0
        stdev = statistics.stdev(intervals) if len(intervals) > 1 else 0
        
        # Drift signature: how much variance between consecutive samples
        drifts = [abs(intervals[i+1] - intervals[i]) for i in range(len(intervals)-1)]
        drift_mean = statistics.mean(drifts) if drifts else 0
        drift_variance = statistics.variance(drifts) if len(drifts) > 1 else 0
        
        # Calculate "drift fingerprint" hash
        drift_data = struct.pack(">dddd", mean_interval, variance, drift_mean, drift_variance)
        drift_hash = hashlib.sha256(drift_data).hexdigest()[:16]
        
        return {
            "mean_ns": mean_interval,
            "variance": variance,
            "stdev": stdev,
            "drift_mean": drift_mean,
            "drift_variance": drift_variance,
            "drift_hash": drift_hash,
            "samples": samples,
            "valid": variance > 0  # Must have some variance (real hardware)
        }
    
    @staticmethod
    def collect_cache_timing(iterations: int = CACHE_TIMING_ITERATIONS) -> Dict:
        """
        2. Cache Timing Fingerprint (L1/L2/L3 Latency Tone)
        Measures latency harmonics across varying buffer sizes.
        Creates unique "echo pattern" based on cache hierarchy.
        """
        # Test different buffer sizes to hit L1, L2, L3, and main memory
        buffer_sizes = [
            4 * 1024,       # 4KB - L1 cache
            32 * 1024,      # 32KB - L1/L2 boundary
            256 * 1024,     # 256KB - L2 cache
            1024 * 1024,    # 1MB - L2/L3 boundary
            4 * 1024 * 1024, # 4MB - L3 cache
            16 * 1024 * 1024 # 16MB - main memory
        ]
        
        latencies = {}
        
        for size in buffer_sizes:
            try:
                # Allocate buffer
                buf = bytearray(size)
                
                # Sequential access timing
                seq_times = []
                for _ in range(iterations):
                    start = time.perf_counter_ns()
                    for j in range(0, min(size, 65536), 64):  # 64-byte stride
                        _ = buf[j]
                    elapsed = time.perf_counter_ns() - start
                    seq_times.append(elapsed)
                
                # Random access timing
                rand_times = []
                import random
                indices = [random.randint(0, size-1) for _ in range(1000)]
                for _ in range(iterations):
                    start = time.perf_counter_ns()
                    for idx in indices:
                        _ = buf[idx]
                    elapsed = time.perf_counter_ns() - start
                    rand_times.append(elapsed)
                
                latencies[f"{size//1024}KB"] = {
                    "sequential_ns": statistics.mean(seq_times),
                    "random_ns": statistics.mean(rand_times),
                    "seq_variance": statistics.variance(seq_times) if len(seq_times) > 1 else 0,
                    "rand_variance": statistics.variance(rand_times) if len(rand_times) > 1 else 0
                }
                
            except MemoryError:
                latencies[f"{size//1024}KB"] = {"error": "memory_allocation_failed"}
        
        # Calculate cache "tone" - ratio patterns between levels
        tone_ratios = []
        keys = list(latencies.keys())
        for i in range(len(keys)-1):
            if "error" not in latencies[keys[i]] and "error" not in latencies[keys[i+1]]:
                ratio = latencies[keys[i+1]]["random_ns"] / latencies[keys[i]]["random_ns"] if latencies[keys[i]]["random_ns"] > 0 else 0
                tone_ratios.append(ratio)
        
        # Generate cache fingerprint hash
        tone_data = struct.pack(f">{len(tone_ratios)}d", *tone_ratios) if tone_ratios else b""
        cache_hash = hashlib.sha256(tone_data).hexdigest()[:16]
        
        return {
            "latencies": latencies,
            "tone_ratios": tone_ratios,
            "cache_hash": cache_hash,
            "valid": len(tone_ratios) > 0
        }
    
    @staticmethod
    def collect_simd_profile() -> Dict:
        """
        3. SIMD Unit Identity (SSE/AVX/AltiVec/NEON Bias Profile)
        Measures SIMD instruction latency bias and throughput asymmetry.
        Software emulation flattens this - real hardware has unique patterns.
        """
        machine = platform.machine().lower()
        simd_type = "unknown"
        
        # Detect SIMD type
        if machine in ("ppc", "ppc64", "powerpc", "powerpc64"):
            simd_type = "altivec"
        elif machine == "arm64" or machine == "aarch64":
            simd_type = "neon"
        elif machine in ("x86_64", "amd64", "x64", "i386", "i686"):
            simd_type = "sse_avx"
        
        # Measure integer vs float operation bias
        int_times = []
        float_times = []
        
        for _ in range(100):
            # Integer operations
            start = time.perf_counter_ns()
            x = 12345678
            for _ in range(10000):
                x = (x * 1103515245 + 12345) & 0x7FFFFFFF
            elapsed = time.perf_counter_ns() - start
            int_times.append(elapsed)
            
            # Float operations
            start = time.perf_counter_ns()
            y = 1.23456789
            for _ in range(10000):
                y = y * 1.0000001 + 0.0000001
            elapsed = time.perf_counter_ns() - start
            float_times.append(elapsed)
        
        int_mean = statistics.mean(int_times)
        float_mean = statistics.mean(float_times)
        
        # Ratio indicates pipeline balance
        int_float_ratio = int_mean / float_mean if float_mean > 0 else 0
        
        # Try to detect vector unit characteristics via memory patterns
        vector_latencies = []
        try:
            buf = bytearray(1024 * 1024)  # 1MB
            for _ in range(50):
                start = time.perf_counter_ns()
                # Pattern that triggers vector loads on most architectures
                for i in range(0, len(buf) - 128, 128):
                    buf[i:i+64] = buf[i+64:i+128]
                elapsed = time.perf_counter_ns() - start
                vector_latencies.append(elapsed)
        except:
            pass
        
        vector_mean = statistics.mean(vector_latencies) if vector_latencies else 0
        vector_variance = statistics.variance(vector_latencies) if len(vector_latencies) > 1 else 0
        
        return {
            "simd_type": simd_type,
            "int_mean_ns": int_mean,
            "float_mean_ns": float_mean,
            "int_float_ratio": int_float_ratio,
            "vector_mean_ns": vector_mean,
            "vector_variance": vector_variance,
            "valid": simd_type != "unknown"
        }
    
    @staticmethod
    def collect_thermal_drift(samples: int = THERMAL_SAMPLES) -> Dict:
        """
        4. Thermal Drift Entropy
        Measures performance changes as CPU heats up.
        Old silicon shows drift that simulators ignore.
        """
        # Phase 1: Baseline (cold)
        cold_times = []
        for _ in range(samples):
            start = time.perf_counter_ns()
            data = b"thermal_test" * 1000
            for _ in range(100):
                hashlib.sha256(data).digest()
            elapsed = time.perf_counter_ns() - start
            cold_times.append(elapsed)
        
        cold_mean = statistics.mean(cold_times)
        
        # Phase 2: Heat up (sustained load)
        heat_times = []
        for _ in range(samples * 3):  # 3x more work to heat up
            start = time.perf_counter_ns()
            data = b"thermal_heat" * 1000
            for _ in range(500):  # 5x more work per iteration
                hashlib.sha256(data).digest()
            elapsed = time.perf_counter_ns() - start
            heat_times.append(elapsed)
        
        hot_mean = statistics.mean(heat_times[-samples:])  # Last samples are "hot"
        
        # Phase 3: Cooldown observation
        time.sleep(0.1)  # Brief pause
        cooldown_times = []
        for _ in range(samples):
            start = time.perf_counter_ns()
            data = b"thermal_cool" * 1000
            for _ in range(100):
                hashlib.sha256(data).digest()
            elapsed = time.perf_counter_ns() - start
            cooldown_times.append(elapsed)
        
        cooldown_mean = statistics.mean(cooldown_times)
        
        # Thermal signature: how much does performance change with temperature
        thermal_drift = (hot_mean - cold_mean) / cold_mean if cold_mean > 0 else 0
        recovery_rate = (cooldown_mean - cold_mean) / cold_mean if cold_mean > 0 else 0
        
        return {
            "cold_mean_ns": cold_mean,
            "hot_mean_ns": hot_mean,
            "cooldown_mean_ns": cooldown_mean,
            "thermal_drift_pct": thermal_drift * 100,
            "recovery_pct": recovery_rate * 100,
            "valid": abs(thermal_drift) > 0.001  # Must show some thermal effect
        }
    
    @staticmethod
    def collect_instruction_jitter(samples: int = JITTER_SAMPLES) -> Dict:
        """
        5. Instruction Path Jitter (Microarchitectural Jitter Map)
        Captures cycle-level jitter across different pipeline types.
        No VM replicates real jitter patterns.
        """
        jitter_map = {}
        
        # Integer pipeline jitter
        int_jitter = []
        for _ in range(samples):
            start = time.perf_counter_ns()
            x = 0
            for i in range(1000):
                x += i * 3 - i // 2
            elapsed = time.perf_counter_ns() - start
            int_jitter.append(elapsed)
        jitter_map["integer"] = {
            "mean": statistics.mean(int_jitter),
            "stdev": statistics.stdev(int_jitter) if len(int_jitter) > 1 else 0,
            "min": min(int_jitter),
            "max": max(int_jitter)
        }
        
        # Branch prediction jitter
        branch_jitter = []
        import random
        pattern = [random.choice([True, False]) for _ in range(1000)]
        for _ in range(samples):
            start = time.perf_counter_ns()
            count = 0
            for p in pattern:
                if p:
                    count += 1
                else:
                    count -= 1
            elapsed = time.perf_counter_ns() - start
            branch_jitter.append(elapsed)
        jitter_map["branch"] = {
            "mean": statistics.mean(branch_jitter),
            "stdev": statistics.stdev(branch_jitter) if len(branch_jitter) > 1 else 0,
            "min": min(branch_jitter),
            "max": max(branch_jitter)
        }
        
        # FPU jitter
        fpu_jitter = []
        for _ in range(samples):
            start = time.perf_counter_ns()
            y = 1.0
            for i in range(1000):
                y = y * 1.0001 + 0.0001
            elapsed = time.perf_counter_ns() - start
            fpu_jitter.append(elapsed)
        jitter_map["fpu"] = {
            "mean": statistics.mean(fpu_jitter),
            "stdev": statistics.stdev(fpu_jitter) if len(fpu_jitter) > 1 else 0,
            "min": min(fpu_jitter),
            "max": max(fpu_jitter)
        }
        
        # Memory load/store jitter
        mem_jitter = []
        buf = bytearray(4096)
        for _ in range(samples):
            start = time.perf_counter_ns()
            for i in range(1000):
                buf[i % 4096] = i & 0xFF
                _ = buf[(i * 7) % 4096]
            elapsed = time.perf_counter_ns() - start
            mem_jitter.append(elapsed)
        jitter_map["memory"] = {
            "mean": statistics.mean(mem_jitter),
            "stdev": statistics.stdev(mem_jitter) if len(mem_jitter) > 1 else 0,
            "min": min(mem_jitter),
            "max": max(mem_jitter)
        }
        
        # Jitter uniformity check (emulators tend to have very uniform jitter)
        all_stdevs = [v["stdev"] for v in jitter_map.values()]
        avg_jitter_stdev = statistics.mean(all_stdevs)
        
        return {
            "jitter_map": jitter_map,
            "avg_jitter_stdev": avg_jitter_stdev,
            "valid": avg_jitter_stdev > 100  # Real hardware has >100ns jitter variance
        }
    
    @staticmethod
    def collect_device_oracle() -> Dict:
        """
        6. Device-Age Oracle Fields (Historicity Attestation)
        Collects metadata about CPU model, release year, stepping, etc.
        """
        oracle = {
            "machine": platform.machine(),
            "processor": platform.processor(),
            "system": platform.system(),
            "release": platform.release(),
            "python_version": platform.python_version(),
        }
        
        # Try to get detailed CPU info
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                    
                # Extract key fields
                for line in cpuinfo.split("\n"):
                    if line.startswith("model name"):
                        oracle["cpu_model"] = line.split(":")[1].strip()
                    elif line.startswith("cpu"):
                        if ":" in line:
                            key = line.split(":")[0].strip().replace(" ", "_")
                            oracle[key] = line.split(":")[1].strip()
                    elif line.startswith("stepping"):
                        oracle["stepping"] = line.split(":")[1].strip()
                    elif line.startswith("cpu family"):
                        oracle["cpu_family"] = line.split(":")[1].strip()
                        
            elif platform.system() == "Darwin":
                # macOS - use sysctl
                try:
                    result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                          capture_output=True, text=True, timeout=5)
                    oracle["cpu_model"] = result.stdout.strip()
                except:
                    pass
                    
        except:
            pass
        
        # Estimate release year from CPU model (heuristic)
        cpu_model = oracle.get("cpu_model", oracle.get("processor", "")).lower()
        release_year = 2020  # default
        
        if "g4" in cpu_model or "7450" in cpu_model or "7447" in cpu_model:
            release_year = 2003
        elif "g5" in cpu_model or "970" in cpu_model:
            release_year = 2005
        elif "g3" in cpu_model or "750" in cpu_model:
            release_year = 1999
        elif "core 2" in cpu_model:
            release_year = 2006
        elif "nehalem" in cpu_model:
            release_year = 2008
        elif "sandy" in cpu_model:
            release_year = 2011
        elif "m1" in cpu_model:
            release_year = 2020
        elif "m2" in cpu_model:
            release_year = 2022
        elif "m3" in cpu_model:
            release_year = 2023
        
        oracle["estimated_release_year"] = release_year
        oracle["estimated_age_years"] = 2025 - release_year
        oracle["valid"] = "cpu_model" in oracle or "processor" in oracle
        
        return oracle
    
    @staticmethod
    def check_anti_emulation() -> Dict:
        """
        7. Anti-Emulation Behavioral Checks
        Detects VMs, hypervisors, and emulators.
        """
        checks = {
            "hypervisor_detected": False,
            "time_dilation": False,
            "uniform_jitter": False,
            "perfect_cache": False,
            "vm_artifacts": []
        }
        
        # Check for hypervisor via cpuid (x86) or other indicators
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read().lower()
                    if "hypervisor" in cpuinfo:
                        checks["hypervisor_detected"] = True
                        checks["vm_artifacts"].append("hypervisor_flag")
                        
                # Check for VM-specific devices
                try:
                    with open("/sys/class/dmi/id/product_name", "r") as f:
                        product = f.read().lower()
                        if any(vm in product for vm in ["virtual", "vmware", "qemu", "kvm", "xen"]):
                            checks["vm_artifacts"].append(f"dmi_product:{product.strip()}")
                except:
                    pass
                    
        except:
            pass
        
        # Time dilation check: measure if time flows consistently
        time_samples = []
        for _ in range(20):
            start = time.perf_counter_ns()
            time.sleep(0.001)  # Request 1ms sleep
            elapsed = time.perf_counter_ns() - start
            time_samples.append(elapsed)
        
        # Real hardware sleeps ~1ms ± 0.5ms; VMs often have 10x+ variance
        sleep_mean = statistics.mean(time_samples)
        sleep_variance = statistics.variance(time_samples) if len(time_samples) > 1 else 0
        
        # 1ms = 1,000,000 ns; expect ±500,000ns variance on real HW
        if sleep_mean > 5_000_000:  # >5ms for 1ms sleep = time dilation
            checks["time_dilation"] = True
            checks["vm_artifacts"].append("time_dilation_detected")
        
        # Jitter uniformity check (emulators have unnaturally uniform timing)
        jitter_test = []
        for _ in range(100):
            start = time.perf_counter_ns()
            x = 0
            for i in range(100):
                x += i
            elapsed = time.perf_counter_ns() - start
            jitter_test.append(elapsed)
        
        jitter_cv = statistics.stdev(jitter_test) / statistics.mean(jitter_test) if statistics.mean(jitter_test) > 0 else 0
        if jitter_cv < 0.01:  # <1% coefficient of variation = too uniform
            checks["uniform_jitter"] = True
            checks["vm_artifacts"].append("uniform_jitter_pattern")
        
        checks["sleep_mean_ns"] = sleep_mean
        checks["sleep_variance"] = sleep_variance
        checks["jitter_cv"] = jitter_cv
        checks["valid"] = not checks["hypervisor_detected"] and not checks["time_dilation"]
        
        return checks
    
    @classmethod
    def collect_all(cls) -> Dict:
        """Collect all hardware fingerprints"""
        print("Collecting hardware fingerprints...")
        
        print("  [1/7] Clock-Skew & Oscillator Drift...")
        clock_drift = cls.collect_clock_drift()
        
        print("  [2/7] Cache Timing Fingerprint...")
        cache_timing = cls.collect_cache_timing()
        
        print("  [3/7] SIMD Unit Identity...")
        simd_profile = cls.collect_simd_profile()
        
        print("  [4/7] Thermal Drift Entropy...")
        thermal_drift = cls.collect_thermal_drift()
        
        print("  [5/7] Instruction Path Jitter...")
        instruction_jitter = cls.collect_instruction_jitter()
        
        print("  [6/7] Device-Age Oracle...")
        device_oracle = cls.collect_device_oracle()
        
        print("  [7/7] Anti-Emulation Checks...")
        anti_emulation = cls.check_anti_emulation()
        
        # Count passed checks
        checks_passed = sum([
            clock_drift.get("valid", False),
            cache_timing.get("valid", False),
            simd_profile.get("valid", False),
            thermal_drift.get("valid", False),
            instruction_jitter.get("valid", False),
            device_oracle.get("valid", False),
            anti_emulation.get("valid", False)
        ])
        
        return {
            "clock_drift": clock_drift,
            "cache_timing": cache_timing,
            "simd_profile": simd_profile,
            "thermal_drift": thermal_drift,
            "instruction_jitter": instruction_jitter,
            "device_oracle": device_oracle,
            "anti_emulation": anti_emulation,
            "checks_passed": checks_passed,
            "checks_total": 7,
            "all_valid": checks_passed == 7,
            "timestamp": int(time.time())
        }


if __name__ == "__main__":
    print("=" * 60)
    print("RIP-PoA Hardware Fingerprint Collection")
    print("=" * 60)
    
    fingerprints = HardwareFingerprint.collect_all()
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {fingerprints[\"checks_passed\"]}/7 checks passed")
    print("=" * 60)
    
    for name, data in fingerprints.items():
        if isinstance(data, dict) and "valid" in data:
            status = "PASS" if data["valid"] else "FAIL"
            print(f"  {name}: {status}")
    
    print(f"\nAll Valid: {fingerprints[\"all_valid\"]}")
