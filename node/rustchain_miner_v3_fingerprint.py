#!/usr/bin/env python3
"""
RustChain Universal Miner v3.0 - With Full Hardware Fingerprinting
===================================================================
Runs all 6 RIP-PoA fingerprint checks to prove real hardware.
Emulators/VMs will FAIL these checks and be denied RTC rewards.
"""
import os, sys, json, time, hashlib, platform, subprocess, statistics, requests
from datetime import datetime
from typing import Dict, Tuple

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "http://50.28.86.131:8088")
ATTESTATION_INTERVAL = 300  # Re-attest every 5 minutes

# ============================================================================
# FINGERPRINT CHECK 1: Clock Drift
# ============================================================================
def check_clock_drift(samples: int = 200) -> Tuple[bool, Dict]:
    """Real CPUs have microscopic oscillator drift - VMs don't"""
    intervals = []
    for i in range(samples):
        data = f"drift_{i}".encode()
        start = time.perf_counter_ns()
        for _ in range(5000):
            hashlib.sha256(data).digest()
        elapsed = time.perf_counter_ns() - start
        intervals.append(elapsed)
        if i % 50 == 0:
            time.sleep(0.001)

    mean_ns = statistics.mean(intervals)
    stdev_ns = statistics.stdev(intervals) if len(intervals) > 1 else 0
    cv = stdev_ns / mean_ns if mean_ns > 0 else 0
    drift_pairs = [intervals[i] - intervals[i-1] for i in range(1, len(intervals))]
    drift_stdev = statistics.stdev(drift_pairs) if len(drift_pairs) > 1 else 0

    data = {"mean_ns": int(mean_ns), "stdev_ns": int(stdev_ns), "cv": round(cv, 6), "drift_stdev": int(drift_stdev)}
    
    valid = True
    if cv < 0.0001:
        valid = False
        data["fail_reason"] = "synthetic_timing"
    elif drift_stdev == 0:
        valid = False
        data["fail_reason"] = "no_drift"
    return valid, data

# ============================================================================
# FINGERPRINT CHECK 2: Cache Timing  
# ============================================================================
def check_cache_timing(iterations: int = 100) -> Tuple[bool, Dict]:
    """Real CPUs have L1/L2/L3 cache latency differences"""
    def measure_access(size: int, accesses: int = 1000) -> float:
        buf = bytearray(size)
        for i in range(0, size, 64):
            buf[i] = i % 256
        start = time.perf_counter_ns()
        for i in range(accesses):
            _ = buf[(i * 64) % size]
        return (time.perf_counter_ns() - start) / accesses

    l1 = [measure_access(8*1024) for _ in range(iterations)]
    l2 = [measure_access(128*1024) for _ in range(iterations)]
    l3 = [measure_access(4*1024*1024) for _ in range(iterations)]

    l1_avg, l2_avg, l3_avg = statistics.mean(l1), statistics.mean(l2), statistics.mean(l3)
    l2_l1_ratio = l2_avg / l1_avg if l1_avg > 0 else 0
    l3_l2_ratio = l3_avg / l2_avg if l2_avg > 0 else 0

    data = {"l1_ns": round(l1_avg, 2), "l2_ns": round(l2_avg, 2), "l3_ns": round(l3_avg, 2),
            "l2_l1_ratio": round(l2_l1_ratio, 3), "l3_l2_ratio": round(l3_l2_ratio, 3)}

    valid = True
    if l2_l1_ratio < 1.01 and l3_l2_ratio < 1.01:
        valid = False
        data["fail_reason"] = "no_cache_hierarchy"
    return valid, data

# ============================================================================
# FINGERPRINT CHECK 3: SIMD Identity
# ============================================================================
def check_simd_identity() -> Tuple[bool, Dict]:
    """Detect SSE/AVX/AltiVec/NEON capabilities"""
    flags = []
    arch = platform.machine().lower()
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "flags" in line.lower() or "features" in line.lower():
                    flags = line.split(":")[1].strip().split() if ":" in line else []
                    break
    except: pass

    data = {"arch": arch, "simd_flags_count": len(flags),
            "has_sse": any("sse" in f.lower() for f in flags),
            "has_avx": any("avx" in f.lower() for f in flags),
            "has_altivec": "ppc" in arch, "has_neon": "arm" in arch}
    
    valid = data["has_sse"] or data["has_avx"] or data["has_altivec"] or data["has_neon"] or len(flags) > 0
    if not valid:
        data["fail_reason"] = "no_simd_detected"
    return valid, data

# ============================================================================
# FINGERPRINT CHECK 4: Thermal Drift
# ============================================================================
def check_thermal_drift(samples: int = 50) -> Tuple[bool, Dict]:
    """Real silicon has thermal variance - emulators don't"""
    cold_times = []
    for i in range(samples):
        start = time.perf_counter_ns()
        for _ in range(10000):
            hashlib.sha256(f"cold_{i}".encode()).digest()
        cold_times.append(time.perf_counter_ns() - start)

    # Warm up CPU
    for _ in range(100):
        for __ in range(50000):
            hashlib.sha256(b"warmup").digest()

    hot_times = []
    for i in range(samples):
        start = time.perf_counter_ns()
        for _ in range(10000):
            hashlib.sha256(f"hot_{i}".encode()).digest()
        hot_times.append(time.perf_counter_ns() - start)

    cold_stdev = statistics.stdev(cold_times) if len(cold_times) > 1 else 0
    hot_stdev = statistics.stdev(hot_times) if len(hot_times) > 1 else 0
    drift_ratio = statistics.mean(hot_times) / statistics.mean(cold_times) if statistics.mean(cold_times) > 0 else 0

    data = {"cold_stdev": int(cold_stdev), "hot_stdev": int(hot_stdev), "drift_ratio": round(drift_ratio, 4)}
    valid = not (cold_stdev == 0 and hot_stdev == 0)
    if not valid:
        data["fail_reason"] = "no_thermal_variance"
    return valid, data

# ============================================================================
# FINGERPRINT CHECK 5: Instruction Jitter
# ============================================================================
def check_instruction_jitter(samples: int = 100) -> Tuple[bool, Dict]:
    """Real CPUs have pipeline jitter - emulators are too uniform"""
    def measure_int(count: int = 10000):
        start = time.perf_counter_ns()
        x = 1
        for i in range(count):
            x = (x * 7 + 13) % 65537
        return time.perf_counter_ns() - start

    def measure_fp(count: int = 10000):
        start = time.perf_counter_ns()
        x = 1.5
        for i in range(count):
            x = (x * 1.414 + 0.5) % 1000.0
        return time.perf_counter_ns() - start

    int_times = [measure_int() for _ in range(samples)]
    fp_times = [measure_fp() for _ in range(samples)]
    int_stdev = statistics.stdev(int_times) if len(int_times) > 1 else 0
    fp_stdev = statistics.stdev(fp_times) if len(fp_times) > 1 else 0

    data = {"int_stdev": int(int_stdev), "fp_stdev": int(fp_stdev)}
    valid = not (int_stdev == 0 and fp_stdev == 0)
    if not valid:
        data["fail_reason"] = "no_jitter"
    return valid, data

# ============================================================================
# FINGERPRINT CHECK 6: Anti-Emulation
# ============================================================================
def check_anti_emulation() -> Tuple[bool, Dict]:
    """Detect VMs, hypervisors, emulators"""
    vm_indicators = []
    vm_strings = ["vmware", "virtualbox", "kvm", "qemu", "xen", "hyperv", "parallels", "bochs"]
    
    # Check DMI/system files
    for path in ["/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor", "/proc/scsi/scsi"]:
        try:
            with open(path, "r") as f:
                content = f.read().lower()
                for vm in vm_strings:
                    if vm in content:
                        vm_indicators.append(f"{path}:{vm}")
        except: pass

    # Check environment
    for key in ["KUBERNETES", "DOCKER", "VIRTUAL", "container"]:
        if key in os.environ:
            vm_indicators.append(f"ENV:{key}")

    # Check cpuinfo for hypervisor flag
    try:
        with open("/proc/cpuinfo", "r") as f:
            if "hypervisor" in f.read().lower():
                vm_indicators.append("cpuinfo:hypervisor")
    except: pass

    data = {"vm_indicators": vm_indicators, "indicator_count": len(vm_indicators)}
    valid = len(vm_indicators) == 0
    if not valid:
        data["fail_reason"] = "vm_detected"
    return valid, data

# ============================================================================
# Run All 6 Checks
# ============================================================================
def run_all_fingerprint_checks() -> Tuple[bool, Dict]:
    """Run all 6 fingerprint checks. ALL MUST PASS."""
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
    
    print("\n[CHECK] Running 6 Hardware Fingerprint Checks...")
    print("=" * 50)
    
    for i, (key, name, func) in enumerate(checks, 1):
        print(f"\n[{i}/6] {name}...")
        try:
            passed, data = func()
        except Exception as e:
            passed = False
            data = {"error": str(e)}
        results[key] = {"passed": passed, "data": data}
        if not passed:
            all_passed = False
        status = "[PASS] PASS" if passed else "[FAIL] FAIL"
        print(f"  Result: {status}")
    
    print("\n" + "=" * 50)
    print(f"OVERALL: {[PASS] ALL CHECKS PASSED if all_passed else [FAIL] FAILED}")
    
    return all_passed, results

# ============================================================================
# Hardware Detection  
# ============================================================================
def detect_hardware() -> Dict:
    """Detect hardware architecture"""
    machine = platform.machine().lower()
    system = platform.system().lower()
    
    hw = {"family": "unknown", "arch": "modern", "cpu": platform.processor() or "unknown",
          "cores": os.cpu_count() or 1, "hostname": platform.node(), "os": system}
    
    if machine in ('ppc', 'ppc64', 'powerpc', 'powerpc64'):
        hw["family"] = "PowerPC"
        try:
            with open('/ proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                if '7450' in cpuinfo or '7447' in cpuinfo or '7455' in cpuinfo:
                    hw["arch"] = "G4"
                elif '970' in cpuinfo:
                    hw["arch"] = "G5"
                elif '750' in cpuinfo:
                    hw["arch"] = "G3"
        except:
            hw["arch"] = "G4"
    elif machine == 'arm64' and system == 'darwin':
        hw["family"] = "ARM"
        hw["arch"] = "apple_silicon"
    elif machine in ('x86_64', 'amd64'):
        hw["family"] = "x86_64"
        hw["arch"] = "modern"
    
    return hw

# ============================================================================
# Main Miner
# ============================================================================
class FingerprintMiner:
    def __init__(self, miner_id: str = None):
        self.node_url = NODE_URL
        self.miner_id = miner_id or f"{platform.node()}-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
        self.hw_info = detect_hardware()
        self.fingerprint_passed = False
        self.fingerprint_results = {}
        
        print("=" * 70)
        print("RustChain Miner v3.0 - Hardware Fingerprint Attestation")
        print("=" * 70)
        print(f"Miner ID: {self.miner_id}")
        print(f"Node: {self.node_url}")
        print(f"Hardware: {self.hw_info['family']} / {self.hw_info['arch']}")
        print("=" * 70)
    
    def collect_fingerprints(self):
        """Run all 6 fingerprint checks"""
        self.fingerprint_passed, self.fingerprint_results = run_all_fingerprint_checks()
        return self.fingerprint_passed
    
    def submit_attestation(self):
        """Submit attestation with fingerprint data"""
        payload = {
            "miner_id": self.miner_id,
            "device_family": self.hw_info["family"],
            "device_arch": self.hw_info["arch"],
            "fingerprint": {
                "all_passed": self.fingerprint_passed,
                "checks": self.fingerprint_results
            }
        }
        
        try:
            resp = requests.post(f"{self.node_url}/attest/submit", json=payload, timeout=30)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def run(self):
        """Main mining loop"""
        while True:
            print(f"\n[{datetime.now().isoformat()}] Starting attestation cycle...")
            
            # Run fingerprint checks
            if self.collect_fingerprints():
                print("[PASS] Hardware verified - submitting attestation...")
                result = self.submit_attestation()
                print(f"  Server response: {result}")
            else:
                print("[FAIL] Fingerprint checks FAILED - may be emulator/VM!")
                print("  Your hardware may not qualify for RTC rewards.")
            
            # Wait for next attestation
            print(f"\n[WAIT] Next attestation in {ATTESTATION_INTERVAL} seconds...")
            time.sleep(ATTESTATION_INTERVAL)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RustChain Miner v3.0 with Hardware Fingerprinting")
    parser.add_argument("--miner-id", "-m", help="Miner ID")
    parser.add_argument("--node", "-n", default=NODE_URL, help="RIP node URL")
    parser.add_argument("--test-only", action="store_true", help="Just run fingerprint tests, don't mine")
    args = parser.parse_args()
    
    if args.node:
        NODE_URL = args.node
    
    if args.test_only:
        passed, results = run_all_fingerprint_checks()
        print("\n\nDetailed Results:")
        print(json.dumps(results, indent=2, default=str))
        sys.exit(0 if passed else 1)
    else:
        miner = FingerprintMiner(args.miner_id)
        miner.run()
