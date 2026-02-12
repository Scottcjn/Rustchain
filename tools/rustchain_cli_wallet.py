#!/usr/bin/env python3
"""
RustChain CLI Wallet (Compatibility Edition)
Supports the hex-ID format used by the current Linux Miner.
"""

import requests
import json
import secrets
import sys
import argparse
from datetime import datetime
import urllib3

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NODE_URL = "https://50.28.86.131"
VERIFY_SSL = False

def create_wallet():
    wallet_id = secrets.token_hex(16)
    print(f"\n✨ New Wallet Created!")
    print(f"ID: {wallet_id}")
    print(f"⚠️  SAVE THIS ID! You will need it to access your RTC.")
    return wallet_id

def get_balance(wallet_id):
    url = f"{NODE_URL}/wallet/balance?miner_id={wallet_id}"
    try:
        resp = requests.get(url, verify=VERIFY_SSL, timeout=10)
        data = resp.json()
        balance = data.get("amount_rtc", 0)
        print(f"\n💰 Balance: {balance:.8f} RTC")
        return balance
    except Exception as e:
        print(f"❌ Error fetching balance: {e}")
        return None

def send_rtc(from_wallet, to_wallet, amount):
    url = f"{NODE_URL}/wallet/transfer"
    payload = {
        "from_miner": from_wallet,
        "to_miner": to_wallet,
        "amount_rtc": float(amount)
    }
    try:
        resp = requests.post(url, json=payload, verify=VERIFY_SSL, timeout=10)
        data = resp.json()
        if data.get("ok"):
            print(f"\n✅ Success! Sent {amount} RTC to {to_wallet}")
            print(f"New Balance: {data.get('sender_balance_rtc', 0):.8f} RTC")
        else:
            print(f"❌ Failed: {data.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error during transfer: {e}")

def get_history(wallet_id):
    url = f"{NODE_URL}/wallet/ledger?miner_id={wallet_id}"
    try:
        resp = requests.get(url, verify=VERIFY_SSL, timeout=10)
        data = resp.json()
        if "transactions" in data:
            print(f"\n📜 Recent Transactions for {wallet_id[:10]}...")
            print(f"{'Time':<20} | {'Type':<10} | {'Amount':<15} | {'Counterparty'}")
            print("-" * 75)
            for tx in data["transactions"][:10]:
                tx_type = "Received" if tx.get("to") == wallet_id else "Sent"
                amount = tx.get("amount_rtc", 0)
                amount_str = f"{'+' if tx_type == 'Received' else '-'}{amount:.6f}"
                counterparty = tx.get("from") if tx_type == "Received" else tx.get("to")
                time_str = tx.get("timestamp", "")[:19].replace("T", " ")
                print(f"{time_str:<20} | {tx_type:<10} | {amount_str:<15} | {counterparty}")
    except Exception as e:
        print(f"❌ Error fetching history: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RustChain CLI Wallet")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("create", help="Create a new wallet")
    
    balance_p = subparsers.add_parser("balance", help="Check wallet balance")
    balance_p.add_argument("wallet_id", help="Your wallet hex ID")

    history_p = subparsers.add_parser("history", help="Show transaction history")
    history_p.add_argument("wallet_id", help="Your wallet hex ID")

    send_p = subparsers.add_parser("send", help="Send RTC")
    send_p.add_argument("from_id", help="Your wallet hex ID")
    send_p.add_argument("to_id", help="Recipient wallet hex ID")
    send_p.add_argument("amount", type=float, help="Amount to send")

    args = parser.parse_args()

    if args.command == "create":
        create_wallet()
    elif args.command == "balance":
        get_balance(args.wallet_id)
    elif args.command == "history":
        get_history(args.wallet_id)
    elif args.command == "send":
        send_rtc(args.from_id, args.to_id, args.amount)
    else:
        parser.print_help()
