#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RustChain Wallet for PowerPC Macs (Tiger/Leopard)
Requires: Python 2.3+ with Tkinter (included in Mac OS X)

Usage: python rustchain_wallet_ppc.py [wallet_address]
"""

import os
import sys
import hashlib
import urllib
import urllib2
import socket

# Set default socket timeout for Python 2.3 compatibility
# (urllib2.urlopen timeout param added in Python 2.6)
socket.setdefaulttimeout(15)

# JSON support for Python 2.3-2.5 (json module added in 2.6)
try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        # Manual JSON parsing for Python 2.3
        class SimpleJSON:
            def loads(self, s):
                """Very basic JSON parser for simple objects"""
                s = s.strip()
                if s.startswith('{') and s.endswith('}'):
                    result = {}
                    s = s[1:-1].strip()
                    if not s:
                        return result
                    # Split by commas (simple case)
                    pairs = []
                    depth = 0
                    current = ""
                    for c in s:
                        if c in '{[':
                            depth += 1
                        elif c in '}]':
                            depth -= 1
                        if c == ',' and depth == 0:
                            pairs.append(current.strip())
                            current = ""
                        else:
                            current += c
                    if current.strip():
                        pairs.append(current.strip())

                    for pair in pairs:
                        if ':' in pair:
                            key, value = pair.split(':', 1)
                            key = key.strip().strip('"')
                            value = value.strip()
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value == 'true':
                                value = True
                            elif value == 'false':
                                value = False
                            elif value == 'null':
                                value = None
                            else:
                                try:
                                    if '.' in value:
                                        value = float(value)
                                    else:
                                        value = int(value)
                                except:
                                    pass
                            result[key] = value
                    return result
                return {}

            def dumps(self, obj):
                """Very basic JSON serializer"""
                if isinstance(obj, dict):
                    pairs = []
                    for k, v in obj.items():
                        pairs.append('"%s": %s' % (k, self.dumps(v)))
                    return '{%s}' % ', '.join(pairs)
                elif isinstance(obj, (list, tuple)):
                    return '[%s]' % ', '.join(self.dumps(x) for x in obj)
                elif isinstance(obj, str):
                    return '"%s"' % obj
                elif isinstance(obj, bool):
                    return 'true' if obj else 'false'
                elif obj is None:
                    return 'null'
                else:
                    return str(obj)

        json = SimpleJSON()

# Tkinter import (Python 2 style)
try:
    import Tkinter as tk
    import tkMessageBox
    import tkSimpleDialog
except ImportError:
    print "Error: Tkinter not available"
    sys.exit(1)

# Configuration
NODE_URL = "https://rustchain.org"
WALLET_FILE = os.path.expanduser("~/.rustchain_wallet")

class RustChainWallet:
    def __init__(self, root):
        self.root = root
        self.root.title("RustChain Wallet - PPC Edition")
        self.root.geometry("500x400")

        # Try to load or generate wallet
        self.wallet_address = self.load_or_create_wallet()

        self.create_widgets()
        self.refresh_balance()

    def load_or_create_wallet(self):
        """Load existing wallet or create new one"""
        if os.path.exists(WALLET_FILE):
            try:
                f = open(WALLET_FILE, 'r')
                addr = f.read().strip()
                f.close()
                if addr:
                    return addr
            except:
                pass

        # Generate deterministic wallet from hostname
        hostname = os.uname()[1]
        miner_id = "ppc-wallet-%s" % hostname
        wallet_hash = hashlib.sha256(miner_id).hexdigest()[:40]
        wallet_addr = "%sRTC" % wallet_hash

        # Save it
        try:
            f = open(WALLET_FILE, 'w')
            f.write(wallet_addr)
            f.close()
        except:
            pass

        return wallet_addr

    def create_widgets(self):
        # Title
        title = tk.Label(self.root, text="RustChain Wallet", font=("Helvetica", 18, "bold"))
        title.pack(pady=10)

        # Wallet Address Frame
        addr_frame = tk.LabelFrame(self.root, text="Your Wallet Address", padx=10, pady=10)
        addr_frame.pack(fill="x", padx=20, pady=10)

        self.addr_var = tk.StringVar()
        self.addr_var.set(self.wallet_address)
        addr_entry = tk.Entry(addr_frame, textvariable=self.addr_var, width=50, state="readonly")
        addr_entry.pack(fill="x")

        copy_btn = tk.Button(addr_frame, text="Copy Address", command=self.copy_address)
        copy_btn.pack(pady=5)

        # Balance Frame
        bal_frame = tk.LabelFrame(self.root, text="Balance", padx=10, pady=10)
        bal_frame.pack(fill="x", padx=20, pady=10)

        self.balance_var = tk.StringVar()
        self.balance_var.set("Loading...")
        balance_label = tk.Label(bal_frame, textvariable=self.balance_var, font=("Helvetica", 24, "bold"))
        balance_label.pack()

        refresh_btn = tk.Button(bal_frame, text="Refresh Balance", command=self.refresh_balance)
        refresh_btn.pack(pady=5)

        # Send Frame
        send_frame = tk.LabelFrame(self.root, text="Send RTC", padx=10, pady=10)
        send_frame.pack(fill="x", padx=20, pady=10)

        # To address
        to_label = tk.Label(send_frame, text="To Address:")
        to_label.grid(row=0, column=0, sticky="e", padx=5, pady=2)

        self.to_entry = tk.Entry(send_frame, width=45)
        self.to_entry.grid(row=0, column=1, padx=5, pady=2)

        # Amount
        amt_label = tk.Label(send_frame, text="Amount (RTC):")
        amt_label.grid(row=1, column=0, sticky="e", padx=5, pady=2)

        self.amt_entry = tk.Entry(send_frame, width=20)
        self.amt_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        send_btn = tk.Button(send_frame, text="Send RTC", command=self.send_rtc)
        send_btn.grid(row=2, column=1, pady=10)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Connected to: %s" % NODE_URL)
        status_bar = tk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    def copy_address(self):
        """Copy wallet address to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.wallet_address)
        self.status_var.set("Address copied to clipboard!")

    def refresh_balance(self):
        """Fetch balance from node"""
        self.status_var.set("Fetching balance...")
        self.root.update()

        try:
            url = "%s/balance/%s" % (NODE_URL, self.wallet_address)
            response = urllib2.urlopen(url)
            data = json.loads(response.read())

            # Server returns balance_rtc directly in RTC
            balance_rtc = data.get("balance_rtc", 0)
            if balance_rtc is None:
                balance_rtc = 0
            balance_rtc = float(balance_rtc)

            self.balance_var.set("%.4f RTC" % balance_rtc)
            self.status_var.set("Balance updated")
        except Exception, e:
            self.balance_var.set("Error")
            self.status_var.set("Error: %s" % str(e))

    def send_rtc(self):
        """Send RTC to another address"""
        to_addr = self.to_entry.get().strip()
        amount_str = self.amt_entry.get().strip()

        if not to_addr:
            tkMessageBox.showerror("Error", "Please enter a recipient address")
            return

        if not amount_str:
            tkMessageBox.showerror("Error", "Please enter an amount")
            return

        try:
            amount = float(amount_str)
        except:
            tkMessageBox.showerror("Error", "Invalid amount")
            return

        if amount <= 0:
            tkMessageBox.showerror("Error", "Amount must be positive")
            return

        # Confirm
        msg = "Send %.4f RTC to\n%s?" % (amount, to_addr)
        if not tkMessageBox.askyesno("Confirm Send", msg):
            return

        self.status_var.set("Sending transaction...")
        self.root.update()

        try:
            # Build transaction payload
            payload = {
                "from": self.wallet_address,
                "to": to_addr,
                "amount": int(amount * 1000000),  # Convert to micro-RTC
                "memo": "PPC Wallet Transfer"
            }

            url = "%s/wallet/transfer" % NODE_URL
            req = urllib2.Request(url, json.dumps(payload))
            req.add_header("Content-Type", "application/json")

            response = urllib2.urlopen(req)
            result = json.loads(response.read())

            if result.get("ok"):
                tkMessageBox.showinfo("Success", "Transaction sent successfully!")
                self.to_entry.delete(0, tk.END)
                self.amt_entry.delete(0, tk.END)
                self.refresh_balance()
            else:
                error = result.get("error", "Unknown error")
                tkMessageBox.showerror("Error", "Transaction failed: %s" % error)
        except Exception, e:
            tkMessageBox.showerror("Error", "Transaction failed: %s" % str(e))

        self.status_var.set("Ready")

def main():
    root = tk.Tk()

    # Set wallet address from command line if provided
    if len(sys.argv) > 1:
        global WALLET_FILE
        # Write provided address to wallet file
        addr = sys.argv[1]
        try:
            f = open(WALLET_FILE, 'w')
            f.write(addr)
            f.close()
        except:
            pass

    app = RustChainWallet(root)
    root.mainloop()

if __name__ == "__main__":
    main()
