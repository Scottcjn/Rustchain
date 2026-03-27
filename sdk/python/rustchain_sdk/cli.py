"""
RustChain CLI
Command-line interface for the RustChain Python SDK.

Usage:
    rustchain wallet create
    rustchain wallet balance <address>
    rustchain wallet send <from> <to> <amount>
    rustchain node status
    rustchain epoch info
    rustchain miners list
    rustchain attest <wallet_address>
"""

import asyncio
import sys
import json
from typing import Optional

import click

from .client import RustChainClient
from .wallet import RustChainWallet
from .exceptions import RustChainError


@click.group()
@click.version_option(version="1.0.0", prog_name="rustchain")
def main():
    """
    RustChain CLI — Interact with the RustChain blockchain.

    Install:  pip install rustchain

    Quick Start:
        rustchain wallet create
        rustchain wallet balance RTC1a...
        rustchain node status
    """
    pass


# ─────────────────────────────────────────────────────────────────
# Wallet Commands
# ─────────────────────────────────────────────────────────────────

@main.group(name="wallet")
def wallet_group():
    """Wallet management commands."""
    pass


@wallet_group.command(name="create")
@click.option(
    "--words",
    type=int,
    default=12,
    help="Number of seed words: 12 or 24.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def wallet_create(words: int, as_json: bool):
    """Create a new RustChain wallet with BIP39 seed phrase."""
    try:
        wallet = RustChainWallet.create(strength=words * 8 + 4)
        if as_json:
            click.echo(json.dumps(wallet.export(), indent=2))
        else:
            click.echo(f"✅  Wallet created successfully!")
            click.echo(f"   Address:      {wallet.address}")
            click.echo(f"   Public Key:   {wallet.public_key_hex}")
            click.echo(f"   Seed Phrase ({len(wallet.seed_phrase)} words):")
            for i in range(0, len(wallet.seed_phrase), 4):
                click.echo("   " + " ".join(wallet.seed_phrase[i : i + 4]))
            click.echo()
            click.echo("⚠️  SAVE YOUR SEED PHRASE! It cannot be recovered.")
    except Exception as e:
        click.echo(f"❌  Error creating wallet: {e}", err=True)
        sys.exit(1)


@wallet_group.command(name="balance")
@click.argument("address")
@click.option(
    "--node",
    default="https://50.28.86.131",
    help="RustChain node URL.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def wallet_balance(address: str, node: str, as_json: bool):
    """Check the balance of a wallet address."""
    asyncio.run(_wallet_balance(address, node, as_json))


async def _wallet_balance(address: str, node: str, as_json: bool):
    try:
        async with RustChainClient(base_url=node) as client:
            result = await client.get_balance(address)
            if as_json:
                click.echo(json.dumps(result, indent=2))
            else:
                balance = result.get("balance", 0)
                nonce = result.get("nonce", 0)
                click.echo(f"Address:  {address}")
                click.echo(f"Balance:  {balance} RTC")
                click.echo(f"Nonce:    {nonce}")
    except RustChainError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@wallet_group.command(name="send")
@click.argument("from_address")
@click.argument("to_address")
@click.argument("amount", type=int)
@click.option(
    "--fee",
    type=int,
    default=0,
    help="Transaction fee.",
)
@click.option(
    "--seed",
    "seed_phrase",
    required=True,
    help="Seed phrase of sender wallet (space-separated words).",
)
@click.option(
    "--node",
    default="https://50.28.86.131",
    help="RustChain node URL.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def wallet_send(
    from_address: str,
    to_address: str,
    amount: int,
    fee: int,
    seed_phrase: str,
    node: str,
    as_json: bool,
):
    """Send RTC from one wallet to another."""
    words = seed_phrase.split()
    asyncio.run(_wallet_send(from_address, to_address, amount, fee, words, node, as_json))


async def _wallet_send(
    from_address: str,
    to_address: str,
    amount: int,
    fee: int,
    seed_phrase: list,
    node: str,
    as_json: bool,
):
    try:
        wallet = RustChainWallet.from_seed_phrase(seed_phrase)
        if wallet.address != from_address:
            click.echo(
                f"❌  Address mismatch: seed phrase produces {wallet.address}, "
                f"but expected {from_address}",
                err=True,
            )
            sys.exit(1)

        async with RustChainClient(base_url=node) as client:
            result = await client.wallet_transfer_with_wallet(
                wallet, to_address, amount, fee
            )
            if as_json:
                click.echo(json.dumps(result, indent=2))
            else:
                tx_hash = result.get("tx_hash", "unknown")
                status = result.get("status", "unknown")
                click.echo(f"✅  Transfer submitted!")
                click.echo(f"   From:     {from_address}")
                click.echo(f"   To:       {to_address}")
                click.echo(f"   Amount:   {amount} RTC")
                click.echo(f"   Fee:      {fee} RTC")
                click.echo(f"   Status:   {status}")
                click.echo(f"   TX Hash:  {tx_hash}")
    except RustChainError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Node Commands
# ─────────────────────────────────────────────────────────────────

@main.command(name="node")
@click.option(
    "--node",
    default="https://50.28.86.131",
    help="RustChain node URL.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def node_status(node: str, as_json: bool):
    """Check node health status."""
    asyncio.run(_node_status(node, as_json))


async def _node_status(node: str, as_json: bool):
    try:
        async with RustChainClient(base_url=node) as client:
            result = await client.health()
            if as_json:
                click.echo(json.dumps(result, indent=2))
            else:
                status = result.get("status", "unknown")
                version = result.get("version", "unknown")
                click.echo(f"✅  Node is healthy" if status == "ok" else f"⚠️  Node status: {status}")
                for key, val in result.items():
                    click.echo(f"   {key}:  {val}")
    except RustChainError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Epoch Commands
# ─────────────────────────────────────────────────────────────────

@main.command(name="epoch")
@click.option(
    "--node",
    default="https://50.28.86.131",
    help="RustChain node URL.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def epoch_info(node: str, as_json: bool):
    """Get current epoch information."""
    asyncio.run(_epoch_info(node, as_json))


async def _epoch_info(node: str, as_json: bool):
    try:
        async with RustChainClient(base_url=node) as client:
            result = await client.get_epoch()
            if as_json:
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo(f"Epoch Info:")
                for key, val in result.items():
                    click.echo(f"   {key}:  {val}")
    except RustChainError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Miner Commands
# ─────────────────────────────────────────────────────────────────

@main.group(name="miners")
def miners_group():
    """Miner management commands."""
    pass


@miners_group.command(name="list")
@click.option(
    "--node",
    default="https://50.28.86.131",
    help="RustChain node URL.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def miners_list(node: str, as_json: bool):
    """List active miners."""
    asyncio.run(_miners_list(node, as_json))


async def _miners_list(node: str, as_json: bool):
    try:
        async with RustChainClient(base_url=node) as client:
            miners = await client.get_miners()
            if as_json:
                click.echo(json.dumps(miners, indent=2))
            else:
                click.echo(f"Active Miners ({len(miners)}):")
                for miner in miners:
                    click.echo(f"   {json.dumps(miner)}")
    except RustChainError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Attestation Commands
# ─────────────────────────────────────────────────────────────────

@main.command(name="attest")
@click.argument("wallet_address")
@click.option(
    "--seed",
    "seed_phrase",
    required=True,
    help="Seed phrase of the miner wallet.",
)
@click.option(
    "--node",
    default="https://50.28.86.131",
    help="RustChain node URL.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def attest(wallet_address: str, seed_phrase: str, node: str, as_json: bool):
    """
    Request and submit an attestation for a miner wallet.

    Uses the wallet's seed phrase to sign the attestation challenge.
    """
    words = seed_phrase.split()
    asyncio.run(_attest(wallet_address, words, node, as_json))


async def _attest(wallet_address: str, seed_phrase: list, node: str, as_json: bool):
    try:
        wallet = RustChainWallet.from_seed_phrase(seed_phrase)
        if wallet.address != wallet_address:
            click.echo(
                f"❌  Address mismatch: seed phrase produces {wallet.address}, "
                f"but expected {wallet_address}",
                err=True,
            )
            sys.exit(1)

        async with RustChainClient(base_url=node) as client:
            # Step 1: Get attestation status
            status = await client.get_attestation_status(wallet.public_key_hex)

            if as_json:
                click.echo(json.dumps(status, indent=2))
                return

            # Step 2: Request challenge
            click.echo("📋  Requesting attestation challenge...")
            challenge_result = await client.attest_challenge(wallet.public_key_hex)
            challenge = challenge_result.get("challenge", "")

            if not challenge:
                click.echo(f"⚠️  No challenge received. Status: {status}")
                return

            # Step 3: Sign the challenge
            signature = wallet.sign(challenge.encode()).hex()

            # Step 4: Submit attestation
            click.echo("📤  Submitting attestation...")
            submit_result = await client.attest_submit(
                wallet.public_key_hex,
                challenge,
                signature,
            )

            click.echo(f"✅  Attestation submitted!")
            click.echo(f"   Result: {json.dumps(submit_result)}")

    except RustChainError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# Allow running as `python -m rustchain_sdk.cli`
if __name__ == "__main__":
    main()
