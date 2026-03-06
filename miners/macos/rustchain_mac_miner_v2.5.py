#!/usr/bin/env python3
"""
RustChain Mac Universal Miner v2.5.0
Supports: Apple Silicon (M1/M2/M3), Intel Mac, PowerPC (G4/G5)
With RIP-PoA Hardware Fingerprint Attestation + Serial Binding v2.0
+ Embedded TLS Proxy Fallback for Legacy Macs (Tiger/Leopard)

New in v2.5:
  - Auto-detect TLS capability: try HTTPS direct, fall back to HTTP proxy
  - Proxy auto-discovery on LAN (192.168.0.160:8089)
  - Python 3.7+ compatible (no walrus, no f-string =)
  - Persistent launchd/cron integration helpers
  - Sleep-resistant: re-attest on wake automatically
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
import statistics
import re
import socket
from datetime import datetime

# Color helper stubs (no-op if terminal doesn't support ANSI)
def info(msg): return msg
def warning(msg): return msg
def success(msg): return msg
def error(msg): return msg

# Attempt to import requests; provide instructions if missing
try:
    import requests
except ImportError:
    print("[ERROR] 'requests' module not found.")
    print("  Install with: pip3 install requests --user")
    print("  Or: python3 -m pip install requests --user")
    sys.exit(1)

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

MINER_VERSION = "2.5.0"
NODE_URL = os.environ.get("RUSTCHAIN_NODE", "https://50.28.86.131")
PROXY_URL = os.environ.get("RUSTCHAIN_PROXY", "http://192.168.0.160:8089")
BLOCK_TIME = 600  # 10 minutes
LOTTERY_CHECK_INTERVAL = 10
ATTESTATION_TTL = 580  # Re-attest 20s before expiry


# ── Transport Layer (HTTPS direct or HTTP proxy) ────────────────────

class NodeTransport:
    """Handles communication with the RustChain node.

    Tries HTTPS directly first. If TLS fails (old Python/OpenSSL on
    Tiger/Leopard), falls back to the HTTP proxy on the NAS.
    """

    def __init__(self, node_url, proxy_url):
        self.node_url = node_url.rstrip("/")
        self.proxy_url = proxy_url.rstrip("/") if proxy_url else None
        self.use_proxy = False
        self._probe_transport()

    def _probe_transport(self):
        """Test if we can reach the node directly via HTTPS."""
        try:
            r = requests.get(
                self.node_url + "/health",
                timeout=10, verify=False
            )
            if r.status_code == 200:
                print(success("[TRANSPORT] Direct HTTPS to node: OK"))
                self.use_proxy = False
                return
        except requests.exceptions.SSLError:
            print(warning("[TRANSPORT] TLS failed (legacy OpenSSL?) - trying proxy..."))
        except Exception as e:
            print(warning("[TRANSPORT] Direct connection failed: {} - trying proxy...".format(e)))

        # Try the proxy
        if self.proxy_url:
            try:
                r = requests.get(
                    self.proxy_url + "/health",
                    timeout=10
                )
                if r.status_code == 200:
                    print(success("[TRANSPORT] HTTP proxy at {}: OK".format(self.proxy_url)))
                    self.use_proxy = True
                    return
            except Exception as e:
                print(warning("[TRANSPORT] Proxy {} also failed: {}".format(self.proxy_url, e)))

        # Last resort: try direct without verify (may work on some old systems)
        print(warning("[TRANSPORT] Falling back to direct HTTPS (verify=False)"))
        self.use_proxy = False

    @property
    def base_url(self):
        if self.use_proxy:
            return self.proxy_url
        return self.node_url

    def get(self, path, **kwargs):
        """GET request through whichever transport works."""
        kwargs.setdefault("timeout", 15)
        kwargs.setdefault("verify", False)
        url = self.base_url + path
        return requests.get(url, **kwargs)

    def post(self, path, **kwargs):
        """POST request through whichever transport works."""
        kwargs.setdefault("timeout", 15)
        kwargs.setdefault("verify", False)
        url = self.base_url + path
        return requests.post(url, **kwargs)


# ── Hardware Detection ──────────────────────────────────────────────

def get_mac_serial():
    """Get hardware serial number for macOS systems."""
    try:
        result = subprocess.run(
            ['system_profiler', 'SPHardwareDataType'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'Serial Number' in line:
                return line.split(':')[1].strip()
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['ioreg', '-l'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'IOPlatformSerialNumber' in line:
                return line.split('"')[-2]
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['system_profiler', 'SPHardwareDataType'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'Hardware UUID' in line:
                return line.split(':')[1].strip()[:16]
    except Exception:
        pass

    return None


def detect_hardware():
    """Auto-detect Mac hardware architecture."""
    machine = platform.machine().lower()

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
    except Exception:
        pass

    # Get memory
    try:
        result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                               capture_output=True, text=True, timeout=5)
        hw_info["memory_gb"] = int(result.stdout.strip()) // (1024**3)
    except Exception:
        pass

    # Apple Silicon Detection (M1/M2/M3/M4)
    if machine == 'arm64':
        hw_info["family"] = "Apple Silicon"
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                   capture_output=True, text=True, timeout=5)
            brand = result.stdout.strip()
            hw_info["cpu"] = brand

            if 'M4' in brand:
                hw_info["arch"] = "M4"
            elif 'M3' in brand:
                hw_info["arch"] = "M3"
            elif 'M2' in brand:
                hw_info["arch"] = "M2"
            elif 'M1' in brand:
                hw_info["arch"] = "M1"
            else:
                hw_info["arch"] = "apple_silicon"
        except Exception:
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

            if CPU_DETECTION_AVAILABLE:
                cpu_info = calculate_antiquity_multiplier(cpu_brand)
                hw_info["arch"] = cpu_info.architecture
                hw_info["cpu_vendor"] = cpu_info.vendor
                hw_info["cpu_year"] = cpu_info.microarch_year
                hw_info["cpu_generation"] = cpu_info.generation
                hw_info["is_server"] = cpu_info.is_server
            else:
                cpu_lower = cpu_brand.lower()
                if 'core 2' in cpu_lower or 'core(tm)2' in cpu_lower:
                    hw_info["arch"] = "core2"
                elif 'xeon' in cpu_lower and ('e5-16' in cpu_lower or 'e5-26' in cpu_lower):
                    hw_info["arch"] = "ivy_bridge"
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
        except Exception:
            hw_info["arch"] = "modern"
            hw_info["cpu"] = "Intel Mac"

    # PowerPC Detection (for vintage Macs)
    elif machine in ('ppc', 'ppc64', 'powerpc', 'powerpc64', 'Power Macintosh'):
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
        except Exception:
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
    except Exception:
        pass

    return hw_info


def collect_entropy(cycles=48, inner_loop=25000):
    """Collect timing entropy for hardware attestation."""
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


# ── Miner Class ─────────────────────────────────────────────────────

class MacMiner:
    def __init__(self, miner_id=None, wallet=None, node_url=None, proxy_url=None):
        self.hw_info = detect_hardware()
        self.fingerprint_data = {}
        self.fingerprint_passed = False

        # Generate miner_id from hardware
        if miner_id:
            self.miner_id = miner_id
        else:
            hw_hash = hashlib.sha256(
                "{}-{}".format(
                    self.hw_info['hostname'],
                    self.hw_info['serial'] or 'unknown'
                ).encode()
            ).hexdigest()[:8]
            arch = self.hw_info['arch'].lower().replace(' ', '_')
            self.miner_id = "{}-{}-{}".format(arch, self.hw_info['hostname'][:10], hw_hash)

        # Generate wallet address
        if wallet:
            self.wallet = wallet
        else:
            wallet_hash = hashlib.sha256(
                "{}-rustchain".format(self.miner_id).encode()
            ).hexdigest()[:38]
            family = self.hw_info['family'].lower().replace(' ', '_')
            self.wallet = "{}_{}RTC".format(family, wallet_hash)

        # Set up transport (HTTPS direct or HTTP proxy)
        self.transport = NodeTransport(
            node_url or NODE_URL,
            proxy_url or PROXY_URL
        )

        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.last_entropy = {}
        self._last_system_time = time.monotonic()

        self._print_banner()

        # Run initial fingerprint check
        if FINGERPRINT_AVAILABLE:
            self._run_fingerprint_checks()

    def _run_fingerprint_checks(self):
        """Run hardware fingerprint checks for RIP-PoA."""
        print(info("\n[FINGERPRINT] Running hardware fingerprint checks..."))
        try:
            passed, results = validate_all_checks()
            self.fingerprint_passed = passed
            self.fingerprint_data = {"checks": results, "all_passed": passed}
            if passed:
                print(success("[FINGERPRINT] All checks PASSED - eligible for full rewards"))
            else:
                failed = [k for k, v in results.items() if not v.get("passed")]
                print(warning("[FINGERPRINT] FAILED checks: {}".format(failed)))
                print(warning("[FINGERPRINT] WARNING: May receive reduced/zero rewards"))
        except Exception as e:
            print(error("[FINGERPRINT] Error running checks: {}".format(e)))
            self.fingerprint_passed = False
            self.fingerprint_data = {"error": str(e), "all_passed": False}

    def _print_banner(self):
        print("=" * 70)
        print("RustChain Mac Miner v{} - Serial Binding + Fingerprint".format(MINER_VERSION))
        print("=" * 70)
        print("Miner ID:    {}".format(self.miner_id))
        print("Wallet:      {}".format(self.wallet))
        print("Transport:   {}".format(
            "PROXY ({})".format(self.transport.proxy_url) if self.transport.use_proxy
            else "DIRECT ({})".format(self.transport.node_url)
        ))
        print("Serial:      {}".format(self.hw_info.get('serial', 'N/A')))
        print("-" * 70)
        print("Hardware:    {} / {}".format(self.hw_info['family'], self.hw_info['arch']))
        print("Model:       {}".format(self.hw_info['model']))
        print("CPU:         {}".format(self.hw_info['cpu']))
        print("Cores:       {}".format(self.hw_info['cores']))
        print("Memory:      {} GB".format(self.hw_info['memory_gb']))
        print("-" * 70)
        weight = self._get_expected_weight()
        print("Expected Weight: {}x (Proof of Antiquity)".format(weight))
        print("=" * 70)

    def _get_expected_weight(self):
        """Calculate expected PoA weight."""
        arch = self.hw_info['arch'].lower()
        family = self.hw_info['family'].lower()

        if family == 'powerpc':
            if arch == 'g3': return 3.0
            if arch == 'g4': return 2.5
            if arch == 'g5': return 2.0
        elif 'apple' in family or 'silicon' in family:
            if arch in ('m1', 'm2', 'm3', 'm4', 'apple_silicon'):
                return 1.2
        elif family == 'x86_64':
            if arch == 'core2': return 1.5
            return 1.0

        return 1.0

    def _detect_sleep_wake(self):
        """Detect if the machine slept (large time jump)."""
        now = time.monotonic()
        gap = now - self._last_system_time
        self._last_system_time = now
        # If more than 2x the check interval elapsed, we probably slept
        if gap > LOTTERY_CHECK_INTERVAL * 3:
            return True
        return False

    def attest(self):
        """Complete hardware attestation with fingerprint."""
        ts = datetime.now().strftime('%H:%M:%S')
        print(info("\n[{}] Attesting hardware...".format(ts)))

        try:
            resp = self.transport.post("/attest/challenge", json={}, timeout=15)
            if resp.status_code != 200:
                print(error("  ERROR: Challenge failed ({})".format(resp.status_code)))
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce", "")
            print(success("  Got challenge nonce: {}...".format(nonce[:16])))

        except Exception as e:
            print(error("  ERROR: Challenge error: {}".format(e)))
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
                "serial": self.hw_info.get("serial")
            },
            "signals": {
                "macs": self.hw_info.get("macs", [self.hw_info["mac"]]),
                "hostname": self.hw_info["hostname"]
            },
            "fingerprint": self.fingerprint_data,
            "miner_version": MINER_VERSION,
        }

        try:
            resp = self.transport.post("/attest/submit", json=attestation, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.attestation_valid_until = time.time() + ATTESTATION_TTL
                    print(success("  SUCCESS: Attestation accepted!"))
                    if self.fingerprint_passed:
                        print(success("  Fingerprint: PASSED"))
                    else:
                        print(warning("  Fingerprint: FAILED (reduced rewards)"))
                    return True
                else:
                    print(warning("  WARNING: {}".format(result)))
                    return False
            else:
                print(error("  ERROR: HTTP {}: {}".format(resp.status_code, resp.text[:200])))
                return False

        except Exception as e:
            print(error("  ERROR: {}".format(e)))
            return False

    def check_eligibility(self):
        """Check lottery eligibility."""
        try:
            resp = self.transport.get(
                "/lottery/eligibility",
                params={"miner_id": self.miner_id},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"eligible": False, "reason": "HTTP {}".format(resp.status_code)}
        except Exception as e:
            return {"eligible": False, "reason": str(e)}

    def submit_header(self, slot):
        """Submit header for slot."""
        try:
            message = "slot:{}:miner:{}:ts:{}".format(slot, self.miner_id, int(time.time()))
            message_hex = message.encode().hex()
            sig_data = hashlib.sha512(
                "{}{}".format(message, self.wallet).encode()
            ).hexdigest()

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

            resp = self.transport.post(
                "/headers/ingest_signed",
                json=header_payload,
                timeout=15,
            )

            self.shares_submitted += 1

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.shares_accepted += 1
                    return True, result
                return False, result
            return False, {"error": "HTTP {}".format(resp.status_code)}

        except Exception as e:
            return False, {"error": str(e)}

    def run(self):
        """Main mining loop with sleep-wake detection."""
        ts = datetime.now().strftime('%H:%M:%S')
        print("\n[{}] Starting miner...".format(ts))

        # Initial attestation
        while not self.attest():
            print("  Retrying attestation in 30 seconds...")
            time.sleep(30)

        last_slot = 0
        status_counter = 0

        while True:
            try:
                # Detect sleep/wake — force re-attest
                if self._detect_sleep_wake():
                    ts = datetime.now().strftime('%H:%M:%S')
                    print("\n[{}] Sleep/wake detected - re-attesting...".format(ts))
                    self.attestation_valid_until = 0

                # Re-attest if expired
                if time.time() > self.attestation_valid_until:
                    self.attest()

                # Check eligibility
                eligibility = self.check_eligibility()
                slot = eligibility.get("slot", 0)

                if eligibility.get("eligible"):
                    ts = datetime.now().strftime('%H:%M:%S')
                    print("\n[{}] ELIGIBLE for slot {}!".format(ts, slot))

                    if slot != last_slot:
                        ok, result = self.submit_header(slot)
                        if ok:
                            print("  Header ACCEPTED! Slot {}".format(slot))
                        else:
                            print("  Header rejected: {}".format(result))
                        last_slot = slot
                else:
                    reason = eligibility.get("reason", "unknown")
                    if reason == "not_attested":
                        ts = datetime.now().strftime('%H:%M:%S')
                        print("[{}] Not attested - re-attesting...".format(ts))
                        self.attest()

                # Status every ~60 seconds
                status_counter += 1
                if status_counter >= (60 // LOTTERY_CHECK_INTERVAL):
                    ts = datetime.now().strftime('%H:%M:%S')
                    print("[{}] Slot {} | Submitted: {} | Accepted: {}".format(
                        ts, slot, self.shares_submitted, self.shares_accepted
                    ))
                    status_counter = 0

                time.sleep(LOTTERY_CHECK_INTERVAL)

            except KeyboardInterrupt:
                print("\n\nShutting down miner...")
                break
            except Exception as e:
                ts = datetime.now().strftime('%H:%M:%S')
                print("[{}] Error: {}".format(ts, e))
                time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Mac Miner v{}".format(MINER_VERSION))
    parser.add_argument("--version", "-v", action="version",
                        version="rustchain-mac-miner {}".format(MINER_VERSION))
    parser.add_argument("--miner-id", "-m", help="Custom miner ID")
    parser.add_argument("--wallet", "-w", help="Custom wallet address")
    parser.add_argument("--node", "-n", default=NODE_URL, help="Node URL (default: {})".format(NODE_URL))
    parser.add_argument("--proxy", "-p", default=PROXY_URL,
                        help="HTTP proxy URL for legacy Macs (default: {})".format(PROXY_URL))
    parser.add_argument("--no-proxy", action="store_true",
                        help="Disable proxy fallback (HTTPS only)")
    args = parser.parse_args()

    node = args.node
    proxy = None if args.no_proxy else args.proxy

    miner = MacMiner(
        miner_id=args.miner_id,
        wallet=args.wallet,
        node_url=node,
        proxy_url=proxy,
    )
    miner.run()
