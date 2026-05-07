#!/usr/bin/env python3
"""
RustChain Wallet GUI
A simple graphical wallet for RTC transactions

Features:
- View balance for any wallet ID
- Send RTC to another wallet
- Transaction history
- Create new wallet

Network Error Handling:
- Distinguishes between network unreachable, timeouts, and API errors
- Implements retry strategy with exponential backoff for transient failures
- Provides clear user-facing diagnostics for troubleshooting
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import json
import hashlib
import secrets
from datetime import datetime
import urllib3
import socket
import time
from typing import Optional, Tuple, Dict, Any

# Conditionally disable SSL warnings only when verification is off
if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
NODE_URL = "https://rustchain.org"
VERIFY_SSL = os.environ.get("RUSTCHAIN_VERIFY_SSL", "true").lower() != "false"

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 10.0  # seconds
NETWORK_TIMEOUT = 15  # seconds


class RustChainWallet:
    def __init__(self, root):
        self.root = root
        self.root.title("RustChain Wallet v1.0")
        self.root.geometry("700x600")
        self.root.configure(bg="#1a1a2e")

        # Current wallet ID
        self.current_wallet = tk.StringVar(value="")
        self.balance = tk.StringVar(value="0.00000000 RTC")

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        """Configure ttk styles for dark theme"""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabel", background="#1a1a2e", foreground="#eee", font=("Helvetica", 11))
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"), foreground="#00d4ff")
        style.configure("Balance.TLabel", font=("Helvetica", 24, "bold"), foreground="#00ff88")
        style.configure("TButton", font=("Helvetica", 10, "bold"), padding=10)
        style.configure("TEntry", font=("Helvetica", 11), padding=5)
        style.configure("Treeview", background="#16213e", foreground="#eee",
                       fieldbackground="#16213e", font=("Helvetica", 10))
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"),
                       background="#0f3460", foreground="#00d4ff")

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="RustChain Wallet", style="Title.TLabel")
        title.pack(pady=(0, 20))

        # Wallet ID Frame
        wallet_frame = ttk.Frame(main_frame)
        wallet_frame.pack(fill=tk.X, pady=10)

        ttk.Label(wallet_frame, text="Wallet ID:").pack(side=tk.LEFT)

        self.wallet_entry = ttk.Entry(wallet_frame, textvariable=self.current_wallet, width=40)
        self.wallet_entry.pack(side=tk.LEFT, padx=10)

        ttk.Button(wallet_frame, text="Load", command=self.load_wallet).pack(side=tk.LEFT, padx=5)
        ttk.Button(wallet_frame, text="New Wallet", command=self.create_new_wallet).pack(side=tk.LEFT, padx=5)

        # Balance Display
        balance_frame = ttk.Frame(main_frame)
        balance_frame.pack(fill=tk.X, pady=20)

        ttk.Label(balance_frame, text="Balance:").pack()
        balance_label = ttk.Label(balance_frame, textvariable=self.balance, style="Balance.TLabel")
        balance_label.pack()

        # Send Frame
        send_frame = ttk.LabelFrame(main_frame, text="Send RTC", padding=15)
        send_frame.pack(fill=tk.X, pady=10)

        # Recipient
        recv_frame = ttk.Frame(send_frame)
        recv_frame.pack(fill=tk.X, pady=5)
        ttk.Label(recv_frame, text="To:").pack(side=tk.LEFT)
        self.recipient_entry = ttk.Entry(recv_frame, width=50)
        self.recipient_entry.pack(side=tk.LEFT, padx=10)

        # Amount
        amt_frame = ttk.Frame(send_frame)
        amt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(amt_frame, text="Amount:").pack(side=tk.LEFT)
        self.amount_entry = ttk.Entry(amt_frame, width=20)
        self.amount_entry.pack(side=tk.LEFT, padx=10)
        ttk.Label(amt_frame, text="RTC").pack(side=tk.LEFT)

        # Send button
        ttk.Button(send_frame, text="Send RTC", command=self.send_rtc).pack(pady=10)

        # Transaction History
        history_frame = ttk.LabelFrame(main_frame, text="Recent Transactions", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Treeview for transactions
        columns = ("time", "type", "counterparty", "amount")
        self.tx_tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=8)

        self.tx_tree.heading("time", text="Time")
        self.tx_tree.heading("type", text="Type")
        self.tx_tree.heading("counterparty", text="From/To")
        self.tx_tree.heading("amount", text="Amount (RTC)")

        self.tx_tree.column("time", width=150)
        self.tx_tree.column("type", width=80)
        self.tx_tree.column("counterparty", width=250)
        self.tx_tree.column("amount", width=120)

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.tx_tree.yview)
        self.tx_tree.configure(yscrollcommand=scrollbar.set)

        self.tx_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status_var = tk.StringVar(value="Ready - Connect to RustChain node")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, font=("Helvetica", 9))
        status_bar.pack(pady=10)

    def _check_network_connectivity(self, url: str = NODE_URL) -> Tuple[bool, str]:
        """
        Check network connectivity to the node.
        
        Returns:
            Tuple of (is_reachable, error_message)
        """
        import urllib.parse
        
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            
            # Try to resolve hostname
            try:
                socket.gethostbyname(host)
            except socket.gaierror as e:
                return False, f"DNS resolution failed for {host}: {e}"
            
            # Try to establish TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:
                return False, f"Cannot connect to {host}:{port} (error code: {result})"
            
            return True, ""
            
        except Exception as e:
            return False, f"Network check failed: {e}"

    def _fetch_with_retry(
        self,
        url: str,
        method: str = "GET",
        data: Dict = None,
        max_retries: int = MAX_RETRIES,
        timeout: int = NETWORK_TIMEOUT,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch JSON from URL with retry logic and proper error classification.
        
        Args:
            url: URL to fetch
            method: HTTP method (GET or POST)
            data: JSON data for POST requests
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (data_dict, error_message)
            - On success: (data, None)
            - On failure: (None, error_description)
        """
        from requests.exceptions import ConnectionError, Timeout, HTTPError
        
        last_error = None
        delay = INITIAL_RETRY_DELAY
        
        for attempt in range(1, max_retries + 1):
            try:
                if method == "GET":
                    resp = requests.get(url, verify=VERIFY_SSL, timeout=timeout)
                else:
                    resp = requests.post(url, json=data, verify=VERIFY_SSL, timeout=timeout)
                
                resp.raise_for_status()
                return resp.json(), None
                
            except ConnectionError as e:
                last_error = str(e)
                # Check if it's a real network issue
                is_reachable, net_error = self._check_network_connectivity(url)
                if not is_reachable:
                    return None, f"Network unreachable: {net_error}"
                
                # Transient connection issue - retry
                if attempt < max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY)
                    
            except Timeout as e:
                last_error = str(e)
                if attempt < max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY)
                else:
                    return None, f"Request timeout after {timeout}s (tried {max_retries}x)"
                    
            except HTTPError as e:
                status = e.response.status_code if e.response else "unknown"
                return None, f"API error: HTTP {status}"
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY)
                else:
                    return None, f"Request failed: {e}"
        
        return None, f"Request failed after {max_retries} retries: {last_error}"

    def api_call(self, endpoint, method="GET", data=None):
        """Make API call to RustChain node with retry logic and error classification."""
        url = f"{NODE_URL}{endpoint}"
        
        if method == "POST":
            result, error = self._fetch_with_retry(url, method="POST", data=data)
        else:
            result, error = self._fetch_with_retry(url, method="GET")
        
        if error:
            # Classify and display error with troubleshooting hints
            error_lower = error.lower()
            
            if "network unreachable" in error_lower or "dns resolution" in error_lower:
                self.status_var.set("Network error - Check connection")
                self._show_network_error_dialog(error)
            elif "timeout" in error_lower:
                self.status_var.set("Request timeout - Node may be busy")
            elif "api error" in error_lower:
                self.status_var.set(f"API error: {error}")
            else:
                self.status_var.set(f"Error: {error}")
            
            return None
        
        return result

    def _show_network_error_dialog(self, error: str):
        """Show detailed network error dialog with troubleshooting hints."""
        is_reachable, net_err = self._check_network_connectivity(NODE_URL)
        
        message = f"Network Error\n\n{error}\n\n"
        
        if not is_reachable:
            message += "⚠ Network Issue Detected:\n"
            message += f"   {net_err}\n\n"
            message += "Troubleshooting:\n"
            message += "   1. Check your internet connection\n"
            message += f"   2. Verify DNS is working (try: ping {NODE_URL})\n"
            message += "   3. Check firewall/proxy settings\n"
            message += "   4. Node may be temporarily offline"
        else:
            message += "⚠ Node Response Issue:\n\n"
            message += "Troubleshooting:\n"
            message += "   1. Node may be syncing or under maintenance\n"
            message += "   2. Try again in a few moments\n"
            message += "   3. Check node status at the RustChain dashboard"
        
        messagebox.showerror("Network Error", message)

    def load_wallet(self):
        """Load wallet and display balance with proper error handling."""
        wallet_id = self.current_wallet.get().strip()
        if not wallet_id:
            messagebox.showwarning("Warning", "Please enter a wallet ID")
            return

        self.status_var.set(f"Loading wallet {wallet_id}...")

        # Get balance with retry logic
        data = self.api_call(f"/wallet/balance?miner_id={wallet_id}")
        if data:
            balance = data.get("amount_rtc", data.get("balance", 0))
            self.balance.set(f"{balance:.8f} RTC")
            self.status_var.set(f"Wallet loaded: {wallet_id}")
        else:
            # API call failed - show 0 balance but keep status message with error
            self.balance.set("0.00000000 RTC")
            # Status already set by api_call with error details
        
        # Load transaction history (may also fail if network is down)
        self.load_history(wallet_id)

    def load_history(self, wallet_id):
        """Load transaction history for wallet"""
        # Clear existing
        for item in self.tx_tree.get_children():
            self.tx_tree.delete(item)

        # Get ledger
        data = self.api_call(f"/wallet/ledger?miner_id={wallet_id}")
        if data and "transactions" in data:
            for tx in data["transactions"][:20]:  # Last 20
                tx_type = "Received" if tx.get("to") == wallet_id else "Sent"
                counterparty = tx.get("from") if tx_type == "Received" else tx.get("to")
                amount = tx.get("amount_rtc", 0)
                timestamp = tx.get("timestamp", "")

                # Format time
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = timestamp[:16] if timestamp else "N/A"

                self.tx_tree.insert("", tk.END, values=(
                    time_str,
                    tx_type,
                    counterparty[:30] + "..." if counterparty and len(counterparty) > 30 else counterparty,
                    f"{amount:+.6f}" if tx_type == "Received" else f"-{amount:.6f}"
                ))

    def create_new_wallet(self):
        """Generate a new wallet ID"""
        # Generate random 32-byte hex string
        wallet_id = secrets.token_hex(16)
        self.current_wallet.set(wallet_id)
        self.balance.set("0.00000000 RTC")
        self.status_var.set(f"New wallet created: {wallet_id[:20]}...")

        # Clear history
        for item in self.tx_tree.get_children():
            self.tx_tree.delete(item)

        messagebox.showinfo("New Wallet",
                           f"New wallet created!\n\nWallet ID:\n{wallet_id}\n\n"
                           "Save this ID - you'll need it to access your funds!")

    def send_rtc(self):
        """Send RTC to another wallet"""
        from_wallet = self.current_wallet.get().strip()
        to_wallet = self.recipient_entry.get().strip()

        try:
            amount = float(self.amount_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid amount")
            return

        if not from_wallet:
            messagebox.showerror("Error", "Please load a wallet first")
            return

        if not to_wallet:
            messagebox.showerror("Error", "Please enter recipient wallet ID")
            return

        if amount <= 0:
            messagebox.showerror("Error", "Amount must be positive")
            return

        # Confirm
        if not messagebox.askyesno("Confirm Transfer",
                                   f"Send {amount:.6f} RTC to:\n{to_wallet}\n\nContinue?"):
            return

        self.status_var.set("Sending transaction...")

        # Make transfer
        data = self.api_call("/wallet/transfer", method="POST", data={
            "from_miner": from_wallet,
            "to_miner": to_wallet,
            "amount_rtc": amount
        })

        if data and data.get("ok"):
            sender_balance = data.get("sender_balance_rtc", 0)
            self.balance.set(f"{sender_balance:.8f} RTC")
            self.status_var.set(f"Sent {amount:.6f} RTC to {to_wallet[:20]}...")

            # Clear fields
            self.recipient_entry.delete(0, tk.END)
            self.amount_entry.delete(0, tk.END)

            # Reload history
            self.load_history(from_wallet)

            messagebox.showinfo("Success",
                              f"Transaction successful!\n\n"
                              f"Sent: {amount:.6f} RTC\n"
                              f"New balance: {sender_balance:.8f} RTC")
        elif data and "error" in data:
            messagebox.showerror("Error", data["error"])
            self.status_var.set(f"Error: {data['error']}")
        else:
            messagebox.showerror("Error", "Transaction failed")
            self.status_var.set("Transaction failed")


def main():
    root = tk.Tk()
    app = RustChainWallet(root)
    root.mainloop()


if __name__ == "__main__":
    main()
