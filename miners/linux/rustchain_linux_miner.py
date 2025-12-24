#!/usr/bin/env python3
"""
RustChain Local x86 Miner - Modern Ryzen
With RIP-PoA Hardware Fingerprint Attestation + Serial Binding v2.0
"""
import warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

import os, sys, json, time, hashlib, uuid, requests, socket, subprocess, platform, statistics, re
from datetime import datetime

# Import fingerprint checks
try:
    from fingerprint_checks import validate_all_checks
    FINGERPRINT_AVAILABLE = True
except ImportError:
    FINGERPRINT_AVAILABLE = False
    print("[WARN] fingerprint_checks.py not found - fingerprint attestation disabled")

NODE_URL = "https://50.28.86.131"  # Use HTTPS via nginx
BLOCK_TIME = 600  # 10 minutes

def get_linux_serial():
    """Get hardware serial number for Linux systems"""
    # Try various sources
    serial_sources = [
        "/sys/class/dmi/id/product_serial",
        "/sys/class/dmi/id/board_serial",
        "/sys/class/dmi/id/chassis_serial",
    ]
    for path in serial_sources:
        try:
            with open(path, 'r') as f:
                serial = f.read().strip()
                if serial and serial not in ['', 'None', 'To Be Filled By O.E.M.', 'Default string']:
                    return serial
        except:
            pass

    # Fallback to machine-id (stable across reboots)
    try:
        with open('/etc/machine-id', 'r') as f:
            return f.read().strip()[:16]  # First 16 chars
    except:
        pass

    return None

class LocalMiner:
    def __init__(self, wallet=None):
        self.node_url = NODE_URL
        self.wallet = wallet or self._gen_wallet()
        self.hw_info = {}
        self.enrolled = False
        self.attestation_valid_until = 0
        self.last_entropy = {}
        self.fingerprint_data = {}
        self.fingerprint_passed = False

        self.serial = get_linux_serial()
        print("="*70)
        print("RustChain Local Miner - HP Victus Ryzen 5 8645HS")
        print("RIP-PoA Hardware Fingerprint + Serial Binding v2.0")
        print("="*70)
        print(f"Node: {self.node_url}")
        print(f"Wallet: {self.wallet}")
        print(f"Serial: {self.serial}")
        print("="*70)

        # Run initial fingerprint check
        if FINGERPRINT_AVAILABLE:
            self._run_fingerprint_checks()

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
        data = f"ryzen5-{uuid.uuid4().hex}-{time.time()}"
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
        # Try `ip -o link`
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

        # Fallback to ifconfig
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
        """Collect hardware info"""
        hw = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
            "family": "x86",
            "arch": "modern",  # Less than 10 years old
            "serial": get_linux_serial()  # Hardware serial for v2 binding
        }

        # Get CPU
        cpu = self._run_cmd("lscpu | grep 'Model name' | cut -d: -f2 | xargs")
        hw["cpu"] = cpu or "Unknown"

        # Get cores
        cores = self._run_cmd("nproc")
        hw["cores"] = int(cores) if cores else 6

        # Get memory
        mem = self._run_cmd("free -g | grep Mem | awk '{print $2}'")
        hw["memory_gb"] = int(mem) if mem else 32

        # Get MACs (ensures PoA signal uses real hardware data)
        macs = self._get_mac_addresses()
        hw["macs"] = macs
        hw["mac"] = macs[0]

        self.hw_info = hw
        return hw

    def attest(self):
        """Hardware attestation"""
        print(f"\n🔐 [{datetime.now().strftime('%H:%M:%S')}] Attesting...")

        self._get_hw_info()

        try:
            # Get challenge (verify=False for self-signed certs)
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=10, verify=False)
            if resp.status_code != 200:
                print(f"❌ Challenge failed: {resp.status_code}")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce")
            print(f"✅ Got challenge nonce")

        except Exception as e:
            print(f"❌ Challenge error: {e}")
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
            "miner_id": f"ryzen5-{self.hw_info['hostname']}",
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
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"],
                "model": "AMD Ryzen 5 8645HS",
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
                    print(f"[PASS] Attestation accepted!")
                    print(f"   CPU: {self.hw_info['cpu']}")
                    print(f"   Arch: {self.hw_info.get('machine', 'x86_64')}/{self.hw_info.get('arch', 'modern')}")

                    # Show fingerprint status with details
                    if self.fingerprint_passed:
                        print(f"   Fingerprint: PASSED")
                    else:
                        print(f"   Fingerprint: FAILED")
                        # Extract failure reasons from fingerprint_data
                        if self.fingerprint_data:
                            checks = self.fingerprint_data.get("checks", {})
                            failed_checks = []
                            for name, check in checks.items():
                                if not check.get("passed", True):
                                    reason = check.get("data", {})
                                    if name == "anti_emulation":
                                        vm_indicators = reason.get("vm_indicators", [])
                                        failed_checks.append(f"VM/Container detected: {vm_indicators}")
                                    else:
                                        failed_checks.append(f"{name}: {reason}")
                            if failed_checks:
                                for fc in failed_checks[:3]:  # Show up to 3 reasons
                                    print(f"      -> {fc}")
                        print(f"   [!] WARNING: VMs/containers receive minimal rewards (1 billionth of real hardware)")
                    return True
                else:
                    print(f"❌ Rejected: {result}")
            else:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            print(f"❌ Error: {e}")

        return False

    def enroll(self):
        """Enroll in epoch"""
        if time.time() >= self.attestation_valid_until:
            print(f"📝 Attestation expired, re-attesting...")
            if not self.attest():
                return False

        print(f"\n📝 [{datetime.now().strftime('%H:%M:%S')}] Enrolling...")

        payload = {
            "miner_pubkey": self.wallet,
            "miner_id": f"ryzen5-{self.hw_info['hostname']}",
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/epoch/enroll",
                                json=payload, timeout=30, verify=False)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.enrolled = True
                    weight = result.get('weight', 1.0)
                    hw_weight = result.get('hw_weight', weight)
                    fingerprint_failed = result.get('fingerprint_failed', False)

                    print(f"[OK] Enrolled!")
                    print(f"   Epoch: {result.get('epoch')}")
                    print(f"   Weight: {weight}x")

                    # Warning for VM/container users (they still earn, just very little)
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
                    print(f"❌ Failed: {result}")
            else:
                error_data = resp.json() if resp.headers.get('content-type') == 'application/json' else {}
                print(f"❌ HTTP {resp.status_code}: {error_data.get('error', resp.text[:200])}")

        except Exception as e:
            print(f"❌ Error: {e}")

        return False

    def check_balance(self):
        """Check balance"""
        try:
            resp = requests.get(f"{self.node_url}/balance/{self.wallet}", timeout=10, verify=False)
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
        print(f"\n⛏️  Starting mining...")
        print(f"Block time: {BLOCK_TIME//60} minutes")
        print(f"Press Ctrl+C to stop\n")

        # Save wallet
        with open("/tmp/local_miner_wallet.txt", "w") as f:
            f.write(self.wallet)
        print(f"💾 Wallet saved to: /tmp/local_miner_wallet.txt\n")

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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", help="Wallet address")
    args = parser.parse_args()

    miner = LocalMiner(wallet=args.wallet)
    miner.mine()
