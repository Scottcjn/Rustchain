// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import sys
import sqlite3
from decimal import Decimal
import requests
from rustchain_crypto import RustChainCrypto

DB_PATH = "rustchain_wallet.db"
NODE_URL = "https://50.28.86.131"

class RustChainWallet:
    def __init__(self):
        self.crypto = RustChainCrypto()
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    private_key TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    label TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    txid TEXT PRIMARY KEY,
                    from_address TEXT,
                    to_address TEXT,
                    amount REAL,
                    fee REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def create_wallet(self, label=None):
        private_key, public_key = self.crypto.generate_keypair()
        address = self.crypto.derive_address(public_key)

        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute(
                    "INSERT INTO wallets (address, private_key, public_key, label) VALUES (?, ?, ?, ?)",
                    (address, private_key, public_key, label)
                )
                conn.commit()
                print(f"✓ New wallet created")
                print(f"Address: {address}")
                if label:
                    print(f"Label: {label}")
                return address
            except sqlite3.IntegrityError:
                print("✗ Wallet already exists")
                return None

    def list_wallets(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT address, label, created_at FROM wallets ORDER BY created_at")
            wallets = cursor.fetchall()

            if not wallets:
                print("No wallets found. Create one with 'create' command.")
                return

            print("\nYour RustChain Wallets:")
            print("-" * 60)
            for addr, lbl, created in wallets:
                balance = self.get_balance(addr)
                label_str = f" ({lbl})" if lbl else ""
                print(f"{addr[:20]}...{label_str}")
                print(f"  Balance: {balance} RTC")
                print(f"  Created: {created}")
                print()

    def get_balance(self, address):
        try:
            response = requests.get(f"{NODE_URL}/api/balance/{address}", timeout=10, verify=False)
            if response.status_code == 200:
                data = response.json()
                return Decimal(str(data.get('balance', 0)))
            else:
                return Decimal('0')
        except Exception:
            return Decimal('0')

    def send_rtc(self, from_address, to_address, amount, fee=0.001):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT private_key FROM wallets WHERE address = ?", (from_address,))
            result = cursor.fetchone()

            if not result:
                print("✗ Wallet not found in local storage")
                return False

            private_key = result[0]

            # Check balance
            balance = self.get_balance(from_address)
            total_needed = Decimal(str(amount)) + Decimal(str(fee))

            if balance < total_needed:
                print(f"✗ Insufficient balance. Need {total_needed} RTC, have {balance} RTC")
                return False

            # Create transaction
            tx_data = {
                'from': from_address,
                'to': to_address,
                'amount': float(amount),
                'fee': float(fee),
                'timestamp': self.crypto.get_timestamp()
            }

            # Sign transaction
            tx_hash = self.crypto.hash_transaction(tx_data)
            signature = self.crypto.sign_data(private_key, tx_hash)

            tx_data['signature'] = signature
            tx_data['hash'] = tx_hash

            try:
                response = requests.post(
                    f"{NODE_URL}/api/transaction",
                    json=tx_data,
                    timeout=15,
                    verify=False
                )

                if response.status_code == 200:
                    result_data = response.json()
                    if result_data.get('success'):
                        # Store transaction locally
                        conn.execute(
                            "INSERT INTO transactions (txid, from_address, to_address, amount, fee, status) VALUES (?, ?, ?, ?, ?, ?)",
                            (tx_hash, from_address, to_address, amount, fee, 'pending')
                        )
                        conn.commit()

                        print(f"✓ Transaction sent successfully")
                        print(f"Transaction ID: {tx_hash}")
                        print(f"Amount: {amount} RTC")
                        print(f"Fee: {fee} RTC")
                        print(f"To: {to_address}")
                        return True
                    else:
                        print(f"✗ Transaction failed: {result_data.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"✗ Network error: {response.status_code}")
                    return False
            except Exception as e:
                print(f"✗ Connection failed: {str(e)}")
                return False

    def import_wallet(self, private_key, label=None):
        try:
            public_key = self.crypto.get_public_key(private_key)
            address = self.crypto.derive_address(public_key)

            with sqlite3.connect(DB_PATH) as conn:
                try:
                    conn.execute(
                        "INSERT INTO wallets (address, private_key, public_key, label) VALUES (?, ?, ?, ?)",
                        (address, private_key, public_key, label)
                    )
                    conn.commit()
                    print(f"✓ Wallet imported successfully")
                    print(f"Address: {address}")
                    if label:
                        print(f"Label: {label}")
                    return address
                except sqlite3.IntegrityError:
                    print("✗ Wallet already exists")
                    return None
        except Exception as e:
            print(f"✗ Invalid private key: {str(e)}")
            return None

    def export_wallet(self, address, output_file=None):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT private_key, public_key, label FROM wallets WHERE address = ?",
                (address,)
            )
            result = cursor.fetchone()

            if not result:
                print("✗ Wallet not found")
                return False

            private_key, public_key, label = result

            export_data = {
                'address': address,
                'private_key': private_key,
                'public_key': public_key,
                'label': label,
                'export_time': self.crypto.get_timestamp()
            }

            if output_file:
                try:
                    with open(output_file, 'w') as f:
                        json.dump(export_data, f, indent=2)
                    print(f"✓ Wallet exported to {output_file}")
                    return True
                except Exception as e:
                    print(f"✗ Export failed: {str(e)}")
                    return False
            else:
                print("\nWallet Export Data:")
                print("=" * 50)
                print(json.dumps(export_data, indent=2))
                print("\n⚠️  Keep this private key secure!")
                return True

def main():
    parser = argparse.ArgumentParser(description="RustChain Wallet CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Create wallet
    create_parser = subparsers.add_parser('create', help='Create new wallet')
    create_parser.add_argument('--label', help='Optional wallet label')

    # List wallets
    subparsers.add_parser('list', help='List all wallets')

    # Check balance
    balance_parser = subparsers.add_parser('balance', help='Check wallet balance')
    balance_parser.add_argument('address', help='Wallet address')

    # Send RTC
    send_parser = subparsers.add_parser('send', help='Send RTC tokens')
    send_parser.add_argument('from_addr', help='From address')
    send_parser.add_argument('to_addr', help='To address')
    send_parser.add_argument('amount', type=float, help='Amount to send')
    send_parser.add_argument('--fee', type=float, default=0.001, help='Transaction fee (default: 0.001)')

    # Import wallet
    import_parser = subparsers.add_parser('import', help='Import wallet from private key')
    import_parser.add_argument('private_key', help='Private key to import')
    import_parser.add_argument('--label', help='Optional wallet label')

    # Export wallet
    export_parser = subparsers.add_parser('export', help='Export wallet private key')
    export_parser.add_argument('address', help='Wallet address to export')
    export_parser.add_argument('--output', help='Output file (prints to console if not specified)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    wallet = RustChainWallet()

    if args.command == 'create':
        wallet.create_wallet(args.label)

    elif args.command == 'list':
        wallet.list_wallets()

    elif args.command == 'balance':
        balance = wallet.get_balance(args.address)
        print(f"Balance for {args.address}: {balance} RTC")

    elif args.command == 'send':
        wallet.send_rtc(args.from_addr, args.to_addr, args.amount, args.fee)

    elif args.command == 'import':
        wallet.import_wallet(args.private_key, args.label)

    elif args.command == 'export':
        wallet.export_wallet(args.address, args.output)

if __name__ == '__main__':
    main()
