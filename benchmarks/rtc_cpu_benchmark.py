#!/usr/bin/env python3
"""
RTC Miner CPU Impact Benchmark
===============================
Proves RustChain miner uses <2% CPU alongside GPU mining workloads.

Measures:
  Phase 1: Baseline (idle system)
  Phase 2: GPU stress only (simulated mining via PyTorch CUDA)
  Phase 3: GPU stress + RTC miner running
  Phase 4: RTC miner only (no GPU load)

Output: Clean report with CPU%, GPU utilization, and delta analysis.

Usage: python3 rtc_cpu_benchmark.py [--duration 30] [--miner-path /path/to/miner]
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import threading
from datetime import datetime

try:
    import psutil
except ImportError:
    print("ERROR: psutil required. Install with: pip install psutil")
    sys.exit(1)

try:
    import torch
    HAVE_TORCH = torch.cuda.is_available()
except ImportError:
    HAVE_TORCH = False


# ─── GPU Stress Worker ───────────────────────────────────────────────

def gpu_stress_worker(stop_event, results):
    """Simulate GPU mining workload using PyTorch CUDA matrix ops.

    Adaptively sizes matrices to fit available VRAM.
    """
    if not HAVE_TORCH:
        results["gpu_error"] = "No CUDA available"
        return

    device = torch.device("cuda:0")
    gpu_name = torch.cuda.get_device_name(0)
    results["gpu_name"] = gpu_name

    # Check available VRAM and size accordingly
    free_mem = torch.cuda.mem_get_info(0)[0]  # free bytes
    free_mb = free_mem / (1024**2)

    # Each FP32 matrix of size N needs N*N*4 bytes, we need 3 (a, b, c)
    # So max N = sqrt(free_bytes / 12) with safety margin
    import math
    max_size = int(math.sqrt(free_mem * 0.7 / 12))  # Use 70% of free VRAM
    size = min(max_size, 4096)
    size = max(size, 256)  # Minimum useful size

    results["matrix_size"] = size
    results["free_vram_mb"] = free_mb

    iterations = 0
    start = time.time()

    try:
        a = torch.randn(size, size, device=device, dtype=torch.float32)
        b = torch.randn(size, size, device=device, dtype=torch.float32)

        while not stop_event.is_set():
            c = torch.mm(a, b)
            torch.cuda.synchronize()
            iterations += 1

    except torch.cuda.OutOfMemoryError:
        results["gpu_error"] = f"OOM with size {size} ({free_mb:.0f}MB free)"
    except Exception as e:
        results["gpu_error"] = str(e)

    elapsed = time.time() - start
    results["gpu_iterations"] = iterations
    results["gpu_elapsed"] = elapsed
    results["gpu_ops_per_sec"] = iterations / elapsed if elapsed > 0 else 0
    # Each matmul: 2 * N^3 FLOPs
    flops = iterations * 2 * (size ** 3)
    results["gpu_tflops"] = flops / elapsed / 1e12 if elapsed > 0 else 0


# ─── Nvidia SMI Sampling ─────────────────────────────────────────────

def sample_nvidia_smi():
    """Get GPU utilization and power from nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw,temperature.gpu,memory.used",
             "--format=csv,noheader,nounits"],
            timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip()
        parts = [x.strip() for x in out.split(",")]
        return {
            "gpu_util": float(parts[0]),
            "power_w": float(parts[1]),
            "temp_c": float(parts[2]),
            "mem_used_mb": float(parts[3]),
        }
    except Exception:
        return None


# ─── CPU Sampling ────────────────────────────────────────────────────

def measure_phase(name, duration, gpu_stress=False, miner_proc=None):
    """Run a measurement phase, sampling CPU and GPU metrics."""
    print(f"\n{'='*60}")
    print(f"  Phase: {name}")
    print(f"  Duration: {duration}s")
    print(f"  GPU Stress: {'YES' if gpu_stress else 'NO'}")
    print(f"  RTC Miner: {'YES' if miner_proc else 'NO'}")
    print(f"{'='*60}")

    gpu_results = {}
    stop_event = threading.Event()
    gpu_thread = None

    if gpu_stress and HAVE_TORCH:
        gpu_thread = threading.Thread(target=gpu_stress_worker,
                                       args=(stop_event, gpu_results), daemon=True)
        gpu_thread.start()
        time.sleep(2)  # Let GPU ramp up

    # Collect CPU samples
    cpu_samples = []
    gpu_samples = []
    miner_cpu_samples = []

    # Get per-CPU baseline
    psutil.cpu_percent(percpu=True)  # Prime the measurement
    time.sleep(0.5)

    sample_interval = 1.0
    num_samples = int(duration / sample_interval)

    for i in range(num_samples):
        # Overall CPU
        per_cpu = psutil.cpu_percent(interval=sample_interval, percpu=True)
        overall = sum(per_cpu) / len(per_cpu)
        cpu_samples.append(overall)

        # GPU metrics
        gpu_snap = sample_nvidia_smi()
        if gpu_snap:
            gpu_samples.append(gpu_snap)

        # Miner process CPU
        if miner_proc and miner_proc.poll() is None:
            try:
                p = psutil.Process(miner_proc.pid)
                children = p.children(recursive=True)
                total_miner_cpu = p.cpu_percent()
                for child in children:
                    try:
                        total_miner_cpu += child.cpu_percent()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                miner_cpu_samples.append(total_miner_cpu)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Progress
        bar = "#" * int((i + 1) / num_samples * 30)
        spaces = " " * (30 - len(bar))
        sys.stdout.write(f"\r  Sampling: [{bar}{spaces}] {i+1}/{num_samples}")
        sys.stdout.flush()

    print()

    # Stop GPU stress
    if gpu_thread:
        stop_event.set()
        gpu_thread.join(timeout=10)

    # Compute stats
    result = {
        "name": name,
        "duration": duration,
        "cpu_mean": sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0,
        "cpu_max": max(cpu_samples) if cpu_samples else 0,
        "cpu_min": min(cpu_samples) if cpu_samples else 0,
        "cpu_samples": len(cpu_samples),
        "num_cores": psutil.cpu_count(),
    }

    if gpu_samples:
        result["gpu_util_mean"] = sum(s["gpu_util"] for s in gpu_samples) / len(gpu_samples)
        result["gpu_power_mean"] = sum(s["power_w"] for s in gpu_samples) / len(gpu_samples)
        result["gpu_temp_mean"] = sum(s["temp_c"] for s in gpu_samples) / len(gpu_samples)

    if miner_cpu_samples:
        result["miner_cpu_mean"] = sum(miner_cpu_samples) / len(miner_cpu_samples)
        result["miner_cpu_max"] = max(miner_cpu_samples)

    result.update(gpu_results)

    # Print summary
    print(f"  CPU Usage:  {result['cpu_mean']:.2f}% avg, {result['cpu_max']:.2f}% peak")
    if "gpu_util_mean" in result:
        print(f"  GPU Util:   {result['gpu_util_mean']:.1f}% avg")
        print(f"  GPU Power:  {result['gpu_power_mean']:.1f}W avg")
    if "gpu_tflops" in result:
        print(f"  GPU Perf:   {result['gpu_tflops']:.2f} TFLOPS ({result['gpu_ops_per_sec']:.1f} matmul/s)")
    if "miner_cpu_mean" in result:
        print(f"  Miner CPU:  {result['miner_cpu_mean']:.2f}% avg, {result['miner_cpu_max']:.2f}% peak")

    return result


# ─── Miner Process Management ────────────────────────────────────────

def start_miner(miner_path):
    """Start the RTC miner as a subprocess."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, miner_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        preexec_fn=os.setsid
    )
    time.sleep(5)  # Let miner initialize and start attestation cycle
    if proc.poll() is not None:
        print("  WARNING: Miner exited early!")
        return None
    print(f"  Miner started (PID {proc.pid})")
    return proc


def stop_miner(proc):
    """Stop the RTC miner subprocess."""
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
        print("  Miner stopped.")


# ─── Report Generation ───────────────────────────────────────────────

def generate_report(phases, system_info):
    """Generate the final benchmark report."""
    baseline = phases[0]
    gpu_only = phases[1]
    gpu_miner = phases[2]
    miner_only = phases[3] if len(phases) > 3 else None

    cpu_delta = gpu_miner["cpu_mean"] - gpu_only["cpu_mean"]
    miner_overhead = gpu_miner.get("miner_cpu_mean", cpu_delta)

    # GPU performance comparison
    gpu_perf_change = 0
    if gpu_only.get("gpu_tflops") and gpu_miner.get("gpu_tflops"):
        gpu_perf_change = ((gpu_miner["gpu_tflops"] - gpu_only["gpu_tflops"])
                           / gpu_only["gpu_tflops"] * 100)

    report = []
    report.append("=" * 70)
    report.append("  RustChain (RTC) Miner — CPU Impact Benchmark Report")
    report.append("=" * 70)
    report.append(f"  Date:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"  System:   {system_info.get('cpu_model', 'Unknown CPU')}")
    report.append(f"  Cores:    {system_info['cores']} cores / {system_info['threads']} threads")
    report.append(f"  RAM:      {system_info['ram_gb']:.1f} GB")
    report.append(f"  GPU:      {system_info.get('gpu_name', 'Unknown GPU')}")
    report.append(f"  OS:       {system_info.get('os', 'Linux')}")
    report.append("")

    report.append("-" * 70)
    report.append("  RESULTS SUMMARY")
    report.append("-" * 70)
    report.append("")
    report.append(f"  {'Phase':<30} {'CPU % (avg)':<15} {'GPU Util %':<15} {'GPU TFLOPS':<12}")
    report.append(f"  {'─'*30} {'─'*15} {'─'*15} {'─'*12}")

    for p in phases:
        gpu_u = f"{p.get('gpu_util_mean', 0):.1f}" if p.get('gpu_util_mean') else "N/A"
        gpu_t = f"{p.get('gpu_tflops', 0):.2f}" if p.get('gpu_tflops') else "N/A"
        report.append(f"  {p['name']:<30} {p['cpu_mean']:<15.2f} {gpu_u:<15} {gpu_t:<12}")

    report.append("")
    report.append("-" * 70)
    report.append("  KEY METRICS")
    report.append("-" * 70)
    report.append("")
    report.append(f"  CPU overhead from RTC miner:     {abs(cpu_delta):.2f}%")
    if miner_overhead > 0:
        report.append(f"  Miner process CPU usage:         {miner_overhead:.2f}%")
    report.append(f"  GPU performance impact:          {gpu_perf_change:+.2f}%")
    report.append("")

    passed = abs(cpu_delta) < 2.0
    if passed:
        report.append(f"  RESULT: PASS — RTC miner adds {abs(cpu_delta):.2f}% CPU overhead (<2% target)")
    else:
        report.append(f"  RESULT: FAIL — RTC miner adds {abs(cpu_delta):.2f}% CPU overhead (>2% target)")

    report.append("")
    report.append("-" * 70)
    report.append("  DETAILED PHASE DATA")
    report.append("-" * 70)

    for p in phases:
        report.append(f"\n  {p['name']}:")
        report.append(f"    CPU:  {p['cpu_mean']:.2f}% avg | {p['cpu_min']:.2f}% min | {p['cpu_max']:.2f}% max")
        if p.get("gpu_util_mean"):
            report.append(f"    GPU:  {p['gpu_util_mean']:.1f}% util | {p.get('gpu_power_mean', 0):.1f}W power | {p.get('gpu_temp_mean', 0):.0f}C temp")
        if p.get("gpu_tflops"):
            report.append(f"    Perf: {p['gpu_tflops']:.2f} TFLOPS ({p['gpu_ops_per_sec']:.1f} matmul/s)")
        if p.get("miner_cpu_mean"):
            report.append(f"    Miner: {p['miner_cpu_mean']:.2f}% CPU avg | {p['miner_cpu_max']:.2f}% peak")

    report.append("")
    report.append("-" * 70)
    report.append("  METHODOLOGY")
    report.append("-" * 70)
    # Get matrix size from phases
    mat_size = gpu_only.get("matrix_size", 4096)
    free_vram = gpu_only.get("free_vram_mb", 0)
    report.append(f"  GPU stress: {mat_size}x{mat_size} FP32 matrix multiplication (PyTorch CUDA)")
    if free_vram > 0 and free_vram < 7000:
        report.append(f"  Note: GPU shared with other workloads ({free_vram:.0f}MB free of 8188MB)")
        report.append(f"        This simulates real-world conditions where GPU is actively mining")
    report.append("  RTC miner: RustChain Proof of Antiquity attestation client")
    report.append("  Sampling: 1-second intervals via psutil + nvidia-smi")
    report.append("  Each phase runs independently with cooldown between phases")
    report.append("")
    report.append("  RTC miner performs hardware fingerprinting (clock drift, cache timing,")
    report.append("  SIMD profiling, thermal entropy) and periodic attestation (~10 min epochs).")
    report.append("  It is CPU-only by design and does not touch GPU resources.")
    report.append("")
    report.append("=" * 70)
    report.append("  Generated by RustChain CPU Impact Benchmark v1.0")
    report.append("  https://rustchain.org | https://github.com/Scottcjn/Rustchain")
    report.append("=" * 70)

    return "\n".join(report)


# ─── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RTC Miner CPU Impact Benchmark")
    parser.add_argument("--duration", type=int, default=30,
                        help="Duration per phase in seconds (default: 30)")
    parser.add_argument("--miner-path", type=str,
                        default="/home/scott/tmp_rustchain/rustchain_linux_miner.py",
                        help="Path to RTC miner script")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file for report (default: stdout + auto-save)")
    args = parser.parse_args()

    print("\n  RustChain (RTC) Miner — CPU Impact Benchmark")
    print("  Proving <2% CPU overhead alongside GPU mining\n")

    # System info
    cpu_model = "Unknown"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_model = line.split(":")[1].strip()
                    break
    except Exception:
        pass

    system_info = {
        "cpu_model": cpu_model,
        "cores": psutil.cpu_count(logical=False),
        "threads": psutil.cpu_count(logical=True),
        "ram_gb": psutil.virtual_memory().total / (1024**3),
        "os": f"Linux {os.uname().release}",
    }

    if HAVE_TORCH:
        system_info["gpu_name"] = torch.cuda.get_device_name(0)

    print(f"  CPU: {cpu_model}")
    print(f"  GPU: {system_info.get('gpu_name', 'No CUDA GPU')}")
    print(f"  RAM: {system_info['ram_gb']:.1f} GB")
    print(f"  Miner: {args.miner_path}")
    print(f"  Duration per phase: {args.duration}s")

    if not os.path.exists(args.miner_path):
        print(f"\n  ERROR: Miner not found at {args.miner_path}")
        sys.exit(1)

    phases = []

    # Phase 1: Baseline
    phases.append(measure_phase("1. Baseline (idle)", args.duration))
    time.sleep(3)  # Cooldown

    # Phase 2: GPU stress only
    phases.append(measure_phase("2. GPU Stress Only", args.duration, gpu_stress=True))
    time.sleep(3)

    # Phase 3: GPU stress + RTC miner
    print("\n  Starting RTC miner...")
    miner_proc = start_miner(args.miner_path)
    phases.append(measure_phase("3. GPU Stress + RTC Miner", args.duration,
                                gpu_stress=True, miner_proc=miner_proc))
    time.sleep(3)

    # Phase 4: RTC miner only (no GPU)
    phases.append(measure_phase("4. RTC Miner Only", args.duration,
                                gpu_stress=False, miner_proc=miner_proc))

    # Stop miner
    stop_miner(miner_proc)

    # Generate report
    report = generate_report(phases, system_info)
    print("\n")
    print(report)

    # Save report
    output_path = args.output or f"/home/scott/scripts/rtc_benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\n  Report saved to: {output_path}")

    # Also save raw JSON data
    json_path = output_path.replace(".txt", ".json")
    with open(json_path, "w") as f:
        json.dump({"system": system_info, "phases": phases}, f, indent=2, default=str)
    print(f"  Raw data saved to: {json_path}")


if __name__ == "__main__":
    main()
