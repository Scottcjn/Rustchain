#!/usr/bin/env python3
"""
RustChain Universal Miner v3.0 - With Hardware Fingerprint Attestation
=======================================================================
All 6 fingerprint checks must pass for RTC antiquity multiplier rewards.

Checks:
1. Clock-Skew & Oscillator Drift
2. Cache Timing Fingerprint (L1/L2/L3)
3. SIMD Unit Identity
4. Thermal Drift Entropy
5. Instruction Path Jitter
6. Anti-Emulation Behavioral Checks
"""
import os
import sys
import json
import time
import hashlib
import platform
import requests
import statistics
import subprocess
from datetime import datetime
from typing import Dict, Tuple

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "http://50.28.86.131:8088")
BLOCK_TIME = 600
LOTTERY_CHECK_INTERVAL = 10

# ============================================================================
# FINGERPRINT CHECKS - All 6 must pass for antiquity multiplier
# ============================================================================

def check_clock_drift(samples: int = 100) -> Tuple[bool, Dict]:
    """Check 1: Clock-Skew & Oscillator Drift"""
    intervals = []
    for i in range(samples):
        data = "drift_{}".format(i).encode()
        start = time.perf_counter_ns()
        for _ in range(3000):
            hashlib.sha256(data).digest()
        elapsed = time.perf_counter_ns() - start
        intervals.append(elapsed)
        if i % 25 == 0:
            time.sleep(0.001)

    mean_ns = statistics.mean(intervals)
    stdev_ns = statistics.stdev(intervals) if len(intervals) > 1 else 0
    cv = stdev_ns / mean_ns if mean_ns > 0 else 0
    drift_pairs = [intervals[i] - intervals[i-1] for i in range(1, len(intervals))]
    drift_stdev = statistics.stdev(drift_pairs) if len(drift_pairs) > 1 else 0

    data = {"mean_ns": int(mean_ns), "cv": round(cv, 6), "drift_stdev": int(drift_stdev)}
    valid = cv >= 0.0001 and drift_stdev > 0
    if not valid:
        data["fail"] = "synthetic"
    return valid, data

def check_cache_timing(iterations: int = 50) -> Tuple[bool, Dict]:
    """Check 2: Cache Timing Fingerprint"""
    def measure_access(buf_size, accesses=500):
        buf = bytearray(buf_size)
        for i in range(0, buf_size, 64):
            buf[i] = i % 256
        start = time.perf_counter_ns()
        for i in range(accesses):
            _ = buf[(i * 64) % buf_size]
        return (time.perf_counter_ns() - start) / accesses

    l1 = [measure_access(8*1024) for _ in range(iterations)]
    l2 = [measure_access(128*1024) for _ in range(iterations)]
    l3 = [measure_access(4*1024*1024) for _ in range(iterations)]

    l1_avg, l2_avg, l3_avg = statistics.mean(l1), statistics.mean(l2), statistics.mean(l3)
    data = {"l1_ns": round(l1_avg,2), "l2_ns": round(l2_avg,2), "l3_ns": round(l3_avg,2)}

    # Valid if we can measure any cache hierarchy
    valid = l1_avg > 0 and l2_avg > 0 and l3_avg > 0
    return valid, data

def check_simd_identity() -> Tuple[bool, Dict]:
    """Check 3: SIMD Unit Identity"""
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

    if not flags:
        try:
            result = subprocess.run(["sysctl", "-a"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split("\n"):
                if "feature" in line.lower() or "altivec" in line.lower():
                    flags.append(line.split(":")[-1].strip())
        except:
            pass

    has_sse = any("sse" in f.lower() for f in flags)
    has_avx = any("avx" in f.lower() for f in flags)
    has_altivec = any("altivec" in f.lower() for f in flags) or "ppc" in arch or "power" in arch
    has_neon = any("neon" in f.lower() for f in flags) or "arm" in arch

    data = {"arch": arch, "flags": len(flags), "sse": has_sse, "avx": has_avx, "altivec": has_altivec, "neon": has_neon}
    valid = has_sse or has_avx or has_altivec or has_neon or len(flags) > 0
    return valid, data

def check_thermal_drift(samples: int = 25) -> Tuple[bool, Dict]:
    """Check 4: Thermal Drift Entropy"""
    cold = []
    for i in range(samples):
        start = time.perf_counter_ns()
        for _ in range(5000):
            hashlib.sha256("cold_{}".format(i).encode()).digest()
        cold.append(time.perf_counter_ns() - start)

    # Warmup
    for _ in range(50):
        for __ in range(20000):
            hashlib.sha256(b"warm").digest()

    hot = []
    for i in range(samples):
        start = time.perf_counter_ns()
        for _ in range(5000):
            hashlib.sha256("hot_{}".format(i).encode()).digest()
        hot.append(time.perf_counter_ns() - start)

    cold_stdev = statistics.stdev(cold) if len(cold) > 1 else 0
    hot_stdev = statistics.stdev(hot) if len(hot) > 1 else 0

    data = {"cold_avg": int(statistics.mean(cold)), "hot_avg": int(statistics.mean(hot)),
            "cold_stdev": int(cold_stdev), "hot_stdev": int(hot_stdev)}
    valid = cold_stdev > 0 or hot_stdev > 0
    return valid, data

def check_instruction_jitter(samples: int = 50) -> Tuple[bool, Dict]:
    """Check 5: Instruction Path Jitter"""
    def int_ops():
        start = time.perf_counter_ns()
        x = 1
        for i in range(5000):
            x = (x * 7 + 13) % 65537
        return time.perf_counter_ns() - start

    def fp_ops():
        start = time.perf_counter_ns()
        x = 1.5
        for i in range(5000):
            x = (x * 1.414 + 0.5) % 1000.0
        return time.perf_counter_ns() - start

    int_times = [int_ops() for _ in range(samples)]
    fp_times = [fp_ops() for _ in range(samples)]

    int_stdev = statistics.stdev(int_times) if len(int_times) > 1 else 0
    fp_stdev = statistics.stdev(fp_times) if len(fp_times) > 1 else 0

    data = {"int_stdev": int(int_stdev), "fp_stdev": int(fp_stdev)}
    valid = int_stdev > 0 or fp_stdev > 0
    return valid, data

def check_anti_emulation() -> Tuple[bool, Dict]:
    """Check 6: Anti-Emulation Behavioral Checks"""
    vm_indicators = []

    vm_paths = ["/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor", "/proc/scsi/scsi"]
    vm_strings = ["vmware", "virtualbox", "kvm", "qemu", "xen", "hyperv", "parallels"]

    for path in vm_paths:
        try:
            with open(path, "r") as f:
                content = f.read().lower()
                for vm in vm_strings:
                    if vm in content:
                        vm_indicators.append("{}:{}".format(path.split("/")[-1], vm))
        except:
            pass

    for key in ["KUBERNETES", "DOCKER", "VIRTUAL", "container"]:
        if key in os.environ:
            vm_indicators.append("ENV:{}".format(key))

    try:
        with open("/proc/cpuinfo", "r") as f:
            if "hypervisor" in f.read().lower():
                vm_indicators.append("hypervisor_flag")
    except:
        pass

    data = {"vm_indicators": vm_indicators, "is_vm": len(vm_indicators) > 0}
    valid = len(vm_indicators) == 0
    return valid, data

def collect_all_fingerprints() -> Tuple[bool, Dict]:
    """Run all 6 fingerprint checks. Returns (all_passed, results)"""
    results = {}
    all_passed = True

    checks = [
        ("clock_drift", check_clock_drift),
        ("cache_timing", check_cache_timing),
        ("simd_identity", check_simd_identity),
        ("thermal_drift", check_thermal_drift),
        ("instruction_jitter", check_instruction_jitter),
        ("anti_emulation", check_anti_emulation),
    ]

    for key, func in checks:
        try:
            passed, data = func()
        except Exception as e:
            passed = False
            data = {"error": str(e)}
        results[key] = {"passed": passed, "data": data}
        if not passed:
            all_passed = False

    return all_passed, results

# ============================================================================
# MINER CLASS
# ============================================================================

class UniversalMiner:
    def __init__(self, miner_id="universal-miner", wallet=None):
        self.node_url = NODE_URL
        self.miner_id = miner_id
        self.wallet = wallet or "rtc_{}_{}_RTC".format(miner_id, hashlib.sha256(str(time.time()).encode()).hexdigest()[:32])
        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.fingerprint_passed = False
        self.fingerprint_data = {}

        # Detect hardware
        self.hw_info = self._detect_hardware()

        print("=" * 70)
        print("RustChain Universal Miner v3.0 - Hardware Fingerprint Attestation")
        print("=" * 70)
        print("Miner ID: {}".format(self.miner_id))
        print("Wallet: {}".format(self.wallet))
        print("Hardware: {} / {}".format(self.hw_info["arch"], self.hw_info["family"]))
        print("=" * 70)

    def _detect_hardware(self) -> Dict:
        """Auto-detect hardware profile"""
        arch = platform.machine().lower()
        system = platform.system()
        processor = platform.processor() or "unknown"

        if "ppc" in arch or "power" in arch:
            family = "PowerPC"
            if "g4" in processor.lower() or "7447" in processor or "7455" in processor:
                arch_type = "G4"
            elif "g5" in processor.lower() or "970" in processor:
                arch_type = "G5"
            else:
                arch_type = "PowerPC"
        elif "arm" in arch or "aarch64" in arch:
            family = "ARM"
            arch_type = arch
        else:
            family = "x86"
            arch_type = arch

        return {
            "family": family,
            "arch": arch_type,
            "model": processor,
            "cpu": processor,
            "cores": os.cpu_count() or 1,
            "system": system,
            "hostname": platform.node(),
        }

    def attest(self) -> bool:
        """Complete hardware attestation with fingerprint checks"""
        print("\n[{}] Running hardware fingerprint attestation...".format(
            datetime.now().strftime('%H:%M:%S')))

        # Run all 6 fingerprint checks
        print("  Collecting fingerprints (6 checks)...")
        self.fingerprint_passed, self.fingerprint_data = collect_all_fingerprints()

        passed_count = sum(1 for v in self.fingerprint_data.values() if v.get("passed"))
        print("  Fingerprint result: {}/6 checks passed".format(passed_count))

        if not self.fingerprint_passed:
            failed = [k for k, v in self.fingerprint_data.items() if not v.get("passed")]
            print("  Failed checks: {}".format(failed))
            print("  (Will receive base 1.0x multiplier, no antiquity bonus)")
        else:
            print("  All checks passed! Eligible for antiquity multiplier")

        try:
            # Get challenge
            resp = requests.post("{}/attest/challenge".format(self.node_url), json={}, timeout=10)
            if resp.status_code != 200:
                print("  Challenge failed: {}".format(resp.status_code))
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce")

            # Build attestation with fingerprint data
            attestation = {
                "miner": self.wallet,
                "miner_id": self.miner_id,
                "nonce": nonce,
                "report": {
                    "nonce": nonce,
                    "commitment": hashlib.sha256("{}{}".format(nonce, self.wallet).encode()).hexdigest()
                },
                "device": {
                    "family": self.hw_info["family"],
                    "arch": self.hw_info["arch"],
                    "model": self.hw_info["model"],
                    "cpu": self.hw_info["cpu"],
                    "cores": self.hw_info["cores"],
                },
                "signals": {
                    "hostname": self.hw_info["hostname"],
                    "system": self.hw_info["system"],
                },
                # NEW: Include fingerprint validation results
                "fingerprint": {
                    "all_passed": self.fingerprint_passed,
                    "checks": {k: v.get("passed", False) for k, v in self.fingerprint_data.items()},
                    "data": self.fingerprint_data,
                }
            }

            resp = requests.post("{}/attest/submit".format(self.node_url),
                               json=attestation, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.attestation_valid_until = time.time() + 580
                    print("  Attestation accepted!")
                    return True
                else:
                    print("  Rejected: {}".format(result))
            else:
                print("  HTTP {}: {}".format(resp.status_code, resp.text[:200]))

        except Exception as e:
            print("  Error: {}".format(e))

        return False

    def enroll(self) -> bool:
        """Enroll in current epoch"""
        if time.time() >= self.attestation_valid_until:
            print("  Attestation expired, re-attesting...")
            if not self.attest():
                return False

        print("\n[{}] Enrolling in epoch...".format(datetime.now().strftime('%H:%M:%S')))

        payload = {
            "miner_pubkey": self.wallet,
            "miner_id": self.miner_id,
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            },
            "fingerprint_passed": self.fingerprint_passed,
        }

        try:
            resp = requests.post("{}/epoch/enroll".format(self.node_url),
                                json=payload, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    weight = result.get('weight', 1.0)
                    print("  Enrolled! Epoch: {} Weight: {}x".format(
                        result.get('epoch'), weight))
                    if not self.fingerprint_passed and weight > 1.0:
                        print("  WARNING: Got multiplier without fingerprint!")
                    return True
                else:
                    print("  Failed: {}".format(result))
            else:
                print("  HTTP {}: {}".format(resp.status_code, resp.text[:200]))

        except Exception as e:
            print("  Error: {}".format(e))

        return False

    def check_lottery(self) -> Tuple[bool, Dict]:
        """Check lottery eligibility"""
        try:
            resp = requests.get(
                "{}/lottery/eligibility".format(self.node_url),
                params={"miner_id": self.miner_id},
                timeout=5
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("eligible", False), result
        except:
            pass
        return False, {}

    def submit_header(self, slot: int) -> bool:
        """Submit block header"""
        message = "{}{}{}".format(slot, self.miner_id, time.time())
        message_hash = hashlib.sha256(message.encode()).hexdigest()

        header = {
            "miner_id": self.miner_id,
            "slot": slot,
            "message": message_hash,
            "signature": "0" * 128,
            "pubkey": self.wallet[:64],
        }

        try:
            resp = requests.post(
                "{}/headers/ingest_signed".format(self.node_url),
                json=header, timeout=10
            )
            self.shares_submitted += 1

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.shares_accepted += 1
                    print("  Header accepted! ({}/{})".format(
                        self.shares_accepted, self.shares_submitted))
                    return True
        except Exception as e:
            print("  Submit error: {}".format(e))

        return False

    def check_balance(self) -> float:
        """Check RTC balance"""
        try:
            resp = requests.get("{}/balance/{}".format(self.node_url, self.wallet), timeout=10)
            if resp.status_code == 200:
                balance = resp.json().get('balance_rtc', 0)
                print("\nBalance: {} RTC".format(balance))
                return balance
        except:
            pass
        return 0

    def mine(self):
        """Main mining loop"""
        print("\nStarting mining loop...")

        if not self.enroll():
            print("Initial enrollment failed!")
            return

        last_balance_check = 0
        last_enroll = time.time()

        try:
            while True:
                # Re-enroll every hour
                if time.time() - last_enroll > 3600:
                    print("\nRe-enrolling...")
                    self.enroll()
                    last_enroll = time.time()

                # Check lottery
                eligible, info = self.check_lottery()
                if eligible:
                    slot = info.get("slot", 0)
                    print("\nLOTTERY WIN! Slot {}".format(slot))
                    self.submit_header(slot)

                # Balance check every 5 minutes
                if time.time() - last_balance_check > 300:
                    self.check_balance()
                    last_balance_check = time.time()

                time.sleep(LOTTERY_CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nMining stopped")
            print("Wallet: {}".format(self.wallet))
            print("Headers: {}/{}".format(self.shares_accepted, self.shares_submitted))
            self.check_balance()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RustChain Universal Miner v3.0")
    parser.add_argument("--miner-id", default="universal-miner", help="Miner ID")
    parser.add_argument("--wallet", help="Wallet address")
    parser.add_argument("--test-fingerprint", action="store_true", help="Test fingerprints only")
    args = parser.parse_args()

    if args.test_fingerprint:
        print("Testing fingerprint checks...")
        passed, results = collect_all_fingerprints()
        print("\nResults:")
        for k, v in results.items():
            status = "PASS" if v.get("passed") else "FAIL"
            print("  {}: {}".format(k, status))
        print("\nOverall: {}".format("PASSED" if passed else "FAILED"))
        print("\nDetailed:")
        print(json.dumps(results, indent=2, default=str))
        return

    miner = UniversalMiner(miner_id=args.miner_id, wallet=args.wallet)
    miner.mine()

if __name__ == "__main__":
    main()
