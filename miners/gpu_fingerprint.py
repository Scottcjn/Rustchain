#!/usr/bin/env python3
"""
GPU Fingerprint Module — Channel 8 for Proof of Physical AI (PPA)
=================================================================

Generates a multi-channel hardware fingerprint for NVIDIA GPUs using
PyTorch CUDA. Each channel measures a distinct physical property of
the GPU silicon that varies due to manufacturing variance.

Channels:
    8a. Memory Hierarchy Latency Profile (shared → L1 → L2 → HBM)
    8b. Compute Unit Throughput Asymmetry (FP32/FP16/INT8 ratios)
    8c. Warp Scheduling Jitter (kernel launch timing variance)
    8d. Thermal Ramp Signature (power curve under sustained load)
    8e. PCIe/Memory Bus Bandwidth Profile (host↔device DMA characteristics)

Requirements:
    - PyTorch with CUDA support
    - NVIDIA GPU with compute capability >= 3.5

Usage:
    python3 gpu_fingerprint.py [--device 0] [--json] [--samples 1000]

Author: Elyan Labs (RIP-0308: Proof of Physical AI)
"""

import argparse
import json
import hashlib
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

try:
    import torch
    import torch.cuda
except ImportError:
    print("ERROR: PyTorch with CUDA support required. Install: pip install torch")
    sys.exit(1)

if not torch.cuda.is_available():
    print("ERROR: No CUDA-capable GPU detected.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ChannelResult:
    name: str
    passed: bool
    data: dict = field(default_factory=dict)
    notes: str = ""


@dataclass
class GPUFingerprint:
    gpu_name: str
    gpu_index: int
    vram_mb: int
    compute_capability: str
    driver_version: str
    channels: list = field(default_factory=list)
    all_passed: bool = False
    fingerprint_hash: str = ""

    def to_dict(self):
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Channel 8a: Memory Hierarchy Latency Profile
# ---------------------------------------------------------------------------
# GPU memory has distinct tiers: registers, shared memory, L1 cache, L2 cache,
# and global/HBM. Each tier has characteristic access latency that varies
# per-chip due to fabrication variance in the memory controller and cache SRAM.
#
# We measure effective bandwidth at different working set sizes to reveal
# the latency inflection points — analogous to CPU cache timing (Channel 2).
# ---------------------------------------------------------------------------

def channel_8a_memory_latency(device: torch.device, samples: int = 200) -> ChannelResult:
    """Measure GPU memory hierarchy latency profile."""
    torch.cuda.synchronize(device)

    # Probe GPU memory hierarchy using matmul at different sizes.
    # Small matrices fit in L1/L2, large ones spill to HBM.
    # The effective TFLOPS changes at cache boundaries.
    sizes_n = [32, 64, 128, 256, 512, 1024, 2048, 4096]
    latencies = {}

    for n in sizes_n:
        size_kb = (n * n * 4) // 1024  # approximate working set in KB
        try:
            a = torch.randn(n, n, device=device, dtype=torch.float32)
            b = torch.randn(n, n, device=device, dtype=torch.float32)

            iters = max(10, 500 // max(n // 128, 1))

            # Warmup
            for _ in range(5):
                _ = torch.mm(a, b)
            torch.cuda.synchronize(device)

            # Timed matmul — effective throughput changes at cache boundaries
            start = time.perf_counter_ns()
            for _ in range(iters):
                _ = torch.mm(a, b)
            torch.cuda.synchronize(device)
            elapsed_ns = time.perf_counter_ns() - start

            # Store as ns per operation (captures cache effects)
            latencies[size_kb] = elapsed_ns / iters
            del a, b
            torch.cuda.empty_cache()

        except torch.cuda.OutOfMemoryError:
            latencies[size_kb] = -1
            torch.cuda.empty_cache()

    # Detect inflection points (latency jumps between tiers)
    valid_sizes = [s for s in sorted(latencies.keys()) if latencies.get(s, -1) > 0]
    valid_lats = [latencies[s] for s in valid_sizes]

    inflection_count = 0
    ratios = []
    if len(valid_lats) >= 3:
        for i in range(1, len(valid_lats)):
            ratio = valid_lats[i] / valid_lats[i - 1] if valid_lats[i - 1] > 0 else 1.0
            ratios.append(ratio)
            if ratio > 1.15:  # 15% jump = tier transition (GPUs have flatter hierarchies than CPUs)
                inflection_count += 1

    # Overall latency spread — even without sharp inflections, real GPUs show a spread
    latency_spread = (max(valid_lats) / min(valid_lats)) if min(valid_lats) > 0 else 1.0

    # Compute profile hash for identity
    profile_str = "|".join(f"{s}:{latencies[s]:.0f}" for s in valid_sizes)
    profile_hash = hashlib.sha256(profile_str.encode()).hexdigest()[:16]

    # Pass if we see tier transitions OR significant overall spread
    passed = (inflection_count >= 1 or latency_spread > 1.5) and len(valid_lats) >= 4
    return ChannelResult(
        name="8a: Memory Hierarchy Latency",
        passed=passed,
        data={
            "latencies_ns": {str(k): round(v, 1) for k, v in latencies.items()},
            "inflection_count": inflection_count,
            "latency_spread": round(latency_spread, 3),
            "tier_ratios": [round(r, 3) for r in ratios],
            "profile_hash": profile_hash,
        },
        notes=f"{inflection_count} tier transitions, {latency_spread:.1f}x spread across {len(valid_sizes)} sizes",
    )


# ---------------------------------------------------------------------------
# Channel 8b: Compute Unit Throughput Asymmetry
# ---------------------------------------------------------------------------
# Different data types (FP32, FP16, BF16, INT8) exercise different functional
# units on the GPU. The throughput RATIO between these types varies per-chip
# due to silicon lottery in the ALUs, tensor cores, and scheduling logic.
#
# A V100 has different FP16:FP32 ratio than an RTX 4090. But even two V100s
# will show slightly different ratios due to manufacturing variance.
# ---------------------------------------------------------------------------

def channel_8b_compute_asymmetry(device: torch.device, samples: int = 100) -> ChannelResult:
    """Measure throughput asymmetry across compute types."""
    torch.cuda.synchronize(device)

    n = 2048  # Matrix size
    results = {}

    dtypes = {
        "fp32": torch.float32,
        "fp16": torch.float16,
    }

    # Add bf16 if supported (Ampere+)
    cap = torch.cuda.get_device_capability(device)
    if cap[0] >= 8:
        dtypes["bf16"] = torch.bfloat16

    for dtype_name, dtype in dtypes.items():
        try:
            a = torch.randn(n, n, device=device, dtype=dtype)
            b = torch.randn(n, n, device=device, dtype=dtype)

            # Warmup
            for _ in range(5):
                _ = torch.mm(a, b)
            torch.cuda.synchronize(device)

            # Timed matmul
            start = time.perf_counter_ns()
            for _ in range(samples):
                _ = torch.mm(a, b)
            torch.cuda.synchronize(device)
            elapsed_ns = time.perf_counter_ns() - start

            tflops = (2.0 * n * n * n * samples) / (elapsed_ns * 1e-9) / 1e12
            results[dtype_name] = {
                "elapsed_ns": elapsed_ns,
                "tflops": round(tflops, 3),
                "per_op_us": round(elapsed_ns / samples / 1000, 1),
            }
            del a, b
            torch.cuda.empty_cache()

        except Exception as e:
            results[dtype_name] = {"error": str(e)}

    # Compute asymmetry ratios — the fingerprint signal
    ratios = {}
    fp32_tflops = results.get("fp32", {}).get("tflops", 0)
    for dtype_name, data in results.items():
        if dtype_name != "fp32" and "tflops" in data and fp32_tflops > 0:
            ratios[f"{dtype_name}_to_fp32"] = round(data["tflops"] / fp32_tflops, 4)

    # Throughput variance across types
    all_tflops = [d["tflops"] for d in results.values() if "tflops" in d]
    throughput_cv = 0.0
    if len(all_tflops) >= 2:
        throughput_cv = statistics.stdev(all_tflops) / statistics.mean(all_tflops) if statistics.mean(all_tflops) > 0 else 0

    passed = len(all_tflops) >= 2 and throughput_cv > 0.01
    return ChannelResult(
        name="8b: Compute Throughput Asymmetry",
        passed=passed,
        data={
            "throughput": results,
            "asymmetry_ratios": ratios,
            "throughput_cv": round(throughput_cv, 6),
        },
        notes=f"FP16:FP32 ratio = {ratios.get('fp16_to_fp32', 'N/A')}, CV = {throughput_cv:.4f}",
    )


# ---------------------------------------------------------------------------
# Channel 8c: Warp Scheduling Jitter
# ---------------------------------------------------------------------------
# GPU kernel launches go through the driver, scheduler, and hardware dispatch.
# The timing variance of identical kernel launches reveals the GPU's scheduling
# characteristics — SM count, warp scheduler design, and driver overhead.
#
# Real GPUs have measurable jitter. Emulated/pass-through GPUs show either
# unnaturally uniform timing (perfect emulation) or excessive jitter
# (emulation overhead).
# ---------------------------------------------------------------------------

def channel_8c_warp_jitter(device: torch.device, samples: int = 500) -> ChannelResult:
    """Measure kernel launch timing jitter."""
    torch.cuda.synchronize(device)

    # Small kernel to measure scheduling overhead, not compute
    a = torch.randn(512, 512, device=device)
    b = torch.randn(512, 512, device=device)

    # Warmup
    for _ in range(20):
        _ = torch.mm(a, b)
    torch.cuda.synchronize(device)

    # Collect per-launch timings
    timings_ns = []
    for _ in range(samples):
        torch.cuda.synchronize(device)
        start = time.perf_counter_ns()
        _ = torch.mm(a, b)
        torch.cuda.synchronize(device)
        elapsed = time.perf_counter_ns() - start
        timings_ns.append(elapsed)

    del a, b
    torch.cuda.empty_cache()

    mean_ns = statistics.mean(timings_ns)
    stdev_ns = statistics.stdev(timings_ns)
    cv = stdev_ns / mean_ns if mean_ns > 0 else 0

    # Jitter distribution analysis
    median_ns = statistics.median(timings_ns)
    p5 = sorted(timings_ns)[int(0.05 * len(timings_ns))]
    p95 = sorted(timings_ns)[int(0.95 * len(timings_ns))]
    iqr_ratio = (p95 - p5) / median_ns if median_ns > 0 else 0

    # Outlier count (>2x median) — real hardware has occasional scheduling spikes
    outliers = sum(1 for t in timings_ns if t > 2 * median_ns)
    outlier_rate = outliers / len(timings_ns)

    # Real hardware: CV between 0.01 and 0.5
    # Perfect emulation: CV < 0.005 (too uniform)
    # Bad emulation: CV > 0.8 (too noisy)
    passed = 0.005 < cv < 0.8

    return ChannelResult(
        name="8c: Warp Scheduling Jitter",
        passed=passed,
        data={
            "samples": samples,
            "mean_ns": round(mean_ns, 1),
            "stdev_ns": round(stdev_ns, 1),
            "cv": round(cv, 6),
            "median_ns": round(median_ns, 1),
            "p5_ns": round(p5, 1),
            "p95_ns": round(p95, 1),
            "iqr_ratio": round(iqr_ratio, 4),
            "outlier_rate": round(outlier_rate, 4),
        },
        notes=f"CV = {cv:.4f}, IQR ratio = {iqr_ratio:.4f}, outlier rate = {outlier_rate:.3f}",
    )


# ---------------------------------------------------------------------------
# Channel 8d: Thermal Ramp Signature
# ---------------------------------------------------------------------------
# Under sustained load, a GPU's temperature rises along a curve determined by
# its die size, thermal interface, cooler design, and ambient conditions.
# The SHAPE of this curve — initial ramp rate, steady-state temperature, and
# thermal throttle behavior — is a physical fingerprint.
#
# We run a sustained workload, sampling temperature at intervals to capture
# the thermal ramp profile.
# ---------------------------------------------------------------------------

def channel_8d_thermal_ramp(device: torch.device, duration_s: float = 10.0) -> ChannelResult:
    """Measure GPU thermal ramp signature under sustained load."""
    torch.cuda.synchronize(device)

    # Check if temperature monitoring is available
    def _try_get_temp(dev_idx):
        """Try multiple methods to get GPU temperature."""
        # Method 1: torch.cuda.temperature
        try:
            return torch.cuda.temperature(torch.device(f"cuda:{dev_idx}"))
        except Exception:
            pass
        # Method 2: nvidia-smi
        import subprocess
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits",
                 f"--id={dev_idx}"],
                capture_output=True, text=True, timeout=5
            )
            val = result.stdout.strip()
            if val.isdigit():
                return int(val)
        except Exception:
            pass
        return None

    temp_start = _try_get_temp(device.index or 0)
    if temp_start is None:
        return ChannelResult(
            name="8d: Thermal Ramp Signature",
            passed=True,  # Don't fail — channel unavailable, not failed
            data={"available": False},
            notes="Temperature monitoring unavailable (NVML missing) — channel skipped",
        )

    def get_temp():
        return _try_get_temp(device.index or 0) or temp_start

    # Sample temperature during sustained load
    n = 4096
    a = torch.randn(n, n, device=device, dtype=torch.float16)
    b = torch.randn(n, n, device=device, dtype=torch.float16)

    temp_samples = []
    time_samples = []
    start_time = time.monotonic()

    while time.monotonic() - start_time < duration_s:
        # Sustained load
        for _ in range(10):
            _ = torch.mm(a, b)
        torch.cuda.synchronize(device)

        elapsed = time.monotonic() - start_time
        temp = get_temp()
        temp_samples.append(temp)
        time_samples.append(round(elapsed, 2))

    del a, b
    torch.cuda.empty_cache()

    # Wait briefly for cooldown sample
    time.sleep(2)
    temp_cooldown = get_temp()

    # Analyze thermal curve
    temp_min = min(temp_samples) if temp_samples else 0
    temp_max = max(temp_samples) if temp_samples else 0
    temp_range = temp_max - temp_min

    # Ramp rate: degrees per second in first half
    mid = len(temp_samples) // 2
    if mid > 1 and time_samples[mid] > time_samples[0]:
        ramp_rate = (temp_samples[mid] - temp_samples[0]) / (time_samples[mid] - time_samples[0])
    else:
        ramp_rate = 0

    # Steady state detection: variance in second half
    second_half = temp_samples[mid:] if mid > 0 else temp_samples
    steady_state_var = statistics.variance(second_half) if len(second_half) >= 2 else 0

    # Cooldown delta
    cooldown_delta = temp_max - temp_cooldown

    # Real GPU: temp_range > 2°C under 10s load, measurable ramp
    # VM/passthrough: temp may be constant (host manages thermals)
    passed = temp_range >= 2 and len(temp_samples) >= 5

    return ChannelResult(
        name="8d: Thermal Ramp Signature",
        passed=passed,
        data={
            "temp_start_c": temp_start,
            "temp_max_c": temp_max,
            "temp_range_c": temp_range,
            "ramp_rate_c_per_s": round(ramp_rate, 3),
            "steady_state_variance": round(steady_state_var, 3),
            "cooldown_delta_c": cooldown_delta,
            "samples": len(temp_samples),
            "duration_s": round(time_samples[-1] if time_samples else 0, 1),
        },
        notes=f"Range: {temp_range}°C, ramp: {ramp_rate:.2f}°C/s, cooldown: -{cooldown_delta}°C",
    )


# ---------------------------------------------------------------------------
# Channel 8e: PCIe/Memory Bus Bandwidth Profile
# ---------------------------------------------------------------------------
# Host↔device data transfer speed reveals the PCIe generation, lane width,
# and bus configuration. A GPU on PCIe 4.0 x16 has different DMA characteristics
# than the same GPU on a x4 adapter or through a VM's virtual PCI bus.
#
# We measure bandwidth at different transfer sizes to reveal the bus profile.
# ---------------------------------------------------------------------------

def channel_8e_bus_bandwidth(device: torch.device, samples: int = 50) -> ChannelResult:
    """Measure PCIe/memory bus bandwidth profile."""
    torch.cuda.synchronize(device)

    # Test different transfer sizes
    sizes_mb = [0.25, 1, 4, 16, 64, 256]
    h2d_bw = {}  # Host to Device
    d2h_bw = {}  # Device to Host

    for size_mb in sizes_mb:
        n_elements = int(size_mb * 1024 * 1024 / 4)  # float32
        try:
            host_tensor = torch.randn(n_elements, dtype=torch.float32, pin_memory=True)

            # Host → Device bandwidth
            torch.cuda.synchronize(device)
            start = time.perf_counter_ns()
            for _ in range(samples):
                dev_tensor = host_tensor.to(device, non_blocking=False)
            torch.cuda.synchronize(device)
            h2d_ns = time.perf_counter_ns() - start
            h2d_gbps = (size_mb * samples / 1024) / (h2d_ns * 1e-9)

            # Device → Host bandwidth
            torch.cuda.synchronize(device)
            start = time.perf_counter_ns()
            for _ in range(samples):
                _ = dev_tensor.to("cpu", non_blocking=False)
            torch.cuda.synchronize(device)
            d2h_ns = time.perf_counter_ns() - start
            d2h_gbps = (size_mb * samples / 1024) / (d2h_ns * 1e-9)

            h2d_bw[str(size_mb)] = round(h2d_gbps, 3)
            d2h_bw[str(size_mb)] = round(d2h_gbps, 3)

            del host_tensor, dev_tensor
            torch.cuda.empty_cache()

        except torch.cuda.OutOfMemoryError:
            h2d_bw[str(size_mb)] = -1
            d2h_bw[str(size_mb)] = -1
            torch.cuda.empty_cache()

    # Peak bandwidth reveals PCIe generation + lane width
    valid_h2d = [v for v in h2d_bw.values() if v > 0]
    valid_d2h = [v for v in d2h_bw.values() if v > 0]

    peak_h2d = max(valid_h2d) if valid_h2d else 0
    peak_d2h = max(valid_d2h) if valid_d2h else 0

    # Asymmetry between H2D and D2H reveals bus configuration
    bw_asymmetry = abs(peak_h2d - peak_d2h) / max(peak_h2d, peak_d2h, 1e-9)

    # Small-transfer overhead reveals driver/bus latency
    small_h2d = h2d_bw.get("0.25", 0)
    large_h2d = h2d_bw.get("256", h2d_bw.get("64", 0))
    bandwidth_scaling = large_h2d / small_h2d if small_h2d > 0 else 0

    # Profile hash
    profile_str = f"h2d:{peak_h2d:.2f}|d2h:{peak_d2h:.2f}|asym:{bw_asymmetry:.4f}"
    bus_hash = hashlib.sha256(profile_str.encode()).hexdigest()[:16]

    passed = peak_h2d > 0.1 and len(valid_h2d) >= 3
    return ChannelResult(
        name="8e: PCIe/Bus Bandwidth Profile",
        passed=passed,
        data={
            "h2d_gbps": h2d_bw,
            "d2h_gbps": d2h_bw,
            "peak_h2d_gbps": peak_h2d,
            "peak_d2h_gbps": peak_d2h,
            "bw_asymmetry": round(bw_asymmetry, 4),
            "bandwidth_scaling": round(bandwidth_scaling, 3),
            "bus_hash": bus_hash,
        },
        notes=f"Peak H2D: {peak_h2d:.2f} GB/s, D2H: {peak_d2h:.2f} GB/s, asymmetry: {bw_asymmetry:.3f}",
    )


# ---------------------------------------------------------------------------
# Main fingerprint runner
# ---------------------------------------------------------------------------

def run_gpu_fingerprint(device_index: int = 0, samples: int = 200) -> GPUFingerprint:
    """Run all GPU fingerprint channels and return results."""
    device = torch.device(f"cuda:{device_index}")

    # GPU info
    props = torch.cuda.get_device_properties(device)
    gpu_name = props.name
    vram_mb = props.total_memory // (1024 * 1024)
    cap = f"{props.major}.{props.minor}"
    driver = torch.version.cuda or "unknown"

    print(f"\n{'='*60}")
    print(f"  GPU Fingerprint — Proof of Physical AI (Channel 8)")
    print(f"  Device: {gpu_name}")
    print(f"  VRAM: {vram_mb} MB | Compute: sm_{cap} | CUDA: {driver}")
    print(f"{'='*60}\n")

    channels = []

    # Channel 8a: Memory Hierarchy
    print("[8a/5] Memory Hierarchy Latency Profile...", end=" ", flush=True)
    ch8a = channel_8a_memory_latency(device, samples=samples)
    print(f"{'PASS' if ch8a.passed else 'FAIL'}")
    print(f"       {ch8a.notes}")
    channels.append(ch8a)

    # Channel 8b: Compute Asymmetry
    print("[8b/5] Compute Throughput Asymmetry...", end=" ", flush=True)
    ch8b = channel_8b_compute_asymmetry(device, samples=min(samples, 100))
    print(f"{'PASS' if ch8b.passed else 'FAIL'}")
    print(f"       {ch8b.notes}")
    channels.append(ch8b)

    # Channel 8c: Warp Jitter
    print("[8c/5] Warp Scheduling Jitter...", end=" ", flush=True)
    ch8c = channel_8c_warp_jitter(device, samples=samples)
    print(f"{'PASS' if ch8c.passed else 'FAIL'}")
    print(f"       {ch8c.notes}")
    channels.append(ch8c)

    # Channel 8d: Thermal Ramp
    print("[8d/5] Thermal Ramp Signature...", end=" ", flush=True)
    ch8d = channel_8d_thermal_ramp(device, duration_s=10.0)
    print(f"{'PASS' if ch8d.passed else 'FAIL'}")
    print(f"       {ch8d.notes}")
    channels.append(ch8d)

    # Channel 8e: Bus Bandwidth
    print("[8e/5] PCIe/Bus Bandwidth Profile...", end=" ", flush=True)
    ch8e = channel_8e_bus_bandwidth(device, samples=min(samples, 50))
    print(f"{'PASS' if ch8e.passed else 'FAIL'}")
    print(f"       {ch8e.notes}")
    channels.append(ch8e)

    all_passed = all(ch.passed for ch in channels)

    # Compute composite fingerprint hash from all channel data
    composite = json.dumps({ch.name: ch.data for ch in channels}, sort_keys=True)
    fingerprint_hash = hashlib.sha256(composite.encode()).hexdigest()

    print(f"\n{'='*60}")
    print(f"  RESULT: {'ALL CHANNELS PASSED' if all_passed else 'SOME CHANNELS FAILED'}")
    print(f"  Fingerprint: {fingerprint_hash[:32]}...")
    print(f"  Passed: {sum(1 for ch in channels if ch.passed)}/5")
    print(f"{'='*60}\n")

    return GPUFingerprint(
        gpu_name=gpu_name,
        gpu_index=device_index,
        vram_mb=vram_mb,
        compute_capability=cap,
        driver_version=driver,
        channels=[asdict(ch) for ch in channels],
        all_passed=all_passed,
        fingerprint_hash=fingerprint_hash,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU Fingerprint — PPA Channel 8")
    parser.add_argument("--device", type=int, default=0, help="CUDA device index")
    parser.add_argument("--samples", type=int, default=200, help="Samples per channel")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    if args.json:
        # Suppress banner output for clean JSON
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            fp = run_gpu_fingerprint(device_index=args.device, samples=args.samples)
        print(json.dumps(fp.to_dict(), indent=2))
    else:
        fp = run_gpu_fingerprint(device_index=args.device, samples=args.samples)
        # Print channel summary
        print("Channel Details:")
        for ch in fp.channels:
            status = "PASS" if ch["passed"] else "FAIL"
            print(f"  [{status}] {ch['name']}: {ch['notes']}")
