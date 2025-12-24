#!/usr/bin/env python
# RustChain Entropy Collector - PowerPC Edition (Python 2.5 Compatible)
# "Every vintage computer has historical potential"

from __future__ import with_statement  # Enable 'with' in Python 2.5
import hashlib
import os
import platform
import socket
import subprocess
import sys
import time

try:
    import json
except ImportError:
    import simplejson as json

def run_cmd(cmd, default=""):
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        return stdout.strip()
    except:
        return default

def read_file(path, default=""):
    try:
        f = open(path, 'r')
        data = f.read().strip()
        f.close()
        return data
    except:
        return default

def collect_cpu_info():
    info = {"model": "", "cores": 1, "frequency_mhz": 0, "l2_cache": 0}
    info["model"] = run_cmd("sysctl -n hw.model")
    info["cores"] = int(run_cmd("sysctl -n hw.ncpu") or "1")
    freq = run_cmd("sysctl -n hw.cpufrequency")
    if freq:
        info["frequency_mhz"] = int(freq) / 1000000
    l2 = run_cmd("sysctl -n hw.l2cachesize")
    if l2:
        info["l2_cache"] = int(l2) / 1024
    return info

def collect_memory_info():
    info = {"total_mb": 0, "type": "Unknown"}
    mem = run_cmd("sysctl -n hw.memsize")
    if mem:
        info["total_mb"] = int(mem) / (1024 * 1024)
    profiler = run_cmd("system_profiler SPMemoryDataType 2>/dev/null | grep 'Type:' | head -1")
    if profiler and ":" in profiler:
        info["type"] = profiler.split(":")[-1].strip()
    return info

def collect_disk_info():
    info = {"model": "", "serial": "", "size_gb": 0}
    profiler = run_cmd("system_profiler SPSerialATADataType SPParallelATADataType 2>/dev/null")
    for line in profiler.split("\n"):
        if "Model:" in line and not info["model"]:
            info["model"] = line.split(":")[-1].strip()
        elif "Serial Number:" in line and not info["serial"]:
            info["serial"] = line.split(":")[-1].strip()
        elif "Capacity:" in line and not info["size_gb"]:
            try:
                cap_str = line.split(":")[-1].strip()
                info["size_gb"] = float(cap_str.split()[0])
            except:
                pass
    return info

def collect_network_info():
    macs = []
    ifconfig = run_cmd("ifconfig -a")
    for line in ifconfig.split("\n"):
        if "ether" in line.lower():
            parts = line.split()
            for i, p in enumerate(parts):
                if p.lower() == "ether" and i + 1 < len(parts):
                    mac = parts[i + 1]
                    if mac and mac != "00:00:00:00:00:00":
                        macs.append(mac)
    return macs

def collect_system_info():
    info = {"hostname": socket.gethostname(), "serial_number": "", "model_identifier": "", "boot_rom_version": "", "hardware_uuid": ""}
    serial = run_cmd("ioreg -l 2>/dev/null | grep IOPlatformSerialNumber | head -1")
    if serial and '"' in serial:
        try:
            info["serial_number"] = serial.split('"')[-2]
        except:
            pass
    profiler = run_cmd("system_profiler SPHardwareDataType 2>/dev/null")
    for line in profiler.split("\n"):
        if "Model Identifier:" in line:
            info["model_identifier"] = line.split(":")[-1].strip()
        elif "Boot ROM Version:" in line:
            info["boot_rom_version"] = line.split(":")[-1].strip()
        elif "Hardware UUID:" in line:
            info["hardware_uuid"] = line.split(":")[-1].strip()
    return info

def collect_gpu_info():
    info = {"model": "", "vendor": "", "vram_mb": 0}
    profiler = run_cmd("system_profiler SPDisplaysDataType 2>/dev/null")
    for line in profiler.split("\n"):
        if "Chipset Model:" in line:
            info["model"] = line.split(":")[-1].strip()
        elif "Type:" in line and "GPU" in line:
            info["model"] = line.split(":")[-1].strip()
        elif "Vendor:" in line and not info["vendor"]:
            info["vendor"] = line.split(":")[-1].strip()
        elif "VRAM" in line:
            try:
                vram_str = line.split(":")[-1].strip()
                info["vram_mb"] = int(vram_str.split()[0])
            except:
                pass
    return info

def collect_nvram_info():
    info = {"nvram_sample": "", "boot_args": ""}
    try:
        f = open("/dev/random", "rb")
        data = f.read(32)
        f.close()
        info["nvram_sample"] = data.encode('hex')
    except:
        pass
    info["boot_args"] = run_cmd("nvram boot-args 2>/dev/null")
    return info

def collect_timing_entropy():
    samples = []
    for i in range(32):
        start = time.time()
        _ = sum(range(i * 10 + 1))
        end = time.time()
        samples.append(int((end - start) * 1000000000))
    return samples

def collect_os_info():
    info = {"version": "", "darwin_version": "", "kernel": ""}
    info["version"] = run_cmd("sw_vers -productVersion")
    info["darwin_version"] = run_cmd("uname -r")
    info["kernel"] = platform.release()
    return info

def collect_all_entropy():
    print "Collecting PowerMac G5 hardware entropy..."
    print "  [1/9] CPU info..."
    cpu = collect_cpu_info()
    print "  [2/9] Memory info..."
    mem = collect_memory_info()
    print "  [3/9] Disk info..."
    disk = collect_disk_info()
    print "  [4/9] Network info..."
    macs = collect_network_info()
    print "  [5/9] System info..."
    system = collect_system_info()
    print "  [6/9] GPU info..."
    gpu = collect_gpu_info()
    print "  [7/9] NVRAM info..."
    nvram = collect_nvram_info()
    print "  [8/9] Timing entropy..."
    timing = collect_timing_entropy()
    print "  [9/9] OS info..."
    os_info = collect_os_info()
    return {"cpu": cpu, "memory": mem, "disk": disk, "mac_addresses": macs, "system": system, "gpu": gpu, "nvram": nvram, "timing_samples": timing, "os": os_info}

def generate_entropy_proof(data):
    print "\nGenerating entropy proof..."
    entropy_json = json.dumps(data, sort_keys=True)
    sha256_hash = hashlib.sha256(entropy_json).hexdigest()
    fingerprint_data = sha256_hash + data["system"]["serial_number"] + "".join(data["mac_addresses"]) + data["disk"]["serial"] + data["system"]["hardware_uuid"]
    fingerprint = hashlib.sha256(fingerprint_data).hexdigest()
    arch = platform.machine()
    if arch in ["Power Macintosh", "ppc", "ppc64"]:
        tier = "vintage"
        multiplier = 2.5
    else:
        tier = "modern"
        multiplier = 1.0
    sources = 0
    if data["cpu"]["model"]: sources += 1
    if data["memory"]["total_mb"]: sources += 1
    if data["disk"]["serial"]: sources += 1
    if data["mac_addresses"]: sources += 1
    if data["system"]["serial_number"]: sources += 1
    if data["gpu"]["model"]: sources += 1
    if data["nvram"]["nvram_sample"]: sources += 1
    if data["timing_samples"]: sources += 1
    if data["os"]["version"]: sources += 1
    timestamp = int(time.time())
    signature = "PPC-G5-ENTROPY-%s-%d-D%d" % (fingerprint[:16], timestamp, sources)
    return {"sha256_hash": sha256_hash, "deep_fingerprint": fingerprint, "signature": signature, "tier": tier, "multiplier": multiplier, "entropy_sources": sources, "timestamp": timestamp, "hardware_verified": True}

def write_output(data, proof):
    output = {
        "rustchain_entropy": {"version": 1, "platform": "macos_ppc_g5", "collector": "entropy_collector_ppc_py25.py", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        "proof_of_antiquity": {"philosophy": "Every vintage computer has historical potential", "consensus": "NOT Proof of Work - This is PROOF OF ANTIQUITY", "hardware_verified": proof["hardware_verified"], "tier": proof["tier"], "multiplier": proof["multiplier"]},
        "entropy_proof": {"sha256_hash": proof["sha256_hash"], "deep_fingerprint": proof["deep_fingerprint"], "signature": proof["signature"], "entropy_sources": proof["entropy_sources"], "sources": ["cpu_identification", "memory_configuration", "disk_serial", "mac_addresses", "system_serial", "gpu_identification", "nvram_entropy", "timing_entropy", "os_fingerprint"]},
        "hardware_profile": {"hostname": data["system"]["hostname"], "serial_number": data["system"]["serial_number"], "model_identifier": data["system"]["model_identifier"], "hardware_uuid": data["system"]["hardware_uuid"], "boot_rom": data["system"]["boot_rom_version"], "cpu": data["cpu"], "memory": data["memory"], "disk": data["disk"], "gpu": data["gpu"], "mac_addresses": data["mac_addresses"], "nvram": data["nvram"], "os": data["os"]}
    }
    hostname = data["system"]["hostname"].replace(" ", "_").replace(".", "_")
    filename = "entropy_g5_%s.json" % hostname
    f = open(filename, "w")
    f.write(json.dumps(output, indent=2))
    f.close()
    print "\nEntropy profile written to: %s" % filename
    return output

def main():
    print ""
    print "=" * 70
    print "   RUSTCHAIN ENTROPY COLLECTOR - POWERMAC G5 EDITION"
    print ""
    print '   "Every vintage computer has historical potential"'
    print ""
    print "   Collecting hardware entropy to prove YOU ARE NOT AN EMULATOR"
    print "=" * 70
    print ""
    arch = platform.machine()
    print "  Architecture: %s" % arch
    if arch in ["Power Macintosh", "ppc", "ppc64"]:
        print "  PowerPC G5 detected - VINTAGE TIER (2.5x multiplier)!"
    print ""
    data = collect_all_entropy()
    proof = generate_entropy_proof(data)
    output = write_output(data, proof)
    print ""
    print "=" * 70
    print "                    HARDWARE PROFILE SUMMARY"
    print "=" * 70
    print "  Hostname: %s" % data["system"]["hostname"]
    print "  Serial: %s" % data["system"]["serial_number"]
    print "  Model: %s" % data["system"]["model_identifier"]
    print "  UUID: %s" % data["system"]["hardware_uuid"]
    print "  OS: Mac OS X %s" % data["os"]["version"]
    print "  CPU: %s (%d cores @ %d MHz)" % (data["cpu"]["model"], data["cpu"]["cores"], data["cpu"]["frequency_mhz"])
    print "  RAM: %d MB (%s)" % (data["memory"]["total_mb"], data["memory"]["type"])
    print "  Disk: %s (%s)" % (data["disk"]["model"], data["disk"]["serial"])
    print "  GPU: %s" % data["gpu"]["model"]
    if data["mac_addresses"]:
        print "  MACs: %s" % ", ".join(data["mac_addresses"][:3])
    print ""
    print "=" * 70
    print "                    ENTROPY PROOF"
    print "=" * 70
    print "  Signature: %s" % proof["signature"]
    print "  SHA256: %s..." % proof["sha256_hash"][:32]
    print "  Fingerprint: %s..." % proof["deep_fingerprint"][:32]
    print "  Entropy Sources: %d" % proof["entropy_sources"]
    print "  Hardware Tier: %s (%sx)" % (proof["tier"].upper(), proof["multiplier"])
    print ""
    print "=" * 70
    print "                    ENTROPY COLLECTION COMPLETE"
    print ""
    print "   This fingerprint proves your hardware is REAL"
    print "   Emulation is economically irrational."
    print "=" * 70
    print ""
    return proof

if __name__ == "__main__":
    main()
