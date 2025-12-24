#!/usr/bin/env python3
"""
RustChain Secure Wallet - Founder Edition
Electrum-style wallet with BIP39 seed phrases and Ed25519 signatures

Features:
- 24-word seed phrase backup
- Password-encrypted keystore
- Ed25519 signed transactions
- Multiple wallet support (founder wallets)
- Transaction history
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import requests
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import urllib3

# Import our crypto module
from rustchain_crypto import RustChainWallet, verify_transaction

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
NODE_URL = "https://50.28.86.131"
VERIFY_SSL = False
KEYSTORE_DIR = Path.home() / ".rustchain" / "wallets"

# Ensure keystore directory exists
KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)


class SecureFounderWallet:
    """Secure founder wallet with seed phrase protection."""

    def __init__(self, root):
        self.root = root
        self.root.title("RustChain Secure Wallet - Founder Edition")
        self.root.geometry("950x800")
        self.root.configure(bg="#0d1117")

        # Current wallet
        self.wallet = None
        self.wallet_name = tk.StringVar(value="No wallet loaded")
        self.balance = tk.StringVar(value="0.00 RTC")
        self.address = tk.StringVar(value="")

        # Loaded wallets cache
        self.loaded_wallets = {}

        self.setup_styles()
        self.create_widgets()

        # Check for existing wallets
        self.check_existing_wallets()

    def setup_styles(self):
        """Configure ttk styles for secure wallet theme."""
        style = ttk.Style()
        style.theme_use('clam')

        # Dark theme with green security accents
        style.configure("TFrame", background="#0d1117")
        style.configure("TLabel", background="#0d1117", foreground="#c9d1d9", font=("Helvetica", 11))
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"), foreground="#58a6ff")
        style.configure("Balance.TLabel", font=("Helvetica", 32, "bold"), foreground="#3fb950")
        style.configure("Address.TLabel", font=("Courier", 10), foreground="#8b949e")
        style.configure("Secure.TLabel", font=("Helvetica", 10), foreground="#3fb950")
        style.configure("Warning.TLabel", font=("Helvetica", 10), foreground="#f85149")
        style.configure("TButton", font=("Helvetica", 10, "bold"), padding=8)
        style.configure("Secure.TButton", font=("Helvetica", 11, "bold"))
        style.configure("TEntry", font=("Helvetica", 11), padding=5)
        style.configure("Treeview", background="#161b22", foreground="#c9d1d9",
                       fieldbackground="#161b22", font=("Helvetica", 10))
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"),
                       background="#21262d", foreground="#58a6ff")

    def create_widgets(self):
        """Create all GUI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(header_frame, text="RustChain Secure Wallet",
                 style="Title.TLabel").pack(side=tk.LEFT)

        lock_label = ttk.Label(header_frame, text="[ENCRYPTED]",
                              style="Secure.TLabel")
        lock_label.pack(side=tk.RIGHT, padx=10)

        # Wallet Management Frame
        wallet_frame = ttk.LabelFrame(main_frame, text="Wallet", padding=10)
        wallet_frame.pack(fill=tk.X, pady=10)

        # Wallet info row
        info_row = ttk.Frame(wallet_frame)
        info_row.pack(fill=tk.X, pady=5)

        ttk.Label(info_row, textvariable=self.wallet_name,
                 font=("Helvetica", 12, "bold")).pack(side=tk.LEFT)

        # Wallet buttons
        btn_row = ttk.Frame(wallet_frame)
        btn_row.pack(fill=tk.X, pady=5)

        ttk.Button(btn_row, text="Create New Wallet",
                  command=self.create_new_wallet).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="Restore from Seed",
                  command=self.restore_from_seed).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="Load Wallet",
                  command=self.load_wallet_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="Backup Seed",
                  command=self.show_seed_phrase).pack(side=tk.LEFT, padx=3)

        # Address display
        addr_frame = ttk.Frame(wallet_frame)
        addr_frame.pack(fill=tk.X, pady=5)
        ttk.Label(addr_frame, text="Address:").pack(side=tk.LEFT)
        ttk.Label(addr_frame, textvariable=self.address,
                 style="Address.TLabel").pack(side=tk.LEFT, padx=10)

        copy_btn = ttk.Button(addr_frame, text="Copy",
                             command=self.copy_address)
        copy_btn.pack(side=tk.LEFT)

        # Balance Display
        balance_frame = ttk.LabelFrame(main_frame, text="Balance", padding=15)
        balance_frame.pack(fill=tk.X, pady=10)

        ttk.Label(balance_frame, textvariable=self.balance,
                 style="Balance.TLabel").pack()

        ttk.Button(balance_frame, text="Refresh",
                  command=self.refresh_balance).pack(pady=5)

        # Send Payment Frame
        send_frame = ttk.LabelFrame(main_frame, text="Send Payment (Signed)", padding=15)
        send_frame.pack(fill=tk.X, pady=10)

        # Recipient
        recv_frame = ttk.Frame(send_frame)
        recv_frame.pack(fill=tk.X, pady=5)
        ttk.Label(recv_frame, text="To Address:").pack(side=tk.LEFT)
        self.recipient_entry = ttk.Entry(recv_frame, width=50)
        self.recipient_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Amount and memo
        amt_frame = ttk.Frame(send_frame)
        amt_frame.pack(fill=tk.X, pady=5)

        ttk.Label(amt_frame, text="Amount:").pack(side=tk.LEFT)
        self.amount_entry = ttk.Entry(amt_frame, width=15)
        self.amount_entry.pack(side=tk.LEFT, padx=10)
        ttk.Label(amt_frame, text="RTC").pack(side=tk.LEFT)

        ttk.Label(amt_frame, text="   Memo:").pack(side=tk.LEFT, padx=(20, 0))
        self.memo_entry = ttk.Entry(amt_frame, width=30)
        self.memo_entry.pack(side=tk.LEFT, padx=10)

        # Quick amounts
        quick_amt_frame = ttk.Frame(send_frame)
        quick_amt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(quick_amt_frame, text="Quick Amount:").pack(side=tk.LEFT)
        for amt in [1, 10, 100, 500, 1000, 5000]:
            btn = ttk.Button(quick_amt_frame, text=f"{amt}",
                           command=lambda a=amt: self.set_amount(a))
            btn.pack(side=tk.LEFT, padx=2)

        # Send button with password
        send_row = ttk.Frame(send_frame)
        send_row.pack(fill=tk.X, pady=10)

        ttk.Label(send_row, text="Password:").pack(side=tk.LEFT)
        self.password_entry = ttk.Entry(send_row, width=20, show="*")
        self.password_entry.pack(side=tk.LEFT, padx=10)

        send_btn = ttk.Button(send_row, text="SIGN & SEND",
                             command=self.send_signed_payment,
                             style="Secure.TButton")
        send_btn.pack(side=tk.LEFT, padx=20)

        # Transaction signature info
        self.sig_label = ttk.Label(send_frame, text="", style="Secure.TLabel")
        self.sig_label.pack()

        # Transaction History
        history_frame = ttk.LabelFrame(main_frame, text="Transaction History", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("time", "type", "counterparty", "amount", "status")
        self.tx_tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=10)

        self.tx_tree.heading("time", text="Time")
        self.tx_tree.heading("type", text="Type")
        self.tx_tree.heading("counterparty", text="From/To")
        self.tx_tree.heading("amount", text="Amount")
        self.tx_tree.heading("status", text="Status")

        self.tx_tree.column("time", width=130)
        self.tx_tree.column("type", width=80)
        self.tx_tree.column("counterparty", width=200)
        self.tx_tree.column("amount", width=120)
        self.tx_tree.column("status", width=100)

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.tx_tree.yview)
        self.tx_tree.configure(yscrollcommand=scrollbar.set)

        self.tx_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)

        self.status_var = tk.StringVar(value="No wallet loaded - Create or restore a wallet")
        ttk.Label(status_frame, textvariable=self.status_var,
                 font=("Helvetica", 9)).pack(side=tk.LEFT)

        ttk.Label(status_frame, text="Ed25519 Signatures | BIP39 Seed Phrases",
                 style="Secure.TLabel").pack(side=tk.RIGHT)

    def check_existing_wallets(self):
        """Check for existing wallet files."""
        wallet_files = list(KEYSTORE_DIR.glob("*.json"))
        if wallet_files:
            self.status_var.set(f"Found {len(wallet_files)} wallet(s) - Click 'Load Wallet' to open")

    def create_new_wallet(self):
        """Create a new wallet with seed phrase."""
        # Get wallet name
        name = simpledialog.askstring("New Wallet", "Enter wallet name:",
                                     parent=self.root)
        if not name:
            return

        # Get password
        password = simpledialog.askstring("Set Password",
                                         "Enter encryption password:\n(You'll need this to send transactions)",
                                         parent=self.root, show='*')
        if not password:
            return

        # Confirm password
        confirm = simpledialog.askstring("Confirm Password",
                                        "Confirm password:",
                                        parent=self.root, show='*')
        if password != confirm:
            messagebox.showerror("Error", "Passwords don't match")
            return

        # Create wallet
        try:
            wallet = RustChainWallet.create()
            self.wallet = wallet

            # Show seed phrase - CRITICAL!
            self.show_seed_phrase_dialog(wallet.mnemonic, is_new=True)

            # Save encrypted
            encrypted = wallet.export_encrypted(password)
            encrypted["name"] = name

            wallet_path = KEYSTORE_DIR / f"{name}.json"
            with open(wallet_path, 'w') as f:
                json.dump(encrypted, f, indent=2)

            # Update UI
            self.wallet_name.set(name)
            self.address.set(wallet.address)
            self.status_var.set(f"Wallet '{name}' created and saved")
            self.refresh_balance()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create wallet: {e}")

    def show_seed_phrase_dialog(self, mnemonic: str, is_new: bool = False):
        """Show seed phrase in a secure dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("IMPORTANT: Backup Your Seed Phrase")
        dialog.geometry("600x500")
        dialog.configure(bg="#1a1a2e")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        if is_new:
            ttk.Label(frame, text="YOUR 24-WORD SEED PHRASE",
                     font=("Helvetica", 16, "bold"),
                     foreground="#f85149").pack(pady=10)

            ttk.Label(frame, text="Write these words down and store them safely.\n"
                               "Anyone with these words can access your funds!\n"
                               "Never share them. Never store them digitally.",
                     foreground="#f0883e").pack(pady=10)
        else:
            ttk.Label(frame, text="SEED PHRASE BACKUP",
                     font=("Helvetica", 16, "bold"),
                     foreground="#58a6ff").pack(pady=10)

        # Display words in grid
        words = mnemonic.split()
        word_frame = ttk.Frame(frame)
        word_frame.pack(pady=20)

        for i, word in enumerate(words):
            row = i // 4
            col = i % 4
            cell = ttk.Frame(word_frame)
            cell.grid(row=row, column=col, padx=10, pady=5)

            ttk.Label(cell, text=f"{i+1}.",
                     font=("Courier", 10),
                     foreground="#8b949e").pack(side=tk.LEFT)
            ttk.Label(cell, text=word,
                     font=("Courier", 12, "bold"),
                     foreground="#3fb950").pack(side=tk.LEFT, padx=5)

        if is_new:
            ttk.Label(frame, text="I have written down my seed phrase",
                     foreground="#8b949e").pack(pady=10)

            def confirm_backup():
                if messagebox.askyesno("Confirm",
                    "Have you written down all 24 words?\n\n"
                    "Without these words, you cannot recover your wallet!"):
                    dialog.destroy()

            ttk.Button(frame, text="I've Backed It Up",
                      command=confirm_backup).pack(pady=10)
        else:
            ttk.Button(frame, text="Close",
                      command=dialog.destroy).pack(pady=10)

    def show_seed_phrase(self):
        """Show seed phrase for current wallet (requires password)."""
        if not self.wallet:
            messagebox.showwarning("Warning", "No wallet loaded")
            return

        if not self.wallet.mnemonic:
            messagebox.showinfo("Info", "Seed phrase not available for this wallet")
            return

        password = simpledialog.askstring("Password Required",
                                         "Enter password to view seed phrase:",
                                         parent=self.root, show='*')
        if not password:
            return

        # Verify password by trying to load wallet
        try:
            wallet_path = KEYSTORE_DIR / f"{self.wallet_name.get()}.json"
            with open(wallet_path, 'r') as f:
                encrypted = json.load(f)
            RustChainWallet.from_encrypted(encrypted, password)
            self.show_seed_phrase_dialog(self.wallet.mnemonic)
        except Exception:
            messagebox.showerror("Error", "Invalid password")

    def restore_from_seed(self):
        """Restore wallet from seed phrase."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Restore from Seed Phrase")
        dialog.geometry("500x400")
        dialog.configure(bg="#0d1117")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Enter Your 24-Word Seed Phrase",
                 font=("Helvetica", 14, "bold")).pack(pady=10)

        ttk.Label(frame, text="Separate words with spaces:").pack()

        seed_text = tk.Text(frame, height=6, width=50, font=("Courier", 11))
        seed_text.pack(pady=10)

        ttk.Label(frame, text="Wallet Name:").pack()
        name_entry = ttk.Entry(frame, width=30)
        name_entry.pack(pady=5)

        ttk.Label(frame, text="Set Password:").pack()
        pass_entry = ttk.Entry(frame, width=30, show='*')
        pass_entry.pack(pady=5)

        def do_restore():
            mnemonic = seed_text.get("1.0", tk.END).strip().lower()
            name = name_entry.get().strip()
            password = pass_entry.get()

            if not name or not password:
                messagebox.showerror("Error", "Name and password required")
                return

            try:
                wallet = RustChainWallet.from_mnemonic(mnemonic)
                self.wallet = wallet

                # Save encrypted
                encrypted = wallet.export_encrypted(password)
                encrypted["name"] = name

                wallet_path = KEYSTORE_DIR / f"{name}.json"
                with open(wallet_path, 'w') as f:
                    json.dump(encrypted, f, indent=2)

                self.wallet_name.set(name)
                self.address.set(wallet.address)
                self.status_var.set(f"Wallet '{name}' restored successfully")
                self.refresh_balance()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Invalid seed phrase: {e}")

        ttk.Button(frame, text="Restore Wallet", command=do_restore).pack(pady=20)

    def load_wallet_dialog(self):
        """Load an existing wallet."""
        wallet_files = list(KEYSTORE_DIR.glob("*.json"))

        if not wallet_files:
            messagebox.showinfo("Info", "No wallets found. Create a new wallet first.")
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Wallet")
        dialog.geometry("400x300")
        dialog.configure(bg="#0d1117")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Select Wallet:",
                 font=("Helvetica", 12, "bold")).pack(pady=10)

        listbox = tk.Listbox(frame, font=("Helvetica", 11), height=8)
        listbox.pack(fill=tk.BOTH, expand=True, pady=10)

        for wf in wallet_files:
            listbox.insert(tk.END, wf.stem)

        ttk.Label(frame, text="Password:").pack()
        pass_entry = ttk.Entry(frame, width=30, show='*')
        pass_entry.pack(pady=5)

        def do_load():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Select a wallet")
                return

            name = listbox.get(selection[0])
            password = pass_entry.get()

            try:
                wallet_path = KEYSTORE_DIR / f"{name}.json"
                with open(wallet_path, 'r') as f:
                    encrypted = json.load(f)

                wallet = RustChainWallet.from_encrypted(encrypted, password)
                self.wallet = wallet
                self.wallet_name.set(name)
                self.address.set(wallet.address)
                self.status_var.set(f"Wallet '{name}' loaded")
                self.refresh_balance()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load wallet: {e}")

        ttk.Button(frame, text="Load", command=do_load).pack(pady=10)

    def copy_address(self):
        """Copy address to clipboard."""
        if self.wallet:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.wallet.address)
            self.status_var.set("Address copied to clipboard")

    def set_amount(self, amount):
        """Set amount from quick button."""
        self.amount_entry.delete(0, tk.END)
        self.amount_entry.insert(0, str(amount))

    def refresh_balance(self):
        """Refresh wallet balance."""
        if not self.wallet:
            return

        try:
            # Query by RTC address
            resp = requests.get(
                f"{NODE_URL}/wallet/balance?miner_id={self.wallet.address}",
                verify=VERIFY_SSL, timeout=10
            )
            data = resp.json()
            balance = data.get("amount_rtc", 0)
            self.balance.set(f"{balance:,.4f} RTC")
            self.status_var.set("Balance refreshed")
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    def send_signed_payment(self):
        """Send a cryptographically signed payment."""
        if not self.wallet:
            messagebox.showerror("Error", "No wallet loaded")
            return

        to_address = self.recipient_entry.get().strip()
        memo = self.memo_entry.get().strip()
        password = self.password_entry.get()

        try:
            amount = float(self.amount_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid amount")
            return

        if not to_address:
            messagebox.showerror("Error", "Enter recipient address")
            return

        if amount <= 0:
            messagebox.showerror("Error", "Amount must be positive")
            return

        if not password:
            messagebox.showerror("Error", "Enter your password to sign")
            return

        # Verify password
        try:
            wallet_path = KEYSTORE_DIR / f"{self.wallet_name.get()}.json"
            with open(wallet_path, 'r') as f:
                encrypted = json.load(f)
            verified_wallet = RustChainWallet.from_encrypted(encrypted, password)
        except Exception:
            messagebox.showerror("Error", "Invalid password")
            return

        # Confirm
        msg = f"Sign and send {amount:,.4f} RTC?\n\nFrom: {self.wallet.address[:30]}...\nTo: {to_address}"
        if memo:
            msg += f"\nMemo: {memo}"

        if not messagebox.askyesno("Confirm Transaction", msg):
            return

        # Sign transaction
        try:
            tx = verified_wallet.sign_transaction(to_address, amount, memo)

            self.sig_label.config(text=f"Signature: {tx['signature'][:40]}...")
            self.status_var.set("Transaction signed, sending...")

            # Send to node
            resp = requests.post(
                f"{NODE_URL}/wallet/transfer/signed",
                json=tx,
                verify=VERIFY_SSL,
                timeout=15
            )

            result = resp.json()

            if result.get("ok"):
                self.status_var.set(f"Sent {amount:,.4f} RTC")
                self.refresh_balance()

                # Add to history
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.tx_tree.insert("", 0, values=(
                    time_str, "Sent", to_address[:25] + "...",
                    f"-{amount:,.4f}", "Confirmed"
                ))

                # Clear fields
                self.recipient_entry.delete(0, tk.END)
                self.amount_entry.delete(0, tk.END)
                self.memo_entry.delete(0, tk.END)
                self.password_entry.delete(0, tk.END)

                messagebox.showinfo("Success", f"Transaction sent!\n\nAmount: {amount:,.4f} RTC")
            else:
                error = result.get("error", "Unknown error")
                messagebox.showerror("Error", error)
                self.status_var.set(f"Error: {error}")

        except Exception as e:
            messagebox.showerror("Error", f"Transaction failed: {e}")
            self.status_var.set(f"Error: {e}")


def main():
    root = tk.Tk()
    app = SecureFounderWallet(root)
    root.mainloop()


if __name__ == "__main__":
    main()
