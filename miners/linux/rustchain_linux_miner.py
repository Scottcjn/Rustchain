#!/usr/bin/env python3
"""
RustChain Local Miner
With RIP-PoA Hardware Fingerprint Attestation + Serial Binding v2.0
"""
import warnings
# warnings.filterwarnings('ignore', message='Unverified HTTPS request')  # No longer needed — TLS verification enabled

import os, sys, json, time, hashlib, uuid, requests, socket, subprocess, platform, statistics, re
from datetime import datetime

# Import fingerprint checks
try:
    from fingerprint_checks import validate_all_checks
    FINGERPRINT_AVAILABLE = True
except ImportError:
    FINGERPRINT_AVAILABLE = False
    print("[WARN] fingerprint_checks.py not found - fingerprint attestation disabled")

# Import Warthog dual-mining sidecar
try:
    from warthog_sidecar import WarthogSidecar
    WARTHOG_AVAILABLE = True
except ImportError:
    WARTHOG_AVAILABLE = False

NODE_URL = "https://rustchain.org"  # Use HTTPS via nginx
BLOCK_TIME = 600  # 10 minutes
NETWORK_RETRY_ATTEMPTS = 3
NETWORK_RETRY_BASE_DELAY = 2

# TLS verification: use pinned cert if available, else system CA bundle
_CERT_PATH = os.path.expanduser("~/.rustchain/node_cert.pem")
TLS_VERIFY = _CERT_PATH if os.path.exists(_CERT_PATH) else True


def _parse_lscpu_model(output):
    for line in output.splitlines():
        key, _, value = line.partition(":")
        if key.strip().lower() == "model name" and value.strip():
            return value.strip()
    return ""


def _parse_free_memory_gb(output):
    for line in output.splitlines():
        parts = line.split()
        if parts and parts[0].lower().rstrip(":") == "mem" and len(parts) > 1:
            try:
                return int(parts[1])
            except ValueError:
                return None
    return None


def _safe_id_part(value):
    slug = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "unknown"


def _miner_id_from_hw(hw_info):
    arch = _safe_id_part(hw_info.get("arch") or hw_info.get("machine") or "linux")
    hostname = _safe_id_part(hw_info.get("hostname") or socket.gethostname())
    return f"{arch}-{hostname}"


def _request_with_network_retry(method, url, action, retries=NETWORK_RETRY_ATTEMPTS,
                                base_delay=NETWORK_RETRY_BASE_DELAY, sleep_func=None,
                                **kwargs):
    """Run an HTTP request with bounded retries for transient network failures."""
    if sleep_func is None:
        sleep_func = time.sleep

    for attempt in range(1, retries + 1):
        try:
            return method(url, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            print(
                "[WARN] Cannot connect to bootstrap node while {} "
                "(attempt {}/{}): {}".format(action, attempt, retries, exc)
            )
            if attempt >= retries:
                print("[ERROR] Cannot connect to bootstrap node.")
                print("[ERROR] Check network connectivity and the RustChain node URL, then retry.")
                return None
            delay = base_delay * (2 ** (attempt - 1))
            print("[WARN] Retrying in {}s...".format(delay))
            sleep_func(delay)
        except requests.exceptions.RequestException as exc:
            print("[ERROR] Network request failed while {}: {}".format(action, exc))
            return None
    return None


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
    def __init__(self, wallet=None, wart_address=None, wart_pool=None,
                 bzminer_path=None, manage_bzminer=False, verbose=False, show_payload=False):
        self.node_url = NODE_URL
        self.wallet = wallet or self._gen_wallet()
        self.hw_info = {}
        self.enrolled = False
        self.attestation_valid_until = 0
        self.last_entropy = {}
        self.fingerprint_data = {}
        self.fingerprint_passed = False
        self.verbose = verbose
        self.show_payload = show_payload

        # Warthog dual-mining sidecar
        self.warthog = None
        if WARTHOG_AVAILABLE and wart_address:
            self.warthog = WarthogSidecar(
                wart_address=wart_address,
                pool_url=wart_pool,
                bzminer_path=bzminer_path,
                manage_bzminer=manage_bzminer,
            )

        self.serial = get_linux_serial()
        print("="*70)
        print(f"RustChain Local Miner - {platform.uname().system} {platform.uname().machine}")
        print("RIP-PoA Hardware Fingerprint + Serial Binding v2.0")
        if self.warthog:
            print("+ Warthog Dual-Mining Sidecar ACTIVE")
        print("="*70)
        print(f"Node: {self.node_url}")
        print(f"Wallet: {self.wallet}")
        print(f"Serial: {self.serial}")
        print("="*70)

        # Run initial fingerprint check
        if FINGERPRINT_AVAILABLE:
            self._run_fingerprint_checks()

    def _get(self, path, action, **kwargs):
        return _request_with_network_retry(
            requests.get,
            f"{self.node_url}{path}",
            action,
            **kwargs,
        )

    def _post(self, path, action, **kwargs):
        return _request_with_network_retry(
            requests.post,
            f"{self.node_url}{path}",
            action,
            **kwargs,
        )

    def check_node_connectivity(self):
        """Verify the configured RustChain node is reachable before mining."""
        resp = self._get("/health", "checking bootstrap connectivity", timeout=10, verify=TLS_VERIFY)
        if resp is None:
            return False
        if resp.status_code != 200:
            print(f"[ERROR] Bootstrap node health check failed: HTTP {resp.status_code}")
            return False
        return True

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
        data = f"{platform.node()}-{uuid.uuid4().hex}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:38] + "RTC"

    def _miner_id(self):
        return _miner_id_from_hw(self.hw_info)

    def _run_cmd(self, args):
        try:
            return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=10).stdout.strip()
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
        machine = platform.machine().lower()
        hw = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
            "family": "x86",
            "arch": machine or "modern",  # Use platform.machine() as primary source
            "serial": get_linux_serial()  # Hardware serial for v2 binding
        }

        # Detect architecture family from platform.machine() FIRST
        # Non-x86 devices must report their real architecture
        if machine in ('aarch64', 'arm64'):
            hw["family"] = "ARM"
            hw["arch"] = "aarch64"
        elif machine in ('armv7l', 'armv6l', 'armhf', 'arm'):
            hw["family"] = "ARM"
            hw["arch"] = "armv7"
        elif machine in ('ppc', 'ppc64', 'ppc64le', 'powerpc', 'powerpc64'):
            hw["family"] = "PowerPC"
            hw["arch"] = "powerpc"
        elif machine in ('sparc', 'sparc64', 'sun4u', 'sun4v'):
            hw["family"] = "SPARC"
            hw["arch"] = "sparc"
        elif machine in ('mips', 'mips64', 'mipsel', 'mips64el'):
            hw["family"] = "MIPS"
            hw["arch"] = "mips"
        elif machine in ('riscv64', 'riscv32', 'riscv'):
            hw["family"] = "RISC-V"
            hw["arch"] = "riscv"
        elif machine in ('m68k',):
            hw["family"] = "M68K"
            hw["arch"] = "68000"
        elif machine in ('ia64',):
            hw["family"] = "IA-64"
            hw["arch"] = "itanium"
        elif machine in ('s390', 's390x'):
            hw["family"] = "S390"
            hw["arch"] = "s390"
        elif machine.startswith('sh'):
            hw["family"] = "SuperH"
            hw["arch"] = machine

        # Get CPU
        cpu = _parse_lscpu_model(self._run_cmd(["lscpu"]))
        hw["cpu"] = cpu or "Unknown"

        # Get cores
        cores = self._run_cmd(["nproc"])
        hw["cores"] = int(cores) if cores else 6

        # Get memory
        mem = _parse_free_memory_gb(self._run_cmd(["free", "-g"]))
        hw["memory_gb"] = mem if mem is not None else 32

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
            # Get challenge (verify=TLS_VERIFY for self-signed certs)
            resp = self._post(
                "/attest/challenge",
                "requesting attestation challenge",
                json={},
                timeout=10,
                verify=TLS_VERIFY,
            )
            if resp is None:
                return False
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
            "miner_id": f"{self.hw_info.get('arch', platform.machine())}-{self.hw_info['hostname']}",
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
                "model": self.hw_info.get("cpu", "Unknown"),
                "cpu": self.hw_info["cpu"],
                "cores": self.hw_info["cores"],
                "memory_gb": self.hw_info["memory_gb"],
                "serial": self.hw_info.get("serial"),  # Hardware serial for v2 binding
                "machine": self.hw_info.get("machine", platform.machine()),
            },
            "signals": {
                "macs": self.hw_info.get("macs", [self.hw_info["mac"]]),
                "hostname": self.hw_info["hostname"]
            },
            # RIP-PoA hardware fingerprint attestation
            "fingerprint": self.fingerprint_data,
            # Warthog dual-mining proof (None if sidecar not active)
            "warthog": self.warthog.collect_proof() if self.warthog else None
        }

        try:
            resp = self._post(
                "/attest/submit",
                "submitting attestation",
                json=attestation,
                timeout=30,
                verify=TLS_VERIFY,
            )
            if resp is None:
                return False

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
            "miner_id": f"{self.hw_info.get('arch', platform.machine())}-{self.hw_info['hostname']}",
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            }
        }

        try:
            resp = self._post(
                "/epoch/enroll",
                "enrolling miner",
                json=payload,
                timeout=30,
                verify=TLS_VERIFY,
            )
            if resp is None:
                return False

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
            resp = self._get(f"/balance/{self.wallet}", "checking wallet balance", timeout=10, verify=TLS_VERIFY)
            if resp is None:
                return 0
            if resp.status_code == 200:
                result = resp.json()
                balance = result.get('balance_rtc', 0)
                print(f"\n💰 Balance: {balance} RTC")
                return balance
        except Exception as e:
            print(f"[WARN] Balance check failed: {e}")
        return 0


    def dry_run(self):
        """Preview miner setup without attesting/enrolling/mining."""
        print("\n[DRY-RUN] RustChain Linux Miner preflight")
        print("[DRY-RUN] No mining or network state will be modified")

        if self.verbose:
            print("[DRY-RUN] Verbose mode: ON")
            print(f"[DRY-RUN] Node URL: {self.node_url}")
            print(f"[DRY-RUN] API endpoint: {self.node_url}/health")
            print(f"[DRY-RUN] TLS verify: {True}")

        self._get_hw_info()
        print(f"[DRY-RUN] Node URL: {self.node_url}")
        print(f"[DRY-RUN] Wallet: {self.wallet}")
        print(f"[DRY-RUN] Hostname: {self.hw_info.get('hostname')}")
        print(f"[DRY-RUN] CPU: {self.hw_info.get('cpu')}")
        print(f"[DRY-RUN] Cores: {self.hw_info.get('cores')}")
        print(f"[DRY-RUN] Memory(GB): {self.hw_info.get('memory_gb')}")
        print(f"[DRY-RUN] MAC count: {len(self.hw_info.get('macs', []))}")
        print(f"[DRY-RUN] Serial present: {'yes' if self.hw_info.get('serial') else 'no'}")

        if FINGERPRINT_AVAILABLE:
            if not self.fingerprint_data:
                self._run_fingerprint_checks()
            print(f"[DRY-RUN] Fingerprint checks available: yes")
            print(f"[DRY-RUN] Fingerprint pass status: {self.fingerprint_passed}")
        else:
            print("[DRY-RUN] Fingerprint checks available: no")

        # Optional health probe (read-only)
        try:
            url = f"{self.node_url}/health"
            if self.verbose:
                print(f"[DRY-RUN] GET {url}")
                print(f"[DRY-RUN] Headers: {{'User-Agent': 'RustChain-Miner/2.2.1'}}")
            r = self._get("/health", "running dry-run health probe", timeout=8, verify=TLS_VERIFY)
            if r is None:
                return True
            print(f"[DRY-RUN] Health probe: HTTP {r.status_code}")
            if self.verbose:
                print(f"[DRY-RUN] Response headers: {dict(r.headers)}")
            if r.ok:
                data = r.json()
                print(f"[DRY-RUN] Node version: {data.get('version', 'n/a')}")
                if self.show_payload:
                    import json
                    print(f"[DRY-RUN] Response body: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"[DRY-RUN] Health probe failed: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()

        print("[DRY-RUN] Next real steps would be: attest -> enroll -> mine loop")
        return True

    def mine(self):
        """Start mining"""
        print(f"\n⛏️  Starting mining...")
        print(f"Block time: {BLOCK_TIME//60} minutes")
        print(f"Press Ctrl+C to stop\n")

        if not self.check_node_connectivity():
            print("[ERROR] Miner startup aborted before mining began.")
            return 1

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
            return 0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RustChain Miner with optional Warthog dual-mining")
    parser.add_argument("--version", "-v", action="version", version="RustChain Miner v2.2.1-rip200")
    parser.add_argument("--wallet", help="Wallet address")
    # Warthog dual-mining options
    parser.add_argument("--wart-address", help="Warthog wallet address (wart1q...) to enable dual-mining")
    parser.add_argument("--wart-pool", help="Warthog mining pool API URL")
    parser.add_argument("--bzminer-path", help="Path to BzMiner binary")
    parser.add_argument("--manage-bzminer", action="store_true", help="Auto-start/stop BzMiner")
    parser.add_argument("--dry-run", action="store_true", help="Run preflight checks only; do not start mining")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output showing API endpoints, headers, and response details")
    parser.add_argument("--show-payload", action="store_true", help="Show request payload in dry-run mode")
    args = parser.parse_args()

    miner = LocalMiner(
        wallet=args.wallet,
        wart_address=args.wart_address,
        wart_pool=args.wart_pool,
        bzminer_path=args.bzminer_path,
        manage_bzminer=args.manage_bzminer,
            verbose=args.verbose,
            show_payload=args.show_payload,
    )
    if args.dry_run:
        result = miner.dry_run()
    else:
        result = miner.mine()

    sys.exit(0 if result in (None, True) else int(result))
