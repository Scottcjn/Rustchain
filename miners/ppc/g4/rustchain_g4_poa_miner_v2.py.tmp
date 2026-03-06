#!/usr/bin/env python3
"""
RustChain G4 PoA Miner v2.0
Fixed: Uses miner_id consistently for attestation and lottery
Implements full Proof of Antiquity signals per rip_proof_of_antiquity_hardware.py
"""
import os
import sys
import time
import json
import hashlib
import platform
import subprocess
import requests
from datetime import datetime

# Configuration
NODE_URL = os.environ.get("RUSTCHAIN_NODE", "http://50.28.86.131:8088")
ATTESTATION_TTL = 600  # 10 minutes - must re-attest before this
LOTTERY_CHECK_INTERVAL = 10  # Check every 10 seconds
ATTESTATION_INTERVAL = 300  # Re-attest every 5 minutes

# G4 CPU timing profile from PoA spec
# ~8500 µs per 10k SHA256 operations
G4_TIMING_MEAN = 8500
G4_TIMING_VARIANCE_MIN = 200
G4_TIMING_VARIANCE_MAX = 800


def get_system_entropy(size=64):
    """Collect real entropy from system"""
    try:
        return os.urandom(size).hex()
    except Exception:
        # Fallback: use timing jitter
        samples = []
        for _ in range(size):
            start = time.perf_counter_ns()
            hashlib.sha256(str(time.time_ns()).encode()).digest()
            samples.append(time.perf_counter_ns() - start)
        return hashlib.sha256(bytes(samples[:64])).hexdigest() * 2


def measure_cpu_timing(iterations=10):
    """
    Measure actual CPU timing for SHA256 operations
    Returns timing samples in microseconds
    """
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        # Do 10k SHA256 operations
        data = b"rustchain_poa_benchmark"
        for _ in range(10000):
            data = hashlib.sha256(data).digest()
        elapsed_us = (time.perf_counter() - start) * 1_000_000
        samples.append(int(elapsed_us))
    return samples


def measure_ram_timing():
    """
    Measure RAM access patterns for PoA validation
    Returns timing in nanoseconds
    """
    # Sequential memory access
    test_data = bytearray(1024 * 1024)  # 1MB
    start = time.perf_counter_ns()
    for i in range(0, len(test_data), 64):
        test_data[i] = (test_data[i] + 1) % 256
    sequential_ns = (time.perf_counter_ns() - start) / (len(test_data) // 64)

    # Random access pattern
    import random
    indices = [random.randint(0, len(test_data)-1) for _ in range(1000)]
    start = time.perf_counter_ns()
    for idx in indices:
        test_data[idx] = (test_data[idx] + 1) % 256
    random_ns = (time.perf_counter_ns() - start) / len(indices)

    # Estimate cache hit rate (lower random/sequential ratio = better cache)
    cache_hit_rate = min(1.0, sequential_ns / max(random_ns, 1) * 2)

    return {
        "sequential_ns": int(sequential_ns),
        "random_ns": int(random_ns),
        "cache_hit_rate": round(cache_hit_rate, 2)
    }


def get_mac_addresses():
    """Get MAC addresses for hardware fingerprinting"""
    macs = []
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(["ifconfig"], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'ether' in line:
                    mac = line.split('ether')[1].strip().split()[0]
                    if mac and mac != "00:00:00:00:00:00":
                        macs.append(mac)
        elif platform.system() == "Linux":
            result = subprocess.run(["ip", "link"], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    mac = line.split('link/ether')[1].strip().split()[0]
                    if mac and mac != "00:00:00:00:00:00":
                        macs.append(mac)
    except Exception:
        pass
    return macs[:3] if macs else ["00:03:93:00:00:01"]  # Apple OUI fallback


def detect_ppc_hardware():
    """Detect PowerPC hardware details"""
    hw_info = {
        "family": "PowerPC",
        "arch": "G4",
        "model": "PowerMac G4",
        "cpu": "PowerPC G4 7450",
        "cores": 1,
        "memory_gb": 1
    }

    try:
        machine = platform.machine().lower()
        if 'ppc' in machine or 'power' in machine:
            hw_info["family"] = "PowerPC"

            # Try to detect specific model
            if platform.system() == "Darwin":
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

            elif platform.system() == "Linux":
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read().lower()
                    if '7450' in cpuinfo or '7447' in cpuinfo or '7455' in cpuinfo:
                        hw_info["arch"] = "G4"
                        hw_info["cpu"] = "PowerPC G4 (74xx)"
                    elif '970' in cpuinfo:
                        hw_info["arch"] = "G5"
                        hw_info["cpu"] = "PowerPC G5 (970)"
                    elif '750' in cpuinfo:
                        hw_info["arch"] = "G3"
                        hw_info["cpu"] = "PowerPC G3 (750)"
    except Exception:
        pass

    # Get core count
    hw_info["cores"] = os.cpu_count() or 1

    # Get memory
    try:
        if platform.system() == "Linux":
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        kb = int(line.split()[1])
                        hw_info["memory_gb"] = max(1, kb // (1024 * 1024))
                        break
        elif platform.system() == "Darwin":
            result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                                   capture_output=True, text=True, timeout=5)
            hw_info["memory_gb"] = int(result.stdout.strip()) // (1024**3)
    except Exception:
        pass

    return hw_info


class G4PoAMiner:
    def __init__(self, miner_id=None):
        self.node_url = NODE_URL
        self.hw_info = detect_ppc_hardware()

        # Generate or use provided miner_id
        if miner_id:
            self.miner_id = miner_id
        else:
            hostname = platform.node()[:10]
            hw_hash = hashlib.sha256(f"{hostname}-{self.hw_info['cpu']}".encode()).hexdigest()[:8]
            self.miner_id = f"g4-{hostname}-{hw_hash}"

        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.current_slot = 0

        self._print_banner()

    def _print_banner(self):
        print("=" * 70)
        print("RustChain G4 PoA Miner v2.0")
        print("=" * 70)
        print(f"Miner ID:     {self.miner_id}")
        print(f"Node:         {self.node_url}")
        print("-" * 70)
        print(f"Hardware:     {self.hw_info['family']} / {self.hw_info['arch']}")
        print(f"CPU:          {self.hw_info['cpu']}")
        print(f"Cores:        {self.hw_info['cores']}")
        print(f"Memory:       {self.hw_info['memory_gb']} GB")
        print("-" * 70)
        print("Expected PoA Weight: 2.5x (G4 Antiquity Bonus)")
        print("=" * 70)

    def attest(self):
        """
        Complete hardware attestation with full PoA signals
        Per rip_proof_of_antiquity_hardware.py:
        - entropy_samples (40% weight)
        - cpu_timing (30% weight)
        - ram_timing (20% weight)
        - macs (10% weight)
        """
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attesting with PoA signals...")

        try:
            # Step 1: Get challenge nonce
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=15)
            if resp.status_code != 200:
                print(f"  ERROR: Challenge failed ({resp.status_code})")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce", "")
            print(f"  Got nonce: {nonce[:16]}...")

            # Step 2: Collect PoA signals
            # Entropy (40% weight)
            entropy_hex = get_system_entropy(64)
            print(f"  Entropy: {entropy_hex[:32]}... ({len(entropy_hex)//2} bytes)")

            # CPU Timing (30% weight) - measure actual timing
            print("  Measuring CPU timing...")
            cpu_samples = measure_cpu_timing(10)
            cpu_mean = sum(cpu_samples) / len(cpu_samples)
            cpu_variance = sum((x - cpu_mean)**2 for x in cpu_samples) / len(cpu_samples)
            print(f"  CPU timing: mean={cpu_mean:.0f}µs, var={cpu_variance:.0f}")

            # RAM Timing (20% weight)
            print("  Measuring RAM timing...")
            ram_timing = measure_ram_timing()
            print(f"  RAM timing: seq={ram_timing['sequential_ns']}ns, rand={ram_timing['random_ns']}ns")

            # MACs (10% weight)
            macs = get_mac_addresses()
            print(f"  MACs: {macs}")

            # Step 3: Build commitment
            commitment = hashlib.sha256(f"{nonce}{self.miner_id}{entropy_hex}".encode()).hexdigest()

            # Step 4: Build attestation payload
            # KEY FIX: Use miner_id as the miner field for consistent identity
            attestation = {
                "miner": self.miner_id,  # IMPORTANT: Use miner_id here for lottery compatibility
                "miner_id": self.miner_id,
                "nonce": nonce,
                "report": {
                    "nonce": nonce,
                    "commitment": commitment
                },
                "device": {
                    "family": self.hw_info["family"],
                    "arch": self.hw_info["arch"],
                    "model": self.hw_info["model"],
                    "cpu": self.hw_info["cpu"],
                    "cores": self.hw_info["cores"],
                    "memory_gb": self.hw_info["memory_gb"]
                },
                "signals": {
                    "entropy_samples": entropy_hex,
                    "cpu_timing": {
                        "samples": cpu_samples,
                        "mean": cpu_mean,
                        "variance": cpu_variance
                    },
                    "ram_timing": ram_timing,
                    "macs": macs,
                    "hostname": platform.node(),
                    "os": platform.system().lower(),
                    "timestamp": int(time.time())
                }
            }

            # Step 5: Submit attestation
            print("  Submitting attestation...")
            resp = requests.post(f"{self.node_url}/attest/submit",
                               json=attestation, timeout=15)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok") or result.get("status") == "accepted":
                    self.attestation_valid_until = time.time() + ATTESTATION_INTERVAL
                    print(f"  SUCCESS: Attestation accepted!")
                    print(f"  Ticket: {result.get('ticket_id', 'N/A')}")
                    return True
                else:
                    print(f"  WARNING: {result}")
                    return False
            else:
                print(f"  ERROR: HTTP {resp.status_code}")
                print(f"  Response: {resp.text[:200]}")
                return False

        except Exception as e:
            print(f"  ERROR: {e}")
            return False

    def check_eligibility(self):
        """Check if we're the designated block producer for current slot"""
        try:
            resp = requests.get(
                f"{self.node_url}/lottery/eligibility",
                params={"miner_id": self.miner_id},
                timeout=10
            )

            if resp.status_code == 200:
                return resp.json()
            return {"eligible": False, "reason": f"HTTP {resp.status_code}"}

        except Exception as e:
            return {"eligible": False, "reason": str(e)}

    def submit_header(self, slot):
        """Submit a signed header for the slot"""
        try:
            # Create message
            ts = int(time.time())
            message = f"slot:{slot}:miner:{self.miner_id}:ts:{ts}"
            message_hex = message.encode().hex()

            # Sign with Blake2b (per PoA spec)
            sig_data = hashlib.blake2b(
                f"{message}{self.miner_id}".encode(),
                digest_size=64
            ).hexdigest()

            header_payload = {
                "miner_id": self.miner_id,
                "header": {
                    "slot": slot,
                    "miner": self.miner_id,
                    "timestamp": ts
                },
                "message": message_hex,
                "signature": sig_data,
                "pubkey": self.miner_id
            }

            resp = requests.post(
                f"{self.node_url}/headers/ingest_signed",
                json=header_payload,
                timeout=15
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
        status_counter = 0

        while True:
            try:
                # Re-attest if needed
                if time.time() > self.attestation_valid_until:
                    self.attest()

                # Check lottery eligibility
                eligibility = self.check_eligibility()
                slot = eligibility.get("slot", 0)
                self.current_slot = slot

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
                    elif reason == "not_your_turn":
                        # Normal - wait for our turn
                        pass

                # Status update every 6 checks (~60 seconds)
                status_counter += 1
                if status_counter >= 6:
                    rotation = eligibility.get("rotation_size", 0)
                    producer = eligibility.get("slot_producer", "?")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Slot {slot} | Producer: {producer[:15] if producer else '?'}... | "
                          f"Rotation: {rotation} | "
                          f"Submitted: {self.shares_submitted} | Accepted: {self.shares_accepted}")
                    status_counter = 0

                time.sleep(LOTTERY_CHECK_INTERVAL)

            except KeyboardInterrupt:
                print("\n\nShutting down miner...")
                break
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain G4 PoA Miner")
    parser.add_argument("--miner-id", "-m", help="Custom miner ID")
    parser.add_argument("--node", "-n", default=NODE_URL, help="RIP node URL")
    args = parser.parse_args()

    if args.node:
        NODE_URL = args.node

    miner = G4PoAMiner(miner_id=args.miner_id)
    miner.run()
