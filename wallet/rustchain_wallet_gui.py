#!/usr/bin/env python3
"""
RustChain Wallet GUI
A simple graphical wallet for RTC transactions

Features:
- View balance for any wallet ID
- Send RTC to another wallet
- Transaction history
- Create new wallet
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import json
import hashlib
import secrets
from datetime import datetime
import urllib3

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
NODE_URL = "https://50.28.86.131"
VERIFY_SSL = False


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

    def api_call(self, endpoint, method="GET", data=None):
        """Make API call to RustChain node"""
        url = f"{NODE_URL}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, verify=VERIFY_SSL, timeout=10)
            else:
                resp = requests.post(url, json=data, verify=VERIFY_SSL, timeout=10)
            return resp.json()
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            return None

    def load_wallet(self):
        """Load wallet and display balance"""
        wallet_id = self.current_wallet.get().strip()
        if not wallet_id:
            messagebox.showwarning("Warning", "Please enter a wallet ID")
            return

        self.status_var.set(f"Loading wallet {wallet_id}...")

        # Get balance
        data = self.api_call(f"/wallet/balance?miner_id={wallet_id}")
        if data:
            balance = data.get("amount_rtc", 0)
            self.balance.set(f"{balance:.8f} RTC")
            self.status_var.set(f"Wallet loaded: {wallet_id}")
        else:
            # Wallet doesn't exist, show 0 balance
            self.balance.set("0.00000000 RTC")
            self.status_var.set(f"New wallet: {wallet_id}")

        # Load transaction history
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
