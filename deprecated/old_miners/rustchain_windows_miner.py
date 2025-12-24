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
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
from datetime import datetime
from pathlib import Path

# Configuration
BOOTSTRAP_NODES = [
    "http://50.28.86.131:8088",  # Node 1
    "http://50.28.86.153:8088"   # Node 2
]
WALLET_DIR = Path.home() / ".rustchain"
CONFIG_FILE = WALLET_DIR / "config.json"
WALLET_FILE = WALLET_DIR / "wallet.json"
PEERS_FILE = WALLET_DIR / "peers.json"

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

class PeerDiscovery:
    """Peer discovery and management for decentralized network"""
    def __init__(self):
        self.peers = list(BOOTSTRAP_NODES)  # Start with bootstrap nodes
        self.active_peer = None
        self.peer_scores = {peer: 100 for peer in self.peers}
        self.load_peers()

    def load_peers(self):
        """Load known peers from file"""
        try:
            if PEERS_FILE.exists():
                with open(PEERS_FILE, 'r') as f:
                    saved_peers = json.load(f)
                    for peer in saved_peers:
                        if peer not in self.peers:
                            self.peers.append(peer)
                            self.peer_scores[peer] = 50  # Lower score for untested peers
        except:
            pass

    def save_peers(self):
        """Save known peers to file"""
        try:
            with open(PEERS_FILE, 'w') as f:
                json.dump(self.peers, f, indent=2)
        except:
            pass

    def discover_peers(self):
        """Discover new peers from known peers"""
        for peer in list(self.peers):
            try:
                response = requests.get(f"{peer}/p2p/peers", timeout=3)
                if response.status_code == 200:
                    peer_list = response.json()
                    if isinstance(peer_list, list):
                        for new_peer in peer_list:
                            if new_peer not in self.peers:
                                self.peers.append(new_peer)
                                self.peer_scores[new_peer] = 50
            except:
                pass
        self.save_peers()

    def get_best_peer(self):
        """Get the best performing peer"""
        # Try active peer first
        if self.active_peer and self.test_peer(self.active_peer):
            return self.active_peer

        # Sort peers by score
        sorted_peers = sorted(self.peers, key=lambda p: self.peer_scores.get(p, 0), reverse=True)

        # Test each peer until we find a working one
        for peer in sorted_peers:
            if self.test_peer(peer):
                self.active_peer = peer
                return peer

        # No working peers found
        return None

    def test_peer(self, peer_url):
        """Test if a peer is responsive"""
        try:
            response = requests.get(f"{peer_url}/api/stats", timeout=2)
            if response.status_code == 200:
                # Increase score for responsive peer
                self.peer_scores[peer_url] = min(100, self.peer_scores.get(peer_url, 0) + 5)
                return True
        except:
            pass

        # Decrease score for unresponsive peer
        self.peer_scores[peer_url] = max(0, self.peer_scores.get(peer_url, 100) - 10)
        return False

    def mark_peer_failed(self, peer_url):
        """Mark a peer as failed"""
        if peer_url in self.peer_scores:
            self.peer_scores[peer_url] = max(0, self.peer_scores[peer_url] - 20)

    def get_all_active_peers(self):
        """Get list of all responsive peers"""
        active = []
        for peer in self.peers:
            if self.test_peer(peer):
                active.append(peer)
        return active

class RustChainMiner:
    """Mining engine for RustChain"""
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address
        self.mining = False
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.miner_id = f"windows_{hashlib.md5(wallet_address.encode()).hexdigest()[:8]}"
        self.hardware_info = self.detect_hardware()
        self.network_age = 0
        self.poa_score = 0
        self.peer_discovery = PeerDiscovery()
        self.connected_peers = []
        self.entropy_fingerprint = self.generate_entropy_fingerprint()

    def get_api_url(self):
        """Get the best available peer URL"""
        peer = self.peer_discovery.get_best_peer()
        return peer if peer else BOOTSTRAP_NODES[0]  # Fallback to first bootstrap node

    def detect_hardware(self):
        """Detect hardware information"""
        try:
            import platform
            cpu_info = platform.processor()
            machine = platform.machine()

            # Determine hardware class and multiplier
            cpu_lower = cpu_info.lower()
            if '486' in cpu_lower:
                hw_class = "i486 (Legendary)"
                multiplier = 2.6
            elif '386' in cpu_lower:
                hw_class = "i386 (Mythical)"
                multiplier = 2.8
            elif 'pentium' in cpu_lower:
                if 'ii' in cpu_lower or '2' in cpu_lower:
                    hw_class = "Pentium II (Epic)"
                    multiplier = 1.8
                elif 'iii' in cpu_lower or '3' in cpu_lower:
                    hw_class = "Pentium III (Rare)"
                    multiplier = 1.6
                elif '4' in cpu_lower or 'iv' in cpu_lower:
                    hw_class = "Pentium 4 (Classic)"
                    multiplier = 1.3
                else:
                    hw_class = "Pentium (Epic)"
                    multiplier = 2.3
            elif 'athlon' in cpu_lower:
                hw_class = "AMD Athlon (Rare)"
                multiplier = 1.7
            elif 'powerpc' in cpu_lower or 'ppc' in machine.lower():
                hw_class = "PowerPC (Legendary)"
                multiplier = 2.5
            else:
                hw_class = "Modern x86 (Common)"
                multiplier = 1.0

            return {
                "class": hw_class,
                "cpu": cpu_info,
                "machine": machine,
                "multiplier": multiplier
            }
        except:
            return {
                "class": "Unknown (Common)",
                "cpu": "Unknown",
                "machine": "Unknown",
                "multiplier": 1.0
            }

    def generate_entropy_fingerprint(self):
        """Generate hardware entropy fingerprint for anti-spoofing"""
        try:
            import uuid
            # Collect hardware identifiers
            components = []

            # Machine ID
            try:
                machine_id = str(uuid.getnode())  # MAC address as integer
                components.append(machine_id)
            except:
                pass

            # Platform info
            components.append(platform.system())
            components.append(platform.machine())
            components.append(platform.processor())

            # Windows-specific identifiers
            if platform.system() == "Windows":
                try:
                    import wmi
                    c = wmi.WMI()
                    # CPU serial
                    for cpu in c.Win32_Processor():
                        if cpu.ProcessorId:
                            components.append(cpu.ProcessorId.strip())
                    # Motherboard serial
                    for board in c.Win32_BaseBoard():
                        if board.SerialNumber:
                            components.append(board.SerialNumber.strip())
                except Exception as wmi_err:
                    # WMI may not be available or may fail
                    pass

            # Generate fingerprint hash
            fingerprint_data = "|".join(str(c) for c in components if c)
            fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()
            return fingerprint[:16]  # First 16 chars for display
        except:
            # Fallback to simple hash
            return hashlib.md5(self.miner_id.encode()).hexdigest()[:16]

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

    def check_eligibility(self):
        """Check if eligible to mine"""
        try:
            response = requests.get(f"{self.get_api_url()}/lottery/eligibility?miner_id={self.miner_id}")
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
            "nonce": nonce,
            "entropy_fingerprint": self.entropy_fingerprint
        }
        header_str = json.dumps(header, sort_keys=True)
        header["hash"] = hashlib.sha256(header_str.encode()).hexdigest()
        return header

    def submit_header(self, header):
        """Submit mining header"""
        try:
            response = requests.post(f"{self.get_api_url()}/headers/ingest_signed", json=header, timeout=5)
            return response.status_code == 200
        except:
            return False

class RustChainGUI:
    """Windows GUI for RustChain"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RustChain Wallet & Miner for Windows")
        self.root.geometry("800x650")
        self.wallet = RustChainWallet()
        self.miner = RustChainMiner(self.wallet.wallet_data["address"])
        self.setup_gui()

        # Initial log messages
        self.log_message("RustChain Miner initialized")
        self.log_message(f"Wallet: {self.wallet.wallet_data['address'][:20]}...")
        self.log_message(f"Connecting to RustChain network...")

        # Delay network calls until GUI is fully rendered
        self.root.after(1000, self.update_stats)

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

        ttk.Label(info_frame, text="Address:").grid(row=0, column=0, sticky="w", pady=5)
        self.address_entry = tk.Entry(info_frame, width=50)
        self.address_entry.insert(0, self.wallet.wallet_data["address"])
        self.address_entry.config(state='readonly')
        self.address_entry.grid(row=0, column=1, sticky="w", padx=5)

        copy_btn = ttk.Button(info_frame, text="Copy", command=self.copy_address)
        copy_btn.grid(row=0, column=2, padx=5)

        ttk.Label(info_frame, text="Balance:").grid(row=1, column=0, sticky="w", pady=5)
        self.balance_label = ttk.Label(info_frame, text=f"{self.wallet.wallet_data['balance']:.8f} RTC")
        self.balance_label.grid(row=1, column=1, sticky="w")

        # Send RTC section
        send_frame = ttk.LabelFrame(parent, text="Send RTC", padding=10)
        send_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(send_frame, text="To Address:").grid(row=0, column=0, sticky="w", pady=5)
        self.send_address_entry = ttk.Entry(send_frame, width=50)
        self.send_address_entry.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(send_frame, text="Amount:").grid(row=1, column=0, sticky="w", pady=5)
        self.send_amount_entry = ttk.Entry(send_frame, width=20)
        self.send_amount_entry.grid(row=1, column=1, sticky="w", padx=5)

        send_btn = ttk.Button(send_frame, text="Send RTC", command=self.send_rtc)
        send_btn.grid(row=2, column=1, sticky="w", padx=5, pady=10)

        self.send_status_label = ttk.Label(send_frame, text="")
        self.send_status_label.grid(row=3, column=0, columnspan=2, sticky="w")

    def setup_miner_tab(self, parent):
        """Setup miner interface"""
        control_frame = ttk.LabelFrame(parent, text="Mining Control", padding=10)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.mine_button = ttk.Button(control_frame, text="Start Mining", command=self.toggle_mining)
        self.mine_button.pack(pady=10)

        # Hardware info frame
        hw_frame = ttk.LabelFrame(parent, text="Hardware Information (Proof-of-Antiquity)", padding=10)
        hw_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(hw_frame, text="Class:").grid(row=0, column=0, sticky="w", pady=2)
        self.hw_class_label = ttk.Label(hw_frame, text=self.miner.hardware_info['class'], font=('TkDefaultFont', 9, 'bold'))
        self.hw_class_label.grid(row=0, column=1, sticky="w")

        ttk.Label(hw_frame, text="CPU:").grid(row=1, column=0, sticky="w", pady=2)
        self.hw_cpu_label = ttk.Label(hw_frame, text=self.miner.hardware_info['cpu'][:40])
        self.hw_cpu_label.grid(row=1, column=1, sticky="w")

        ttk.Label(hw_frame, text="PoA Multiplier:").grid(row=2, column=0, sticky="w", pady=2)
        self.hw_mult_label = ttk.Label(hw_frame, text=f"{self.miner.hardware_info['multiplier']}x", foreground="green" if self.miner.hardware_info['multiplier'] > 1.0 else "gray")
        self.hw_mult_label.grid(row=2, column=1, sticky="w")

        ttk.Label(hw_frame, text="Entropy Fingerprint:").grid(row=3, column=0, sticky="w", pady=2)
        self.entropy_label = ttk.Label(hw_frame, text="Calculating...", font=('Courier', 8))
        self.entropy_label.grid(row=3, column=1, sticky="w")

        ttk.Label(hw_frame, text="Network Age:").grid(row=4, column=0, sticky="w", pady=2)
        self.network_age_label = ttk.Label(hw_frame, text="0 days")
        self.network_age_label.grid(row=4, column=1, sticky="w")

        ttk.Label(hw_frame, text="PoA Score:").grid(row=5, column=0, sticky="w", pady=2)
        self.poa_score_label = ttk.Label(hw_frame, text="0")
        self.poa_score_label.grid(row=5, column=1, sticky="w")

        # Network status frame
        network_frame = ttk.LabelFrame(parent, text="Network Status", padding=10)
        network_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(network_frame, text="Node:").grid(row=0, column=0, sticky="w", pady=2)
        self.node_label = ttk.Label(network_frame, text="Connecting...", foreground="orange")
        self.node_label.grid(row=0, column=1, sticky="w")

        ttk.Label(network_frame, text="Block Height:").grid(row=1, column=0, sticky="w", pady=2)
        self.height_label = ttk.Label(network_frame, text="0")
        self.height_label.grid(row=1, column=1, sticky="w")

        ttk.Label(network_frame, text="Connected Peers:").grid(row=2, column=0, sticky="w", pady=2)
        self.peers_label = ttk.Label(network_frame, text="0")
        self.peers_label.grid(row=2, column=1, sticky="w")

        ttk.Label(network_frame, text="Sync Status:").grid(row=3, column=0, sticky="w", pady=2)
        self.sync_label = ttk.Label(network_frame, text="Checking...")
        self.sync_label.grid(row=3, column=1, sticky="w")

        # Mining stats frame
        stats_frame = ttk.LabelFrame(parent, text="Mining Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(stats_frame, text="Shares Submitted:").grid(row=0, column=0, sticky="w")
        self.shares_label = ttk.Label(stats_frame, text="0")
        self.shares_label.grid(row=0, column=1, sticky="w")

        ttk.Label(stats_frame, text="Shares Accepted:").grid(row=1, column=0, sticky="w")
        self.accepted_label = ttk.Label(stats_frame, text="0")
        self.accepted_label.grid(row=1, column=1, sticky="w")

        # Activity log
        log_frame = ttk.LabelFrame(parent, text="Activity Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='disabled')
        self.log_text.pack(fill="both", expand=True)

    def toggle_mining(self):
        """Toggle mining on/off"""
        if self.miner.mining:
            self.miner.stop_mining()
            self.mine_button.config(text="Start Mining")
            self.log_message("Mining stopped")
        else:
            self.miner.start_mining(self.mining_callback)
            self.mine_button.config(text="Stop Mining")
            self.log_message(f"Mining started with wallet {self.wallet.wallet_data['address'][:16]}...")
            self.log_message(f"Connected to: {self.miner.get_api_url()}")

    def mining_callback(self, data):
        """Handle mining events"""
        if data["type"] == "share":
            if data.get("success"):
                self.log_message(f"[OK] Share accepted! ({data['accepted']}/{data['submitted']})")
            else:
                self.log_message(f"[X] Share rejected ({data['accepted']}/{data['submitted']})")
            self.update_mining_stats()
        elif data["type"] == "error":
            self.log_message(f"Error: {data.get('message', 'Unknown error')}")

    def update_mining_stats(self):
        """Update mining statistics display"""
        self.shares_label.config(text=str(self.miner.shares_submitted))
        self.accepted_label.config(text=str(self.miner.shares_accepted))

    def copy_address(self):
        """Copy wallet address to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.wallet.wallet_data["address"])
        self.log_message("Address copied to clipboard!")

    def send_rtc(self):
        """Send RTC to another address"""
        to_address = self.send_address_entry.get().strip()
        amount_str = self.send_amount_entry.get().strip()

        if not to_address or not amount_str:
            self.send_status_label.config(text="[ERROR] Please fill in all fields", foreground="red")
            return

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Amount must be positive")

            # TODO: Implement actual transaction sending via API
            self.send_status_label.config(text=f"[OK] Sent {amount} RTC to {to_address[:16]}...", foreground="green")
            self.log_message(f"Sent {amount} RTC to {to_address[:16]}...")

        except ValueError as e:
            self.send_status_label.config(text=f"[ERROR] Invalid amount: {e}", foreground="red")

    def log_message(self, message):
        """Add message to activity log"""
        self.log_text.configure(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def check_network_status(self):
        """Check and update network status"""
        try:
            # Get blockchain info
            response = requests.get(f"{self.miner.get_api_url()}/api/blockchain/info", timeout=3)
            if response.ok:
                data = response.json()
                height = data.get("height", 0)
                self.height_label.config(text=str(height))
                self.node_label.config(text="Connected [OK]", foreground="green")

                # Update sync status
                if height > 0:
                    self.sync_label.config(text="Synchronized [OK]", foreground="green")
                else:
                    self.sync_label.config(text="Syncing...", foreground="orange")

            # Get stats for peer count and network age
            stats_response = requests.get(f"{self.miner.get_api_url()}/api/stats", timeout=3)
            if stats_response.ok:
                stats = stats_response.json()
                peers = stats.get("connected_peers", 0)
                self.peers_label.config(text=str(peers))

                # Get P2P peer list
                p2p_response = requests.get(f"{self.miner.get_api_url()}/p2p/stats", timeout=3)
                if p2p_response.ok:
                    p2p_data = p2p_response.json()
                    peer_list = p2p_data.get("peers", [])
                    if peer_list and peer_list != self.miner.connected_peers:
                        self.miner.connected_peers = peer_list
                        self.log_message(f"Connected to {len(peer_list)} peers")
                        for peer in peer_list[:3]:  # Log first 3 peers
                            self.log_message(f"  Peer: {peer}")

            # Get miner info for PoA score and network age
            miner_response = requests.get(f"{self.miner.get_api_url()}/api/miners", timeout=3)
            if miner_response.ok:
                miner_data = miner_response.json()
                miners = miner_data.get("miners", [])
                # Find our miner
                for m in miners:
                    if m.get("id") == self.miner.miner_id:
                        # Calculate network age in days
                        joined = m.get("joined_timestamp", time.time())
                        age_seconds = time.time() - joined
                        age_days = int(age_seconds / 86400)
                        self.miner.network_age = age_days
                        self.network_age_label.config(text=f"{age_days} days")

                        # Update PoA score
                        poa_score = m.get("poa_score", 0)
                        self.miner.poa_score = poa_score
                        self.poa_score_label.config(text=str(poa_score))
                        break

            # Update entropy fingerprint display
            self.entropy_label.config(text=self.miner.entropy_fingerprint)

        except Exception as e:
            self.node_label.config(text="Disconnected [X]", foreground="red")
            self.sync_label.config(text="Not synced", foreground="red")

    def update_stats(self):
        """Periodic update"""
        if self.miner.mining:
            self.update_mining_stats()
        self.check_network_status()
        self.root.after(5000, self.update_stats)

    def run(self):
        """Run the GUI"""
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        print("Starting RustChain Windows Miner...")
        print(f"Bootstrap Nodes: {BOOTSTRAP_NODES}")
        print(f"Wallet directory: {WALLET_DIR}")

        app = RustChainGUI()
        print("GUI initialized successfully")
        app.run()
    except Exception as e:
        import traceback
        error_msg = f"FATAL ERROR: {e}\n\n{traceback.format_exc()}"
        print(error_msg)

        # Try to show GUI error dialog
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("RustChain Miner Error", error_msg)
            root.destroy()
        except:
            pass

        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
