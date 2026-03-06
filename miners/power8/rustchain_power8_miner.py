#!/usr/bin/env python3
"""
RustChain POWER8 S824 Miner
With RIP-PoA Hardware Fingerprint Attestation
"""
import os, sys, json, time, hashlib, uuid, requests, socket, subprocess, platform, statistics, re, warnings
from datetime import datetime

# Suppress SSL warnings for self-signed cert
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Import fingerprint checks
try:
    from fingerprint_checks import validate_all_checks
    FINGERPRINT_AVAILABLE = True
except ImportError:
    FINGERPRINT_AVAILABLE = False
    print("[WARN] fingerprint_checks.py not found - fingerprint attestation disabled")

NODE_URL = "https://rustchain.org"  # Use HTTPS via nginx
BLOCK_TIME = 600  # 10 minutes

WALLET_FILE = os.path.expanduser("~/rustchain/power8_wallet.txt")

class LocalMiner:
    def __init__(self, wallet=None):
        self.node_url = NODE_URL
        self.wallet = wallet or self._load_or_gen_wallet()
        self.hw_info = {}
        self.enrolled = False
        self.attestation_valid_until = 0
        self.last_entropy = {}
        self.fingerprint_data = {}
        self.fingerprint_passed = False

        print("="*70)
        print("RustChain POWER8 S824 Miner")
        print("IBM Power System S824 - Dual 8-core POWER8")
        print("RIP-PoA Hardware Fingerprint Enabled")
        print("="*70)
        print(f"Node: {self.node_url}")
        print(f"Wallet: {self.wallet}")
        print("="*70)

        # Run initial fingerprint check
        if FINGERPRINT_AVAILABLE:
            self._run_fingerprint_checks()

    def _load_or_gen_wallet(self):
        """Load wallet from file or generate new one (persist on first run)"""
        if os.path.exists(WALLET_FILE):
            with open(WALLET_FILE, 'r') as f:
                wallet = f.read().strip()
                if wallet:
                    print(f"[WALLET] Loaded existing wallet from {WALLET_FILE}")
                    return wallet
        # Generate new wallet
        wallet = self._gen_wallet()
        # Save it
        os.makedirs(os.path.dirname(WALLET_FILE), exist_ok=True)
        with open(WALLET_FILE, 'w') as f:
            f.write(wallet)
        print(f"[WALLET] Generated and saved new wallet to {WALLET_FILE}")
        return wallet

    def _run_fingerprint_checks(self):
        """Run 6 hardware fingerprint checks for RIP-PoA"""
        print("\n[FINGERPRINT] Running 6 hardware fingerprint checks...")
        try:
            passed, results = validate_all_checks()
            self.fingerprint_passed = passed
            self.fingerprint_data = {"checks": results, "all_passed": passed}
            if passed:
                print("[FINGERPRINT] All checks PASSED - eligible for full rewards")
            else:
                failed = [k for k, v in results.items() if not v.get("passed")]
                print(f"[FINGERPRINT] FAILED checks: {failed}")
                print("[FINGERPRINT] WARNING: May receive reduced/zero rewards")
        except Exception as e:
            print(f"[FINGERPRINT] Error running checks: {e}")
            self.fingerprint_passed = False
            self.fingerprint_data = {"error": str(e), "all_passed": False}

    def _gen_wallet(self):
        data = f"power8-s824-{uuid.uuid4().hex}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:38] + "RTC"

    def _run_cmd(self, cmd):
        try:
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=10, shell=True).stdout.strip()
        except:
            return ""

    def _get_mac_addresses(self):
        """Return list of real MAC addresses present on the system."""
        macs = []
        try:
            output = subprocess.run(
                ["ip", "-o", "link"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).stdout.splitlines()
            for line in output:
                m = re.search(r"link/(?:ether|loopback)\s+([0-9a-f:]{17})", line, re.IGNORECASE)
                if m:
                    mac = m.group(1).lower()
                    if mac != "00:00:00:00:00:00":
                        macs.append(mac)
        except Exception:
            pass

        if not macs:
            try:
                output = subprocess.run(
                    ["ifconfig", "-a"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                ).stdout.splitlines()
                for line in output:
                    m = re.search(r"(?:ether|HWaddr)\s+([0-9a-f:]{17})", line, re.IGNORECASE)
                    if m:
                        mac = m.group(1).lower()
                        if mac != "00:00:00:00:00:00":
                            macs.append(mac)
            except Exception:
                pass

        return macs or ["00:00:00:00:00:01"]

    def _collect_entropy(self, cycles: int = 48, inner_loop: int = 25000):
        """
        Collect simple timing entropy by measuring tight CPU loops.
        Returns summary statistics the node can score.
        """
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

    def _get_hw_info(self):
        """Collect hardware info for POWER8"""
        hw = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
            "family": "PowerPC",
            "arch": "power8"  # Server-class POWER8
        }

        # Get CPU info for POWER8
        cpu = self._run_cmd("lscpu | grep 'Model name' | cut -d: -f2 | xargs")
        if not cpu:
            cpu = self._run_cmd("cat /proc/cpuinfo | grep 'cpu' | head -1 | cut -d: -f2 | xargs")
        hw["cpu"] = cpu or "IBM POWER8"

        # Get cores (POWER8 has 16 cores, 128 threads with SMT8)
        cores = self._run_cmd("nproc")
        hw["cores"] = int(cores) if cores else 128

        # Get memory (576GB on S824)
        mem = self._run_cmd("free -g | grep Mem | awk '{print $2}'")
        hw["memory_gb"] = int(mem) if mem else 576

        # Get MACs
        macs = self._get_mac_addresses()
        hw["macs"] = macs
        hw["mac"] = macs[0]

        self.hw_info = hw
        return hw

    def attest(self):
        """Hardware attestation"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attesting...")

        self._get_hw_info()

        try:
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=10, verify=False)
            if resp.status_code != 200:
                print(f"[FAIL] Challenge failed: {resp.status_code}")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce")
            print(f"[OK] Got challenge nonce")

        except Exception as e:
            print(f"[FAIL] Challenge error: {e}")
            return False

        # Collect entropy just before signing the report
        entropy = self._collect_entropy()
        self.last_entropy = entropy

        # Re-run fingerprint checks if needed
        if FINGERPRINT_AVAILABLE and not self.fingerprint_data:
            self._run_fingerprint_checks()

        # Submit attestation with fingerprint data
        attestation = {
            "miner": self.wallet,
            "miner_id": f"power8-s824-{self.hw_info['hostname']}",
            "nonce": nonce,
            "report": {
                "nonce": nonce,
                "commitment": hashlib.sha256(
                    (nonce + self.wallet + json.dumps(entropy, sort_keys=True)).encode()
                ).hexdigest(),
                "derived": entropy,
                "entropy_score": entropy.get("variance_ns", 0.0)
            },
            "device": {
                "device_family": self.hw_info["family"],
                "device_arch": self.hw_info["arch"],
                "device_model": "IBM POWER8 S824 (8286-42A)",
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"],
                "model": "IBM POWER8 S824 (8286-42A)",
                "cpu": self.hw_info["cpu"],
                "cores": self.hw_info["cores"],
                "memory_gb": self.hw_info["memory_gb"]
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
                    print(f"[PASS] Attestation accepted!")
                    print(f"   CPU: {self.hw_info['cpu']}")
                    print(f"   Arch: {self.hw_info.get('machine', 'ppc64le')}/{self.hw_info.get('arch', 'power8')}")

                    if self.fingerprint_passed:
                        print(f"   Fingerprint: PASSED")
                    else:
                        print(f"   Fingerprint: FAILED")
                        if self.fingerprint_data:
                            checks = self.fingerprint_data.get("checks", {})
                            failed_checks = []
                            for name, check in checks.items():
                                if not check.get("passed"):
                                    reason = check.get("data", {}).get("fail_reason", "unknown")
                                    failed_checks.append(f"{name}:{reason}")
                            if failed_checks:
                                print(f"   Failed: {', '.join(failed_checks)}")

                    return True
                else:
                    print(f"[FAIL] {result.get('error', 'Unknown error')}")
            else:
                error_data = resp.json() if resp.headers.get('content-type') == 'application/json' else {}
                print(f"[FAIL] HTTP {resp.status_code}: {error_data.get('error', resp.text[:200])}")

        except Exception as e:
            print(f"[FAIL] Error: {e}")

        return False

    def enroll(self):
        """Epoch enrollment"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Enrolling for epoch...")

        # First attest
        if not self.attest():
            return False

        try:
            # Get challenge
            resp = requests.post(f"{self.node_url}/epoch/enroll", json={
                "miner_id": f"power8-s824-{self.hw_info['hostname']}",
                "miner_pubkey": self.wallet,  # Testnet: wallet as pubkey
                "signature": "0" * 128   # Testnet: mock signature
            }, timeout=10, verify=False)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.enrolled = True
                    weight = result.get('weight', 1.0)
                    hw_weight = result.get('hw_weight', 1.0)
                    fingerprint_failed = result.get('fingerprint_failed', False)

                    print(f"[OK] Enrolled!")
                    print(f"   Epoch: {result.get('epoch')}")
                    print(f"   Weight: {weight}x")

                    if fingerprint_failed or weight < 0.001:
                        print("")
                        print("=" * 60)
                        print("[!] VM/CONTAINER DETECTED - MINIMAL REWARDS")
                        print("=" * 60)
                        print("   Your fingerprint check failed, indicating you are")
                        print("   running in a virtual machine or container.")
                        print("")
                        print("   Hardware weight would be: {:.1f}x".format(hw_weight))
                        print("   Actual weight assigned:   {:.9f}x".format(weight))
                        print("")
                        print("   VMs/containers CAN mine, but earn ~1 billionth")
                        print("   of what real hardware earns per epoch.")
                        print("   Run on real hardware for meaningful rewards.")
                        print("=" * 60)
                        print("")

                    return True
                else:
                    print(f"[FAIL] {result}")
            else:
                error_data = resp.json() if resp.headers.get('content-type') == 'application/json' else {}
                print(f"[FAIL] HTTP {resp.status_code}: {error_data.get('error', resp.text[:200])}")

        except Exception as e:
            print(f"[FAIL] Error: {e}")

        return False

    def check_balance(self):
        """Check balance"""
        try:
            resp = requests.get(f"{self.node_url}/balance/{self.wallet}", timeout=10, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                balance = result.get('balance_rtc', 0)
                print(f"\n[BALANCE] {balance} RTC")
                return balance
        except:
            pass
        return 0

    def mine(self):
        """Start mining"""
        print(f"\n[START] Mining...")
        print(f"Block time: {BLOCK_TIME//60} minutes")
        print(f"Press Ctrl+C to stop\n")

        # Save wallet
        wallet_file = os.path.expanduser("~/rustchain/power8_wallet.txt")
        with open(wallet_file, "w") as f:
            f.write(self.wallet)
        print(f"[SAVE] Wallet saved to: {wallet_file}\n")

        cycle = 0

        try:
            while True:
                cycle += 1
                print(f"\n{'='*70}")
                print(f"Cycle #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*70}")

                if self.enroll():
                    print(f"[MINING] Mining for {BLOCK_TIME//60} minutes...")

                    for i in range(BLOCK_TIME // 30):
                        time.sleep(30)
                        elapsed = (i + 1) * 30
                        remaining = BLOCK_TIME - elapsed
                        print(f"   [{elapsed}s elapsed, {remaining}s remaining...]")

                    self.check_balance()

                else:
                    print("[RETRY] Enrollment failed. Retrying in 60s...")
                    time.sleep(60)

        except KeyboardInterrupt:
            print(f"\n\n[STOP] Mining stopped")
            print(f"   Wallet: {self.wallet}")
            self.check_balance()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", help="Wallet address")
    args = parser.parse_args()

    miner = LocalMiner(wallet=args.wallet)
    miner.mine()
