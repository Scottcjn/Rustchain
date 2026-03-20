# SPDX-License-Identifier: MIT

import argparse
import getpass
import json
import os
import sqlite3
import sys
import time
from base64 import b64encode, b64decode
from hashlib import sha256
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from mnemonic import Mnemonic

# Network configuration
DEFAULT_NODE = "https://50.28.86.131"
WALLET_DIR = Path.home() / ".rustchain" / "wallets"
DB_PATH = WALLET_DIR / "wallet.db"

class WalletError(Exception):
    pass

class RustChainWallet:
    def __init__(self, node_url: str = DEFAULT_NODE):
        self.node_url = node_url.rstrip('/')
        self.ensure_wallet_dir()
        self.init_db()

    def ensure_wallet_dir(self):
        WALLET_DIR.mkdir(parents=True, exist_ok=True)

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    name TEXT PRIMARY KEY,
                    encrypted_keystore BLOB NOT NULL,
                    salt BLOB NOT NULL,
                    public_key TEXT NOT NULL,
                    address TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    wallet_name TEXT,
                    tx_hash TEXT,
                    block_height INTEGER,
                    timestamp INTEGER,
                    amount REAL,
                    fee REAL,
                    from_addr TEXT,
                    to_addr TEXT,
                    tx_type TEXT,
                    FOREIGN KEY (wallet_name) REFERENCES wallets (name)
                )
            """)

    def derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        return kdf.derive(password.encode())

    def encrypt_keystore(self, private_key_bytes: bytes, password: str) -> Tuple[bytes, bytes]:
        salt = os.urandom(16)
        key = self.derive_key(password, salt)

        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, private_key_bytes, None)

        encrypted_data = nonce + ciphertext
        return encrypted_data, salt

    def decrypt_keystore(self, encrypted_data: bytes, password: str, salt: bytes) -> bytes:
        key = self.derive_key(password, salt)
        aesgcm = AESGCM(key)

        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]

        try:
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            raise WalletError("Invalid password")

    def generate_seed_phrase(self) -> str:
        mnemo = Mnemonic("english")
        return mnemo.generate(strength=256)

    def seed_to_private_key(self, seed_phrase: str) -> Ed25519PrivateKey:
        mnemo = Mnemonic("english")
        if not mnemo.check(seed_phrase):
            raise WalletError("Invalid seed phrase")

        seed = mnemo.to_seed(seed_phrase)
        private_key_bytes = sha256(seed).digest()[:32]
        return Ed25519PrivateKey.from_private_bytes(private_key_bytes)

    def address_from_public_key(self, public_key: Ed25519PublicKey) -> str:
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        addr_hash = sha256(pub_bytes).digest()
        return "rtc1" + b64encode(addr_hash[:20]).decode().rstrip('=')

    def create_wallet(self, name: str, password: str, seed_phrase: Optional[str] = None) -> Dict:
        if self.wallet_exists(name):
            raise WalletError(f"Wallet '{name}' already exists")

        if seed_phrase is None:
            seed_phrase = self.generate_seed_phrase()

        private_key = self.seed_to_private_key(seed_phrase)
        public_key = private_key.public_key()
        address = self.address_from_public_key(public_key)

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        encrypted_keystore, salt = self.encrypt_keystore(private_key_bytes, password)

        public_key_hex = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO wallets (name, encrypted_keystore, salt, public_key, address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, encrypted_keystore, salt, public_key_hex, address, int(time.time())))

        return {
            "name": name,
            "address": address,
            "seed_phrase": seed_phrase,
            "created": True
        }

    def wallet_exists(self, name: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT 1 FROM wallets WHERE name = ?", (name,))
            return cursor.fetchone() is not None

    def get_wallet_info(self, name: str) -> Optional[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT name, public_key, address, created_at FROM wallets WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "name": row[0],
                    "public_key": row[1],
                    "address": row[2],
                    "created_at": row[3]
                }
        return None

    def load_private_key(self, name: str, password: str) -> Ed25519PrivateKey:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT encrypted_keystore, salt FROM wallets WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if not row:
                raise WalletError(f"Wallet '{name}' not found")

        encrypted_keystore, salt = row
        private_key_bytes = self.decrypt_keystore(encrypted_keystore, password, salt)
        return Ed25519PrivateKey.from_private_bytes(private_key_bytes)

    def get_balance(self, address: str) -> float:
        try:
            response = requests.get(f"{self.node_url}/api/balance/{address}", timeout=10)
            if response.ok:
                data = response.json()
                return float(data.get("amount_rtc", 0))
        except Exception:
            pass
        return 0.0

    def send_transaction(self, from_wallet: str, password: str, to_address: str, amount: float) -> Dict:
        wallet_info = self.get_wallet_info(from_wallet)
        if not wallet_info:
            raise WalletError(f"Wallet '{from_wallet}' not found")

        private_key = self.load_private_key(from_wallet, password)

        # Build transaction payload
        tx_data = {
            "from": wallet_info["address"],
            "to": to_address,
            "amount": amount,
            "timestamp": int(time.time() * 1000)
        }

        # Sign transaction
        message = json.dumps(tx_data, sort_keys=True).encode()
        signature = private_key.sign(message)

        payload = {
            "transaction": tx_data,
            "signature": b64encode(signature).decode(),
            "public_key": wallet_info["public_key"]
        }

        try:
            response = requests.post(
                f"{self.node_url}/api/transaction",
                json=payload,
                timeout=15
            )

            if response.ok:
                result = response.json()
                if result.get("success"):
                    # Store transaction in local history
                    self.store_transaction(
                        from_wallet, result.get("tx_hash", "unknown"),
                        0, int(time.time()), -amount, 0,
                        wallet_info["address"], to_address, "send"
                    )
                return result
            else:
                raise WalletError(f"Transaction failed: {response.text}")
        except requests.RequestException as e:
            raise WalletError(f"Network error: {str(e)}")

    def store_transaction(self, wallet_name: str, tx_hash: str, block_height: int,
                         timestamp: int, amount: float, fee: float,
                         from_addr: str, to_addr: str, tx_type: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO transactions
                (wallet_name, tx_hash, block_height, timestamp, amount, fee, from_addr, to_addr, tx_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (wallet_name, tx_hash, block_height, timestamp, amount, fee, from_addr, to_addr, tx_type))

    def get_transaction_history(self, wallet_name: str, limit: int = 50) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT tx_hash, block_height, timestamp, amount, fee, from_addr, to_addr, tx_type
                FROM transactions
                WHERE wallet_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (wallet_name, limit))

            transactions = []
            for row in cursor.fetchall():
                transactions.append({
                    "tx_hash": row[0],
                    "block_height": row[1],
                    "timestamp": row[2],
                    "amount": row[3],
                    "fee": row[4],
                    "from_addr": row[5],
                    "to_addr": row[6],
                    "tx_type": row[7]
                })
            return transactions

    def export_wallet(self, name: str, password: str) -> str:
        private_key = self.load_private_key(name, password)

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Convert back to seed phrase
        seed = private_key_bytes + b'\x00' * 32  # Pad to 64 bytes
        mnemo = Mnemonic("english")
        return mnemo.to_mnemonic(seed[:32])

    def import_wallet(self, name: str, password: str, seed_phrase: str) -> Dict:
        if self.wallet_exists(name):
            raise WalletError(f"Wallet '{name}' already exists")

        return self.create_wallet(name, password, seed_phrase)

    def get_miners_info(self) -> List[Dict]:
        try:
            response = requests.get(f"{self.node_url}/api/miners", timeout=10)
            if response.ok:
                return response.json().get("miners", [])
        except Exception:
            pass
        return []

    def get_epoch_info(self) -> Dict:
        try:
            response = requests.get(f"{self.node_url}/api/epoch", timeout=10)
            if response.ok:
                return response.json()
        except Exception:
            pass
        return {}

    def list_wallets(self) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT name, address, created_at FROM wallets ORDER BY created_at")
            wallets = []
            for row in cursor.fetchall():
                wallets.append({
                    "name": row[0],
                    "address": row[1],
                    "created_at": row[2]
                })
            return wallets


def main():
    parser = argparse.ArgumentParser(description="RustChain Wallet CLI")
    parser.add_argument("--node", default=DEFAULT_NODE, help="RustChain node URL")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create wallet
    create_parser = subparsers.add_parser("create", help="Create new wallet")
    create_parser.add_argument("name", help="Wallet name")
    create_parser.add_argument("--seed", help="Import from seed phrase")

    # Balance
    balance_parser = subparsers.add_parser("balance", help="Show wallet balance")
    balance_parser.add_argument("wallet", help="Wallet name")

    # Send
    send_parser = subparsers.add_parser("send", help="Send RTC")
    send_parser.add_argument("wallet", help="From wallet name")
    send_parser.add_argument("to", help="Recipient address")
    send_parser.add_argument("amount", type=float, help="Amount to send")

    # Import
    import_parser = subparsers.add_parser("import", help="Import wallet from seed phrase")
    import_parser.add_argument("name", help="Wallet name")

    # Export
    export_parser = subparsers.add_parser("export", help="Export wallet seed phrase")
    export_parser.add_argument("wallet", help="Wallet name")

    # History
    history_parser = subparsers.add_parser("history", help="Show transaction history")
    history_parser.add_argument("wallet", help="Wallet name")
    history_parser.add_argument("--limit", type=int, default=20, help="Number of transactions")

    # Miners
    subparsers.add_parser("miners", help="Show active miners")

    # Epoch
    subparsers.add_parser("epoch", help="Show epoch information")

    # List wallets
    subparsers.add_parser("list", help="List all wallets")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    wallet_manager = RustChainWallet(args.node)

    try:
        if args.command == "create":
            password = getpass.getpass("Enter wallet password: ")
            confirm_password = getpass.getpass("Confirm password: ")

            if password != confirm_password:
                print("Error: Passwords do not match")
                return

            result = wallet_manager.create_wallet(args.name, password, args.seed)
            print(f"✅ Wallet '{result['name']}' created successfully")
            print(f"Address: {result['address']}")
            if not args.seed:
                print(f"\n⚠️  IMPORTANT: Save your seed phrase securely!")
                print(f"Seed phrase: {result['seed_phrase']}")

        elif args.command == "balance":
            wallet_info = wallet_manager.get_wallet_info(args.wallet)
            if not wallet_info:
                print(f"Error: Wallet '{args.wallet}' not found")
                return

            balance = wallet_manager.get_balance(wallet_info["address"])
            print(f"Wallet: {args.wallet}")
            print(f"Address: {wallet_info['address']}")
            print(f"Balance: {balance:.8f} RTC")

        elif args.command == "send":
            password = getpass.getpass("Enter wallet password: ")

            result = wallet_manager.send_transaction(args.wallet, password, args.to, args.amount)
            if result.get("success"):
                print(f"✅ Transaction sent successfully")
                print(f"TX Hash: {result.get('tx_hash', 'N/A')}")
            else:
                print(f"❌ Transaction failed: {result.get('error', 'Unknown error')}")

        elif args.command == "import":
            seed_phrase = getpass.getpass("Enter seed phrase: ")
            password = getpass.getpass("Enter wallet password: ")
            confirm_password = getpass.getpass("Confirm password: ")

            if password != confirm_password:
                print("Error: Passwords do not match")
                return

            result = wallet_manager.import_wallet(args.name, password, seed_phrase)
            print(f"✅ Wallet '{result['name']}' imported successfully")
            print(f"Address: {result['address']}")

        elif args.command == "export":
            password = getpass.getpass("Enter wallet password: ")

            seed_phrase = wallet_manager.export_wallet(args.wallet, password)
            print(f"⚠️  Seed phrase for wallet '{args.wallet}':")
            print(seed_phrase)

        elif args.command == "history":
            transactions = wallet_manager.get_transaction_history(args.wallet, args.limit)
            if not transactions:
                print("No transactions found")
                return

            print(f"Transaction history for '{args.wallet}' (last {len(transactions)}):")
            print("-" * 80)
            for tx in transactions:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tx["timestamp"]))
                print(f"{timestamp} | {tx['tx_type'].upper():4} | {tx['amount']:+.8f} RTC | {tx['tx_hash'][:16]}...")

        elif args.command == "miners":
            miners = wallet_manager.get_miners_info()
            if not miners:
                print("No miners information available")
                return

            print(f"Active Miners ({len(miners)}):")
            print("-" * 80)
            for miner in miners:
                hardware = miner.get("hardware_info", {})
                hw_type = hardware.get("arch", "Unknown")
                multiplier = miner.get("multiplier", 1.0)
                blocks = miner.get("blocks_mined", 0)
                print(f"{miner.get('id', 'Unknown')[:12]}... | {hw_type:12} | {multiplier:4.1f}x | {blocks:4} blocks")

        elif args.command == "epoch":
            epoch_info = wallet_manager.get_epoch_info()
            if not epoch_info:
                print("No epoch information available")
                return

            print("Current Epoch Information:")
            print("-" * 40)
            for key, value in epoch_info.items():
                print(f"{key.replace('_', ' ').title()}: {value}")

        elif args.command == "list":
            wallets = wallet_manager.list_wallets()
            if not wallets:
                print("No wallets found")
                return

            print(f"Local Wallets ({len(wallets)}):")
            print("-" * 80)
            for wallet in wallets:
                created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wallet["created_at"]))
                print(f"{wallet['name']:20} | {wallet['address']} | {created}")

    except WalletError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
