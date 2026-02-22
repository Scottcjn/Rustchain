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
    def __init__(self, miner_id=None, json_mode=False):
        self.node_url = NODE_URL
        self.hw_info = detect_hardware()
        self.json_mode = json_mode

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

        if self.json_mode:
            self.emit("startup", wallet=self.wallet, node=self.node_url, 
                     hardware={"arch": self.hw_info["arch"], "family": self.hw_info["family"]})
        else:
            self._print_banner()

    def emit(self, event_type, **data):
        """Output either JSON or human-readable text based on json_mode"""
        if self.json_mode:
            output = {"event": event_type, "timestamp": int(time.time()), **data}
            print(json.dumps(output))
        else:
            # Human-readable output
            if event_type == "startup":
                pass  # Already handled in _print_banner
            elif event_type == "attestation":
                status = data.get("status", "unknown")
                epoch = data.get("epoch", 0)
                slot = data.get("slot", 0)
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attestation: {status} (epoch={epoch}, slot={slot})")
            elif event_type == "attestation_error":
                print(f"  ERROR: {data.get('message')}")
            elif event_type == "eligible":
                slot = data.get("slot", 0)
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ELIGIBLE for slot {slot}!")
            elif event_type == "header_accepted":
                slot = data.get("slot", 0)
                print(f"  Header ACCEPTED! Slot {slot}")
            elif event_type == "header_rejected":
                print(f"  Header rejected: {data.get('message')}")
            elif event_type == "status":
                slot = data.get("slot", 0)
                submitted = data.get("submitted", 0)
                accepted = data.get("accepted", 0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Slot {slot} | Submitted: {submitted} | Accepted: {accepted}")

    def _print_banner(self):
        print("=" * 70)
        print("RustChain Universal Miner v2.3.0")
        print("=" * 70)
        print(f"Miner ID:    {self.miner_id}")
        print(f"Wallet:      {self.wallet}")
        print(f"Node:        {self.node_url}")
        print("-" * 70)
        print(f"Hardware:    {self.hw_info['family']} / {self.hw_info['arch']}")
        print(f"CPU:         {self.hw_info['cpu']}")
        print(f"Cores:       {self.hw_info['cores']}")
        print(f"Memory:      {self.hw_info['memory_gb']} GB")
        print(f"OS:          {self.hw_info['os']}")
        print("-" * 70)

        # Show expected PoA weight
        weight = self._get_expected_weight()
        print(f"Expected Weight: {weight}x (Proof of Antiquity)")
        print("=" * 70)

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
        self.emit("attestation", status="in_progress")

        try:
            # Step 1: Get challenge nonce
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=15)
            if resp.status_code != 200:
                self.emit("attestation_error", message=f"Challenge failed ({resp.status_code})")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce", "")
            if not self.json_mode:
                print(f"  Got challenge nonce: {nonce[:16]}...")

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
                    self.emit("attestation", status="success", ticket_id=result.get('ticket_id', 'N/A'))
                    return True
                else:
                    self.emit("attestation_error", message=str(result))
                    return False
            else:
                self.emit("attestation_error", message=f"Attestation failed ({resp.status_code})")
                return False

        except Exception as e:
            self.emit("attestation_error", message=str(e))
            return False

    def check_eligibility(self):
        """Check if we're eligible for the current lottery slot"""
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
        self.emit("startup", status="miner_running")

        # Initial attestation
        while not self.attest():
            if not self.json_mode:
                print("  Retrying attestation in 30 seconds...")
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
                    self.emit("eligible", slot=slot)

                    if slot != last_slot:
                        # Submit header
                        success, result = self.submit_header(slot)
                        if success:
                            self.emit("header_accepted", slot=slot)
                        else:
                            self.emit("header_rejected", message=str(result))
                        last_slot = slot
                else:
                    reason = eligibility.get("reason", "unknown")
                    if reason == "not_attested":
                        self.emit("attestation", status="re-attesting")
                        self.attest()
                    else:
                        # Normal not-eligible, just wait
                        pass

                # Status update every 60 seconds
                if int(time.time()) % 60 == 0:
                    self.emit("status", slot=slot, submitted=self.shares_submitted, accepted=self.shares_accepted)

                time.sleep(LOTTERY_CHECK_INTERVAL)

            except KeyboardInterrupt:
                if not self.json_mode:
                    print("\n\nShutting down miner...")
                break
            except Exception as e:
                self.emit("error", message=str(e))
                time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Universal Miner")
    parser.add_argument("--miner-id", "-m", help="Custom miner ID")
    parser.add_argument("--node", "-n", default=NODE_URL, help="RIP node URL")
    parser.add_argument("--json", action="store_true", help="Output structured JSON instead of human-readable text")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (don't actually mine)")
    args = parser.parse_args()

    if args.node:
        NODE_URL = args.node

    miner = UniversalMiner(miner_id=args.miner_id, json_mode=args.json)
    if args.dry_run and args.json:
        # In dry-run + JSON mode, just emit startup event and exit
        print(json.dumps({"event": "ready", "status": "dry-run complete"}))
    else:
        miner.run()
