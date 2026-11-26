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
    rustchain services list
"""

import asyncio
import sys
import json
from dataclasses import asdict
from typing import Optional

import click

from .client import DEFAULT_NODE_URL, RustChainClient
from .wallet import RustChainWallet
from .bottube import BoTTubeClient
from .bottube.exceptions import BoTTubeError
from . import __version__
from .exceptions import RustChainError


@click.group()
@click.version_option(version=__version__, prog_name="rustchain")
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
        if words not in (12, 24):
            raise ValueError("Number of seed words must be 12 or 24")
        strength = 128 if words == 12 else 256
        wallet = RustChainWallet.create(strength=strength)
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
    default=DEFAULT_NODE_URL,
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
    default=DEFAULT_NODE_URL,
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
    default=DEFAULT_NODE_URL,
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
    default=DEFAULT_NODE_URL,
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
    default=DEFAULT_NODE_URL,
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
    default=DEFAULT_NODE_URL,
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


# ─────────────────────────────────────────────────────────────────
# Services Commands (BoTTube RTC spend flow)
# ─────────────────────────────────────────────────────────────────

@main.group(name="services")
def services_group():
    """Spend RTC on BoTTube services (bottube.ai)."""
    pass


def _services_client() -> BoTTubeClient:
    # API key resolves from BOTTUBE_API_KEY or ~/.bottube/config.json;
    # no --api-key flag, so the secret never hits shell history.
    return BoTTubeClient()


@services_group.command(name="list")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def services_list(as_json: bool):
    """List purchasable RTC services with prices."""
    try:
        offers = _services_client().list_services()
        if as_json:
            click.echo(json.dumps([asdict(o) for o in offers], indent=2, default=str))
        else:
            click.echo(f"Services ({len(offers)}):")
            for offer in offers:
                cap = f" (max {offer.max_quantity}/order)" if offer.max_quantity else ""
                click.echo(
                    f"  {offer.key:<20} {offer.price} {offer.currency}{cap}"
                    f"  {offer.name}"
                )
    except BoTTubeError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@services_group.command(name="buy")
@click.argument("service_key")
@click.option(
    "--qty",
    type=int,
    default=1,
    help="Quantity to purchase.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the confirmation prompt.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def services_buy(service_key: str, qty: int, yes: bool, as_json: bool):
    """Buy an RTC service with RTC from the BoTTube account balance."""
    try:
        if qty < 1:
            raise click.BadParameter("must be >= 1", param_hint="'--qty'")
        client = _services_client()
        try:
            offer = next(
                (o for o in client.list_services() if o.key == service_key), None
            )
        except BoTTubeError:
            # shortcut: price preview is best-effort; pay() still validates
            # the service server-side.
            offer = None
        if offer is not None:
            total = offer.price * qty
            click.echo(
                f"Price: {offer.price} {offer.currency} x {qty} "
                f"= {total} {offer.currency}"
            )
        else:
            click.echo(
                f"Service '{service_key}' not in the current listing; "
                "the server will validate it."
            )
        if not yes and not click.confirm(f"Buy {qty} x {service_key}?", default=False):
            click.echo("Aborted.")
            return
        receipt = client.pay(service_key, quantity=qty)
        if as_json:
            click.echo(json.dumps(asdict(receipt), indent=2, default=str))
        else:
            click.echo("✅  Purchase submitted!")
            click.echo(f"   Service:    {receipt.service}")
            click.echo(f"   Quantity:   {receipt.quantity}")
            click.echo(
                f"   Cost:       {receipt.unit_price} x {receipt.quantity} "
                f"= {receipt.total_cost} RTC"
            )
            click.echo(f"   Token:      {receipt.token}")
    except (BoTTubeError, click.ClickException) as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@services_group.command(name="use")
@click.argument("service_token")
@click.argument("payload", nargs=-1, metavar="[KEY=VALUE]...")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def services_use(service_token: str, payload: tuple, as_json: bool):
    """Redeem a purchased service token; KEY=VALUE args become the payload."""
    try:
        data = {}
        for item in payload:
            if "=" not in item:
                raise click.BadParameter(
                    f"expected KEY=VALUE, got {item!r}", param_hint="'PAYLOAD'"
                )
            key, _, value = item.partition("=")
            data[key] = value
        result = _services_client().use(service_token, **data)
        if as_json:
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo(f"✅  Service used: {json.dumps(result, default=str)}")
    except (BoTTubeError, click.ClickException) as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


@services_group.command(name="purchases")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON.",
)
def services_purchases(as_json: bool):
    """List your RTC service purchase history."""
    try:
        receipts = _services_client().purchases()
        if as_json:
            click.echo(
                json.dumps([asdict(r) for r in receipts], indent=2, default=str)
            )
        else:
            click.echo(f"Purchases ({len(receipts)}):")
            for receipt in receipts:
                click.echo(
                    f"  {receipt.service:<20} x{receipt.quantity}"
                    f"  {receipt.total_cost} RTC  token={receipt.token[:16]}"
                )
    except BoTTubeError as e:
        click.echo(f"❌  Error: {e}", err=True)
        sys.exit(1)


# Allow running as `python -m rustchain_sdk.cli`
if __name__ == "__main__":
    main()
