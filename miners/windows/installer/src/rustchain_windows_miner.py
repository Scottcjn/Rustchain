#!/usr/bin/env python3
"""
RustChain Windows Wallet Miner
Full-featured wallet and miner for Windows
Enhanced with: config manager, tray icon, --minimized mode, SSL verify=False
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
import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
from datetime import datetime
from pathlib import Path

# Suppress SSL warnings (self-signed cert on node)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Try importing installer components ---
try:
    from config_manager import ConfigManager
    CONFIG = ConfigManager()
except ImportError:
    CONFIG = None

try:
    from tray_icon import RustChainTray, TRAY_AVAILABLE
except ImportError:
    TRAY_AVAILABLE = False

# --- Logging Setup ---
LOG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "RustChain" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"miner_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("RustChain")

# Configuration
RUSTCHAIN_API = CONFIG.node_url if CONFIG else "http://50.28.86.131:8088"
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
        logger.info("Mining started.")
        self.mining_thread = threading.Thread(target=self._mine_loop, args=(callback,))
        self.mining_thread.daemon = True
        self.mining_thread.start()

    def stop_mining(self):
        """Stop mining"""
        self.mining = False
        logger.info("Mining stopped.")

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
                        logger.info(f"Share accepted! ({self.shares_accepted}/{self.shares_submitted})")
                    if callback:
                        callback({
                            "type": "share",
                            "submitted": self.shares_submitted,
                            "accepted": self.shares_accepted,
                            "success": success
                        })
                time.sleep(10)
            except Exception as e:
                logger.error(f"Mining error: {e}")
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
            challenge = requests.post(
                f"{self.node_url}/attest/challenge", json={}, timeout=10, verify=False
            ).json()
            nonce = challenge.get("nonce")
            logger.info("Attestation challenge received.")
        except Exception as e:
            logger.error(f"Attestation challenge failed: {e}")
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
            resp = requests.post(
                f"{self.node_url}/attest/submit", json=attestation, timeout=30, verify=False
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                self.attestation_valid_until = time.time() + 580
                logger.info("Attestation accepted.")
                return True
        except Exception as e:
            logger.error(f"Attestation submit failed: {e}")
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
            resp = requests.post(
                f"{self.node_url}/epoch/enroll", json=payload, timeout=15, verify=False
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                self.enrolled = True
                self.last_enroll = time.time()
                logger.info("Epoch enrollment successful.")
                return True
        except Exception as e:
            logger.error(f"Epoch enrollment failed: {e}")
        return False

    def check_eligibility(self):
        """Check if eligible to mine"""
        try:
            response = requests.get(
                f"{RUSTCHAIN_API}/lottery/eligibility?miner_id={self.miner_id}",
                verify=False
            )
            if response.ok:
                data = response.json()
                return data.get("eligible", False)
        except Exception:
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
            response = requests.post(
                f"{RUSTCHAIN_API}/headers/ingest_signed", json=header, timeout=5, verify=False
            )
            return response.status_code == 200
        except Exception:
            return False

class RustChainGUI:
    """Windows GUI for RustChain"""
    def __init__(self, start_minimized=False):
        self.root = tk.Tk()

        # Window title — include wallet name if available
        wallet_name = CONFIG.wallet_name if CONFIG and CONFIG.wallet_name else ""
        title = "RustChain Wallet & Miner"
        if wallet_name:
            title += f" — {wallet_name}"
        self.root.title(title)
        self.root.geometry("800x600")

        # Set window icon if available
        self._set_window_icon()

        self.wallet = RustChainWallet()
        self.miner = RustChainMiner(self.wallet.wallet_data["address"])

        # System tray icon
        self.tray = None
        if TRAY_AVAILABLE:
            try:
                self.tray = RustChainTray(
                    on_start=self._tray_start,
                    on_stop=self._tray_stop,
                    on_show=self._tray_show,
                    on_quit=self._tray_quit
                )
                self.tray.run_detached()
            except Exception as e:
                logger.warning(f"Tray icon failed to initialize: {e}")
                self.tray = None

        self.setup_gui()
        self.update_stats()

        # Handle window close — minimize to tray instead of quitting
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start minimized if requested
        if start_minimized:
            self.root.withdraw()
            logger.info("Started minimized to tray.")

    def _set_window_icon(self):
        """Try to set the window icon."""
        icon_candidates = [
            Path(__file__).parent / "assets" / "rustchain.ico",
            Path(__file__).parent.parent / "assets" / "rustchain.ico",
        ]
        if hasattr(sys, "_MEIPASS"):
            icon_candidates.insert(0, Path(sys._MEIPASS) / "assets" / "rustchain.ico")

        for icon_path in icon_candidates:
            if icon_path.exists():
                try:
                    self.root.iconbitmap(str(icon_path))
                    break
                except Exception:
                    continue

    def _on_close(self):
        """Minimize to tray on close if tray is available, otherwise quit."""
        if self.tray:
            self.root.withdraw()
        else:
            self._quit()

    def _quit(self):
        """Full shutdown."""
        self.miner.stop_mining()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    # --- Tray callbacks ---
    def _tray_start(self):
        if not self.miner.mining:
            self.miner.start_mining(self.mining_callback)
            self.root.after(0, lambda: self.mine_button.config(text="Stop Mining"))

    def _tray_stop(self):
        if self.miner.mining:
            self.miner.stop_mining()
            self.root.after(0, lambda: self.mine_button.config(text="Start Mining"))

    def _tray_show(self):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_quit(self):
        self.root.after(0, self._quit)

    def setup_gui(self):
        """Setup GUI elements"""
        # Style configuration
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass

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

        # Log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Log")
        self.setup_log_tab(log_frame)

    def setup_wallet_tab(self, parent):
        """Setup wallet interface"""
        info_frame = ttk.LabelFrame(parent, text="Wallet Information", padding=10)
        info_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(info_frame, text="Address:").grid(row=0, column=0, sticky="w")
        self.address_label = ttk.Label(info_frame, text=self.wallet.wallet_data["address"])
        self.address_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        ttk.Label(info_frame, text="Balance:").grid(row=1, column=0, sticky="w")
        self.balance_label = ttk.Label(info_frame, text=f"{self.wallet.wallet_data['balance']:.8f} RTC")
        self.balance_label.grid(row=1, column=1, sticky="w", padx=(10, 0))

        # Show wallet name if configured
        if CONFIG and CONFIG.wallet_name:
            ttk.Label(info_frame, text="Wallet Name:").grid(row=2, column=0, sticky="w")
            ttk.Label(info_frame, text=CONFIG.wallet_name).grid(row=2, column=1, sticky="w", padx=(10, 0))

    def setup_miner_tab(self, parent):
        """Setup miner interface"""
        control_frame = ttk.LabelFrame(parent, text="Mining Control", padding=10)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.mine_button = ttk.Button(control_frame, text="Start Mining", command=self.toggle_mining)
        self.mine_button.pack(pady=10)

        self.status_label = ttk.Label(control_frame, text="Status: Idle", foreground="gray")
        self.status_label.pack(pady=(0, 5))

        stats_frame = ttk.LabelFrame(parent, text="Mining Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(stats_frame, text="Shares Submitted:").grid(row=0, column=0, sticky="w")
        self.shares_label = ttk.Label(stats_frame, text="0")
        self.shares_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        ttk.Label(stats_frame, text="Shares Accepted:").grid(row=1, column=0, sticky="w")
        self.accepted_label = ttk.Label(stats_frame, text="0")
        self.accepted_label.grid(row=1, column=1, sticky="w", padx=(10, 0))

        ttk.Label(stats_frame, text="Miner ID:").grid(row=2, column=0, sticky="w")
        self.minerid_label = ttk.Label(stats_frame, text=self.miner.miner_id)
        self.minerid_label.grid(row=2, column=1, sticky="w", padx=(10, 0))

    def setup_log_tab(self, parent):
        """Setup log viewer tab"""
        self.log_text = scrolledtext.ScrolledText(parent, state="disabled", wrap="word", height=20)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_log).pack(side="left")
        ttk.Button(btn_frame, text="Open Log Folder", command=self._open_log_folder).pack(side="left", padx=(10, 0))

    def _refresh_log(self):
        """Reload log file into the log viewer."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    # Read last 200 lines
                    lines = f.readlines()[-200:]
                    self.log_text.insert("end", "".join(lines))
                    self.log_text.see("end")
            except Exception:
                self.log_text.insert("end", "Error reading log file.")
        else:
            self.log_text.insert("end", "No log file found yet.")
        self.log_text.config(state="disabled")

    def _open_log_folder(self):
        """Open log folder in Explorer."""
        try:
            os.startfile(str(LOG_DIR))
        except Exception:
            subprocess.Popen(["explorer", str(LOG_DIR)])

    def toggle_mining(self):
        """Toggle mining on/off"""
        if self.miner.mining:
            self.miner.stop_mining()
            self.mine_button.config(text="Start Mining")
            self.status_label.config(text="Status: Idle", foreground="gray")
            if self.tray:
                self.tray.set_status("Idle", "idle")
        else:
            self.miner.start_mining(self.mining_callback)
            self.mine_button.config(text="Stop Mining")
            self.status_label.config(text="Status: Mining...", foreground="green")
            if self.tray:
                self.tray.set_status("Mining...", "active")

    def mining_callback(self, data):
        """Handle mining events"""
        try:
            if data["type"] == "share":
                self.root.after(0, self.update_mining_stats)
            elif data["type"] == "error":
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Status: Error — {data['message'][:50]}", foreground="red"
                ))
                if self.tray:
                    self.tray.set_status(f"Error: {data['message'][:30]}", "error")
        except Exception:
            pass

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

def main():
    """Main entry point"""
    # Check for --minimized flag
    start_minimized = "--minimized" in sys.argv

    logger.info("RustChain Miner starting...")
    app = RustChainGUI(start_minimized=start_minimized)
    app.run()

if __name__ == "__main__":
    main()
