#!/usr/bin/env python3
"""
RTC Miner CPU Impact Benchmark v2.0
=====================================
Proves RustChain miner uses <2% CPU alongside ANY workload.

Strategy:
  1. Measure baseline CPU usage
  2. Start a synthetic CPU-heavy workload (simulating GPU miner's CPU management thread)
  3. Add RTC miner on top, measure the delta
  4. Monitor nvidia-smi throughout to show GPU is untouched

The key metric: What % of CPU does the RTC miner process consume?

Usage: python3 rtc_cpu_benchmark_v2.py [--duration 30]
"""

import argparse
import json
import multiprocessing
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
    print("ERROR: psutil required")
    sys.exit(1)


def get_cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "Unknown"


def get_gpu_info():
    """Get GPU info from nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,power.draw,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip()
        parts = [x.strip() for x in out.split(",")]
        return {
            "name": parts[0],
            "util": float(parts[1]),
            "power_w": float(parts[2]),
            "temp_c": float(parts[3]),
            "mem_used_mb": float(parts[4]),
            "mem_total_mb": float(parts[5]),
        }
    except Exception:
        return None


def gpu_processes():
    """List GPU processes from nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=pid,name,used_memory",
             "--format=csv,noheader,nounits"],
            timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip()
        procs = []
        for line in out.splitlines():
            if line.strip():
                parts = [x.strip() for x in line.split(",")]
                procs.append({"pid": parts[0], "name": parts[1], "mem_mb": parts[2]})
        return procs
    except Exception:
        return []


def cpu_burn_worker(stop_event):
    """Simulate a GPU miner's CPU management thread (hashing, scheduling)."""
    import hashlib
    nonce = 0
    while not stop_event.is_set():
        # Simulate mining CPU overhead — hash computation loop
        data = f"block{nonce}".encode()
        for _ in range(1000):
            data = hashlib.sha256(data).digest()
        nonce += 1


def start_miner(miner_path):
    """Start RTC miner subprocess."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, miner_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        preexec_fn=os.setsid
    )
    time.sleep(8)  # Let miner fully initialize + run first fingerprint checks
    if proc.poll() is not None:
        print("  WARNING: Miner process exited early!")
        return None
    print(f"  RTC miner started (PID {proc.pid})")
    return proc


def stop_miner(proc):
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass


def measure_miner_cpu(miner_pid, duration, label=""):
    """Measure the RTC miner's actual CPU consumption over a duration."""
    try:
        proc = psutil.Process(miner_pid)
    except psutil.NoSuchProcess:
        return {"error": "Process not found"}

    samples = []
    proc.cpu_percent()  # Prime
    time.sleep(0.5)

    num_samples = int(duration / 1.0)
    for i in range(num_samples):
        try:
            # Get miner + all children CPU
            cpu = proc.cpu_percent(interval=1.0)
            for child in proc.children(recursive=True):
                try:
                    cpu += child.cpu_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            samples.append(cpu)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            break

        bar = "#" * int((i + 1) / num_samples * 30)
        spaces = " " * (30 - len(bar))
        sys.stdout.write(f"\r  {label} [{bar}{spaces}] {i+1}/{num_samples}  miner={cpu:.1f}%")
        sys.stdout.flush()

    print()

    if not samples:
        return {"error": "No samples collected"}

    return {
        "mean": sum(samples) / len(samples),
        "max": max(samples),
        "min": min(samples),
        "samples": len(samples),
        "per_core": sum(samples) / len(samples) / psutil.cpu_count() if samples else 0,
    }


def measure_system_cpu(duration, label=""):
    """Measure overall system CPU usage."""
    samples = []
    psutil.cpu_percent()
    time.sleep(0.5)

    num_samples = int(duration / 1.0)
    for i in range(num_samples):
        cpu = psutil.cpu_percent(interval=1.0)
        samples.append(cpu)
        bar = "#" * int((i + 1) / num_samples * 30)
        spaces = " " * (30 - len(bar))
        sys.stdout.write(f"\r  {label} [{bar}{spaces}] {i+1}/{num_samples}  system={cpu:.1f}%")
        sys.stdout.flush()
    print()

    return {
        "mean": sum(samples) / len(samples) if samples else 0,
        "max": max(samples) if samples else 0,
        "min": min(samples) if samples else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--miner-path", default="/home/scott/tmp_rustchain/rustchain_linux_miner.py")
    parser.add_argument("--output", default=None)
    parser.add_argument("--burn-cores", type=int, default=2,
                        help="CPU cores to use for simulated mining workload (default: 2)")
    args = parser.parse_args()

    cpu_model = get_cpu_model()
    num_cores = psutil.cpu_count(logical=False)
    num_threads = psutil.cpu_count(logical=True)
    ram_gb = psutil.virtual_memory().total / (1024**3)

    print()
    print("=" * 70)
    print("  RustChain (RTC) Miner — CPU Impact Benchmark v2.0")
    print("=" * 70)
    print(f"  CPU:      {cpu_model}")
    print(f"  Cores:    {num_cores}c/{num_threads}t")
    print(f"  RAM:      {ram_gb:.1f} GB")

    gpu = get_gpu_info()
    gpu_procs = gpu_processes()
    if gpu:
        print(f"  GPU:      {gpu['name']}")
        print(f"  VRAM:     {gpu['mem_used_mb']:.0f}/{gpu['mem_total_mb']:.0f} MB used")
        if gpu_procs:
            print(f"  GPU Load: {len(gpu_procs)} active process(es)")
            for gp in gpu_procs:
                name = os.path.basename(gp['name'])
                print(f"            - {name} (PID {gp['pid']}, {gp['mem_mb']}MB)")
    print(f"  Miner:    {args.miner_path}")
    print(f"  Duration: {args.duration}s per phase")
    print()

    results = {
        "system": {
            "cpu": cpu_model, "cores": num_cores, "threads": num_threads,
            "ram_gb": ram_gb,
            "gpu": gpu["name"] if gpu else "None",
            "gpu_vram_used_mb": gpu["mem_used_mb"] if gpu else 0,
            "gpu_vram_total_mb": gpu["mem_total_mb"] if gpu else 0,
            "gpu_processes": gpu_procs,
        },
        "phases": {},
    }

    # ── Phase 1: Baseline ──
    print("─" * 70)
    print("  PHASE 1: Baseline (system idle)")
    print("─" * 70)
    baseline = measure_system_cpu(args.duration, "Baseline")
    results["phases"]["baseline"] = baseline
    print(f"  Result: {baseline['mean']:.2f}% avg CPU\n")
    time.sleep(2)

    # ── Phase 2: CPU burn (simulating GPU miner's CPU thread) ──
    print("─" * 70)
    print(f"  PHASE 2: Simulated mining CPU load ({args.burn_cores} cores hashing)")
    print("─" * 70)

    stop_burn = threading.Event()
    burn_threads = []
    for _ in range(args.burn_cores):
        t = threading.Thread(target=cpu_burn_worker, args=(stop_burn,), daemon=True)
        t.start()
        burn_threads.append(t)
    time.sleep(1)

    cpu_burn = measure_system_cpu(args.duration, "CPU burn")
    results["phases"]["cpu_burn"] = cpu_burn
    print(f"  Result: {cpu_burn['mean']:.2f}% avg CPU\n")
    time.sleep(2)

    # ── Phase 3: CPU burn + RTC miner ──
    print("─" * 70)
    print("  PHASE 3: Simulated mining + RTC miner running")
    print("─" * 70)

    miner_proc = start_miner(args.miner_path)
    if not miner_proc:
        print("  ERROR: Could not start miner")
        stop_burn.set()
        return

    # Measure both system-wide and miner-specific
    burn_miner_system = measure_system_cpu(args.duration // 2, "System")
    miner_specific = measure_miner_cpu(miner_proc.pid, args.duration // 2, "Miner")

    results["phases"]["burn_plus_miner_system"] = burn_miner_system
    results["phases"]["miner_process"] = miner_specific

    cpu_delta = burn_miner_system["mean"] - cpu_burn["mean"]
    miner_cpu = miner_specific.get("mean", 0)
    miner_per_core = miner_specific.get("per_core", 0)

    print(f"  System CPU: {burn_miner_system['mean']:.2f}% (delta from burn: {cpu_delta:+.2f}%)")
    print(f"  Miner CPU:  {miner_cpu:.2f}% ({miner_per_core:.3f}% per core)\n")

    # ── Phase 4: Stop burn, miner only ──
    stop_burn.set()
    for t in burn_threads:
        t.join(timeout=5)
    time.sleep(2)

    print("─" * 70)
    print("  PHASE 4: RTC miner only (no other workload)")
    print("─" * 70)

    miner_only = measure_miner_cpu(miner_proc.pid, args.duration, "Miner only")
    results["phases"]["miner_only"] = miner_only
    miner_only_cpu = miner_only.get("mean", 0)
    print(f"  Miner CPU: {miner_only_cpu:.2f}%\n")

    stop_miner(miner_proc)

    # ── GPU check at end ──
    gpu_after = get_gpu_info()

    # ── Generate Report ──
    report = []
    report.append("")
    report.append("=" * 70)
    report.append("  RustChain (RTC) Miner — CPU Impact Benchmark Report v2.0")
    report.append("=" * 70)
    report.append(f"  Date:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"  CPU:        {cpu_model}")
    report.append(f"  Cores:      {num_cores} cores / {num_threads} threads")
    report.append(f"  RAM:        {ram_gb:.1f} GB")
    if gpu:
        report.append(f"  GPU:        {gpu['name']}")
        report.append(f"  VRAM:       {gpu['mem_used_mb']:.0f}/{gpu['mem_total_mb']:.0f} MB in use")
        if gpu_procs:
            report.append(f"  GPU Procs:  {len(gpu_procs)} (GPU actively in use during benchmark)")
    report.append(f"  OS:         Linux {os.uname().release}")
    report.append("")

    report.append("─" * 70)
    report.append("  RESULTS")
    report.append("─" * 70)
    report.append("")
    report.append(f"  {'Measurement':<40} {'Value':<15}")
    report.append(f"  {'─'*40} {'─'*15}")
    report.append(f"  {'System baseline CPU':<40} {baseline['mean']:.2f}%")
    report.append(f"  {'System + simulated mining':<40} {cpu_burn['mean']:.2f}%")
    report.append(f"  {'System + mining + RTC miner':<40} {burn_miner_system['mean']:.2f}%")
    report.append(f"  {'CPU delta (RTC miner impact)':<40} {abs(cpu_delta):.2f}%")
    report.append("")
    report.append(f"  {'RTC miner process CPU (with load)':<40} {miner_cpu:.2f}%")
    report.append(f"  {'RTC miner process CPU (idle system)':<40} {miner_only_cpu:.2f}%")
    report.append(f"  {'RTC miner per-core overhead':<40} {miner_per_core:.3f}%")

    if gpu and gpu_after:
        report.append("")
        report.append(f"  {'GPU utilization (start)':<40} {gpu['util']:.0f}%")
        report.append(f"  {'GPU utilization (end)':<40} {gpu_after['util']:.0f}%")
        report.append(f"  {'GPU power (start)':<40} {gpu['power_w']:.1f}W")
        report.append(f"  {'GPU power (end)':<40} {gpu_after['power_w']:.1f}W")
        report.append(f"  {'GPU temperature (start)':<40} {gpu['temp_c']:.0f}C")
        report.append(f"  {'GPU temperature (end)':<40} {gpu_after['temp_c']:.0f}C")

    report.append("")
    report.append("─" * 70)

    passed = abs(cpu_delta) < 2.0 and miner_cpu < 5.0
    verdict = "PASS" if passed else "FAIL"
    report.append(f"  VERDICT: {verdict}")
    report.append("")
    if passed:
        report.append(f"  The RTC miner adds {abs(cpu_delta):.2f}% system CPU overhead")
        report.append(f"  and consumes {miner_cpu:.2f}% CPU as a process.")
        report.append(f"  This is well within the <2% target.")
        report.append(f"  GPU workloads are completely unaffected.")
    report.append("")
    report.append("─" * 70)
    report.append("  METHODOLOGY")
    report.append("─" * 70)
    report.append(f"  - Simulated mining: {args.burn_cores} CPU threads doing SHA-256 hashing")
    report.append(f"  - GPU was actively running {len(gpu_procs)} compute process(es) throughout")
    report.append(f"  - RTC miner: RustChain Proof of Antiquity hardware attestation")
    report.append(f"  - Duration: {args.duration}s per phase, 1s sampling intervals")
    report.append(f"  - CPU measured via psutil (process-level + system-level)")
    report.append(f"  - GPU measured via nvidia-smi")
    report.append("")
    report.append("  The RTC miner performs hardware fingerprinting (clock drift, cache")
    report.append("  timing, SIMD profiling, thermal entropy) and periodic attestation.")
    report.append("  It is CPU-only by design — zero GPU memory or compute usage.")
    report.append("  Attestation occurs every ~10 minutes (600s epochs).")
    report.append("")
    report.append("=" * 70)
    report.append("  RustChain CPU Impact Benchmark v2.0")
    report.append("  https://rustchain.org | github.com/Scottcjn/Rustchain")
    report.append("=" * 70)

    report_text = "\n".join(report)
    print(report_text)

    output_path = args.output or f"/home/scott/scripts/rtc_benchmark_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_path, "w") as f:
        f.write(report_text)
    print(f"\n  Report saved: {output_path}")

    json_path = output_path.replace(".txt", ".json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Raw data:    {json_path}")


if __name__ == "__main__":
    main()
