#!/usr/bin/env python3
"""
RustChain Signed Transfer Example — Bounty #1494

This script demonstrates how to create and submit a signed transfer transaction
on the RustChain network using Ed25519 signatures.

Features:
- Generate Ed25519 keypair (or use existing mnemonic)
- Construct transfer payload
- Sign with Ed25519
- Submit to node API
- Verify transaction status

Requirements:
    pip install cryptography requests

Usage:
    # Generate new wallet and send transfer
    python3 signed_transfer_example.py --generate --to RECIPIENT_WALLET --amount 1.0

    # Use existing mnemonic
    python3 signed_transfer_example.py --mnemonic "word1 word2 ... word24" --to RECIPIENT --amount 0.5

    # Dry run (no actual transfer)
    python3 signed_transfer_example.py --dry-run --to RECIPIENT --amount 1.0
"""

import argparse
import hashlib
import json
import sys
import time
from typing import Optional, Tuple

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

# Configuration
NODE_URL = "https://rustchain.org"
VERIFY_SSL = False  # Node uses self-signed certificate

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RustChainWallet:
    """Simple Ed25519 wallet for signing transfers."""

    def __init__(self, private_key: Optional[Ed25519PrivateKey] = None):
        if private_key is None:
            self.private_key = Ed25519PrivateKey.generate()
        else:
            self.private_key = private_key
        self.public_key = self.private_key.public_key()

    @classmethod
    def from_mnemonic(cls, mnemonic: str, passphrase: str = "") -> "RustChainWallet":
        """
        Derive Ed25519 keypair from BIP39 mnemonic.

        Uses SLIP10-style derivation for Ed25519.
        """
        try:
            from mnemonic import Mnemonic
        except ImportError:
            raise ImportError("Install mnemonic: pip install mnemonic")

        m = Mnemonic("english")
        if not m.check(mnemonic):
            raise ValueError("Invalid BIP39 mnemonic")

        # Derive seed
        seed = Mnemonic.to_seed(mnemonic, passphrase=passphrase)

        # SLIP10 master key derivation for Ed25519
        import hmac
        i = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
        sk = i[:32]

        # Create private key from raw bytes
        private_key = Ed25519PrivateKey.from_private_bytes(sk)
        return cls(private_key)

    @classmethod
    def from_seed_hex(cls, seed_hex: str) -> "RustChainWallet":
        """Create wallet from raw seed hex string."""
        seed_bytes = bytes.fromhex(seed_hex)
        private_key = Ed25519PrivateKey.from_private_bytes(seed_bytes)
        return cls(private_key)

    @property
    def address(self) -> str:
        """Get wallet address (RTC prefix + SHA256 hash of pubkey)."""
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        hash_hex = hashlib.sha256(pub_bytes).hexdigest()[:40]
        return f"RTC{hash_hex}"

    @property
    def public_key_hex(self) -> str:
        """Get public key as hex string."""
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return pub_bytes.hex()

    @property
    def private_key_hex(self) -> str:
        """Get private key as hex string (KEEP SECRET!)."""
        priv_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw
        )
        return priv_bytes.hex()

    def sign_message(self, message: bytes) -> str:
        """Sign a message and return signature as hex string."""
        signature = self.private_key.sign(message)
        return signature.hex()

    def sign_transfer_payload(self, payload: dict) -> str:
        """
        Sign a transfer payload.

        The message to sign is the JSON-serialized payload with sorted keys.
        """
        # Canonical JSON serialization (sorted keys, no spaces)
        message = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        message_bytes = message.encode('utf-8')
        return self.sign_message(message_bytes)


class RustChainClient:
    """HTTP client for RustChain node API."""

    def __init__(self, base_url: str = NODE_URL, verify_ssl: bool = VERIFY_SSL):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl

    def health(self) -> dict:
        """Check node health."""
        response = self.session.get(f"{self.base_url}/health", timeout=10)
        response.raise_for_status()
        return response.json()

    def balance(self, miner_id: str) -> dict:
        """Get wallet balance."""
        response = self.session.get(
            f"{self.base_url}/wallet/balance",
            params={"miner_id": miner_id},
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def submit_signed_transfer(
        self,
        from_address: str,
        to_address: str,
        amount_rtc: float,
        signature: str,
        public_key: str,
        nonce: Optional[int] = None,
        memo: str = ""
    ) -> dict:
        """
        Submit a signed transfer transaction.

        Args:
            from_address: Sender's RTC wallet address
            to_address: Recipient's RTC wallet address
            amount_rtc: Amount to transfer in RTC
            signature: Ed25519 signature (hex)
            public_key: Sender's public key (hex)
            nonce: Unique nonce for replay protection (default: timestamp)
            memo: Optional memo

        Returns:
            Transaction result dict
        """
        if nonce is None:
            nonce = int(time.time() * 1000)  # Millisecond timestamp

        payload = {
            "from_address": from_address,
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "nonce": nonce,
            "signature": signature,
            "public_key": public_key,
            "memo": memo
        }

        response = self.session.post(
            f"{self.base_url}/wallet/transfer/signed",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP session."""
        self.session.close()


def generate_wallet() -> Tuple[RustChainWallet, str]:
    """Generate a new wallet and return wallet + mnemonic."""
    try:
        from mnemonic import Mnemonic
    except ImportError:
        raise ImportError("Install mnemonic: pip install mnemonic")

    m = Mnemonic("english")
    mnemonic = m.generate(strength=256)  # 24 words
    wallet = RustChainWallet.from_mnemonic(mnemonic)
    return wallet, mnemonic


def print_wallet_info(wallet: RustChainWallet, mnemonic: Optional[str] = None):
    """Print wallet information."""
    print("\n" + "=" * 60)
    print("WALLET INFORMATION")
    print("=" * 60)
    print(f"Address:     {wallet.address}")
    print(f"Public Key:  {wallet.public_key_hex}")
    if mnemonic:
        print(f"\n⚠️  SEED PHRASE (STORE SECURELY):\n{mnemonic}")
    print("=" * 60 + "\n")


def validate_address(address: str) -> bool:
    """Validate RTC wallet address format."""
    if not address.startswith("RTC"):
        return False
    if len(address) != 43:  # RTC + 40 hex chars
        return False
    try:
        int(address[3:], 16)
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Signed Transfer Example (Bounty #1494)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate new wallet and check balance
  python3 signed_transfer_example.py --generate --balance-only

  # Send transfer with new wallet
  python3 signed_transfer_example.py --generate --to RTCabc... --amount 1.0

  # Use existing mnemonic
  python3 signed_transfer_example.py --mnemonic "word1 word2 ..." --to RTCabc... --amount 0.5

  # Dry run (no actual transfer)
  python3 signed_transfer_example.py --dry-run --to RTCabc... --amount 1.0
        """
    )

    parser.add_argument("--generate", action="store_true",
                       help="Generate a new wallet")
    parser.add_argument("--mnemonic", type=str,
                       help="Use existing BIP39 mnemonic (24 words)")
    parser.add_argument("--seed", type=str,
                       help="Use raw seed hex (64 chars)")
    parser.add_argument("--to", type=str, dest="recipient",
                       help="Recipient wallet address")
    parser.add_argument("--amount", type=float, default=1.0,
                       help="Amount to transfer in RTC (default: 1.0)")
    parser.add_argument("--memo", type=str, default="",
                       help="Optional memo for the transfer")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show transaction details without submitting")
    parser.add_argument("--balance-only", action="store_true",
                       help="Only check balance, don't send transfer")
    parser.add_argument("--node", type=str, default=NODE_URL,
                       help=f"Node URL (default: {NODE_URL})")

    args = parser.parse_args()

    # Validate arguments
    if not any([args.generate, args.mnemonic, args.seed]):
        print("Error: Must specify --generate, --mnemonic, or --seed")
        parser.print_help()
        sys.exit(1)

    if args.recipient and not validate_address(args.recipient):
        print(f"Error: Invalid recipient address: {args.recipient}")
        print("Address must start with 'RTC' followed by 40 hex characters")
        sys.exit(1)

    # Create wallet
    wallet: Optional[RustChainWallet] = None
    mnemonic: Optional[str] = None

    try:
        if args.generate:
            wallet, mnemonic = generate_wallet()
            print_wallet_info(wallet, mnemonic)
        elif args.mnemonic:
            wallet = RustChainWallet.from_mnemonic(args.mnemonic)
            print_wallet_info(wallet)
        elif args.seed:
            if len(args.seed) != 64:
                print("Error: Seed must be 64 hex characters (32 bytes)")
                sys.exit(1)
            wallet = RustChainWallet.from_seed_hex(args.seed)
            print_wallet_info(wallet)
    except Exception as e:
        print(f"Error creating wallet: {e}")
        sys.exit(1)

    # Initialize client
    client = RustChainClient(base_url=args.node)

    try:
        # Check node health
        print("Checking node health...")
        health = client.health()
        print(f"✓ Node healthy: {health.get('version', 'unknown')}")

        # Check balance
        print(f"\nChecking balance for {wallet.address}...")
        try:
            balance = client.balance(wallet.address)
            amount_rtc = balance.get("amount_rtc", 0)
            print(f"Balance: {amount_rtc} RTC")

            if args.balance_only:
                print("\n✓ Balance check complete")
                return

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                print("Wallet not found (may need to be created on-chain first)")
            else:
                raise

        # Prepare transfer
        if not args.recipient:
            print("\nNo recipient specified. Use --to <address> to send transfer.")
            print("\nTo get test RTC, visit the faucet or ask in the community.")
            return

        if args.amount <= 0:
            print("Error: Amount must be positive")
            sys.exit(1)

        # Construct payload for signing
        nonce = int(time.time() * 1000)
        payload_for_signing = {
            "from_address": wallet.address,
            "to_address": args.recipient,
            "amount_rtc": args.amount,
            "nonce": nonce,
            "memo": args.memo
        }

        # Sign the payload
        signature = wallet.sign_transfer_payload(payload_for_signing)

        # Display transaction details
        print("\n" + "=" * 60)
        print("TRANSACTION DETAILS")
        print("=" * 60)
        print(f"From:        {wallet.address}")
        print(f"To:          {args.recipient}")
        print(f"Amount:      {args.amount} RTC")
        print(f"Nonce:       {nonce}")
        print(f"Memo:        {args.memo or '(none)'}")
        print(f"Public Key:  {wallet.public_key_hex}")
        print(f"Signature:   {signature[:64]}...")
        print("=" * 60)

        if args.dry_run:
            print("\n🔍 DRY RUN - Transaction NOT submitted")
            print("\nTo submit, remove --dry-run flag")
            return

        # Confirm before sending
        if amount_rtc < args.amount:
            print(f"\n⚠️  WARNING: Balance ({amount_rtc} RTC) < Amount ({args.amount} RTC)")
            print("Transaction will likely fail with insufficient balance")

        confirm = input("\nSubmit transaction? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("Transaction cancelled")
            return

        # Submit transaction
        print("\nSubmitting transaction...")
        result = client.submit_signed_transfer(
            from_address=wallet.address,
            to_address=args.recipient,
            amount_rtc=args.amount,
            signature=signature,
            public_key=wallet.public_key_hex,
            nonce=nonce,
            memo=args.memo
        )

        # Display result
        print("\n" + "=" * 60)
        print("TRANSACTION RESULT")
        print("=" * 60)

        if result.get("ok") or result.get("success"):
            print("✓ Transaction submitted successfully!")
            if "tx_hash" in result:
                print(f"TX Hash: {result['tx_hash']}")
            if "replay_protected" in result:
                print(f"Replay Protected: {result['replay_protected']}")
        else:
            print("⚠️  Transaction submitted with warnings:")
            print(f"Response: {json.dumps(result, indent=2)}")

        print("=" * 60)

    except requests.exceptions.ConnectionError as e:
        print(f"\nError: Could not connect to node: {e}")
        print("Check your network connection and node URL")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\nError: Request timed out")
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"\nError: HTTP {e.response.status_code}")
        try:
            error_body = e.response.json()
            print(f"Response: {json.dumps(error_body, indent=2)}")
        except:
            print(f"Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
