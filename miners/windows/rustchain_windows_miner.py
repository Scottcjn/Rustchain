#!/usr/bin/env python3
"""
RustChain Windows Wallet Miner
Full-featured wallet and miner for Windows
"""

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

# Configuration
RUSTCHAIN_API = "http://50.28.86.131:8088"
WALLET_DIR = Path.home() / ".rustchain"
CONFIG_FILE = WALLET_DIR / "config.json"
WALLET_FILE = WALLET_DIR / "wallet.json"

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

class RustChainMiner:
    """Mining engine for RustChain"""
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address
        self.mining = False
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.miner_id = f"windows_{hashlib.md5(wallet_address.encode()).hexdigest()[:8]}"
        self.node_url = RUSTCHAIN_API
        self.attestation_valid_until = 0
        self.last_enroll = 0
        self.enrolled = False
        self.hw_info = self._get_hw_info()
        self.last_entropy = {}

    def start_mining(self, callback=None):
        """Start mining process"""
        self.mining = True
        self.mining_thread = threading.Thread(target=self._mine_loop, args=(callback,))
        self.mining_thread.daemon = True
        self.mining_thread.start()

    def stop_mining(self):
        """Stop mining"""
        self.mining = False

    def _mine_loop(self, callback):
        """Main mining loop"""
        while self.mining:
            try:
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
                time.sleep(10)
            except Exception as e:
                if callback:
                    callback({"type": "error", "message": str(e)})
                time.sleep(30)

    def _ensure_ready(self, callback):
        """Ensure we have a fresh attestation and current epoch enrollment."""
        now = time.time()

        if now >= self.attestation_valid_until - 60:
            if not self.attest():
                if callback:
                    callback({"type": "error", "message": "Attestation failed"})
                return False

        if (now - self.last_enroll) > 3600 or not self.enrolled:
            if not self.enroll():
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
        """Perform hardware attestation for PoA."""
        try:
            challenge = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=10).json()
            nonce = challenge.get("nonce")
        except Exception:
            return False

        entropy = self._collect_entropy()
        self.last_entropy = entropy

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
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/attest/submit", json=attestation, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                self.attestation_valid_until = time.time() + 580
                return True
        except Exception:
            pass
        return False

    def enroll(self):
        """Enroll the miner into the current epoch after attesting."""
        payload = {
            "miner_pubkey": self.wallet_address,
            "miner_id": self.miner_id,
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/epoch/enroll", json=payload, timeout=15)
            if resp.status_code == 200 and resp.json().get("ok"):
                self.enrolled = True
                self.last_enroll = time.time()
                return True
        except Exception:
            pass
        return False

    def check_eligibility(self):
        """Check if eligible to mine"""
        try:
            response = requests.get(f"{RUSTCHAIN_API}/lottery/eligibility?miner_id={self.miner_id}")
            if response.ok:
                data = response.json()
                return data.get("eligible", False)
        except:
            pass
        return False

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
            response = requests.post(f"{RUSTCHAIN_API}/headers/ingest_signed", json=header, timeout=5)
            return response.status_code == 200
        except:
            return False

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

def run_headless(wallet_address: str, node_url: str) -> int:
    wallet = RustChainWallet()
    if wallet_address:
        wallet.wallet_data["address"] = wallet_address
        wallet.save_wallet(wallet.wallet_data)
    miner = RustChainMiner(wallet.wallet_data["address"])
    miner.node_url = node_url

    def cb(evt):
        t = evt.get("type")
        if t == "share":
            ok = "OK" if evt.get("success") else "FAIL"
            print(f"[share] submitted={evt.get('submitted')} accepted={evt.get('accepted')} {ok}", flush=True)
        elif t == "error":
            print(f"[error] {evt.get('message')}", file=sys.stderr, flush=True)

    print("RustChain Windows miner: headless mode", flush=True)
    print(f"node={miner.node_url} miner_id={miner.miner_id}", flush=True)
    miner.start_mining(cb)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        miner.stop_mining()
        print("\nStopping miner.", flush=True)
        return 0


def main(argv=None):
    """Main entry point"""
    ap = argparse.ArgumentParser(description="RustChain Windows wallet + miner (GUI or headless fallback).")
    ap.add_argument("--headless", action="store_true", help="Run without GUI (recommended for embeddable Python).")
    ap.add_argument("--node", default=RUSTCHAIN_API, help="RustChain node base URL.")
    ap.add_argument("--wallet", default="", help="Wallet address / miner pubkey string.")
    args = ap.parse_args(argv)

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
        app.miner.miner_id = f"windows_{hashlib.md5(args.wallet.encode()).hexdigest()[:8]}"
    app.run()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
