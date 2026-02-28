#!/usr/bin/env python3
"""
RustChain Mac Universal Miner v2.4.0
Supports: Apple Silicon (M1/M2/M3), Intel Mac, PowerPC (G4/G5)
With RIP-PoA Hardware Fingerprint Attestation + Serial Binding v2.0
"""
import warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

import os
import sys
import json
import time
import hashlib
import platform
import subprocess
import requests
import statistics
import re
from datetime import datetime

# Import fingerprint checks
try:
    from fingerprint_checks import validate_all_checks
    FINGERPRINT_AVAILABLE = True
except ImportError:
    FINGERPRINT_AVAILABLE = False
    print(warning("[WARN] fingerprint_checks.py not found - fingerprint attestation disabled"))

# Import CPU architecture detection
try:
    from cpu_architecture_detection import detect_cpu_architecture, calculate_antiquity_multiplier
    CPU_DETECTION_AVAILABLE = True
except ImportError:
    CPU_DETECTION_AVAILABLE = False
    print(info("[INFO] cpu_architecture_detection.py not found - using basic detection"))

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
BLOCK_TIME = 600  # 10 minutes
LOTTERY_CHECK_INTERVAL = 10  # Check every 10 seconds

def get_mac_serial():
    """Get hardware serial number for macOS systems"""
    try:
        # Method 1: system_profiler
        result = subprocess.run(
            ['system_profiler', 'SPHardwareDataType'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'Serial Number' in line:
                return line.split(':')[1].strip()
    except:
        pass

    try:
        # Method 2: ioreg
        result = subprocess.run(
            ['ioreg', '-l'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'IOPlatformSerialNumber' in line:
                return line.split('"')[-2]
    except:
        pass

    try:
        # Method 3: Hardware UUID fallback
        result = subprocess.run(
            ['system_profiler', 'SPHardwareDataType'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'Hardware UUID' in line:
                return line.split(':')[1].strip()[:16]
    except:
        pass

    return None


def detect_hardware():
    """Auto-detect Mac hardware architecture"""
    machine = platform.machine().lower()
    system = platform.system().lower()

    hw_info = {
        "family": "unknown",
        "arch": "unknown",
        "model": "Mac",
        "cpu": "unknown",
        "cores": os.cpu_count() or 1,
        "memory_gb": 4,
        "hostname": platform.node(),
        "mac": "00:00:00:00:00:00",
        "macs": [],
        "serial": get_mac_serial()
    }

    # Get MAC addresses
    try:
        result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
        macs = re.findall(r'ether\s+([0-9a-f:]{17})', result.stdout, re.IGNORECASE)
        hw_info["macs"] = macs if macs else ["00:00:00:00:00:00"]
        hw_info["mac"] = macs[0] if macs else "00:00:00:00:00:00"
    except:
        pass

    # Get memory
    try:
        result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                               capture_output=True, text=True, timeout=5)
        hw_info["memory_gb"] = int(result.stdout.strip()) // (1024**3)
    except:
        pass

    # Apple Silicon Detection (M1/M2/M3)
    if machine == 'arm64':
        hw_info["family"] = "Apple Silicon"
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                   capture_output=True, text=True, timeout=5)
            brand = result.stdout.strip()
            hw_info["cpu"] = brand

            if 'M3' in brand:
                hw_info["arch"] = "M3"
            elif 'M2' in brand:
                hw_info["arch"] = "M2"
            elif 'M1' in brand:
                hw_info["arch"] = "M1"
            else:
                hw_info["arch"] = "apple_silicon"
        except:
            hw_info["arch"] = "apple_silicon"
            hw_info["cpu"] = "Apple Silicon"

    # Intel Mac Detection
    elif machine == 'x86_64':
        hw_info["family"] = "x86_64"
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                   capture_output=True, text=True, timeout=5)
            cpu_brand = result.stdout.strip()
            hw_info["cpu"] = cpu_brand

            # Use comprehensive CPU detection if available
            if CPU_DETECTION_AVAILABLE:
                cpu_info = calculate_antiquity_multiplier(cpu_brand)
                hw_info["arch"] = cpu_info.architecture
                hw_info["cpu_vendor"] = cpu_info.vendor
                hw_info["cpu_year"] = cpu_info.microarch_year
                hw_info["cpu_generation"] = cpu_info.generation
                hw_info["is_server"] = cpu_info.is_server
                print(f"[CPU] Detected: {cpu_info.generation} ({cpu_info.architecture}, {cpu_info.microarch_year})")
            else:
                # Fallback: Basic detection for retro Intel architectures
                cpu_lower = cpu_brand.lower()
                if 'core 2' in cpu_lower or 'core(tm)2' in cpu_lower:
                    hw_info["arch"] = "core2"  # 1.3x
                elif 'xeon' in cpu_lower and ('e5-16' in cpu_lower or 'e5-26' in cpu_lower):
                    hw_info["arch"] = "ivy_bridge"  # Xeon E5 v2 = Ivy Bridge-E
                elif 'i7-3' in cpu_lower or 'i5-3' in cpu_lower or 'i3-3' in cpu_lower:
                    hw_info["arch"] = "ivy_bridge"
                elif 'i7-2' in cpu_lower or 'i5-2' in cpu_lower or 'i3-2' in cpu_lower:
                    hw_info["arch"] = "sandy_bridge"
                elif 'i7-9' in cpu_lower and '900' in cpu_lower:
                    hw_info["arch"] = "nehalem"
                elif 'i7-4' in cpu_lower or 'i5-4' in cpu_lower:
                    hw_info["arch"] = "haswell"
                elif 'pentium' in cpu_lower:
                    hw_info["arch"] = "pentium4"
                else:
                    hw_info["arch"] = "modern"
        except:
            hw_info["arch"] = "modern"
            hw_info["cpu"] = "Intel Mac"

    # PowerPC Detection (for old Macs)
    elif machine in ('ppc', 'ppc64', 'powerpc', 'powerpc64'):
        hw_info["family"] = "PowerPC"
        try:
            result = subprocess.run(['system_profiler', 'SPHardwareDataType'],
                                   capture_output=True, text=True, timeout=10)
            output = result.stdout.lower()

            if 'g5' in output or 'powermac11' in output:
                hw_info["arch"] = "G5"
                hw_info["cpu"] = "PowerPC G5"
            elif 'g4' in output or 'powermac3' in output or 'powerbook' in output:
                hw_info["arch"] = "G4"
                hw_info["cpu"] = "PowerPC G4"
            elif 'g3' in output:
                hw_info["arch"] = "G3"
                hw_info["cpu"] = "PowerPC G3"
            else:
                hw_info["arch"] = "G4"
                hw_info["cpu"] = "PowerPC"
        except:
            hw_info["arch"] = "G4"
            hw_info["cpu"] = "PowerPC G4"

    # Get model name
    try:
        result = subprocess.run(['system_profiler', 'SPHardwareDataType'],
                               capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            if 'Model Name' in line or 'Model Identifier' in line:
                hw_info["model"] = line.split(':')[1].strip()
                break
    except:
        pass

    return hw_info


def collect_entropy(cycles=48, inner_loop=25000):
    """Collect timing entropy for hardware attestation"""
    samples = []
    for _ in range(cycles):
        start = time.perf_counter_ns()
        acc = 0
        for j in range(inner_loop):
            acc ^= (j * 31) & 0xFFFFFFFF
        duration = time.perf_counter_ns() - start
        samples.append(duration)

    mean_ns = sum(samples) / len(samples)
    variance_ns = statistics.pvariance(samples) if len(samples) > 1 else 0.0

    return {
        "mean_ns": mean_ns,
        "variance_ns": variance_ns,
        "min_ns": min(samples),
        "max_ns": max(samples),
        "sample_count": len(samples),
        "samples_preview": samples[:12],
    }


class MacMiner:
    def __init__(self, miner_id=None, wallet=None):
        self.node_url = NODE_URL
        self.hw_info = detect_hardware()
        self.fingerprint_data = {}
        self.fingerprint_passed = False

        # Generate miner_id from hardware
        if miner_id:
            self.miner_id = miner_id
        else:
            hw_hash = hashlib.sha256(
                f"{self.hw_info['hostname']}-{self.hw_info['serial'] or 'unknown'}".encode()
            ).hexdigest()[:8]
            arch = self.hw_info['arch'].lower().replace(' ', '_')
            self.miner_id = f"{arch}-{self.hw_info['hostname'][:10]}-{hw_hash}"

        # Generate wallet address
        if wallet:
            self.wallet = wallet
        else:
            wallet_hash = hashlib.sha256(f"{self.miner_id}-rustchain".encode()).hexdigest()[:38]
            self.wallet = f"{self.hw_info['family'].lower().replace(' ', '_')}_{wallet_hash}RTC"

        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.last_entropy = {}

        self._print_banner()

        # Run initial fingerprint check
        if FINGERPRINT_AVAILABLE:
            self._run_fingerprint_checks()

    def _run_fingerprint_checks(self):
        """Run hardware fingerprint checks for RIP-PoA"""
        print(info("\n[FINGERPRINT] Running hardware fingerprint checks..."))
        try:
            passed, results = validate_all_checks()
            self.fingerprint_passed = passed
            self.fingerprint_data = {"checks": results, "all_passed": passed}
            if passed:
                print(success("[FINGERPRINT] All checks PASSED - eligible for full rewards"))
            else:
                failed = [k for k, v in results.items() if not v.get("passed")]
                print(warning(f"[FINGERPRINT] FAILED checks: {failed}"))
                print(warning("[FINGERPRINT] WARNING: May receive reduced/zero rewards"))
        except Exception as e:
            print(error(f"[FINGERPRINT] Error running checks: {e}"))
            self.fingerprint_passed = False
            self.fingerprint_data = {"error": str(e), "all_passed": False}

    def _print_banner(self):
        print("=" * 70)
        print("RustChain Mac Miner v2.4.0 - Serial Binding + Fingerprint")
        print("=" * 70)
        print(f"Miner ID:    {self.miner_id}")
        print(f"Wallet:      {self.wallet}")
        print(f"Node:        {self.node_url}")
        print(f"Serial:      {self.hw_info.get('serial', 'N/A')}")
        print("-" * 70)
        print(f"Hardware:    {self.hw_info['family']} / {self.hw_info['arch']}")
        print(f"Model:       {self.hw_info['model']}")
        print(f"CPU:         {self.hw_info['cpu']}")
        print(f"Cores:       {self.hw_info['cores']}")
        print(f"Memory:      {self.hw_info['memory_gb']} GB")
        print("-" * 70)
        weight = self._get_expected_weight()
        print(f"Expected Weight: {weight}x (Proof of Antiquity)")
        print("=" * 70)

    def _get_expected_weight(self):
        """Calculate expected PoA weight"""
        arch = self.hw_info['arch'].lower()
        family = self.hw_info['family'].lower()

        if family == 'powerpc':
            if arch == 'g3': return 3.0
            if arch == 'g4': return 2.5
            if arch == 'g5': return 2.0
        elif 'apple' in family or 'silicon' in family:
            if arch in ('m1', 'm2', 'm3', 'apple_silicon'): return 1.2
        elif family == 'x86_64':
            if arch == 'core2': return 1.5
            return 1.0

        return 1.0

    def attest(self):
        """Complete hardware attestation with fingerprint"""
        print(info(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attesting hardware..."))

        try:
            # Step 1: Get challenge
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=15, verify=False)
            if resp.status_code != 200:
                print(error(f"  ERROR: Challenge failed ({resp.status_code})"))
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce", "")
            print(success(f"  Got challenge nonce: {nonce[:16]}..."))

        except Exception as e:
            print(error(f"  ERROR: Challenge error: {e}"))
            return False

        # Collect entropy
        entropy = collect_entropy()
        self.last_entropy = entropy

        # Re-run fingerprint checks if needed
        if FINGERPRINT_AVAILABLE and not self.fingerprint_data:
            self._run_fingerprint_checks()

        # Build attestation payload
        commitment = hashlib.sha256(
            (nonce + self.wallet + json.dumps(entropy, sort_keys=True)).encode()
        ).hexdigest()

        attestation = {
            "miner": self.wallet,
            "miner_id": self.miner_id,
            "nonce": nonce,
            "report": {
                "nonce": nonce,
                "commitment": commitment,
                "derived": entropy,
                "entropy_score": entropy.get("variance_ns", 0.0)
            },
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"],
                "model": self.hw_info["model"],
                "cpu": self.hw_info["cpu"],
                "cores": self.hw_info["cores"],
                "memory_gb": self.hw_info["memory_gb"],
                "serial": self.hw_info.get("serial")  # Hardware serial for v2 binding
            },
            "signals": {
                "macs": self.hw_info.get("macs", [self.hw_info["mac"]]),
                "hostname": self.hw_info["hostname"]
            },
            # RIP-PoA hardware fingerprint attestation
            "fingerprint": self.fingerprint_data
        }

        try:
            resp = requests.post(f"{self.node_url}/attest/submit",
                               json=attestation, timeout=30, verify=False)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.attestation_valid_until = time.time() + 580
                    print(success(f"  SUCCESS: Attestation accepted!"))

                    # Show fingerprint status
                    if self.fingerprint_passed:
                        print(success(f"  Fingerprint: PASSED"))
                    else:
                        print(warning(f"  Fingerprint: FAILED (reduced rewards)"))
                    return True
                else:
                    print(warning(f"  WARNING: {result}"))
                    return False
            else:
                print(error(f"  ERROR: HTTP {resp.status_code}: {resp.text[:200]}"))
                return False

        except Exception as e:
            print(error(f"  ERROR: {e}"))
            return False

    def check_eligibility(self):
        """Check lottery eligibility"""
        try:
            resp = requests.get(
                f"{self.node_url}/lottery/eligibility",
                params={"miner_id": self.miner_id},
                timeout=10,
                verify=False
            )
            if resp.status_code == 200:
                return resp.json()
            return {"eligible": False, "reason": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"eligible": False, "reason": str(e)}

    def submit_header(self, slot):
        """Submit header for slot"""
        try:
            message = f"slot:{slot}:miner:{self.miner_id}:ts:{int(time.time())}"
            message_hex = message.encode().hex()
            sig_data = hashlib.sha512(f"{message}{self.wallet}".encode()).hexdigest()

            header_payload = {
                "miner_id": self.miner_id,
                "header": {
                    "slot": slot,
                    "miner": self.miner_id,
                    "timestamp": int(time.time())
                },
                "message": message_hex,
                "signature": sig_data,
                "pubkey": self.wallet
            }

            resp = requests.post(
                f"{self.node_url}/headers/ingest_signed",
                json=header_payload,
                timeout=15,
                verify=False
            )

            self.shares_submitted += 1

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.shares_accepted += 1
                    return True, result
                return False, result
            return False, {"error": f"HTTP {resp.status_code}"}

        except Exception as e:
            return False, {"error": str(e)}

    def run(self):
        """Main mining loop"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting miner...")

        # Initial attestation
        while not self.attest():
            print("  Retrying attestation in 30 seconds...")
            time.sleep(30)

        last_slot = 0

        while True:
            try:
                # Re-attest if needed
                if time.time() > self.attestation_valid_until:
                    self.attest()

                # Check eligibility
                eligibility = self.check_eligibility()
                slot = eligibility.get("slot", 0)

                if eligibility.get("eligible"):
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ELIGIBLE for slot {slot}!")

                    if slot != last_slot:
                        success, result = self.submit_header(slot)
                        if success:
                            print(f"  Header ACCEPTED! Slot {slot}")
                        else:
                            print(f"  Header rejected: {result}")
                        last_slot = slot
                else:
                    reason = eligibility.get("reason", "unknown")
                    if reason == "not_attested":
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Not attested - re-attesting...")
                        self.attest()

                # Status every 60 seconds
                if int(time.time()) % 60 == 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} | "
                          f"Submitted: {self.shares_submitted} | "
                          f"Accepted: {self.shares_accepted}")

                time.sleep(LOTTERY_CHECK_INTERVAL)

            except KeyboardInterrupt:
                print("\n\nShutting down miner...")
                break
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Mac Miner v2.4.0")
    parser.add_argument("--version", "-v", action="version", version="clawrtc 1.5.0")
    parser.add_argument("--miner-id", "-m", help="Custom miner ID")
    parser.add_argument("--wallet", "-w", help="Custom wallet address")
    parser.add_argument("--node", "-n", default=NODE_URL, help="Node URL")
    args = parser.parse_args()

    if args.node:
        NODE_URL = args.node

    miner = MacMiner(miner_id=args.miner_id, wallet=args.wallet)
    miner.run()
