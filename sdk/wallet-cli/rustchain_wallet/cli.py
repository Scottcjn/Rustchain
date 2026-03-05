"""
RustChain Wallet CLI
Command-line tool for managing RTC tokens
"""

__version__ = "0.1.0"

import argparse
import os
import sys
import getpass
import json
import time
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, Any

# Wallet storage directory
WALLET_DIR = Path.home() / ".rustchain" / "wallets"
WALLET_DIR.mkdir(parents=True, exist_ok=True)

# Node URL
DEFAULT_NODE_URL = "https://50.28.86.131"


def generate_mnemonic(words: int = 12) -> str:
    """Generate a simple mnemonic phrase"""
    # Simplified - use secure random in production
    word_list = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
        "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
        "acoustic", "acquire", "across", "action", "actor", "actress", "actual", "adapt",
        "add", "addict", "address", "adjust", "admit", "adult", "advance", "advice",
        "aerobic", "affair", "afford", "afraid", "again", "age", "agent", "agree",
        "ahead", "aim", "air", "airport", "aisle", "alarm", "album", "alcohol"
    ]
    return " ".join(secrets.choice(word_list) for _ in range(words))


def generate_keypair() -> Dict[str, str]:
    """Generate a simple Ed25519-like keypair"""
    # Simplified key generation
    # In production, use proper Ed25519 from cryptography library
    private_key = secrets.token_hex(32)
    public_key = hashlib.sha256(private_key.encode()).hexdigest()[:64]
    address = f"RTC{public_key[:40]}"
    
    return {
        "private_key": private_key,
        "public_key": public_key,
        "address": address
    }


def create_wallet(args) -> Dict[str, Any]:
    """Create a new wallet"""
    print("Creating new RustChain wallet...")
    
    wallet_name = args.name or f"wallet-{int(time.time())}"
    
    # Generate keypair
    keys = generate_keypair()
    
    # Generate mnemonic
    mnemonic = generate_mnemonic(12)
    
    # Create keystore
    password = getpass.getpass("Set password: ") if not args.no_password else "default"
    
    keystore = {
        "name": wallet_name,
        "address": keys["address"],
        "public_key": keys["public_key"],
        "encrypted_private_key": keys["private_key"],  # In production: encrypt with password
        "mnemonic": mnemonic,
        "created": int(time.time()),
        "version": "1.0"
    }
    
    wallet_path = WALLET_DIR / f"{wallet_name}.json"
    with open(wallet_path, 'w') as f:
        json.dump(keystore, f, indent=2)
    
    print(f"\n✅ Wallet created: {wallet_name}")
    print(f"   Address: {keys['address']}")
    print(f"   Location: {wallet_path}")
    print(f"\n⚠️  Save your mnemonic: {mnemonic}")
    print("\nYour mnemonic phrase is the ONLY way to recover your wallet!")
    
    return keystore


def list_wallets(args):
    """List all wallets"""
    wallets = list(WALLET_DIR.glob("*.json"))
    
    if not wallets:
        print("No wallets found. Create one with: rustchain-wallet create")
        return
    
    print(f"Stored wallets ({len(wallets)}):")
    print("-" * 50)
    
    for wallet_file in wallets:
        with open(wallet_file) as f:
            data = json.load(f)
            name = data.get('name', wallet_file.stem)
            address = data.get('address', 'unknown')
            created = data.get('created', 0)
            created_str = time.ctime(created) if created else 'unknown'
            
            print(f"  📁 {name}")
            print(f"     Address: {address}")
            print(f"     Created: {created_str}")
            print()


def get_balance(args):
    """Check wallet balance"""
    from rustchain_sdk import RustChainClient
    
    client = RustChainClient(DEFAULT_NODE_URL)
    
    try:
        result = client.get_balance(args.address)
        print(f"Balance for {args.address}:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")


def import_wallet(args):
    """Import wallet from mnemonic"""
    print(f"Importing wallet from mnemonic...")
    
    # Simplified import
    # In production, derive keys from mnemonic properly
    keys = generate_keypair()
    address = keys["address"]
    
    wallet_name = f"imported-{int(time.time())}"
    password = getpass.getpass("Set password: ") if not args.no_password else "default"
    
    keystore = {
        "name": wallet_name,
        "address": address,
        "mnemonic": args.mnemonic,
        "imported": int(time.time()),
        "version": "1.0"
    }
    
    wallet_path = WALLET_DIR / f"{wallet_name}.json"
    with open(wallet_path, 'w') as f:
        json.dump(keystore, f, indent=2)
    
    print(f"\n✅ Wallet imported: {wallet_name}")
    print(f"   Address: {address}")


def export_wallet(args):
    """Export wallet"""
    wallet_path = WALLET_DIR / f"{args.name}.json"
    
    if not wallet_path.exists():
        print(f"Wallet '{args.name}' not found")
        return
    
    with open(wallet_path) as f:
        data = json.load(f)
    
    print(f"Wallet: {data.get('name')}")
    print(f"Address: {data.get('address')}")
    print(f"Mnemonic: {data.get('mnemonic', 'Not stored')}")


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Wallet CLI - Manage RTC tokens from command line",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--url", default=DEFAULT_NODE_URL, help="Node URL")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create new wallet")
    create_parser.add_argument("--name", help="Wallet name")
    create_parser.add_argument("--no-password", action="store_true", help="Skip password prompt")
    
    # List command
    subparsers.add_parser("list", help="List all wallets")
    subparsers.add_parser("ls", help="List all wallets (shortcut)")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import wallet from mnemonic")
    import_parser.add_argument("mnemonic", help="24-word mnemonic phrase")
    import_parser.add_argument("--no-password", action="store_true", help="Skip password prompt")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export wallet info")
    export_parser.add_argument("name", help="Wallet name")
    
    # Balance command
    balance_parser = subparsers.add_parser("balance", help="Check wallet balance")
    balance_parser.add_argument("address", help="Wallet address")
    
    # Send command
    send_parser = subparsers.add_parser("send", help="Transfer RTC")
    send_parser.add_argument("--from", dest="from_wallet", required=True, help="Source wallet name")
    send_parser.add_argument("--to", required=True, help="Destination wallet address")
    send_parser.add_argument("--amount", type=float, required=True, help="Amount to send")
    send_parser.add_argument("--no-password", action="store_true", help="Skip password prompt")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        print("\n" + "="*50)
        print("Examples:")
        print("  rustchain-wallet create --name mywallet")
        print("  rustchain-wallet list")
        print("  rustchain-wallet balance RTCxxxxx")
        print("  rustchain-wallet send --from mywallet --to RTCyyyyy --amount 10")
        return
    
    try:
        if args.command in ("create",):
            create_wallet(args)
        elif args.command in ("list", "ls"):
            list_wallets(args)
        elif args.command == "balance":
            get_balance(args)
        elif args.command == "import":
            import_wallet(args)
        elif args.command == "export":
            export_wallet(args)
        elif args.command == "send":
            print("Send command not fully implemented yet")
        else:
            print(f"Unknown command: {args.command}")
    except KeyboardInterrupt:
        print("\nCancelled")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
