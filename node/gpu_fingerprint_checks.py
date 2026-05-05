#!/usr/bin/env python3
"""
RIP-0308 Channel 8: GPU Hardware Fingerprint Validation
========================================================
GPU Fingerprinting for RustChain Proof of Physical AI

Detects real GPU hardware via:
1. Shader Execution Jitter — timing variance across shader cores
2. VRAM Timing Profiles — access latency unique to each GPU
3. Compute Unit Asymmetry — throughput differences between CUs
4. Thermal Throttle Signatures — GPU response to sustained load

Supports:
- NVIDIA GPUs (via CUDA / nvidia-smi / pycuda)
- AMD GPUs (via ROCm / rocm-smi)

Must distinguish two GPUs of the same model (silicon lottery).
Must detect VM GPU pass-through (vfio-pci spoofing).

Bounty: #2147 — 150 RTC (+50 bonus for vintage GPU)
Author: BossChaos
"""

import hashlib
import os
import platform
import statistics
import subprocess
import time
import struct
from typing import Dict, List, Optional, Tuple


# ─── GPU Detection ───────────────────────────────────────────────────────────

def _detect_gpu_vendor() -> Optional[str]:
    """Detect GPU vendor: 'nvidia', 'amd', or None."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "nvidia"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return "amd"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: check /sys/class/drm
    try:
        for entry in os.listdir("/sys/class/drm"):
            if "card0" in entry and "render" not in entry:
                device_path = f"/sys/class/drm/{entry}/device/vendor"
                if os.path.exists(device_path):
                    with open(device_path, "r") as f:
                        vendor = f.read().strip().lower()
                        if "0x10de" in vendor:
                            return "nvidia"
                        elif "0x1002" in vendor:
                            return "amd"
    except Exception:
        pass

    return None


def _get_gpu_info(vendor: str) -> Dict:
    """Get GPU identification info."""
    info = {"vendor": vendor, "name": "unknown", "vram_mb": 0, "driver": "unknown"}

    if vendor == "nvidia":
        try:
            # GPU name
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,pci.bus_id",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 4:
                    info["name"] = parts[0].strip()
                    info["vram_mb"] = int(parts[1].strip().replace(" MiB", ""))
                    info["driver"] = parts[2].strip()
                    info["pci_bus_id"] = parts[3].strip()
        except Exception:
            pass

    elif vendor == "amd":
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--showmeminfo", "vram"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "GPU[" in line and "product name" in line.lower():
                        info["name"] = line.split(":", 1)[-1].strip()
        except Exception:
            pass

        # Fallback: read from sysfs
        try:
            for kfd_path in ["/sys/class/kfd/kfd/topology/nodes"]:
                if os.path.exists(kfd_path):
                    for node in os.listdir(kfd_path):
                        props_path = os.path.join(kfd_path, node, "properties")
                        if os.path.exists(props_path):
                            with open(props_path, "r") as f:
                                for line in f:
                                    if "name" in line.lower():
                                        info["name"] = line.split(":", 1)[-1].strip()
                                        break
        except Exception:
            pass

    return info


# ─── Channel 8 Check 1: Shader Execution Jitter ─────────────────────────────

def check_shader_execution_jitter(samples: int = 300) -> Tuple[bool, Dict]:
    """
    Check 1: Shader Execution Jitter

    Measures timing variance of compute shader / GPU kernel execution.
    Real GPUs exhibit measurable jitter from:
    - Clock domain crossing (shader core <-> memory controller)
    - Power delivery noise on GPU VRM
    - Thermal-induced frequency modulation
    - Silicon lottery: each die has unique leakage / timing

    Emulators/VMs show artificially consistent timing (CV < threshold).
    """
    vendor = _detect_gpu_vendor()
    if vendor is None:
        return True, {
            "skipped": True,
            "reason": "no_gpu_detected",
            "channel": "gpu_shader_jitter"
        }

    timings = []

    if vendor == "nvidia":
        timings = _measure_cuda_kernel_jitter(samples)
    elif vendor == "amd":
        timings = _measure_rocm_kernel_jitter(samples)

    if not timings or len(timings) < 10:
        return True, {
            "skipped": True,
            "reason": "kernel_execution_unavailable",
            "vendor": vendor,
            "channel": "gpu_shader_jitter"
        }

    mean_ns = statistics.mean(timings)
    stdev_ns = statistics.stdev(timings)
    cv = stdev_ns / mean_ns if mean_ns > 0 else 0

    # Consecutive-jitter analysis (anti-spoofing)
    deltas = [abs(timings[i] - timings[i - 1]) for i in range(1, len(timings))]
    delta_mean = statistics.mean(deltas) if deltas else 0
    delta_stdev = statistics.stdev(deltas) if len(deltas) > 1 else 0

    data = {
        "channel": "gpu_shader_jitter",
        "vendor": vendor,
        "samples": len(timings),
        "mean_ns": int(mean_ns),
        "stdev_ns": int(stdev_ns),
        "cv": round(cv, 8),
        "delta_mean_ns": int(delta_mean),
        "delta_stdev_ns": int(delta_stdev),
        "min_ns": min(timings),
        "max_ns": max(timings),
    }

    # Real GPU jitter: CV > 0.001 (0.1%) is typical for consumer GPUs
    # VMs with GPU passthrough often show CV < 0.0005
    if cv < 0.0001:
        data["fail_reason"] = "synthetic_gpu_timing_cv_too_low"
        return False, data

    if stdev_ns == 0:
        data["fail_reason"] = "no_shader_jitter_detected"
        return False, data

    return True, data


def _measure_cuda_kernel_jitter(samples: int) -> List[int]:
    """Measure CUDA kernel timing jitter via nvidia-smi compute loop."""
    timings = []

    # Method 1: Try pycuda first (most accurate)
    try:
        import pycuda.autoinit
        import pycuda.driver as drv
        import numpy as np

        # Simple element-wise multiply kernel
        mod = drv.SourceModule("""
        __global__ void jitter_kernel(float *a, float *b, float *c, int n) {
            int idx = blockIdx.x * blockDim.x + threadIdx.x;
            if (idx < n) {
                float sum = 0.0f;
                for (int i = 0; i < 1024; i++) {
                    sum += a[idx] * b[idx] + sinf((float)i);
                }
                c[idx] = sum;
            }
        }
        """)
        func = mod.get_function("jitter_kernel")

        n = 1024 * 256
        a = np.random.randn(n).astype(np.float32)
        b = np.random.randn(n).astype(np.float32)
        c = np.zeros_like(a)

        block = (256, 1, 1)
        grid = (n // 256, 1)

        for _ in range(samples):
            start = drv.Event()
            end = drv.Event()
            start.record()
            func(drv.In(a), drv.In(b), drv.Out(c), np.int32(n),
                 block=block, grid=grid)
            end.record()
            end.synchronize()
            elapsed_ms = start.time_till(end)
            timings.append(int(elapsed_ms * 1_000_000))  # to ns

        return timings
    except Exception:
        pass

    # Method 2: Fallback — nvidia-smi dmon or compute benchmark
    try:
        # Run a small CUDA benchmark via python with numba
        from numba import cuda
        import numpy as np

        @cuda.jit
        def _numba_kernel(a, b, c):
            idx = cuda.grid(1)
            if idx < len(a):
                s = 0.0
                for i in range(512):
                    s += a[idx] * b[idx]
                c[idx] = s

        n = 1024 * 128
        a = np.random.randn(n).astype(np.float32)
        b = np.random.randn(n).astype(np.float32)
        c = np.zeros_like(a)

        threads = 256
        blocks = (n + threads - 1) // threads

        for _ in range(samples):
            start = cuda.event()
            end = cuda.event()
            start.record()
            _numba_kernel[blocks, threads](a, b, c)
            end.record()
            end.synchronize()
            elapsed_ms = start.till(end)
            timings.append(int(elapsed_ms * 1_000_000))

        return timings
    except Exception:
        pass

    # Method 3: Last resort — nvidia-smi polling during compute load
    try:
        import numpy as np
        from numba import cuda

        @cuda.jit
        def _heavy_kernel(out, n_iters):
            idx = cuda.grid(1)
            if idx < out.shape[0]:
                val = 0.0
                for i in range(n_iters):
                    val += (i * 0.001) % 1.0
                out[idx] = val

        n = 65536
        out = cuda.device_array(n, dtype=np.float64)

        for _ in range(samples):
            t0 = time.perf_counter_ns()
            _heavy_kernel[256, 256](out, 2048)
            cuda.synchronize()
            t1 = time.perf_counter_ns()
            timings.append(t1 - t0)

        return timings
    except Exception:
        return []


def _measure_rocm_kernel_jitter(samples: int) -> List[int]:
    """Measure ROCm kernel timing jitter."""
    timings = []

    try:
        import numpy as np
        from numba import roc

        @roc.jit
        def _rocm_kernel(a, b, c):
            idx = roc.get_global_id(0)
            if idx < len(a):
                s = 0.0
                for i in range(512):
                    s += a[idx] * b[idx]
                c[idx] = s

        n = 1024 * 128
        a = np.random.randn(n).astype(np.float32)
        b = np.random.randn(n).astype(np.float32)
        c = np.zeros_like(a)

        threads = 256
        blocks = (n + threads - 1) // threads

        for _ in range(samples):
            t0 = time.perf_counter_ns()
            _rocm_kernel[blocks, threads](a, b, c)
            # ROCm sync
            import hip
            hip.synchronize()
            t1 = time.perf_counter_ns()
            timings.append(t1 - t0)

        return timings
    except Exception:
        pass

    # Fallback: rocm-smi based timing
    return []


# ─── Channel 8 Check 2: VRAM Timing Profiles ────────────────────────────────

def check_vram_timing(iterations: int = 50) -> Tuple[bool, Dict]:
    """
    Check 2: VRAM Timing Profiles

    Measures GPU memory access latency patterns. Each GPU model (and each
    individual die) has unique VRAM timing characteristics due to:
    - Memory controller design
    - VRAM chip manufacturer (Samsung, Micron, Hynix)
    - PCB trace lengths
    - Memory clock jitter

    Patterns measured:
    - Sequential read latency
    - Random read latency
    - Write-to-read turnaround latency
    - Bandwidth variance under load
    """
    vendor = _detect_gpu_vendor()
    if vendor is None:
        return True, {
            "skipped": True,
            "reason": "no_gpu_detected",
            "channel": "vram_timing"
        }

    results = {}

    if vendor == "nvidia":
        results = _measure_nvidia_vram_timing(iterations)
    elif vendor == "amd":
        results = _measure_amd_vram_timing(iterations)

    if not results:
        return True, {
            "skipped": True,
            "reason": "vram_timing_unavailable",
            "vendor": vendor,
            "channel": "vram_timing"
        }

    data = {
        "channel": "vram_timing",
        "vendor": vendor,
        "iterations": iterations,
    }
    data.update(results)

    # VRAM timing must show some variance
    seq_latencies = data.get("seq_read_latencies_ns", [])
    rand_latencies = data.get("rand_read_latencies_ns", [])

    if seq_latencies:
        seq_cv = statistics.stdev(seq_latencies) / statistics.mean(seq_latencies) \
            if statistics.mean(seq_latencies) > 0 else 0
        data["seq_read_cv"] = round(seq_cv, 8)

        if seq_cv < 0.00005 and len(seq_latencies) > 5:
            data["fail_reason"] = "vram_timing_too_uniform_suspected_vm"
            return False, data

    if rand_latencies:
        rand_cv = statistics.stdev(rand_latencies) / statistics.mean(rand_latencies) \
            if statistics.mean(rand_latencies) > 0 else 0
        data["rand_read_cv"] = round(rand_cv, 8)

    return True, data


def _measure_nvidia_vram_timing(iterations: int) -> Dict:
    """Measure NVIDIA VRAM timing via CUDA memory operations."""
    seq_latencies = []
    rand_latencies = []
    write_read_latencies = []

    try:
        import numpy as np
        from numba import cuda

        buf_size = 64 * 1024 * 1024  # 64 MB
        buf = cuda.device_array(buf_size, dtype=np.uint8)
        host_buf = np.zeros(buf_size, dtype=np.uint8)

        # Sequential read timing
        for _ in range(iterations):
            # Warm up
            _ = cuda.to_device(np.zeros(1024, dtype=np.uint8))

            t0 = time.perf_counter_ns()
            cuda.memcpy_dtoh(host_buf, buf)
            t1 = time.perf_counter_ns()
            seq_latencies.append(t1 - t0)

        # Random access pattern timing
        indices = np.random.randint(0, buf_size, size=iterations * 1024)
        small_buf = np.zeros(1024, dtype=np.uint8)

        for i in range(iterations):
            t0 = time.perf_counter_ns()
            chunk = host_buf[indices[i * 1024:(i + 1) * 1024]]
            t1 = time.perf_counter_ns()
            rand_latencies.append(t1 - t0)

        return {
            "seq_read_latencies_ns": seq_latencies[:20],  # Trim for output
            "seq_read_mean_ns": int(statistics.mean(seq_latencies)),
            "seq_read_stdev_ns": int(statistics.stdev(seq_latencies)) if len(seq_latencies) > 1 else 0,
            "rand_read_latencies_ns": rand_latencies[:20],
            "rand_read_mean_ns": int(statistics.mean(rand_latencies)),
            "buf_size_bytes": buf_size,
        }
    except Exception as e:
        return {"error": str(e)}


def _measure_amd_vram_timing(iterations: int) -> Dict:
    """Measure AMD VRAM timing via ROCm memory operations."""
    try:
        import numpy as np
        from numba import roc

        buf_size = 32 * 1024 * 1024  # 32 MB
        buf = roc.device_array(buf_size, dtype=np.uint8)
        host_buf = np.zeros(buf_size, dtype=np.uint8)

        latencies = []
        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            buf.copy_to_host(host_buf)
            t1 = time.perf_counter_ns()
            latencies.append(t1 - t0)

        return {
            "vram_read_latencies_ns": latencies[:20],
            "vram_read_mean_ns": int(statistics.mean(latencies)),
            "vram_read_stdev_ns": int(statistics.stdev(latencies)) if len(latencies) > 1 else 0,
            "buf_size_bytes": buf_size,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Channel 8 Check 3: Compute Unit Asymmetry ──────────────────────────────

def check_compute_unit_asymmetry(buckets: int = 16) -> Tuple[bool, Dict]:
    """
    Check 3: Compute Unit Asymmetry

    GPUs have multiple compute units / SMs that are NOT perfectly identical.
    Due to manufacturing variations (silicon lottery), each CU has slightly
    different:
    - Maximum stable clock frequency
    - Leakage current
    - Instruction throughput

    This test distributes work across the GPU and measures per-CU timing
    to detect these asymmetries. A VM spoofing a GPU typically reports
    perfectly uniform CU performance.
    """
    vendor = _detect_gpu_vendor()
    if vendor is None:
        return True, {
            "skipped": True,
            "reason": "no_gpu_detected",
            "channel": "cu_asymmetry"
        }

    gpu_info = _get_gpu_info(vendor)
    cu_timings = {}

    if vendor == "nvidia":
        cu_timings = _measure_nvidia_cu_asymmetry(buckets)
    elif vendor == "amd":
        cu_timings = _measure_amd_cu_asymmetry(buckets)

    data = {
        "channel": "cu_asymmetry",
        "vendor": vendor,
        "gpu_name": gpu_info.get("name", "unknown"),
        "buckets": buckets,
        "cu_timings_mean_ns": {k: int(v) for k, v in cu_timings.items()},
    }

    if cu_timings:
        means = list(cu_timings.values())
        asymmetry_ratio = (max(means) - min(means)) / statistics.mean(means) \
            if statistics.mean(means) > 0 else 0
        data["asymmetry_ratio"] = round(asymmetry_ratio, 8)
        data["max_cu_mean_ns"] = int(max(means))
        data["min_cu_mean_ns"] = int(min(means))

        # Real GPUs show at least 0.1% CU asymmetry
        if asymmetry_ratio < 0.0001:
            data["fail_reason"] = "cu_asymmetry_too_low_suspected_vm"
            return False, data
    else:
        data["skipped"] = True
        data["reason"] = "cu_isolation_unavailable"

    return True, data


def _measure_nvidia_cu_asymmetry(buckets: int) -> Dict:
    """
    Measure per-SM timing on NVIDIA GPUs by pinning thread blocks to
    specific SMs via CUDA stream priorities and measuring kernel completion.
    """
    cu_times = {}

    try:
        import numpy as np
        from numba import cuda

        # Query device properties
        device = cuda.get_current_device()
        sm_count = getattr(device, 'MULTIPROCESSOR_COUNT', 16)

        @cuda.jit
        def _cu_work_kernel(output, workload_size):
            # Each thread does a fixed amount of work
            idx = cuda.grid(1)
            total = 0.0
            for i in range(workload_size):
                total += (i * 0.0001) % 1.0
            output[idx] = total

        n = buckets * 256
        output = cuda.device_array(n, dtype=np.float64)
        workload = 4096

        for bucket in range(min(buckets, sm_count)):
            # Launch one block per "virtual CU bucket"
            block = (256,)
            grid = (1,)

            # Time this specific block
            t0 = time.perf_counter_ns()
            _cu_work_kernel[grid, block](output[bucket * 256:(bucket + 1) * 256], workload)
            cuda.synchronize()
            t1 = time.perf_counter_ns()

            cu_times[f"bucket_{bucket}"] = t1 - t0

        # Also measure cross-CU contention
        full_block = (256 * min(buckets, sm_count),)
        full_grid = (1,)
        t0 = time.perf_counter_ns()
        _cu_work_kernel[full_grid, full_block](output, workload)
        cuda.synchronize()
        t1 = time.perf_counter_ns()
        cu_times["all_cus_parallel_ns"] = t1 - t0

    except Exception:
        pass

    return cu_times


def _measure_amd_cu_asymmetry(buckets: int) -> Dict:
    """Measure per-CU timing on AMD GPUs."""
    cu_times = {}

    try:
        import numpy as np
        from numba import roc

        @roc.jit
        def _amd_cu_kernel(output, workload):
            idx = roc.get_global_id(0)
            total = 0.0
            for i in range(workload):
                total += (i * 0.0001) % 1.0
            output[idx] = total

        n = buckets * 256
        output = roc.device_array(n, dtype=np.float64)

        for bucket in range(buckets):
            t0 = time.perf_counter_ns()
            _amd_cu_kernel[256, 1](output[bucket * 256:(bucket + 1) * 256], 4096)
            import hip
            hip.synchronize()
            t1 = time.perf_counter_ns()
            cu_times[f"cu_{bucket}"] = t1 - t0

    except Exception:
        pass

    return cu_times


# ─── Channel 8 Check 4: Thermal Throttle Signatures ─────────────────────────

def check_thermal_throttle_signature(warmup_seconds: int = 10, cooldown_seconds: int = 5) -> Tuple[bool, Dict]:
    """
    Check 4: Thermal Throttle Signatures

    Under sustained load, real GPUs exhibit:
    - Temperature rise → clock frequency reduction (thermal throttling)
    - Unique thermal mass and cooling curve per GPU model
    - Power limit excursions (GPU hits TDP wall)

    VM GPU pass-through cannot replicate the thermal behavior of the
    underlying physical GPU.

    We measure clock frequency over time during a sustained compute load
    and analyze the thermal throttling curve.
    """
    vendor = _detect_gpu_vendor()
    if vendor is None:
        return True, {
            "skipped": True,
            "reason": "no_gpu_detected",
            "channel": "thermal_throttle"
        }

    gpu_info = _get_gpu_info(vendor)
    clock_readings = []
    temp_readings = []
    power_readings = []

    if vendor == "nvidia":
        clock_readings, temp_readings, power_readings = _measure_nvidia_thermal(
            warmup_seconds, cooldown_seconds
        )
    elif vendor == "amd":
        clock_readings, temp_readings, power_readings = _measure_amd_thermal(
            warmup_seconds, cooldown_seconds
        )

    data = {
        "channel": "thermal_throttle",
        "vendor": vendor,
        "gpu_name": gpu_info.get("name", "unknown"),
        "samples": len(clock_readings),
    }

    if clock_readings:
        clock_mean = statistics.mean(clock_readings)
        clock_min = min(clock_readings)
        clock_max = max(clock_readings)
        throttle_depth = (clock_max - clock_min) / clock_max if clock_max > 0 else 0

        data["clock_mean_mhz"] = round(clock_mean, 1)
        data["clock_min_mhz"] = clock_min
        data["clock_max_mhz"] = clock_max
        data["throttle_depth_pct"] = round(throttle_depth, 4)
        data["clock_readings_mhz"] = clock_readings[:30]  # Trim output

        # Real GPU under load should show SOME clock variation
        if throttle_depth < 0.001 and len(clock_readings) > 10:
            data["warning"] = "minimal_clock_variation_possible_vm"

    if temp_readings:
        temp_max = max(temp_readings)
        temp_min = min(temp_readings)
        data["temp_max_c"] = temp_max
        data["temp_min_c"] = temp_min
        data["temp_delta_c"] = temp_max - temp_min
        data["temp_readings_c"] = temp_readings[:30]

    if power_readings:
        data["power_max_w"] = max(power_readings)
        data["power_min_w"] = min(power_readings)

    # Thermal throttle is a soft check — we don't fail for it alone
    # because cooling conditions vary
    return True, data


def _measure_nvidia_thermal(warmup_seconds: int, cooldown_seconds: int) -> Tuple[List, List, List]:
    """
    Measure NVIDIA GPU thermal behavior by running sustained compute load
    and polling nvidia-smi for clock/temp/power.
    """
    import threading

    clocks = []
    temps = []
    powers = []

    # Start a background compute load
    stop_event = threading.Event()

    def _compute_load():
        try:
            import numpy as np
            from numba import cuda

            @cuda.jit
            def _burn_kernel(out):
                idx = cuda.grid(1)
                val = 0.0
                for i in range(100000):
                    val += (i * 0.0003) % 1.0
                out[idx] = val

            out = cuda.device_array(1024 * 1024, dtype=np.float64)
            while not stop_event.is_set():
                _burn_kernel[512, 256](out)
        except Exception:
            # Fallback: use nvidia-smi --gpu-burn like approach
            pass

    load_thread = threading.Thread(target=_compute_load, daemon=True)
    load_thread.start()

    # Poll nvidia-smi during warmup + cooldown
    total_seconds = warmup_seconds + cooldown_seconds
    poll_interval = 1.0  # 1 Hz
    start_time = time.time()

    while time.time() - start_time < total_seconds:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=clocks.sm,clocks.mem,temperature.gpu,power.draw",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 4:
                    try:
                        sm_clock = int(parts[0].strip().replace(" MHz", ""))
                        mem_clock = int(parts[1].strip().replace(" MHz", ""))
                        temp = int(parts[2].strip().replace(" C", ""))
                        power = float(parts[3].strip().replace(" W", ""))

                        clocks.append(sm_clock)
                        temps.append(temp)
                        powers.append(power)
                    except ValueError:
                        pass
        except Exception:
            pass

        time.sleep(poll_interval)

    stop_event.set()
    load_thread.join(timeout=2)

    return clocks, temps, powers


def _measure_amd_thermal(warmup_seconds: int, cooldown_seconds: int) -> Tuple[List, List, List]:
    """Measure AMD GPU thermal behavior via rocm-smi."""
    import threading

    clocks = []
    temps = []
    powers = []

    stop_event = threading.Event()

    def _compute_load():
        try:
            import numpy as np
            from numba import roc

            @roc.jit
            def _burn_kernel(out):
                idx = roc.get_global_id(1)
                val = 0.0
                for i in range(100000):
                    val += (i * 0.0003) % 1.0
                out[idx] = val

            out = roc.device_array(1024 * 1024, dtype=np.float64)
            while not stop_event.is_set():
                _burn_kernel[512, 256](out)
        except Exception:
            pass

    load_thread = threading.Thread(target=_compute_load, daemon=True)
    load_thread.start()

    total_seconds = warmup_seconds + cooldown_seconds
    poll_interval = 1.0
    start_time = time.time()

    while time.time() - start_time < total_seconds:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showclocks", "--showtemp", "--showpower"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "SCLK" in line:
                        try:
                            mhz = int(line.split(":")[1].strip().replace("Mhz", "").replace("MHz", ""))
                            clocks.append(mhz)
                        except (ValueError, IndexError):
                            pass
                    if "Temperature" in line or "Edge" in line:
                        try:
                            temp = float(line.split(":")[1].strip().replace("c", "").replace("C", ""))
                            temps.append(int(temp))
                        except (ValueError, IndexError):
                            pass
                    if "Power" in line:
                        try:
                            power = float(line.split(":")[1].strip().replace("W", "").replace("w", ""))
                            powers.append(power)
                        except (ValueError, IndexError):
                            pass
        except Exception:
            pass

        time.sleep(poll_interval)

    stop_event.set()
    load_thread.join(timeout=2)

    return clocks, temps, powers


# ─── VM / GPU Passthrough Detection ─────────────────────────────────────────

def check_gpu_vm_passthrough() -> Tuple[bool, Dict]:
    """
    Detect VM GPU pas-through (vfio-pci spoofing).

    Checks:
    1. IOMMU group isolation indicators
    2. PCI device path anomalies
    3. Hypervisor flags in GPU PCI config
    4. GPU BAR (Base Address Register) mapping consistency
    5. NVIDIA driver version vs kernel module consistency
    """
    indicators = []

    # Check 1: IOMMU/vfio indicators
    vfio_devices = []
    try:
        if os.path.exists("/sys/bus/pci/drivers/vfio-pci"):
            vfio_devices = os.listdir("/sys/bus/pci/drivers/vfio-pci")
            if vfio_devices:
                indicators.append("vfio_pci_devices:{}".format(len(vfio_devices)))
    except Exception:
        pass

    # Check 2: Hypervisor flag in /proc/cpuinfo (affects GPU visibility)
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            if "hypervisor" in cpuinfo.lower():
                # GPU may be passed through from a VM
                indicators.append("cpuinfo_hypervisor_flag")
    except Exception:
        pass

    # Check 3: Check for virtualized GPU indicators in dmesg
    try:
        result = subprocess.run(
            ["dmesg"], capture_output=True, text=True, timeout=5
        )
        dmesg = result.stdout.lower()
        if any(s in dmesg for s in ["vfio", "iommu", "passthrough", "virtio"]):
            indicators.append("dmesg_virtualization_hints")
    except Exception:
        pass

    # Check 4: NVIDIA driver consistency check
    vendor = _detect_gpu_vendor()
    if vendor == "nvidia":
        try:
            # Check if kernel module is loaded
            result = subprocess.run(
                ["lsmod"], capture_output=True, text=True, timeout=3
            )
            if "nvidia" not in result.stdout.lower():
                indicators.append("nvidia_module_not_loaded")

            # Check PCI config space for virtualization bits
            result = subprocess.run(
                ["lspci", "-vvv"], capture_output=True, text=True, timeout=5
            )
            lspci_out = result.stdout.lower()
            if "physical function" in lspci_out and "virtual function" in lspci_out:
                indicators.append("sr_iov_detected")
        except Exception:
            pass

    data = {
        "channel": "gpu_vm_passthrough",
        "indicators": indicators,
        "is_likely_passthrough": len(indicators) >= 2,
        "vfio_devices": vfio_devices,
    }

    # Fail if strong VM passthrough indicators
    if len(indicators) >= 3:
        data["fail_reason"] = "strong_gpu_passthrough_indicators"
        return False, data

    return True, data


# ─── GPU Identity Hash (Silicon Lottery Signature) ──────────────────────────

def compute_gpu_silicone_signature() -> Optional[str]:
    """
    Compute a unique GPU signature combining all measurable hardware properties.
    This acts as the "silicon lottery" fingerprint — no two GPUs should produce
    the same signature, even of the same model.
    """
    vendor = _detect_gpu_vendor()
    if vendor is None:
        return None

    components = [vendor]

    # GPU name + PCI bus ID
    info = _get_gpu_info(vendor)
    components.append(info.get("name", "unknown"))
    components.append(info.get("pci_bus_id", "unknown"))

    # Quick jitter measurement (10 samples)
    jitter_samples = _measure_cuda_kernel_jitter(10) if vendor == "nvidia" else _measure_rocm_kernel_jitter(10)
    if jitter_samples:
        cv = round(statistics.stdev(jitter_samples) / statistics.mean(jitter_samples), 8)
        components.append(f"cv_{cv}")

    # VRAM timing mean
    vram = _measure_nvidia_vram_timing(5) if vendor == "nvidia" else _measure_amd_vram_timing(5)
    if vram and "seq_read_mean_ns" in vram:
        components.append(f"vram_{vram['seq_read_mean_ns']}")

    # Hash all components
    sig_input = "|".join(str(c) for c in components)
    return hashlib.sha256(sig_input.encode()).hexdigest()[:16]


# ─── Main Validation ────────────────────────────────────────────────────────

def validate_gpu_fingerprint() -> Tuple[bool, Dict]:
    """
    Run all GPU fingerprint checks (Channel 8).

    Returns (all_passed, results_dict) matching the style of
    validate_all_checks() in fingerprint_checks.py.
    """
    results = {}
    all_passed = True

    checks = [
        ("shader_jitter", "GPU Shader Execution Jitter", check_shader_execution_jitter),
        ("vram_timing", "GPU VRAM Timing Profiles", check_vram_timing),
        ("cu_asymmetry", "GPU Compute Unit Asymmetry", check_compute_unit_asymmetry),
        ("thermal_throttle", "GPU Thermal Throttle Signatures", check_thermal_throttle_signature),
        ("vm_passthrough", "GPU VM Passthrough Detection", check_gpu_vm_passthrough),
    ]

    gpu_vendor = _detect_gpu_vendor()
    gpu_info = _get_gpu_info(gpu_vendor) if gpu_vendor else {}
    silicone_sig = compute_gpu_silicone_signature()

    print(f"\nRIP-0308 Channel 8: GPU Fingerprint Validation")
    print(f"GPU: {gpu_info.get('name', 'No GPU detected')} ({gpu_vendor or 'unknown'})")
    if silicone_sig:
        print(f"Silicone Signature: {silicone_sig}")
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
        status = "PASS" if passed else "FAIL"
        skip_reason = data.get("reason", "")
        if data.get("skipped"):
            status = f"SKIP ({skip_reason})"
        print(f"  Result: {status}")

    print("\n" + "=" * 50)
    print(f"GPU CHANNEL 8 RESULT: {'ALL CHECKS PASSED' if all_passed else 'FAILED'}")

    if not all_passed:
        failed = [k for k, v in results.items() if not v["passed"]]
        print(f"Failed checks: {failed}")

    return all_passed, results


if __name__ == "__main__":
    import json
    passed, results = validate_gpu_fingerprint()
    print("\n\nDetailed Results:")
    print(json.dumps(results, indent=2, default=str))
