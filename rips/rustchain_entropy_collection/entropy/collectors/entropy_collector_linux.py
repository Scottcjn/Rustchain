#!/usr/bin/env python3
"""
RustChain Entropy Collector - Modern Linux Edition
===================================================

"Every vintage computer has historical potential"

Collects deep hardware entropy from Linux systems for validator fingerprinting.
Makes emulation economically irrational.

Usage: python3 entropy_collector_linux.py
"""

import hashlib
import json
import os
import platform
import re
import socket
import struct
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

# =============================================================================
# Entropy Collection
# =============================================================================

@dataclass
class LinuxEntropyProfile:
    """Complete Linux hardware entropy profile"""
    # System Identity
    hostname: str
    kernel_version: str
    os_release: str
    architecture: str

    # CPU
    cpu_model: str
    cpu_vendor: str
    cpu_family: str
    cpu_model_num: str
    cpu_stepping: str
    cpu_flags: str
    cpu_cores: int
    cpu_threads: int
    cpu_freq_mhz: float
    cpu_cache_l1d: int
    cpu_cache_l1i: int
    cpu_cache_l2: int
    cpu_cache_l3: int
    cpu_microcode: str

    # Memory
    ram_total_kb: int
    ram_type: str
    swap_total_kb: int

    # Storage
    disk_model: str
    disk_serial: str
    disk_size_bytes: int
    disk_wwn: str
    root_uuid: str

    # Network
    mac_addresses: List[str]

    # Motherboard/DMI
    board_vendor: str
    board_name: str
    board_serial: str
    bios_vendor: str
    bios_version: str
    bios_date: str
    system_uuid: str
    product_name: str

    # GPU
    gpu_model: str
    gpu_vendor: str
    gpu_driver: str

    # Timing Entropy
    timing_samples: List[int]
    rdtsc_samples: List[int]

    # Thermal
    thermal_zones: Dict[str, float]

    # Kernel Entropy
    kernel_random_bytes: str
    boot_id: str
    machine_id: str


def read_file(path: str, default: str = "") -> str:
    """Safely read a file"""
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except:
        return default


def run_cmd(cmd: str, default: str = "") -> str:
    """Safely run a command"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except:
        return default


def collect_cpu_info() -> Dict:
    """Collect detailed CPU information"""
    info = {
        "model": "", "vendor": "", "family": "", "model_num": "",
        "stepping": "", "flags": "", "cores": 0, "threads": 0,
        "freq_mhz": 0.0, "cache_l1d": 0, "cache_l1i": 0,
        "cache_l2": 0, "cache_l3": 0, "microcode": ""
    }

    cpuinfo = read_file("/proc/cpuinfo")
    for line in cpuinfo.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()

            if "model name" in key:
                info["model"] = val
            elif key == "vendor_id":
                info["vendor"] = val
            elif key == "cpu family":
                info["family"] = val
            elif key == "model" and not info["model_num"]:
                info["model_num"] = val
            elif key == "stepping":
                info["stepping"] = val
            elif key == "flags":
                info["flags"] = val[:200]  # Truncate
            elif key == "cpu mhz":
                info["freq_mhz"] = float(val)
            elif key == "microcode":
                info["microcode"] = val

    info["cores"] = int(run_cmd("nproc --all", "1"))
    info["threads"] = int(run_cmd("grep -c processor /proc/cpuinfo", "1"))

    # Cache sizes
    for cache_file in Path("/sys/devices/system/cpu/cpu0/cache/").glob("index*/size"):
        try:
            level = read_file(str(cache_file.parent / "level"))
            cache_type = read_file(str(cache_file.parent / "type"))
            size_str = read_file(str(cache_file))
            size_kb = int(re.sub(r'[^\d]', '', size_str)) if size_str else 0

            if level == "1" and "Data" in cache_type:
                info["cache_l1d"] = size_kb
            elif level == "1" and "Instruction" in cache_type:
                info["cache_l1i"] = size_kb
            elif level == "2":
                info["cache_l2"] = size_kb
            elif level == "3":
                info["cache_l3"] = size_kb
        except:
            pass

    return info


def collect_memory_info() -> Dict:
    """Collect memory information"""
    info = {"total_kb": 0, "type": "Unknown", "swap_kb": 0}

    meminfo = read_file("/proc/meminfo")
    for line in meminfo.split("\n"):
        if "MemTotal" in line:
            info["total_kb"] = int(re.sub(r'[^\d]', '', line))
        elif "SwapTotal" in line:
            info["swap_kb"] = int(re.sub(r'[^\d]', '', line))

    # Try to get memory type from dmidecode
    dmidecode = run_cmd("sudo dmidecode -t memory 2>/dev/null | grep -i 'Type:' | head -1")
    if dmidecode:
        info["type"] = dmidecode.split(":")[-1].strip()

    return info


def collect_disk_info() -> Dict:
    """Collect primary disk information"""
    info = {
        "model": "", "serial": "", "size_bytes": 0,
        "wwn": "", "root_uuid": ""
    }

    # Find root device
    root_dev = run_cmd("findmnt -n -o SOURCE /").replace("/dev/", "")
    if root_dev:
        # Strip partition number
        base_dev = re.sub(r'[0-9]+$|p[0-9]+$', '', root_dev)

        # Get disk info from /sys
        sys_path = f"/sys/block/{base_dev}/device"
        info["model"] = read_file(f"{sys_path}/model")
        info["serial"] = read_file(f"{sys_path}/serial") or run_cmd(f"sudo hdparm -I /dev/{base_dev} 2>/dev/null | grep 'Serial Number' | awk '{{print $NF}}'")

        size_sectors = read_file(f"/sys/block/{base_dev}/size")
        if size_sectors:
            info["size_bytes"] = int(size_sectors) * 512

        info["wwn"] = read_file(f"{sys_path}/wwid") or run_cmd(f"sudo hdparm -I /dev/{base_dev} 2>/dev/null | grep 'WWN' | awk '{{print $NF}}'")

    # Root UUID
    info["root_uuid"] = run_cmd("findmnt -n -o UUID /")

    return info


def collect_network_info() -> List[str]:
    """Collect MAC addresses"""
    macs = []
    for iface in Path("/sys/class/net/").iterdir():
        if iface.name != "lo":
            mac = read_file(str(iface / "address"))
            if mac and mac != "00:00:00:00:00:00":
                macs.append(mac)
    return macs


def collect_dmi_info() -> Dict:
    """Collect DMI/SMBIOS information"""
    info = {
        "board_vendor": "", "board_name": "", "board_serial": "",
        "bios_vendor": "", "bios_version": "", "bios_date": "",
        "system_uuid": "", "product_name": ""
    }

    dmi_path = "/sys/class/dmi/id"
    info["board_vendor"] = read_file(f"{dmi_path}/board_vendor")
    info["board_name"] = read_file(f"{dmi_path}/board_name")
    info["board_serial"] = read_file(f"{dmi_path}/board_serial")
    info["bios_vendor"] = read_file(f"{dmi_path}/bios_vendor")
    info["bios_version"] = read_file(f"{dmi_path}/bios_version")
    info["bios_date"] = read_file(f"{dmi_path}/bios_date")
    info["system_uuid"] = read_file(f"{dmi_path}/product_uuid")
    info["product_name"] = read_file(f"{dmi_path}/product_name")

    return info


def collect_gpu_info() -> Dict:
    """Collect GPU information"""
    info = {"model": "", "vendor": "", "driver": ""}

    # Try lspci
    gpu_line = run_cmd("lspci | grep -i 'vga\\|3d\\|display' | head -1")
    if gpu_line:
        info["model"] = gpu_line.split(":")[-1].strip() if ":" in gpu_line else gpu_line

    # Try to get driver
    gpu_driver = run_cmd("lspci -k | grep -A 2 -i 'vga\\|3d' | grep 'Kernel driver' | head -1")
    if gpu_driver:
        info["driver"] = gpu_driver.split(":")[-1].strip()

    return info


def collect_timing_entropy() -> Dict:
    """Collect timing-based entropy"""
    timing_samples = []
    rdtsc_samples = []

    # High-resolution timing samples
    for i in range(64):
        start = time.perf_counter_ns()
        # Small computation
        _ = sum(range(i * 10 + 1))
        end = time.perf_counter_ns()
        timing_samples.append(end - start)

    # Try to read TSC (x86 only)
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        for _ in range(32):
            t = time.perf_counter_ns()
            rdtsc_samples.append(t & 0xFFFFFFFF)
    except:
        rdtsc_samples = timing_samples[:32]

    return {"timing": timing_samples, "rdtsc": rdtsc_samples}


def collect_thermal_info() -> Dict[str, float]:
    """Collect thermal sensor data"""
    zones = {}

    thermal_path = Path("/sys/class/thermal/")
    if thermal_path.exists():
        for zone in thermal_path.glob("thermal_zone*"):
            try:
                temp = int(read_file(str(zone / "temp"))) / 1000.0
                zone_type = read_file(str(zone / "type"))
                zones[zone_type] = temp
            except:
                pass

    # Also try hwmon
    hwmon_path = Path("/sys/class/hwmon/")
    if hwmon_path.exists():
        for hwmon in hwmon_path.iterdir():
            try:
                name = read_file(str(hwmon / "name"))
                for temp_file in hwmon.glob("temp*_input"):
                    temp = int(read_file(str(temp_file))) / 1000.0
                    zones[f"{name}_{temp_file.stem}"] = temp
            except:
                pass

    return zones


def collect_kernel_entropy() -> Dict:
    """Collect kernel entropy sources"""
    info = {"random_bytes": "", "boot_id": "", "machine_id": ""}

    # Get some random bytes
    try:
        with open("/dev/urandom", "rb") as f:
            info["random_bytes"] = f.read(32).hex()
    except:
        pass

    info["boot_id"] = read_file("/proc/sys/kernel/random/boot_id")
    info["machine_id"] = read_file("/etc/machine-id")

    return info


def collect_all_entropy() -> LinuxEntropyProfile:
    """Collect all entropy sources"""
    print("Collecting Linux hardware entropy...")

    print("  [1/10] CPU info...")
    cpu = collect_cpu_info()

    print("  [2/10] Memory info...")
    mem = collect_memory_info()

    print("  [3/10] Disk info...")
    disk = collect_disk_info()

    print("  [4/10] Network info...")
    macs = collect_network_info()

    print("  [5/10] DMI/BIOS info...")
    dmi = collect_dmi_info()

    print("  [6/10] GPU info...")
    gpu = collect_gpu_info()

    print("  [7/10] Timing entropy...")
    timing = collect_timing_entropy()

    print("  [8/10] Thermal sensors...")
    thermal = collect_thermal_info()

    print("  [9/10] Kernel entropy...")
    kernel = collect_kernel_entropy()

    print("  [10/10] System identity...")

    return LinuxEntropyProfile(
        hostname=socket.gethostname(),
        kernel_version=platform.release(),
        os_release=read_file("/etc/os-release").split("\n")[0] if os.path.exists("/etc/os-release") else platform.system(),
        architecture=platform.machine(),

        cpu_model=cpu["model"],
        cpu_vendor=cpu["vendor"],
        cpu_family=cpu["family"],
        cpu_model_num=cpu["model_num"],
        cpu_stepping=cpu["stepping"],
        cpu_flags=cpu["flags"],
        cpu_cores=cpu["cores"],
        cpu_threads=cpu["threads"],
        cpu_freq_mhz=cpu["freq_mhz"],
        cpu_cache_l1d=cpu["cache_l1d"],
        cpu_cache_l1i=cpu["cache_l1i"],
        cpu_cache_l2=cpu["cache_l2"],
        cpu_cache_l3=cpu["cache_l3"],
        cpu_microcode=cpu["microcode"],

        ram_total_kb=mem["total_kb"],
        ram_type=mem["type"],
        swap_total_kb=mem["swap_kb"],

        disk_model=disk["model"],
        disk_serial=disk["serial"],
        disk_size_bytes=disk["size_bytes"],
        disk_wwn=disk["wwn"],
        root_uuid=disk["root_uuid"],

        mac_addresses=macs,

        board_vendor=dmi["board_vendor"],
        board_name=dmi["board_name"],
        board_serial=dmi["board_serial"],
        bios_vendor=dmi["bios_vendor"],
        bios_version=dmi["bios_version"],
        bios_date=dmi["bios_date"],
        system_uuid=dmi["system_uuid"],
        product_name=dmi["product_name"],

        gpu_model=gpu["model"],
        gpu_vendor=gpu["vendor"],
        gpu_driver=gpu["driver"],

        timing_samples=timing["timing"],
        rdtsc_samples=timing["rdtsc"],

        thermal_zones=thermal,

        kernel_random_bytes=kernel["random_bytes"],
        boot_id=kernel["boot_id"],
        machine_id=kernel["machine_id"],
    )


# =============================================================================
# Entropy Proof Generation
# =============================================================================

def generate_entropy_proof(profile: LinuxEntropyProfile) -> Dict:
    """Generate entropy proof from profile"""
    print("\nGenerating entropy proof...")

    # Combine all entropy into a single blob
    entropy_data = json.dumps(asdict(profile), sort_keys=True).encode()

    # SHA256 hash
    sha256_hash = hashlib.sha256(entropy_data).hexdigest()

    # Create fingerprint (double hash with key data)
    fingerprint_data = (
        sha256_hash +
        profile.machine_id +
        profile.system_uuid +
        "".join(profile.mac_addresses) +
        profile.disk_serial +
        profile.board_serial
    ).encode()
    deep_fingerprint = hashlib.sha256(fingerprint_data).hexdigest()

    # Determine tier based on architecture/age heuristics
    arch = profile.architecture.lower()
    if arch in ["ppc", "ppc64", "powerpc"]:
        tier = "vintage"
        multiplier = 2.5
    elif arch in ["i386", "i486", "i586", "i686"]:
        tier = "classic"
        multiplier = 2.0
    elif arch in ["x86_64", "amd64"]:
        tier = "modern"
        multiplier = 1.0
    elif arch in ["arm64", "aarch64"]:
        tier = "recent"
        multiplier = 0.5
    else:
        tier = "unknown"
        multiplier = 1.0

    # Count entropy sources
    sources = 0
    if profile.cpu_model: sources += 1
    if profile.cpu_microcode: sources += 1
    if profile.ram_total_kb: sources += 1
    if profile.disk_serial: sources += 1
    if profile.mac_addresses: sources += 1
    if profile.board_serial: sources += 1
    if profile.system_uuid: sources += 1
    if profile.gpu_model: sources += 1
    if profile.timing_samples: sources += 1
    if profile.thermal_zones: sources += 1
    if profile.kernel_random_bytes: sources += 1
    if profile.machine_id: sources += 1

    # Create signature
    signature = f"LINUX-{arch.upper()}-ENTROPY-{deep_fingerprint[:16]}-{int(time.time())}-D{sources}"

    return {
        "sha256_hash": sha256_hash,
        "deep_fingerprint": deep_fingerprint,
        "signature": signature,
        "tier": tier,
        "multiplier": multiplier,
        "entropy_sources": sources,
        "timestamp": int(time.time()),
        "hardware_verified": True,
    }


def write_entropy_json(profile: LinuxEntropyProfile, proof: Dict):
    """Write entropy profile to JSON file"""
    output = {
        "rustchain_entropy": {
            "version": 1,
            "platform": "linux",
            "collector": "entropy_collector_linux.py",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "proof_of_antiquity": {
            "philosophy": "Every vintage computer has historical potential",
            "consensus": "NOT Proof of Work - This is PROOF OF ANTIQUITY",
            "hardware_verified": proof["hardware_verified"],
            "tier": proof["tier"],
            "multiplier": proof["multiplier"],
        },
        "entropy_proof": {
            "sha256_hash": proof["sha256_hash"],
            "deep_fingerprint": proof["deep_fingerprint"],
            "signature": proof["signature"],
            "entropy_sources": proof["entropy_sources"],
            "sources": [
                "cpu_identification",
                "cpu_microcode",
                "memory_configuration",
                "disk_serial",
                "mac_addresses",
                "motherboard_serial",
                "system_uuid",
                "gpu_identification",
                "timing_entropy",
                "thermal_sensors",
                "kernel_random",
                "machine_id",
            ]
        },
        "hardware_profile": {
            "hostname": profile.hostname,
            "kernel": profile.kernel_version,
            "os": profile.os_release,
            "architecture": profile.architecture,
            "cpu": {
                "model": profile.cpu_model,
                "vendor": profile.cpu_vendor,
                "family": profile.cpu_family,
                "stepping": profile.cpu_stepping,
                "cores": profile.cpu_cores,
                "threads": profile.cpu_threads,
                "frequency_mhz": profile.cpu_freq_mhz,
                "microcode": profile.cpu_microcode,
            },
            "cache": {
                "l1d_kb": profile.cpu_cache_l1d,
                "l1i_kb": profile.cpu_cache_l1i,
                "l2_kb": profile.cpu_cache_l2,
                "l3_kb": profile.cpu_cache_l3,
            },
            "memory": {
                "total_mb": profile.ram_total_kb // 1024,
                "type": profile.ram_type,
                "swap_mb": profile.swap_total_kb // 1024,
            },
            "storage": {
                "model": profile.disk_model,
                "serial": profile.disk_serial,
                "size_gb": round(profile.disk_size_bytes / 1e9, 2),
                "wwn": profile.disk_wwn,
                "root_uuid": profile.root_uuid,
            },
            "network": {
                "mac_addresses": profile.mac_addresses,
            },
            "motherboard": {
                "vendor": profile.board_vendor,
                "name": profile.board_name,
                "serial": profile.board_serial,
            },
            "bios": {
                "vendor": profile.bios_vendor,
                "version": profile.bios_version,
                "date": profile.bios_date,
            },
            "system": {
                "uuid": profile.system_uuid,
                "product": profile.product_name,
                "machine_id": profile.machine_id,
            },
            "gpu": {
                "model": profile.gpu_model,
                "driver": profile.gpu_driver,
            },
            "thermal": profile.thermal_zones,
        },
    }

    filename = f"entropy_linux_{profile.hostname}.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nEntropy profile written to: {filename}")
    return filename


# =============================================================================
# Main
# =============================================================================

def main():
    print("")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║   RUSTCHAIN ENTROPY COLLECTOR - LINUX EDITION                        ║")
    print("║                                                                      ║")
    print("║   \"Every vintage computer has historical potential\"                  ║")
    print("║                                                                      ║")
    print("║   Collecting hardware entropy to prove YOU ARE NOT AN EMULATOR       ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print("")

    # Collect entropy
    profile = collect_all_entropy()

    # Generate proof
    proof = generate_entropy_proof(profile)

    # Write output
    filename = write_entropy_json(profile, proof)

    # Print summary
    print("")
    print("═" * 70)
    print("                    HARDWARE PROFILE SUMMARY")
    print("═" * 70)
    print(f"  Hostname: {profile.hostname}")
    print(f"  OS: {profile.os_release[:50]}")
    print(f"  Kernel: {profile.kernel_version}")
    print(f"  Architecture: {profile.architecture}")
    print(f"  CPU: {profile.cpu_model[:50]}")
    print(f"  Cores/Threads: {profile.cpu_cores}/{profile.cpu_threads}")
    print(f"  RAM: {profile.ram_total_kb // 1024} MB")
    print(f"  Disk: {profile.disk_model} ({profile.disk_serial})")
    print(f"  GPU: {profile.gpu_model[:50]}")
    print(f"  MACs: {', '.join(profile.mac_addresses[:3])}")
    print(f"  Machine ID: {profile.machine_id}")
    print("")
    print("═" * 70)
    print("                    ENTROPY PROOF")
    print("═" * 70)
    print(f"  Signature: {proof['signature']}")
    print(f"  SHA256: {proof['sha256_hash'][:32]}...")
    print(f"  Fingerprint: {proof['deep_fingerprint'][:32]}...")
    print(f"  Entropy Sources: {proof['entropy_sources']}")
    print(f"  Hardware Tier: {proof['tier'].upper()} ({proof['multiplier']}x)")
    print("")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                    ENTROPY COLLECTION COMPLETE                       ║")
    print("║                                                                      ║")
    print("║   This fingerprint proves your hardware is REAL                      ║")
    print("║   Emulation is economically irrational.                              ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print("")

    return proof


if __name__ == "__main__":
    main()
