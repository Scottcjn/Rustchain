#!/usr/bin/env python3
"""
RustChain Universal Miner v2.3.0
Supports: PowerPC (G3/G4/G5), Apple Silicon (M1/M2/M3), x86_64 Linux/Windows
Automatically detects hardware and applies correct attestation flow
"""
import os
import sys
import json
import time
import hashlib
import platform
import subprocess
import requests
from datetime import datetime

# Terminal styling
NO_COLOR = bool(os.environ.get("NO_COLOR", "").strip())
GREEN = "\033[92m" if not NO_COLOR else ""
YELLOW = "\033[93m" if not NO_COLOR else ""
RED = "\033[91m" if not NO_COLOR else ""
CYAN = "\033[96m" if not NO_COLOR else ""
RESET = "\033[0m" if not NO_COLOR else ""


def emit(prefix, message, color, payload=None, json_mode=False):
    """Emit plain or JSON logs with status prefix."""
    if json_mode:
        event = {"event": prefix, "message": message, "timestamp": datetime.utcnow().isoformat() + "Z"}
        if payload:
            event.update(payload)
        print(json.dumps(event, ensure_ascii=False))
        return

    print(f"{color}[{prefix}]{RESET} {message}")

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "http://50.28.86.131:8088")
BLOCK_TIME = 600  # 10 minutes
ATTESTATION_INTERVAL = 300  # Re-attest every 5 minutes
LOTTERY_CHECK_INTERVAL = 10  # Check every 10 seconds

def detect_hardware():
    """Auto-detect hardware architecture and return profile"""
    machine = platform.machine().lower()
    system = platform.system().lower()

    hw_info = {
        "family": "unknown",
        "arch": "unknown",
        "model": platform.processor() or "unknown",
        "cpu": "unknown",
        "cores": os.cpu_count() or 1,
        "memory_gb": 4,
        "hostname": platform.node(),
        "os": system
    }

    # PowerPC Detection
    if machine in ('ppc', 'ppc64', 'powerpc', 'powerpc64'):
        hw_info["family"] = "PowerPC"

        # Try to detect specific PPC model
        try:
            if system == 'darwin':
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
            elif system == 'linux':
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
        except:
            hw_info["arch"] = "G4"  # Default to G4 for PPC
            hw_info["cpu"] = "PowerPC G4"

    # Apple Silicon Detection
    elif machine == 'arm64' and system == 'darwin':
        hw_info["family"] = "ARM"
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                   capture_output=True, text=True, timeout=5)
            brand = result.stdout.strip()
            if 'M3' in brand:
                hw_info["arch"] = "M3"
                hw_info["cpu"] = brand
            elif 'M2' in brand:
                hw_info["arch"] = "M2"
                hw_info["cpu"] = brand
            elif 'M1' in brand:
                hw_info["arch"] = "M1"
                hw_info["cpu"] = brand
            else:
                hw_info["arch"] = "Apple Silicon"
                hw_info["cpu"] = brand or "Apple Silicon"
        except:
            hw_info["arch"] = "M1"
            hw_info["cpu"] = "Apple M1"

    # x86_64 Detection
    elif machine in ('x86_64', 'amd64', 'x64'):
        hw_info["family"] = "x86_64"
        try:
            if system == 'linux':
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            hw_info["cpu"] = line.split(':')[1].strip()
                            break
            elif system == 'darwin':
                result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                       capture_output=True, text=True, timeout=5)
                hw_info["cpu"] = result.stdout.strip()
            elif system == 'windows':
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                hw_info["cpu"] = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        except:
            hw_info["cpu"] = "x86_64"

        # Detect if Intel Core 2 (vintage bonus)
        if hw_info["cpu"] and 'core 2' in hw_info["cpu"].lower():
            hw_info["arch"] = "Core2"
        else:
            hw_info["arch"] = "modern"

    # ARM Linux
    elif machine.startswith('arm') or machine == 'aarch64':
        hw_info["family"] = "ARM"
        hw_info["arch"] = "aarch64" if machine == 'aarch64' else "arm32"
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line.lower() or 'hardware' in line.lower():
                        hw_info["cpu"] = line.split(':')[1].strip()
                        break
        except:
            hw_info["cpu"] = machine

    # Try to get memory
    try:
        if system == 'linux':
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        kb = int(line.split()[1])
                        hw_info["memory_gb"] = round(kb / 1024 / 1024)
                        break
        elif system == 'darwin':
            result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                                   capture_output=True, text=True, timeout=5)
            hw_info["memory_gb"] = int(result.stdout.strip()) // (1024**3)
    except:
        pass

    return hw_info


class UniversalMiner:
    def __init__(self, miner_id=None, json_mode=False, dry_run=False):
        self.node_url = NODE_URL
        self.hw_info = detect_hardware()
        self.json_mode = json_mode
        self.dry_run = dry_run

        # Generate miner_id if not provided
        if miner_id:
            self.miner_id = miner_id
        else:
            hw_hash = hashlib.sha256(f"{self.hw_info['hostname']}-{self.hw_info['cpu']}".encode()).hexdigest()[:8]
            self.miner_id = f"{self.hw_info['arch'].lower()}-{self.hw_info['hostname'][:10]}-{hw_hash}"

        # Generate wallet address
        wallet_hash = hashlib.sha256(f"{self.miner_id}-rustchain".encode()).hexdigest()[:38]
        self.wallet = f"{self.hw_info['family'].lower()}_{wallet_hash}RTC"

        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0

        self._print_banner()

    def _print_banner(self):
        weight = self._get_expected_weight()
        emit("INFO", "RustChain Universal Miner v2.3.0", CYAN, {
            "miner_id": self.miner_id,
            "wallet": self.wallet,
            "node": self.node_url,
            "weight": weight
        }, json_mode=self.json_mode)
        emit("INFO", "System profile", CYAN, {
            "hardware_family": self.hw_info['family'],
            "hardware_arch": self.hw_info['arch'],
            "cpu": self.hw_info['cpu'],
            "cores": self.hw_info['cores'],
            "memory_gb": self.hw_info['memory_gb'],
            "os": self.hw_info['os'],
        }, json_mode=self.json_mode)
        if not self.json_mode:
            print("=" * 70)
            print(f"Expected Weight: {weight}x (Proof of Antiquity)")
            print("=" * 70)

    def _log(self, event, message, payload=None):
        if payload is None:
            payload = {}
        event_map = {
            "GREEN": "OK",
            "YELLOW": "WAIT",
            "RED": "ERR",
            "CYAN": "INFO",
        }
        color_map = {
            "GREEN": GREEN,
            "YELLOW": YELLOW,
            "RED": RED,
            "CYAN": CYAN,
        }
        label = event_map.get(event, event)
        emit(label.lower(), message, color_map.get(event, CYAN), {"miner_id": self.miner_id, **payload}, json_mode=self.json_mode)

    def _get_expected_weight(self):
        """Calculate expected PoA weight based on hardware"""
        arch = self.hw_info['arch'].lower()
        family = self.hw_info['family'].lower()

        if family == 'powerpc':
            if arch == 'g3': return 3.0
            if arch == 'g4': return 2.5
            if arch == 'g5': return 2.0
        elif family == 'arm':
            if arch in ('m1', 'm2', 'm3', 'apple silicon'): return 1.2
        elif family == 'x86_64':
            if arch == 'core2': return 1.5
            return 0.8  # Modern x86 penalty

        return 1.0

    def attest(self):
        """Complete hardware attestation with RIP server"""
        self._log("CYAN", f"\n[{datetime.now().strftime('%H:%M:%S')}] Attesting hardware...")

        try:
            # Step 1: Get challenge nonce
            if self.dry_run:
                self._log("CYAN", "Dry-run mode: simulated attestation challenge")
                self.attestation_valid_until = time.time() + ATTESTATION_INTERVAL
                return True
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=15)
            if resp.status_code != 200:
                self._log("RED", f"  ERROR: Challenge failed ({resp.status_code})")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce", "")
            self._log("CYAN", f"  Got challenge nonce: {nonce[:16]}...")

            # Step 2: Build attestation payload
            commitment = hashlib.sha256(f"{nonce}{self.wallet}{self.miner_id}".encode()).hexdigest()

            attestation = {
                "miner": self.miner_id,  # KEY FIX: Use miner_id for lottery compatibility
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
                    "hostname": self.hw_info["hostname"],
                    "os": self.hw_info["os"],
                    "timestamp": int(time.time())
                }
            }

            # Step 3: Submit attestation
            resp = requests.post(f"{self.node_url}/attest/submit",
                               json=attestation, timeout=15)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok") or result.get("status") == "accepted":
                    self.attestation_valid_until = time.time() + ATTESTATION_INTERVAL
                    self._log("GREEN", f"  SUCCESS: Attestation accepted!")
                    self._log("GREEN", f"  Ticket: {result.get('ticket_id', 'N/A')}")
                    return True
                else:
                    self._log("YELLOW", f"  WARNING: {result}")
                    return False
            else:
                self._log("RED", f"  ERROR: Attestation failed ({resp.status_code})")
                return False

        except Exception as e:
            self._log("RED", f"  ERROR: {e}")
            return False

    def check_eligibility(self):
        """Check if we're eligible for the current lottery slot"""
        try:
            if self.dry_run:
                self._log("CYAN", "Dry-run mode: skipping eligibility", {"slot": 0, "eligible": False})
                return {"eligible": False, "slot": 0}
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
        """Submit a signed header for the current slot"""
        try:
            # Create header message
            message = f"slot:{slot}:miner:{self.miner_id}:ts:{int(time.time())}"
            message_hex = message.encode().hex()

            # Simple signature (in production, use proper ed25519)
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

            if self.dry_run:
                self._log("CYAN", f"Dry-run mode: simulated header submit", {"slot": slot})
                self.shares_submitted += 1
                self.shares_accepted += 1
                return True, {"dry_run": True}

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
        self._log("CYAN", f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting miner...")

        # Initial attestation
        while not self.attest():
            self._log("YELLOW", "  Retrying attestation in 30 seconds...")
            time.sleep(30)

        last_slot = 0

        while True:
            try:
                # Re-attest if needed
                if time.time() > self.attestation_valid_until:
                    self.attest()

                # Check lottery eligibility
                eligibility = self.check_eligibility()
                slot = eligibility.get("slot", 0)

                if eligibility.get("eligible"):
                    self._log("GREEN", f"\n[{datetime.now().strftime('%H:%M:%S')}] ELIGIBLE for slot {slot}!")

                    if slot != last_slot:
                        # Submit header
                        success, result = self.submit_header(slot)
                        if success:
                            self._log("GREEN", f"  Header ACCEPTED! Slot {slot}")
                        else:
                            self._log("RED", f"  Header rejected: {result}")
                        last_slot = slot
                else:
                    reason = eligibility.get("reason", "unknown")
                    if reason == "not_attested":
                        self._log("YELLOW", f"[{datetime.now().strftime('%H:%M:%S')}] Not attested - re-attesting...")
                        self.attest()
                    else:
                        # Normal not-eligible, just wait
                        pass

                # Status update every 60 seconds
                if int(time.time()) % 60 == 0:
                    self._log("CYAN", f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} | "
                          f"Submitted: {self.shares_submitted} | "
                          f"Accepted: {self.shares_accepted}")

                time.sleep(LOTTERY_CHECK_INTERVAL)

            except KeyboardInterrupt:
                self._log("YELLOW", "\n\nShutting down miner...")
                break
            except Exception as e:
                self._log("RED", f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Universal Miner")
    parser.add_argument("--version", "-v", action="version", version="clawrtc 1.5.0")
    parser.add_argument("--json", action="store_true", help="Emit logs as JSON lines")
    parser.add_argument("--miner-id", "-m", help="Custom miner ID")
    parser.add_argument("--node", "-n", default=NODE_URL, help="RIP node URL")
    parser.add_argument("--dry-run", action="store_true", help="Skip network requests and print planned output")
    args = parser.parse_args()

    if args.node:
        NODE_URL = args.node

    miner = UniversalMiner(miner_id=args.miner_id, json_mode=args.json, dry_run=args.dry_run)
    miner.run()
