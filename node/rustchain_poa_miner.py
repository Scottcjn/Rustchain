#!/usr/bin/env python3
"""
RustChain PoA Miner v3.1.0
=========================
Based on rip_proof_of_antiquity_hardware.py requirements:
- entropy_samples (hex) - 40% weight
- cpu_timing {samples[], mean, variance} - 30% weight
- ram_timing {sequential_ns, random_ns, cache_hit_rate} - 20% weight
- macs [] - 10% weight

CPU Timing Profiles (µs per 10k hash ops):
- ppc_g4: mean=8500, variance 200-800
- ppc_g5: mean=5000, variance 150-600
- x86_vintage: mean=3000, variance 100-400
- x86_modern: mean=500, variance 10-100
- arm_modern: mean=300, variance 5-50
"""
import os
import sys
import json
import time
import struct
import platform
import subprocess
import statistics
import uuid
import requests
from hashlib import sha256, blake2b
from datetime import datetime

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "http://50.28.86.131:8088")
BLOCK_TIME = 600
ATTESTATION_INTERVAL = 300
LOTTERY_CHECK_INTERVAL = 10


def collect_entropy_samples(num_bytes=64):
    """Collect REAL entropy from hardware source"""
    try:
        if os.path.exists('/dev/urandom'):
            with open('/dev/urandom', 'rb') as f:
                return f.read(num_bytes).hex()
    except:
        pass
    return os.urandom(num_bytes).hex()


def run_cpu_timing_benchmark(iterations=15):
    """
    Run CPU timing benchmark for PoA validation.
    Returns microseconds per 10,000 SHA256 hash operations.

    Expected profiles from PoA doc:
    - ppc_g4: mean ~8500µs, variance 200-800
    - ppc_g5: mean ~5000µs, variance 150-600
    """
    samples = []
    data = b"rustchain_poa_timing_benchmark_v3"

    for _ in range(iterations):
        start = time.perf_counter_ns()
        for i in range(10000):
            data = sha256(data).digest()
        elapsed_us = (time.perf_counter_ns() - start) / 1000  # to microseconds
        samples.append(elapsed_us)

    return {
        "samples": samples,
        "mean": statistics.mean(samples),
        "variance": statistics.variance(samples) if len(samples) > 1 else 0
    }


def run_ram_timing_benchmark():
    """
    Run RAM access pattern benchmark for PoA validation.
    Measures sequential vs random access patterns.
    """
    import random

    # Allocate 1MB test buffer
    buffer_size = 1024 * 1024
    buffer = bytearray(buffer_size)

    # Sequential access timing (write every 64 bytes)
    start = time.perf_counter_ns()
    for i in range(0, buffer_size, 64):
        buffer[i] = (i & 0xFF)
    seq_total_ns = time.perf_counter_ns() - start
    sequential_ns = seq_total_ns / (buffer_size // 64)

    # Random access timing (10k random reads)
    indices = [random.randint(0, buffer_size - 1) for _ in range(10000)]
    start = time.perf_counter_ns()
    checksum = 0
    for idx in indices:
        checksum ^= buffer[idx]
    rand_total_ns = time.perf_counter_ns() - start
    random_ns = rand_total_ns / 10000

    # Cache hit rate estimation
    cache_hit_rate = min(1.0, sequential_ns / random_ns) if random_ns > 0 else 0.5

    return {
        "sequential_ns": round(sequential_ns, 2),
        "random_ns": round(random_ns, 2),
        "cache_hit_rate": round(cache_hit_rate, 3)
    }


def get_mac_addresses():
    """Get network interface MAC addresses"""
    macs = []
    try:
        if platform.system().lower() == 'linux':
            import glob
            for path in glob.glob('/sys/class/net/*/address'):
                with open(path) as f:
                    mac = f.read().strip()
                    if mac and mac != '00:00:00:00:00:00':
                        macs.append(mac)
        elif platform.system().lower() == 'darwin':
            result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'ether' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        macs.append(parts[1])
    except:
        pass

    # Fallback: generate one from UUID
    if not macs:
        node = uuid.getnode()
        mac = ':'.join(f'{(node >> (8 * i)) & 0xff:02x}' for i in range(5, -1, -1))
        macs.append(mac)

    return macs[:3]  # Max 3 MACs


def detect_hardware():
    """Detect hardware architecture"""
    machine = platform.machine().lower()
    system = platform.system().lower()

    hw = {
        "family": "unknown",
        "arch": "unknown",
        "model": platform.processor() or "unknown",
        "cpu": "unknown",
        "cores": os.cpu_count() or 1,
        "memory_gb": 4,
        "hostname": platform.node(),
        "os": system
    }

    # PowerPC
    if machine in ('ppc', 'ppc64', 'powerpc', 'powerpc64'):
        hw["family"] = "PowerPC"
        hw["arch"] = "G4"  # Default
        try:
            if system == 'darwin':
                result = subprocess.run(['system_profiler', 'SPHardwareDataType'],
                                       capture_output=True, text=True, timeout=10)
                out = result.stdout.lower()
                if 'g5' in out or 'powermac11' in out:
                    hw["arch"] = "G5"
                    hw["cpu"] = "PowerPC G5"
                elif 'g4' in out or 'powerbook' in out:
                    hw["arch"] = "G4"
                    hw["cpu"] = "PowerPC G4"
            elif system == 'linux':
                with open('/proc/cpuinfo') as f:
                    cpuinfo = f.read().lower()
                    if '970' in cpuinfo:
                        hw["arch"], hw["cpu"] = "G5", "PowerPC G5 (970)"
                    elif any(x in cpuinfo for x in ['7450', '7447', '7455']):
                        hw["arch"], hw["cpu"] = "G4", "PowerPC G4 (74xx)"
        except:
            hw["cpu"] = "PowerPC G4"

    # Apple Silicon
    elif machine == 'arm64' and system == 'darwin':
        hw["family"] = "ARM"
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                   capture_output=True, text=True, timeout=5)
            brand = result.stdout.strip()
            for chip in ['M3', 'M2', 'M1']:
                if chip in brand:
                    hw["arch"] = chip
                    hw["cpu"] = brand
                    break
        except:
            hw["arch"], hw["cpu"] = "M1", "Apple M1"

    # x86_64
    elif machine in ('x86_64', 'amd64', 'x64'):
        hw["family"] = "x86_64"
        try:
            if system == 'linux':
                with open('/proc/cpuinfo') as f:
                    for line in f:
                        if line.startswith('model name'):
                            hw["cpu"] = line.split(':')[1].strip()
                            break
            elif system == 'darwin':
                result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                       capture_output=True, text=True, timeout=5)
                hw["cpu"] = result.stdout.strip()
        except:
            hw["cpu"] = "x86_64"
        hw["arch"] = "Core2" if hw["cpu"] and 'core 2' in hw["cpu"].lower() else "modern"

    # ARM Linux
    elif 'arm' in machine or machine == 'aarch64':
        hw["family"] = "ARM"
        hw["arch"] = "aarch64" if machine == 'aarch64' else "arm32"

    # Memory
    try:
        if system == 'linux':
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        hw["memory_gb"] = round(int(line.split()[1]) / 1024 / 1024)
                        break
        elif system == 'darwin':
            result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                                   capture_output=True, text=True, timeout=5)
            hw["memory_gb"] = int(result.stdout.strip()) // (1024**3)
    except:
        pass

    return hw


class PoAMiner:
    def __init__(self, miner_id=None):
        self.node_url = NODE_URL
        self.hw = detect_hardware()

        # Generate miner ID
        if miner_id:
            self.miner_id = miner_id
        else:
            hw_hash = blake2b(f"{self.hw['hostname']}-{self.hw['cpu']}".encode(),
                             digest_size=8).hexdigest()
            self.miner_id = f"{self.hw['arch'].lower()}-{self.hw['hostname'][:10]}-{hw_hash}"

        # Generate wallet
        wallet_hash = blake2b(f"{self.miner_id}-rustchain-poa".encode(),
                             digest_size=20).hexdigest()
        self.wallet = f"{self.hw['family'].lower()}_{wallet_hash}RTC"

        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0

        # Pre-run benchmarks
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running PoA benchmarks...")
        self.cpu_timing = run_cpu_timing_benchmark(15)
        self.ram_timing = run_ram_timing_benchmark()
        self.macs = get_mac_addresses()

        self._print_banner()

    def _print_banner(self):
        weight = self._get_weight()
        print("=" * 70)
        print("RustChain PoA Miner v3.1.0 (Proof-of-Antiquity)")
        print("=" * 70)
        print(f"Miner ID:    {self.miner_id}")
        print(f"Wallet:      {self.wallet}")
        print(f"Node:        {self.node_url}")
        print("-" * 70)
        print(f"Hardware:    {self.hw['family']} / {self.hw['arch']}")
        print(f"CPU:         {self.hw['cpu']}")
        print(f"Cores:       {self.hw['cores']}")
        print(f"Memory:      {self.hw['memory_gb']} GB")
        print("-" * 70)
        print("PoA Signals:")
        print(f"  CPU Timing: mean={self.cpu_timing['mean']:.0f}µs, var={self.cpu_timing['variance']:.0f}")
        print(f"  RAM Timing: seq={self.ram_timing['sequential_ns']:.1f}ns, rand={self.ram_timing['random_ns']:.1f}ns")
        print(f"  Cache Rate: {self.ram_timing['cache_hit_rate']:.3f}")
        print(f"  MACs:       {len(self.macs)} interface(s)")
        print("-" * 70)
        print(f"Expected Antiquity: {weight}x multiplier")
        print("=" * 70)

    def _get_weight(self):
        arch = self.hw['arch'].lower()
        family = self.hw['family'].lower()
        if family == 'powerpc':
            if arch == 'g3': return 3.0
            if arch == 'g4': return 2.5
            if arch == 'g5': return 2.0
        elif family == 'arm':
            if arch in ('m1', 'm2', 'm3'): return 1.2
        elif family == 'x86_64':
            if arch == 'core2': return 1.5
            return 0.8
        return 1.0

    def attest(self):
        """Complete PoA attestation with all required signals"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attesting with PoA signals...")

        try:
            # Get challenge
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=15)
            if resp.status_code != 200:
                print(f"  ERROR: Challenge failed ({resp.status_code})")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce", "")
            print(f"  Got nonce: {nonce[:16]}...")

            # Collect fresh entropy
            entropy_hex = collect_entropy_samples(64)
            print(f"  Entropy: {entropy_hex[:32]}... ({len(entropy_hex)//2} bytes)")

            # Build commitment with Blake2b
            commitment_data = f"{nonce}{self.wallet}{self.miner_id}{entropy_hex}"
            commitment = blake2b(commitment_data.encode(), digest_size=32).hexdigest()

            # Build attestation with ALL PoA signals
            attestation = {
                "miner": self.wallet,
                "miner_id": self.miner_id,
                "nonce": nonce,
                "report": {
                    "nonce": nonce,
                    "commitment": commitment
                },
                "device": {
                    "family": self.hw["family"],
                    "arch": self.hw["arch"],
                    "model": self.hw["model"],
                    "cpu": self.hw["cpu"],
                    "cores": self.hw["cores"],
                    "memory_gb": self.hw["memory_gb"]
                },
                "signals": {
                    # CRITICAL: These are the PoA validation signals
                    "entropy_samples": entropy_hex,  # 40% weight
                    "cpu_timing": self.cpu_timing,   # 30% weight
                    "ram_timing": self.ram_timing,   # 20% weight
                    "macs": self.macs,               # 10% weight
                    # Extra context
                    "hostname": self.hw["hostname"],
                    "os": self.hw["os"],
                    "timestamp": int(time.time())
                }
            }

            # Submit
            print(f"  Submitting attestation...")
            resp = requests.post(f"{self.node_url}/attest/submit", json=attestation, timeout=15)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok") or result.get("status") == "accepted":
                    self.attestation_valid_until = time.time() + ATTESTATION_INTERVAL
                    print(f"  SUCCESS: Attestation accepted!")
                    print(f"  Ticket: {result.get('ticket_id', 'N/A')}")
                    if 'entropy_score' in result:
                        print(f"  Entropy Score: {result['entropy_score']:.3f}")
                    if 'antiquity_tier' in result:
                        print(f"  Antiquity Tier: {result['antiquity_tier']}")
                    return True
                else:
                    print(f"  WARNING: {result}")
                    return False
            else:
                print(f"  ERROR: HTTP {resp.status_code}")
                try:
                    print(f"  Response: {resp.text[:200]}")
                except:
                    pass
                return False

        except Exception as e:
            print(f"  ERROR: {e}")
            return False

    def check_eligibility(self):
        """Check lottery eligibility"""
        try:
            resp = requests.get(
                f"{self.node_url}/lottery/eligibility",
                params={"miner_id": self.miner_id},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {"eligible": False, "reason": "unknown"}

    def submit_header(self, slot):
        """Submit header using Blake2b signature"""
        try:
            ts = int(time.time())
            header = {"slot": slot, "miner": self.miner_id, "timestamp": ts}
            header_json = json.dumps(header, sort_keys=True, separators=(',', ':'))
            message_hex = header_json.encode().hex()

            # Blake2b-512 signature
            sig = blake2b(header_json.encode() + self.wallet.encode(), digest_size=64).hexdigest()

            payload = {
                "miner_id": self.miner_id,
                "header": header,
                "message": message_hex,
                "signature": sig,
                "pubkey": self.wallet
            }

            resp = requests.post(f"{self.node_url}/headers/ingest_signed", json=payload, timeout=15)
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
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting PoA miner...")

        # Initial attestation with retry
        retries = 0
        while not self.attest():
            retries += 1
            wait = min(30 * retries, 300)
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)

        last_slot = 0
        last_status = 0

        while True:
            try:
                # Re-attest if needed
                if time.time() > self.attestation_valid_until:
                    self.attest()

                # Check lottery
                elig = self.check_eligibility()
                slot = elig.get("slot", 0)

                if elig.get("eligible"):
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ELIGIBLE for slot {slot}!")
                    if slot != last_slot:
                        ok, result = self.submit_header(slot)
                        if ok:
                            print(f"  Header ACCEPTED!")
                        else:
                            print(f"  Rejected: {result}")
                        last_slot = slot
                else:
                    reason = elig.get("reason", "unknown")
                    if reason == "not_attested":
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Not attested - re-attesting...")
                        self.attest()

                # Status every 60s
                now = time.time()
                if now - last_status >= 60:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} | "
                          f"Submitted: {self.shares_submitted} | "
                          f"Accepted: {self.shares_accepted} | "
                          f"Eligible: {elig.get('eligible', False)}")
                    last_status = now

                time.sleep(LOTTERY_CHECK_INTERVAL)

            except KeyboardInterrupt:
                print("\n\nShutting down...")
                break
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RustChain PoA Miner v3.1")
    parser.add_argument("--miner-id", "-m", help="Custom miner ID")
    parser.add_argument("--node", "-n", default=NODE_URL, help="RIP node URL")
    args = parser.parse_args()

    if args.node:
        NODE_URL = args.node

    miner = PoAMiner(miner_id=args.miner_id)
    miner.run()
