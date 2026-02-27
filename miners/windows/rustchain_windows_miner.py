#!/usr/bin/env python3
"""
RustChain Windows Wallet Miner
Full-featured wallet and miner for Windows
With RIP-PoA Hardware Fingerprint Attestation + HTTPS + Auto-Update
"""

MINER_VERSION = "1.6.0"

import warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

import os
import sys
import time
import json
import hashlib
import platform
import threading
import statistics
import uuid
import subprocess
import re
import shutil
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    TK_AVAILABLE = True
    _TK_IMPORT_ERROR = ""
except Exception as e:
    # Windows embeddable Python often ships without Tcl/Tk. We support headless mode.
    TK_AVAILABLE = False
    _TK_IMPORT_ERROR = str(e)
    tk = None
    ttk = None
    messagebox = None
    scrolledtext = None
import requests
from datetime import datetime
from pathlib import Path
import argparse

# Import fingerprint checks for RIP-PoA
try:
    from fingerprint_checks import validate_all_checks
    FINGERPRINT_AVAILABLE = True
except ImportError:
    FINGERPRINT_AVAILABLE = False
    print("[WARN] fingerprint_checks.py not found - fingerprint attestation disabled")

# Configuration - Use HTTPS (self-signed cert on server)
RUSTCHAIN_API = "https://50.28.86.131"
WALLET_DIR = Path.home() / ".rustchain"
CONFIG_FILE = WALLET_DIR / "config.json"
WALLET_FILE = WALLET_DIR / "wallet.json"

# Auto-update configuration
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows"
UPDATE_CHECK_INTERVAL = 3600  # Check for updates every hour
UPDATE_FILES = ["rustchain_windows_miner.py", "fingerprint_checks.py"]


# ── Auto-Update ──────────────────────────────────────────────────────────

def check_for_updates(miner_dir):
    """Check GitHub for newer miner files and apply updates.

    Preserves the current wallet/miner_id configuration across updates.
    Returns True if an update was applied and a restart is needed.
    """
    updated = False
    for filename in UPDATE_FILES:
        try:
            url = f"{GITHUB_RAW_BASE}/{filename}"
            resp = requests.get(url, timeout=15, verify=False)
            if resp.status_code != 200:
                continue

            remote_content = resp.text
            local_path = miner_dir / filename

            # Read local file
            local_content = ""
            if local_path.exists():
                with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                    local_content = f.read()

            # Compare by hash (ignore line-ending differences)
            local_hash = hashlib.sha256(local_content.strip().encode()).hexdigest()
            remote_hash = hashlib.sha256(remote_content.strip().encode()).hexdigest()

            if local_hash == remote_hash:
                continue

            # Extract remote version for the miner
            if filename == "rustchain_windows_miner.py":
                remote_ver = ""
                for line in remote_content.splitlines()[:15]:
                    if line.startswith("MINER_VERSION"):
                        remote_ver = line.split("=")[1].strip().strip('"').strip("'")
                        break
                if remote_ver:
                    print(f"[UPDATE] {filename}: {MINER_VERSION} -> {remote_ver}", flush=True)
                else:
                    print(f"[UPDATE] {filename}: new version available", flush=True)

            # Backup current file
            backup_path = local_path.with_suffix(".bak")
            if local_path.exists():
                shutil.copy2(local_path, backup_path)

            # Write new file
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(remote_content)
            print(f"[UPDATE] {filename} updated (backup: {backup_path.name})", flush=True)
            updated = True

        except Exception as e:
            print(f"[UPDATE] Failed to check {filename}: {e}", flush=True)

    return updated


def auto_update_and_restart(miner_dir, argv):
    """Check for updates, and if found, restart the miner process.

    The --wallet argument is always preserved across restarts so the
    miner_id stays the same after an update.
    """
    try:
        if check_for_updates(miner_dir):
            print("[UPDATE] Restarting miner with updated code...", flush=True)
            # Re-exec with same arguments to pick up new code
            python = sys.executable
            os.execv(python, [python] + sys.argv)
    except Exception as e:
        print(f"[UPDATE] Auto-restart failed: {e}", flush=True)


# ── Wallet ───────────────────────────────────────────────────────────────

class RustChainWallet:
    """Windows wallet for RustChain"""
    def __init__(self):
        self.wallet_dir = WALLET_DIR
        self.wallet_dir.mkdir(exist_ok=True)
        self.wallet_data = self.load_wallet()

    def load_wallet(self):
        """Load or create wallet"""
        if WALLET_FILE.exists():
            with open(WALLET_FILE, 'r') as f:
                return json.load(f)
        else:
            return self.create_new_wallet()

    def create_new_wallet(self):
        """Create new wallet with address"""
        timestamp = str(int(time.time()))
        random_data = os.urandom(32).hex()
        wallet_seed = hashlib.sha256(f"{timestamp}{random_data}".encode()).hexdigest()

        wallet_data = {
            "address": f"{wallet_seed[:40]}RTC",
            "balance": 0.0,
            "created": datetime.now().isoformat(),
            "transactions": []
        }

        self.save_wallet(wallet_data)
        return wallet_data

    def save_wallet(self, wallet_data=None):
        """Save wallet data"""
        if wallet_data:
            self.wallet_data = wallet_data
        with open(WALLET_FILE, 'w') as f:
            json.dump(self.wallet_data, f, indent=2)


# ── Miner ────────────────────────────────────────────────────────────────

class RustChainMiner:
    """Mining engine for RustChain with RIP-PoA fingerprint attestation"""
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address
        self.mining = False
        self.shares_submitted = 0
        self.shares_accepted = 0
        # Use wallet address directly as miner_id for consistency across updates
        self.miner_id = wallet_address
        self.node_url = RUSTCHAIN_API
        self.attestation_valid_until = 0
        self.last_enroll = 0
        self.enrolled = False
        self.hw_info = self._get_hw_info()
        self.last_entropy = {}
        self.fingerprint_data = {}
        self.fingerprint_passed = False
        self.last_update_check = 0
        self.miner_dir = Path(__file__).resolve().parent
        self.callback = None

        # Run initial fingerprint check
        if FINGERPRINT_AVAILABLE:
            self._run_fingerprint_checks()

    def _run_fingerprint_checks(self):
        """Run hardware fingerprint checks for RIP-PoA"""
        print("\n[FINGERPRINT] Running hardware fingerprint checks...", flush=True)
        try:
            passed, results = validate_all_checks()
            self.fingerprint_passed = passed
            self.fingerprint_data = {"checks": results, "all_passed": passed}
            if passed:
                print("[FINGERPRINT] All checks PASSED - eligible for full rewards", flush=True)
            else:
                failed = [k for k, v in results.items() if not v.get("passed")]
                print(f"[FINGERPRINT] FAILED checks: {failed}", flush=True)
                print("[FINGERPRINT] WARNING: May receive reduced/zero rewards", flush=True)
        except Exception as e:
            print(f"[FINGERPRINT] Error running checks: {e}", flush=True)
            self.fingerprint_passed = False
            self.fingerprint_data = {"error": str(e), "all_passed": False}

    def start_mining(self, callback=None):
        """Start mining process"""
        self.callback = callback
        self.mining = True
        self.mining_thread = threading.Thread(target=self._mine_loop, args=(callback,))
        self.mining_thread.daemon = True
        self.mining_thread.start()

    def _emit(self, event):
        """Emit structured event to callback if available."""
        cb = self.callback
        if cb:
            try:
                cb(event)
            except Exception:
                pass

    def stop_mining(self):
        """Stop mining"""
        self.mining = False

    def _mine_loop(self, callback):
        """Main mining loop"""
        while self.mining:
            try:
                # Periodic auto-update check
                now = time.time()
                if now - self.last_update_check > UPDATE_CHECK_INTERVAL:
                    self.last_update_check = now
                    auto_update_and_restart(self.miner_dir, sys.argv)

                if not self._ensure_ready(callback):
                    time.sleep(10)
                    continue

                # Check eligibility
                eligible = self.check_eligibility()
                if eligible:
                    header = self.generate_header()
                    success = self.submit_header(header)
                    self.shares_submitted += 1
                    if success:
                        self.shares_accepted += 1
                    if callback:
                        callback({
                            "type": "share",
                            "submitted": self.shares_submitted,
                            "accepted": self.shares_accepted,
                            "success": success
                        })
                self._emit({"type": "heartbeat", "shares_submitted": self.shares_submitted, "shares_accepted": self.shares_accepted, "enrolled": self.enrolled, "attestation_valid_for_sec": max(0, int(self.attestation_valid_until - time.time()))})
                time.sleep(10)
            except Exception as e:
                if callback:
                    callback({"type": "error", "message": str(e)})
                time.sleep(30)

    def _ensure_ready(self, callback):
        """Ensure we have a fresh attestation and current epoch enrollment."""
        now = time.time()

        if now >= self.attestation_valid_until - 60:
            self._emit({"type": "attestation", "stage": "started"})
            if not self.attest():
                self._emit({"type": "attestation", "stage": "failed"})
                if callback:
                    callback({"type": "error", "message": "Attestation failed"})
                return False

        if (now - self.last_enroll) > 3600 or not self.enrolled:
            self._emit({"type": "enroll", "stage": "started"})
            if not self.enroll():
                self._emit({"type": "enroll", "stage": "failed"})
                if callback:
                    callback({"type": "error", "message": "Epoch enrollment failed"})
                return False

        return True

    def _get_mac_addresses(self):
        macs = set()

        try:
            node_mac = uuid.getnode()
            if node_mac:
                mac = ":".join(f"{(node_mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))
                macs.add(mac)
        except Exception:
            pass

        creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            output = subprocess.check_output(
                ["getmac", "/fo", "csv", "/nh"],
                stderr=subprocess.DEVNULL,
                creationflags=creation_flag
            ).decode("utf-8", "ignore").splitlines()
            for line in output:
                m = re.search(r"([0-9A-Fa-f:-]{17})", line)
                if m:
                    mac = m.group(1).replace("-", ":").lower()
                    if mac != "00:00:00:00:00:00":
                        macs.add(mac)
        except Exception:
            pass

        return list(macs) or ["00:00:00:00:00:01"]

    def _get_hw_info(self):
        return {
            "platform": platform.system(),
            "machine": platform.machine(),
            "model": platform.machine() or "Windows-PC",
            "hostname": platform.node(),
            "family": "Windows",
            "arch": platform.processor() or "x86_64",
            "macs": self._get_mac_addresses()
        }

    def _collect_entropy(self, cycles=48, inner=30000):
        samples = []
        for _ in range(cycles):
            start = time.perf_counter_ns()
            acc = 0
            for j in range(inner):
                acc ^= (j * 29) & 0xFFFFFFFF
            samples.append(time.perf_counter_ns() - start)

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

    def attest(self):
        """Perform hardware attestation for PoA with fingerprint data."""
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{ts}] Attesting to {self.node_url}...", flush=True)

        try:
            resp = requests.post(f"{self.node_url}/attest/challenge", json={},
                               timeout=10, verify=False)
            if resp.status_code != 200:
                print(f"[FAIL] Challenge failed: HTTP {resp.status_code}", flush=True)
                return False
            challenge = resp.json()
            nonce = challenge.get("nonce")
            print(f"[OK] Got challenge nonce", flush=True)
        except Exception as e:
            print(f"[FAIL] Challenge error: {e}", flush=True)
            return False

        entropy = self._collect_entropy()
        self.last_entropy = entropy

        # Re-run fingerprint checks if we don't have data yet
        if FINGERPRINT_AVAILABLE and not self.fingerprint_data:
            self._run_fingerprint_checks()

        report_payload = {
            "nonce": nonce,
            "commitment": hashlib.sha256(
                (nonce + self.wallet_address + json.dumps(entropy, sort_keys=True)).encode()
            ).hexdigest(),
            "derived": entropy,
            "entropy_score": entropy.get("variance_ns", 0.0)
        }

        attestation = {
            "miner": self.wallet_address,
            "miner_id": self.miner_id,
            "nonce": nonce,
            "report": report_payload,
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"],
                "model": self.hw_info.get("model") or self.hw_info.get("machine"),
                "cpu": platform.processor(),
                "cores": os.cpu_count()
            },
            "signals": {
                "macs": self.hw_info["macs"],
                "hostname": self.hw_info["hostname"]
            },
            # RIP-PoA hardware fingerprint attestation
            "fingerprint": self.fingerprint_data if self.fingerprint_data else None
        }

        try:
            resp = requests.post(f"{self.node_url}/attest/submit",
                               json=attestation, timeout=30, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.attestation_valid_until = time.time() + 580
                    print(f"[PASS] Attestation accepted!", flush=True)
                    print(f"   CPU: {platform.processor()}", flush=True)
                    print(f"   Arch: {self.hw_info.get('machine', 'x86_64')}/{self.hw_info.get('arch', 'modern')}", flush=True)
                    if self.fingerprint_passed:
                        print(f"   Fingerprint: PASSED", flush=True)
                    elif FINGERPRINT_AVAILABLE:
                        print(f"   Fingerprint: FAILED (reduced rewards)", flush=True)
                    else:
                        print(f"   Fingerprint: N/A (module not available)", flush=True)
                    self._emit({"type": "attestation", "stage": "success", "valid_for_sec": max(0, int(self.attestation_valid_until - time.time()))})
                    return True
                else:
                    print(f"[FAIL] Rejected: {result}", flush=True)
            else:
                print(f"[FAIL] HTTP {resp.status_code}: {resp.text[:200]}", flush=True)
        except Exception as e:
            print(f"[FAIL] Submit error: {e}", flush=True)

        self._emit({"type": "attestation", "stage": "failed"})
        return False

    def enroll(self):
        """Enroll the miner into the current epoch after attesting."""
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{ts}] Enrolling in epoch...", flush=True)

        payload = {
            "miner_pubkey": self.wallet_address,
            "miner_id": self.miner_id,
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/epoch/enroll",
                               json=payload, timeout=15, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.enrolled = True
                    self.last_enroll = time.time()
                    weight = result.get('weight', 1.0)
                    print(f"[OK] Enrolled! Epoch: {result.get('epoch')} Weight: {weight}x", flush=True)
                    self._emit({"type": "enroll", "stage": "success", "epoch": result.get("epoch"), "weight": weight})
                    return True
                else:
                    print(f"[FAIL] Enroll rejected: {result}", flush=True)
            else:
                print(f"[FAIL] Enroll HTTP {resp.status_code}: {resp.text[:200]}", flush=True)
        except Exception as e:
            print(f"[FAIL] Enroll error: {e}", flush=True)
        self._emit({"type": "enroll", "stage": "failed"})
        return False

    def check_eligibility(self):
        """Check if eligible to mine"""
        try:
            response = requests.get(
                f"{self.node_url}/lottery/eligibility?miner_id={self.miner_id}",
                timeout=10, verify=False)
            if response.ok:
                data = response.json()
                return data.get("eligible", False)
        except:
            pass
        return False

    def check_balance(self):
        """Check RTC balance"""
        try:
            resp = requests.get(f"{self.node_url}/balance/{self.wallet_address}",
                              timeout=10, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                return result.get('balance_rtc', 0)
        except:
            pass
        return 0

    def generate_header(self):
        """Generate mining header"""
        timestamp = int(time.time())
        nonce = os.urandom(4).hex()
        header = {
            "miner_id": self.miner_id,
            "wallet": self.wallet_address,
            "timestamp": timestamp,
            "nonce": nonce
        }
        header_str = json.dumps(header, sort_keys=True)
        header["hash"] = hashlib.sha256(header_str.encode()).hexdigest()
        return header

    def submit_header(self, header):
        """Submit mining header"""
        try:
            response = requests.post(f"{self.node_url}/headers/ingest_signed",
                                    json=header, timeout=5, verify=False)
            return response.status_code == 200
        except:
            return False


# ── GUI ──────────────────────────────────────────────────────────────────

class RustChainGUI:
    """Windows GUI for RustChain"""
    def __init__(self):
        if not TK_AVAILABLE:
            raise RuntimeError(f"tkinter is not available: {_TK_IMPORT_ERROR}")
        self.root = tk.Tk()
        self.root.title("RustChain Wallet & Miner for Windows")
        self.root.geometry("800x600")
        self.wallet = RustChainWallet()
        self.miner = RustChainMiner(self.wallet.wallet_data["address"])
        self.setup_gui()
        self.update_stats()

    def setup_gui(self):
        """Setup GUI elements"""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Wallet tab
        wallet_frame = ttk.Frame(notebook)
        notebook.add(wallet_frame, text="Wallet")
        self.setup_wallet_tab(wallet_frame)

        # Miner tab
        miner_frame = ttk.Frame(notebook)
        notebook.add(miner_frame, text="Miner")
        self.setup_miner_tab(miner_frame)

    def setup_wallet_tab(self, parent):
        """Setup wallet interface"""
        info_frame = ttk.LabelFrame(parent, text="Wallet Information", padding=10)
        info_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(info_frame, text="Address:").grid(row=0, column=0, sticky="w")
        self.address_label = ttk.Label(info_frame, text=self.wallet.wallet_data["address"])
        self.address_label.grid(row=0, column=1, sticky="w")

        ttk.Label(info_frame, text="Balance:").grid(row=1, column=0, sticky="w")
        self.balance_label = ttk.Label(info_frame, text=f"{self.wallet.wallet_data['balance']:.8f} RTC")
        self.balance_label.grid(row=1, column=1, sticky="w")

    def setup_miner_tab(self, parent):
        """Setup miner interface"""
        control_frame = ttk.LabelFrame(parent, text="Mining Control", padding=10)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.mine_button = ttk.Button(control_frame, text="Start Mining", command=self.toggle_mining)
        self.mine_button.pack(pady=10)

        stats_frame = ttk.LabelFrame(parent, text="Mining Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(stats_frame, text="Shares Submitted:").grid(row=0, column=0, sticky="w")
        self.shares_label = ttk.Label(stats_frame, text="0")
        self.shares_label.grid(row=0, column=1, sticky="w")

        ttk.Label(stats_frame, text="Shares Accepted:").grid(row=1, column=0, sticky="w")
        self.accepted_label = ttk.Label(stats_frame, text="0")
        self.accepted_label.grid(row=1, column=1, sticky="w")

    def toggle_mining(self):
        """Toggle mining on/off"""
        if self.miner.mining:
            self.miner.stop_mining()
            self.mine_button.config(text="Start Mining")
        else:
            self.miner.start_mining(self.mining_callback)
            self.mine_button.config(text="Stop Mining")

    def mining_callback(self, data):
        """Handle mining events"""
        if data["type"] == "share":
            self.update_mining_stats()

    def update_mining_stats(self):
        """Update mining statistics display"""
        self.shares_label.config(text=str(self.miner.shares_submitted))
        self.accepted_label.config(text=str(self.miner.shares_accepted))

    def update_stats(self):
        """Periodic update"""
        if self.miner.mining:
            self.update_mining_stats()
        self.root.after(5000, self.update_stats)

    def run(self):
        """Run the GUI"""
        self.root.mainloop()


# ── Headless mode ────────────────────────────────────────────────────────

def run_headless(wallet_address: str, node_url: str) -> int:
    wallet = RustChainWallet()
    if wallet_address:
        wallet.wallet_data["address"] = wallet_address
        wallet.save_wallet(wallet.wallet_data)
    miner = RustChainMiner(wallet.wallet_data["address"])
    miner.node_url = node_url

    def cb(evt):
        t = evt.get("type")
        ts = datetime.now().strftime('%H:%M:%S')
        if t == "share":
            ok = "OK" if evt.get("success") else "FAIL"
            print(f"[{ts}] [share] submitted={evt.get('submitted')} accepted={evt.get('accepted')} {ok}", flush=True)
        elif t == "error":
            print(f"[{ts}] [error] {evt.get('message')}", flush=True)
        elif t == "attestation":
            stage = evt.get("stage")
            if stage == "started":
                print(f"[{ts}] [attestation] started", flush=True)
            elif stage == "success":
                print(f"[{ts}] [attestation] success valid_for={evt.get('valid_for_sec', 0)}s", flush=True)
            elif stage == "failed":
                print(f"[{ts}] [attestation] failed", flush=True)
        elif t == "enroll":
            stage = evt.get("stage")
            if stage == "started":
                print(f"[{ts}] [enroll] started", flush=True)
            elif stage == "success":
                print(f"[{ts}] [enroll] success epoch={evt.get('epoch')} weight={evt.get('weight')}", flush=True)
            elif stage == "failed":
                print(f"[{ts}] [enroll] failed", flush=True)
        elif t == "heartbeat":
            print(f"[{ts}] [heartbeat] enrolled={evt.get('enrolled')} attest_ttl={evt.get('attestation_valid_for_sec')}s shares={evt.get('shares_submitted')}/{evt.get('shares_accepted')}", flush=True)

    print("=" * 60, flush=True)
    print(f"RustChain Windows Miner v{MINER_VERSION} (HTTPS + RIP-PoA + Auto-Update)", flush=True)
    print("=" * 60, flush=True)
    print(f"Node:      {miner.node_url}", flush=True)
    print(f"Wallet:    {miner.wallet_address}", flush=True)
    print(f"Miner ID:  {miner.miner_id}", flush=True)
    print(f"CPU:       {platform.processor()}", flush=True)
    print(f"Fingerprint: {'AVAILABLE' if FINGERPRINT_AVAILABLE else 'NOT AVAILABLE'}", flush=True)
    if FINGERPRINT_AVAILABLE:
        print(f"Fingerprint passed: {miner.fingerprint_passed}", flush=True)
    print(f"Auto-Update: Enabled (checks every {UPDATE_CHECK_INTERVAL}s)", flush=True)
    print("=" * 60, flush=True)
    print("Mining... Press Ctrl+C to stop.\n", flush=True)

    miner.start_mining(cb)
    try:
        cycle = 0
        while True:
            time.sleep(60)
            cycle += 1
            if cycle % 10 == 0:
                balance = miner.check_balance()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Balance: {balance} RTC | "
                      f"Shares: {miner.shares_submitted}/{miner.shares_accepted}", flush=True)
    except KeyboardInterrupt:
        miner.stop_mining()
        print("\nStopping miner.", flush=True)
        return 0


def main(argv=None):
    """Main entry point"""
    ap = argparse.ArgumentParser(description="RustChain Windows wallet + miner (GUI or headless fallback).")
    ap.add_argument("--version", "-v", action="version", version=f"clawrtc {MINER_VERSION}")
    ap.add_argument("--headless", action="store_true", help="Run without GUI (recommended for embeddable Python).")
    ap.add_argument("--node", default=RUSTCHAIN_API, help="RustChain node base URL.")
    ap.add_argument("--wallet", default="", help="Wallet address / miner ID string.")
    ap.add_argument("--no-update", action="store_true", help="Disable auto-update.")
    args = ap.parse_args(argv)

    if args.no_update:
        global UPDATE_CHECK_INTERVAL
        UPDATE_CHECK_INTERVAL = float('inf')

    if args.headless or not TK_AVAILABLE:
        if not TK_AVAILABLE and not args.headless:
            print(f"tkinter unavailable ({_TK_IMPORT_ERROR}); falling back to --headless.", file=sys.stderr)
        return run_headless(args.wallet, args.node)

    app = RustChainGUI()
    app.miner.node_url = args.node
    if args.wallet:
        app.wallet.wallet_data["address"] = args.wallet
        app.wallet.save_wallet(app.wallet.wallet_data)
        app.miner.wallet_address = args.wallet
        app.miner.miner_id = args.wallet
    app.run()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
