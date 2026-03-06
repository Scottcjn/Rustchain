#!/usr/bin/env python3
"""
RustChain PoA Hardware Fingerprint Validation for Windows
Ported from Linux fingerprint_checks.py
"""

import hashlib
import os
import platform
import statistics
import subprocess
import time
import winreg
import uuid
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
    """Check 3: SIMD Unit Identity (Windows Version)"""
    cpu_info = ""
    try:
        cpu_info = subprocess.check_output(
            ["wmic", "cpu", "get", "Caption"],
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode().strip()
    except:
        cpu_info = platform.processor()

    has_sse = "sse" in cpu_info.lower() or "intel" in cpu_info.lower() or "amd" in cpu_info.lower()
    has_avx = "avx" in cpu_info.lower()

    data = {
        "arch": platform.machine(),
        "cpu_caption": cpu_info,
        "has_sse": has_sse,
        "has_avx": has_avx,
    }

    # If x86_64, we assume at least SSE2
    if platform.machine().lower() in ["amd64", "x86_64"]:
        has_sse = True

    valid = has_sse or has_avx
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
    """Check 6: Anti-Emulation Behavioral Checks (Windows Version)

    Detects traditional hypervisors AND cloud provider VMs:
    - VMware, VirtualBox, KVM, QEMU, Xen, Hyper-V, Parallels
    - AWS EC2 (Nitro/Xen), GCP, Azure, DigitalOcean
    - Linode, Vultr, Hetzner, Oracle Cloud, OVH

    Updated 2026-02-21: Added cloud provider detection after
    discovering AWS t3.medium instances attempting to mine.
    """
    vm_indicators = []

    # --- Registry checks (traditional + cloud) ---
    reg_checks = [
        # Traditional hypervisors
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System", "SystemBiosVersion", "vbox"),
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System", "VideoBiosVersion", "vbox"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VMware, Inc.\VMware Tools", "", ""),
        # AWS EC2
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS", "SystemManufacturer", "amazon"),
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS", "SystemProductName", "ec2"),
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS", "BIOSVendor", "amazon"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Amazon\MachineImage", "", ""),
        # Google Cloud
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS", "SystemManufacturer", "google"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Google\ComputeEngine", "", ""),
        # Azure
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS", "SystemManufacturer", "microsoft"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Azure", "", ""),
        # QEMU/KVM
        (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\Description\System\BIOS", "SystemManufacturer", "qemu"),
    ]

    for root, path, val_name, search_str in reg_checks:
        try:
            with winreg.OpenKey(root, path) as key:
                if val_name:
                    val, _ = winreg.QueryValueEx(key, val_name)
                    if search_str.lower() in str(val).lower():
                        vm_indicators.append(f"REG:{path}\\{val_name}:{search_str}")
                else:
                    vm_indicators.append(f"REG:{path}")
        except (WindowsError, FileNotFoundError, OSError):
            pass

    # --- File checks (traditional + cloud agent files) ---
    vm_files = [
        # VirtualBox
        r"C:\windows\System32\Drivers\VBoxGuest.sys",
        r"C:\windows\System32\Drivers\vmmouse.sys",
        r"C:\windows\System32\Drivers\vmusb.sys",
        r"C:\windows\System32\Drivers\vm3dver.dll",
        # VMware
        r"C:\windows\System32\Drivers\vmhgfs.sys",
        # AWS
        r"C:\Program Files\Amazon\SSM\amazon-ssm-agent.exe",
        r"C:\Program Files\Amazon\EC2Launch\EC2Launch.exe",
        r"C:\ProgramData\Amazon\EC2-Windows\Launch\Settings\LaunchConfig.json",
        # Google Cloud
        r"C:\Program Files\Google\Compute Engine\agent\GCEWindowsAgent.exe",
        # Azure
        r"C:\WindowsAzure\GuestAgent\WaAppAgent.exe",
        r"C:\Packages\Plugins\Microsoft.Compute.VMAccessAgent",
    ]

    for f in vm_files:
        if os.path.exists(f):
            vm_indicators.append(f"FILE:{f}")

    # --- WMI check for cloud provider ---
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "bios", "get", "serialnumber,manufacturer", "/format:list"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.lower()
        cloud_strings = ["amazon", "ec2", "google", "azure", "digitalocean",
                         "vultr", "linode", "hetzner", "oracle", "ovh"]
        for cs in cloud_strings:
            if cs in output:
                vm_indicators.append(f"WMI_BIOS:{cs}")
    except:
        pass

    # --- Cloud metadata endpoint check ---
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/",
            headers={"Metadata": "true"}
        )
        resp = urllib.request.urlopen(req, timeout=1)
        cloud_body = resp.read(512).decode("utf-8", errors="replace").lower()
        cloud_provider = "unknown_cloud"
        if "latest" in cloud_body or "meta-data" in cloud_body:
            cloud_provider = "aws_or_gcp"
        if "azure" in cloud_body or "microsoft" in cloud_body:
            cloud_provider = "azure"
        vm_indicators.append(f"cloud_metadata:{cloud_provider}")
    except:
        pass

    # --- AWS IMDSv2 check (token-based, Nitro instances) ---
    try:
        import urllib.request
        token_req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "5"},
            method="PUT"
        )
        token_resp = urllib.request.urlopen(token_req, timeout=1)
        if token_resp.status == 200:
            vm_indicators.append("cloud_metadata:aws_imdsv2")
    except:
        pass

    # --- Environment variable checks ---
    for key in ["KUBERNETES", "DOCKER", "VIRTUAL", "container",
                "AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI",
                "GOOGLE_CLOUD_PROJECT", "AZURE_FUNCTIONS_ENVIRONMENT",
                "WEBSITE_INSTANCE_ID"]:
        if key in os.environ:
            vm_indicators.append(f"ENV:{key}")

    data = {
        "vm_indicators": vm_indicators,
        "indicator_count": len(vm_indicators),
        "is_likely_vm": len(vm_indicators) > 0,
    }

    valid = len(vm_indicators) == 0
    if not valid:
        data["fail_reason"] = "vm_detected"

    return valid, data


def validate_all_checks_win() -> Tuple[bool, Dict]:
    """Run all 6 fingerprint checks for Windows."""
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

    for key, name, func in checks:
        try:
            passed, data = func()
        except Exception as e:
            passed = False
            data = {"error": str(e)}
        results[key] = {"passed": passed, "data": data}
        if not passed:
            all_passed = True # Temporarily passing for dev, change to False for prod
            # Wait, Scott said they must pass. But Windows environments might be tricky.
            # I'll set all_passed = False if any fail.
            all_passed = False

    return all_passed, results
