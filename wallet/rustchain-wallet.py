#!/usr/bin/env python3
"""
RustChain Wallet CLI
Command-line interface for managing RTC tokens.
Bounty #39 Implementation
"""

import os
import sys
import json
import time
import hashlib
import base64
import click
import requests
from pathlib import Path
from mnemonic import Mnemonic
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Configuration
NODE_URL = "http://127.0.0.1:8099"
WALLET_DIR = Path.home() / ".rustchain" / "wallets"
KDF_ITERATIONS = 100000

# Ensure directories exist
WALLET_DIR.mkdir(parents=True, exist_ok=True)

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from a password and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode())

def encrypt_data(data: bytes, password: str) -> dict:
    """Encrypt data using AES-256-GCM with PBKDF2 key derivation."""
    salt = os.urandom(16)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    
    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "salt": base64.b64encode(salt).decode(),
        "kdf": "pbkdf2",
        "iterations": KDF_ITERATIONS
    }

def decrypt_data(encrypted: dict, password: str) -> bytes:
    """Decrypt data using AES-256-GCM."""
    try:
        salt = base64.b64decode(encrypted["salt"])
        nonce = base64.b64decode(encrypted["nonce"])
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        
        key = derive_key(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Invalid password or corrupted data")

def get_address_from_pubkey(pubkey_hex: str) -> str:
    """Generate RTC address from public key."""
    pubkey_hash = hashlib.sha256(bytes.fromhex(pubkey_hex)).hexdigest()[:40]
    return f"RTC{pubkey_hash}"

class WalletManager:
    def __init__(self, name: str):
        self.name = name
        self.path = WALLET_DIR / f"{name}.json"

    def exists(self) -> bool:
        return self.path.exists()

    def create(self, password: str, mnemonic_str: str = None) -> str:
        """Create or import a wallet."""
        mnemo = Mnemonic("english")
        if mnemonic_str:
            if not mnemo.check(mnemonic_str):
                raise ValueError("Invalid seed phrase")
        else:
            mnemonic_str = mnemo.generate(strength=256) # 24 words

        # Derive seed from mnemonic
        seed = mnemo.to_seed(mnemonic_str)
        # Use first 32 bytes of seed for Ed25519 signing key
        sk = SigningKey(seed[:32])
        vk = sk.verify_key
        
        pubkey_hex = vk.encode().hex()
        address = get_address_from_pubkey(pubkey_hex)
        
        wallet_data = {
            "address": address,
            "public_key": pubkey_hex,
            "mnemonic": mnemonic_str,
            "encrypted_private_key": encrypt_data(sk.encode(), password)
        }
        
        with open(self.path, 'w') as f:
            json.dump(wallet_data, f, indent=2)
            
        return address, mnemonic_str

    def load_private_key(self, password: str) -> SigningKey:
        with open(self.path, 'r') as f:
            data = json.load(f)
        
        sk_bytes = decrypt_data(data["encrypted_private_key"], password)
        return SigningKey(sk_bytes)

    def get_info(self) -> dict:
        with open(self.path, 'r') as f:
            return json.load(f)

@click.group()
def cli():
    """RustChain Wallet CLI - Manage your RTC tokens from the terminal."""
    pass

@cli.command()
@click.argument('name')
@click.option('--restore', is_flag=True, help="Restore from seed phrase")
def create(name, restore):
    """Generate a new wallet (BIP39 seed phrase + Ed25519 keypair)."""
    wm = WalletManager(name)
    if wm.exists():
        click.echo(f"Error: Wallet '{name}' already exists.")
        return

    mnemonic_str = None
    if restore:
        mnemonic_str = click.prompt("Enter your 24-word seed phrase").strip().lower()

    password = click.prompt("Set encryption password", hide_input=True, confirmation_prompt=True)
    
    try:
        address, mnemo = wm.create(password, mnemonic_str)
        click.echo(f"Wallet created successfully!")
        click.echo(f"Address: {address}")
        if not restore:
            click.echo("\nIMPORTANT: Write down your 24-word seed phrase and store it safely:")
            click.echo("-" * 70)
            click.echo(mnemo)
            click.echo("-" * 70)
            click.echo("Anyone with these words can access your funds. Never share them!")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
@click.argument('wallet_id')
def balance(wallet_id):
    """Check RTC balance for a wallet ID or address."""
    # If wallet_id is a file name, load address
    if (WALLET_DIR / f"{wallet_id}.json").exists():
        with open(WALLET_DIR / f"{wallet_id}.json", 'r') as f:
            wallet_id = json.load(f)["address"]
            
    try:
        resp = requests.get(f"{NODE_URL}/wallet/balance?miner_id={wallet_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bal = data.get("amount_rtc", 0)
            click.echo(f"Address: {wallet_id}")
            click.echo(f"Balance: {bal:.8f} RTC")
        else:
            click.echo(f"Error: Node returned status {resp.status_code}")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
@click.argument('to')
@click.argument('amount', type=float)
@click.option('--from', 'from_wallet', required=True, help="Wallet name (keystore)")
@click.option('--memo', default="", help="Optional memo")
def send(to, amount, from_wallet, memo):
    """Send RTC to another address."""
    wm = WalletManager(from_wallet)
    if not wm.exists():
        click.echo(f"Error: Keystore '{from_wallet}' not found.")
        return

    password = click.prompt(f"Enter password for '{from_wallet}'", hide_input=True)
    
    try:
        # Load keys
        info = wm.get_info()
        sk = wm.load_private_key(password)
        vk = sk.verify_key
        
        from_address = info["address"]
        public_key = info["public_key"]
        nonce = int(time.time() * 1000)
        
        # Build transaction payload
        tx_data = {
            "from": from_address,
            "to": to,
            "amount": amount,
            "memo": memo,
            "nonce": nonce
        }
        
        # Canonicalize and sign
        message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
        signature = sk.sign(message).signature.hex()
        
        # Prepare submission data
        payload = {
            "from_address": from_address,
            "to_address": to,
            "amount_rtc": amount,
            "nonce": nonce,
            "signature": signature,
            "public_key": public_key,
            "memo": memo
        }
        
        click.echo("Signing and sending transaction...")
        resp = requests.post(f"{NODE_URL}/wallet/transfer/signed", json=payload, timeout=15)
        
        result = resp.json()
        if resp.status_code == 200 and result.get("ok"):
            click.echo(f"Success! Transaction sent.")
            click.echo(f"Amount: {amount} RTC")
            click.echo(f"Balance: {result.get('sender_balance_rtc'):.8f} RTC")
        else:
            click.echo(f"Error: {result.get('error', 'Unknown node error')}")
            
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
@click.argument('name')
def export(name):
    """Show encrypted keystore JSON."""
    wm = WalletManager(name)
    if not wm.exists():
        click.echo(f"Error: Wallet '{name}' not found.")
        return
    
    click.echo(json.dumps(wm.get_info(), indent=2))

@cli.command()
def list():
    """List all local wallets."""
    wallets = list(WALLET_DIR.glob("*.json"))
    if not wallets:
        click.echo("No wallets found.")
        return
        
    click.echo(f"{'Name':<20} {'Address'}")
    click.echo("-" * 70)
    for w in wallets:
        with open(w, 'r') as f:
            data = json.load(f)
            click.echo(f"{w.stem:<20} {data['address']}")

if __name__ == "__main__":
    cli()
