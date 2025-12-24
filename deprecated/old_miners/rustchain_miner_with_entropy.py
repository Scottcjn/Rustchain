#!/usr/bin/env python3
"""
RustChain Miner with Full Entropy Collection
=============================================
Collects comprehensive hardware fingerprints:
- CPU timing characteristics (100+ samples)
- RAM access patterns (sequential vs random)
- Hardware entropy samples
- MAC addresses

Works on Mac, Linux, and other Unix systems.
"""
import os, sys, json, time, hashlib, uuid, socket, subprocess, platform, requests
import statistics, random, array
from datetime import datetime
from typing import Dict, List, Optional

NODE_URL = "http://50.28.86.131:8088"
BLOCK_TIME = 600  # 10 minutes


class EntropyCollector:
    """Collects hardware entropy and timing characteristics"""

    @staticmethod
    def collect_cpu_timing_samples(iterations=100) -> Dict:
        """
        Collect CPU timing samples by running hash operations.

        Returns:
            {
                "samples": [us_per_iteration, ...],
                "mean": float,
                "variance": float
            }
        """
        samples = []

        # Run hash operations and measure time
        for _ in range(iterations):
            data = os.urandom(1024)  # 1KB random data

            start = time.perf_counter()
            for _ in range(1000):  # 1000 hash operations
                hashlib.sha256(data).digest()
            elapsed = time.perf_counter() - start

            # Convert to microseconds
            us_per_iter = (elapsed / 1000) * 1_000_000
            samples.append(us_per_iter)

        mean = statistics.mean(samples) if samples else 0
        variance = statistics.variance(samples) if len(samples) > 1 else 0

        return {
            "samples": samples,
            "mean": round(mean, 2),
            "variance": round(variance, 2)
        }

    @staticmethod
    def collect_ram_timing() -> Dict:
        """
        Measure RAM access patterns.

        Returns:
            {
                "sequential_ns": float,
                "random_ns": float,
                "cache_hit_rate": float
            }
        """
        # Create large array (10MB)
        size = 10 * 1024 * 1024 // 4  # 10MB of 32-bit integers
        data = array.array('i', range(size))

        # Sequential access
        seq_times = []
        for _ in range(10):
            start = time.perf_counter()
            total = 0
            for i in range(0, min(100000, size)):
                total += data[i]
            elapsed = time.perf_counter() - start
            seq_times.append(elapsed)

        sequential_ns = (statistics.mean(seq_times) / 100000) * 1_000_000_000

        # Random access
        indices = [random.randint(0, size - 1) for _ in range(100000)]
        rand_times = []
        for _ in range(10):
            start = time.perf_counter()
            total = 0
            for i in indices[:10000]:  # Sample 10k random accesses
                total += data[i]
            elapsed = time.perf_counter() - start
            rand_times.append(elapsed)

        random_ns = (statistics.mean(rand_times) / 10000) * 1_000_000_000

        # Estimate cache hit rate (if random is only 2-3x slower, good cache)
        cache_estimate = min(sequential_ns / random_ns, 1.0) if random_ns > 0 else 0.5

        return {
            "sequential_ns": round(sequential_ns, 2),
            "random_ns": round(random_ns, 2),
            "cache_hit_rate": round(cache_estimate, 2)
        }

    @staticmethod
    def collect_entropy_samples(num_bytes=256) -> str:
        """
        Collect hardware entropy samples.

        Returns:
            Hex string of random bytes
        """
        return os.urandom(num_bytes).hex()

    @staticmethod
    def collect_all() -> Dict:
        """Collect all entropy data"""
        print("   🔬 Collecting CPU timing samples (100 iterations)...")
        cpu_timing = EntropyCollector.collect_cpu_timing_samples(100)

        print("   🔬 Measuring RAM access patterns...")
        ram_timing = EntropyCollector.collect_ram_timing()

        print("   🔬 Gathering hardware entropy...")
        entropy_samples = EntropyCollector.collect_entropy_samples(256)

        return {
            "cpu_timing": cpu_timing,
            "ram_timing": ram_timing,
            "entropy_samples": entropy_samples
        }


class EnhancedMiner:
    def __init__(self, wallet=None, node_url=NODE_URL):
        self.node_url = node_url
        self.wallet = wallet or self._gen_wallet()
        self.hw_info = {}
        self.enrolled = False
        self.attestation_valid_until = 0

        print("="*70)
        print("RustChain Enhanced Miner with Entropy Collection")
        print("="*70)
        print(f"Node: {self.node_url}")
        print(f"Wallet: {self.wallet}")
        print("="*70)

    def _gen_wallet(self):
        data = f"{platform.node()}-{uuid.uuid4().hex}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:38] + "RTC"

    def _run_cmd(self, cmd):
        """Run shell command safely"""
        try:
            if isinstance(cmd, str):
                result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, timeout=10)
            else:
                result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, timeout=10)
            return result.stdout.strip()
        except:
            return ""

    def _get_mac_address(self):
        """Get primary MAC address (cross-platform)"""
        system = platform.system()

        if system == "Darwin":  # macOS
            result = self._run_cmd(["ifconfig", "en0"])
            for line in result.split('\n'):
                if "ether" in line.lower():
                    return line.split()[1]

        elif system == "Linux":
            result = self._run_cmd("ip link show | grep ether | head -1 | awk '{print $2}'")
            if result:
                return result

        # Fallback
        mac_int = uuid.getnode()
        return ':'.join(('%012x' % mac_int)[i:i+2] for i in range(0, 12, 2))

    def _get_hw_info(self):
        """Collect hardware information (cross-platform)"""
        system = platform.system()
        hw = {
            "platform": system,
            "machine": platform.machine(),
            "hostname": socket.gethostname()
        }

        if system == "Darwin":  # macOS
            hw["cpu"] = self._run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Unknown"
            hw["model"] = self._run_cmd(["sysctl", "-n", "hw.model"]) or "Unknown"
            hw["cores"] = int(self._run_cmd(["sysctl", "-n", "hw.physicalcpu"]) or 2)
            mem_bytes = self._run_cmd(["sysctl", "-n", "hw.memsize"])
            hw["memory_gb"] = int(mem_bytes) // (1024**3) if mem_bytes else 4

            # Determine Mac age
            year_map = {
                "MacPro1,1": 2006, "MacPro2,1": 2007, "MacPro3,1": 2008,
                "MacPro4,1": 2009, "MacPro5,1": 2010, "MacPro6,1": 2013,
                "MacPro7,1": 2019, "iMac20,1": 2020
            }
            mfg_year = year_map.get(hw["model"], 2015)
            age = datetime.now().year - mfg_year

            if hw["machine"] == "arm64":
                hw["family"] = "arm64"
                hw["arch"] = "m_series"
            else:
                hw["family"] = "x86"
                if age >= 20:
                    hw["arch"] = "ancient"
                elif age >= 10:
                    hw["arch"] = "retro"
                else:
                    hw["arch"] = "modern"

        elif system == "Linux":
            hw["cpu"] = self._run_cmd("lscpu | grep 'Model name' | cut -d: -f2 | xargs") or "Unknown"
            hw["model"] = self._run_cmd("cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null") or "Linux PC"
            hw["cores"] = int(self._run_cmd("nproc") or 2)
            mem = self._run_cmd("free -g | grep Mem | awk '{print $2}'")
            hw["memory_gb"] = int(mem) if mem else 4

            machine = hw["machine"]
            if machine in ["x86_64", "i686", "i386"]:
                hw["family"] = "x86"
                hw["arch"] = "modern"  # Assume modern for Linux unless detected otherwise
            elif machine in ["aarch64", "armv7l"]:
                hw["family"] = "ARM"
                hw["arch"] = "default"
            else:
                hw["family"] = machine
                hw["arch"] = "default"

        else:
            # Generic Unix
            hw["cpu"] = "Unknown"
            hw["model"] = "Unknown"
            hw["cores"] = os.cpu_count() or 2
            hw["memory_gb"] = 4
            hw["family"] = "x86"
            hw["arch"] = "modern"

        hw["mac"] = self._get_mac_address()

        self.hw_info = hw
        return hw

    def attest(self):
        """Complete hardware attestation with entropy collection"""
        print(f"\n🔐 [{datetime.now().strftime('%H:%M:%S')}] Starting attestation...")

        # Collect basic hardware info
        self._get_hw_info()

        # Collect entropy data (this takes ~5-10 seconds)
        print("📊 Collecting entropy fingerprints...")
        entropy_data = EntropyCollector.collect_all()

        print(f"   CPU timing: {entropy_data['cpu_timing']['mean']:.2f} µs/hash (variance: {entropy_data['cpu_timing']['variance']:.2f})")
        print(f"   RAM sequential: {entropy_data['ram_timing']['sequential_ns']:.2f} ns")
        print(f"   RAM random: {entropy_data['ram_timing']['random_ns']:.2f} ns")
        print(f"   Entropy samples: {len(entropy_data['entropy_samples'])} hex chars")

        # Get challenge nonce
        try:
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Failed to get challenge: {resp.status_code}")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce")
            print(f"✅ Got challenge nonce")

        except Exception as e:
            print(f"❌ Challenge error: {e}")
            return False

        # Build attestation with entropy data
        attestation = {
            "miner": self.wallet,
            "miner_id": self.wallet,
            "nonce": nonce,
            "report": {
                "nonce": nonce,
                "commitment": hashlib.sha256(f"{nonce}{self.wallet}".encode()).hexdigest()
            },
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"],
                "model": self.hw_info.get("model", "Unknown"),
                "cpu": self.hw_info["cpu"],
                "cores": self.hw_info["cores"],
                "memory_gb": self.hw_info["memory_gb"]
            },
            "signals": {
                "macs": [self.hw_info["mac"]],
                "hostname": self.hw_info["hostname"],
                # NEW: Entropy data
                "cpu_timing": entropy_data["cpu_timing"],
                "ram_timing": entropy_data["ram_timing"],
                "entropy_samples": entropy_data["entropy_samples"]
            }
        }

        # Submit attestation
        try:
            print("📤 Submitting attestation with entropy proof...")
            resp = requests.post(f"{self.node_url}/attest/submit",
                               json=attestation, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.attestation_valid_until = time.time() + 580
                    print(f"✅ Attestation accepted!")
                    print(f"   Model: {self.hw_info.get('model', 'Unknown')}")
                    print(f"   Architecture: {self.hw_info['family']}/{self.hw_info['arch']}")
                    print(f"   MAC: {self.hw_info['mac']}")

                    # Show entropy score if provided
                    if "entropy_score" in result:
                        print(f"   Entropy Score: {result['entropy_score']:.3f}")
                    if "antiquity_tier" in result:
                        print(f"   Antiquity Tier: {result['antiquity_tier']}")

                    return True
                else:
                    print(f"❌ Attestation rejected: {result}")
            else:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            print(f"❌ Attestation error: {e}")

        return False

    def enroll(self):
        """Enroll in current epoch"""
        if time.time() >= self.attestation_valid_until:
            print(f"\n📝 Attestation expired, re-attesting...")
            if not self.attest():
                return False

        print(f"\n📝 [{datetime.now().strftime('%H:%M:%S')}] Enrolling in epoch...")

        payload = {
            "miner_pubkey": self.wallet,
            "miner_id": self.wallet,
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/epoch/enroll",
                                json=payload, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.enrolled = True
                    weight = result.get('weight', 1.0)
                    print(f"✅ Enrolled!")
                    print(f"   Epoch: {result.get('epoch')}")
                    print(f"   Weight: {weight}x")
                    return True
                else:
                    print(f"❌ Enrollment failed: {result}")
            else:
                error_data = resp.json() if resp.headers.get('content-type') == 'application/json' else {}
                print(f"❌ HTTP {resp.status_code}: {error_data.get('error', resp.text[:200])}")

        except Exception as e:
            print(f"❌ Error: {e}")

        return False

    def check_balance(self):
        """Check current balance"""
        try:
            resp = requests.get(f"{self.node_url}/balance/{self.wallet}", timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                balance = result.get('balance_rtc', 0)
                print(f"\n💰 Balance: {balance} RTC")
                return balance
        except:
            pass
        return 0

    def mine(self):
        """Start mining"""
        print(f"\n⛏️  Starting mining operation...")
        print(f"Block time: {BLOCK_TIME//60} minutes")
        print("\nPress Ctrl+C to stop\n")

        # Save wallet
        wallet_file = f"/tmp/{platform.node()}_wallet.txt"
        with open(wallet_file, "w") as f:
            f.write(self.wallet)
        print(f"💾 Wallet saved to: {wallet_file}\n")

        cycle = 0

        try:
            while True:
                cycle += 1
                print(f"\n{'='*70}")
                print(f"Cycle #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*70}")

                if self.enroll():
                    print(f"⏳ Mining for {BLOCK_TIME//60} minutes...")

                    for i in range(BLOCK_TIME // 30):
                        time.sleep(30)
                        elapsed = (i + 1) * 30
                        remaining = BLOCK_TIME - elapsed
                        print(f"   ⏱️  {elapsed}s elapsed, {remaining}s remaining...")

                    self.check_balance()

                else:
                    print("❌ Enrollment failed. Retrying in 60s...")
                    time.sleep(60)

        except KeyboardInterrupt:
            print(f"\n\n⛔ Mining stopped")
            print(f"   Wallet: {self.wallet}")
            self.check_balance()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RustChain Miner with Entropy Collection")
    parser.add_argument("--wallet", help="Wallet address")
    parser.add_argument("--node", default=NODE_URL, help="Node URL")
    parser.add_argument("--test-entropy", action="store_true",
                       help="Test entropy collection only")
    args = parser.parse_args()

    if args.test_entropy:
        print("Testing entropy collection...")
        entropy = EntropyCollector.collect_all()
        print("\nResults:")
        print(json.dumps(entropy, indent=2))
        return

    miner = EnhancedMiner(wallet=args.wallet, node_url=args.node)
    miner.mine()


if __name__ == "__main__":
    main()
