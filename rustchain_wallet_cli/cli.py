#!/usr/bin/env python3
"""
RustChain Wallet CLI — Command-Line RTC Management

Usage:
    rustchain-wallet create [--words 12|24] [--save NAME]
    rustchain-wallet balance <address> [--node URL]
    rustchain-wallet send <to> <amount> --from NAME [--node URL]
    rustchain-wallet import [--words "..."] [--save NAME]
    rustchain-wallet export NAME
    rustchain-wallet list
    rustchain-wallet history <address> [--node URL]
    rustchain-wallet miners [--node URL]
    rustchain-wallet epoch [--node URL]

Bounty: #39
Wallet: klowagent
"""

import json
import sys
import getpass
import urllib.request
import urllib.error
import ssl
from typing import Optional

import click

from .wallet import (
    RustChainWallet,
    list_wallets,
    get_wallet_path,
    KEYSTORE_DIR,
)

DEFAULT_NODE_URL = "https://rustchain.org"


def _api_get(url: str, timeout: float = 10.0) -> dict:
    """GET a JSON API endpoint (HTTPS only)."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode())


def _api_post(url: str, data: dict, timeout: float = 10.0) -> dict:
    """POST a JSON API endpoint (HTTPS only)."""
    ctx = ssl.create_default_context()
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode())


def _get_password(confirm: bool = True) -> str:
    """Prompt for password without echoing."""
    pw = getpass.getpass("Keystore password: ")
    if confirm:
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            click.echo("❌  Passwords do not match", err=True)
            sys.exit(1)
    return pw


def _load_wallet_from_keystore(name: str) -> RustChainWallet:
    """Load a wallet from keystore by name."""
    path = get_wallet_path(name)
    if not path:
        click.echo(f"❌  Wallet '{name}' not found in {KEYSTORE_DIR}", err=True)
        click.echo(f"   Available: {[w['name'] for w in list_wallets()]}", err=True)
        sys.exit(1)

    pw = getpass.getpass(f"Password for '{name}': ")
    try:
        return RustChainWallet.from_keystore(path, pw)
    except Exception as e:
        click.echo(f"❌  Failed to decrypt wallet: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="1.0.0", prog_name="rustchain-wallet")
def main():
    """
    RustChain Wallet CLI — Command-line RTC management.

    Create wallets, check balances, send transfers — all from the terminal.

    \b
    Quick Start:
        rustchain-wallet create
        rustchain-wallet balance RTCabc...
        rustchain-wallet send RTCxyz... 10 --from default
    """
    pass


# ─────────────────────────────────────────────────────────────────
# Wallet Commands
# ─────────────────────────────────────────────────────────────────

@main.command(name="create")
@click.option("--words", type=click.Choice(["12", "24"]), default="12",
              help="Number of seed words (12 or 24).")
@click.option("--save", "name", default="default",
              help="Wallet name for keystore (default: 'default').")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def wallet_create(words: str, name: str, as_json: bool):
    """Create a new RustChain wallet with BIP39 seed phrase."""
    try:
        strength = 128 if words == "12" else 256
        wallet = RustChainWallet.create(strength=strength)

        if as_json:
            click.echo(json.dumps(wallet.export(), indent=2))
        else:
            click.echo("✅  Wallet created!")
            click.echo(f"   Address:  {wallet.address}")
            click.echo(f"   PubKey:   {wallet.public_key_hex[:32]}...")
            click.echo()
            click.echo(f"   Seed Phrase ({len(wallet.seed_phrase)} words):")
            for i in range(0, len(wallet.seed_phrase), 4):
                click.echo("   " + " ".join(wallet.seed_phrase[i:i + 4]))
            click.echo()
            click.echo("⚠️  SAVE YOUR SEED PHRASE! It cannot be recovered.")

        # Save to keystore
        pw = _get_password()
        path = wallet.save_keystore(pw, name)
        click.echo(f"\n💾  Saved to: {path}")

    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@main.command(name="import")
@click.option("--words", "seed_phrase", required=True,
              help="Seed phrase (space-separated words).")
@click.option("--save", "name", default="default",
              help="Wallet name for keystore (default: 'default').")
def wallet_import(seed_phrase: str, name: str):
    """Import a wallet from BIP39 seed phrase."""
    try:
        words = seed_phrase.strip().split()
        if len(words) not in (12, 24):
            click.echo(f"❌  Expected 12 or 24 words, got {len(words)}", err=True)
            sys.exit(1)

        wallet = RustChainWallet.from_seed_phrase(words)
        click.echo(f"✅  Wallet imported!")
        click.echo(f"   Address:  {wallet.address}")

        pw = _get_password()
        path = wallet.save_keystore(pw, name)
        click.echo(f"💾  Saved to: {path}")

    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@main.command(name="export")
@click.argument("name")
def wallet_export(name: str):
    """Export wallet keystore (shows encrypted keystore JSON)."""
    path = get_wallet_path(name)
    if not path:
        click.echo(f"❌  Wallet '{name}' not found", err=True)
        sys.exit(1)

    data = json.loads(path.read_text())
    click.echo(json.dumps(data, indent=2))


@main.command(name="list")
def wallet_list():
    """List all wallets in the keystore."""
    wallets = list_wallets()
    if not wallets:
        click.echo(f"No wallets found in {KEYSTORE_DIR}")
        click.echo("Run 'rustchain-wallet create' to make one.")
        return

    click.echo(f"Wallets in {KEYSTORE_DIR}:\n")
    for w in wallets:
        click.echo(f"  {w['name']:20s}  {w['address']}")


# ─────────────────────────────────────────────────────────────────
# Balance
# ─────────────────────────────────────────────────────────────────

@main.command(name="balance")
@click.argument("address")
@click.option("--node", default=DEFAULT_NODE_URL, help="RustChain node URL.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def wallet_balance(address: str, node: str, as_json: bool):
    """Check the balance of a wallet address."""
    try:
        url = f"{node}/wallet/balance?miner_id={address}"
        result = _api_get(url)

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            amount = result.get("amount_rtc", result.get("balance", 0))
            nonce = result.get("nonce", 0)
            click.echo(f"Address:  {address}")
            click.echo(f"Balance:  {amount} RTC")
            if nonce:
                click.echo(f"Nonce:    {nonce}")

    except urllib.error.HTTPError as e:
        click.echo(f"❌  HTTP {e.code}: {e.reason}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Send
# ─────────────────────────────────────────────────────────────────

@main.command(name="send")
@click.argument("to_address")
@click.argument("amount", type=float)
@click.option("--from", "from_name", required=True,
              help="Sender wallet name from keystore.")
@click.option("--node", default=DEFAULT_NODE_URL, help="RustChain node URL.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def wallet_send(to_address: str, amount: float, from_name: str, node: str, as_json: bool):
    """Send RTC to another wallet."""
    try:
        wallet = _load_wallet_from_keystore(from_name)

        # Build transfer payload
        import time
        nonce = int(time.time() * 1000)
        message = f"{wallet.address}:{to_address}:{amount}:{nonce}"
        signature = wallet.sign(message.encode()).hex()

        payload = {
            "from_address": wallet.address,
            "to_address": to_address,
            "amount_rtc": amount,
            "nonce": nonce,
            "signature": signature,
            "public_key": wallet.public_key_hex,
        }

        result = _api_post(f"{node}/wallet/transfer/signed", payload)

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            tx_hash = result.get("tx_hash", result.get("pending_id", "unknown"))
            status = result.get("status", "unknown")
            click.echo("✅  Transfer submitted!")
            click.echo(f"   From:   {wallet.address}")
            click.echo(f"   To:     {to_address}")
            click.echo(f"   Amount: {amount} RTC")
            click.echo(f"   Status: {status}")
            click.echo(f"   TX:     {tx_hash}")

    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Network Info
# ─────────────────────────────────────────────────────────────────

@main.command(name="history")
@click.argument("address")
@click.option("--node", default=DEFAULT_NODE_URL, help="RustChain node URL.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def wallet_history(address: str, node: str, as_json: bool):
    """Show transaction history for a wallet."""
    try:
        url = f"{node}/wallet/history?miner_id={address}"
        result = _api_get(url)

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            txs = result if isinstance(result, list) else result.get("transactions", [])
            if not txs:
                click.echo(f"No transactions found for {address}")
                return

            click.echo(f"Transaction History for {address}:\n")
            for tx in txs[:20]:
                click.echo(f"  {json.dumps(tx)}")

    except urllib.error.HTTPError as e:
        click.echo(f"❌  HTTP {e.code}: {e.reason}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@main.command(name="miners")
@click.option("--node", default=DEFAULT_NODE_URL, help="RustChain node URL.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def miners_list(node: str, as_json: bool):
    """List active miners on the network."""
    try:
        result = _api_get(f"{node}/api/miners")
        miners = result.get("miners", []) if isinstance(result, dict) else result

        if as_json:
            click.echo(json.dumps(miners, indent=2))
        else:
            click.echo(f"Active Miners ({len(miners)}):\n")
            for m in miners:
                mid = m.get("miner", m.get("miner_id", "?"))
                hw = m.get("hardware_type", "?")
                mult = m.get("antiquity_multiplier", 0)
                click.echo(f"  {mid:30s}  {hw:15s}  {mult}x")

    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@main.command(name="epoch")
@click.option("--node", default=DEFAULT_NODE_URL, help="RustChain node URL.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def epoch_info(node: str, as_json: bool):
    """Show current epoch information."""
    try:
        result = _api_get(f"{node}/epoch")

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("Epoch Info:\n")
            for key, val in result.items():
                click.echo(f"  {key:20s}  {val}")

    except Exception as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
