"""
RustChain Discord Bot

Slash-command bot that queries the RustChain API.

Commands:
    /health              - Node health status
    /epoch               - Current epoch information
    /balance <miner_id>  - Wallet balance lookup
    /miners              - List active miners
    /tip <to> <amount>   - Tip RTC to another miner (requires signed transfer)

Environment variables:
    DISCORD_TOKEN        - Bot token (required)
    RUSTCHAIN_NODE_URL   - Node URL (default: https://rustchain.org)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import os
import sys
from datetime import datetime, timezone

import discord
import httpx
from discord import app_commands
from discord.ext import commands

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("rustchain-bot")

RUSTCHAIN_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://rustchain.org").rstrip("/")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
API_TIMEOUT = _env_float("API_TIMEOUT", 10.0)
# Explicit chain id for /tip instructions. Unset = ask the node (GET /network/info)
# and refuse to show instructions if it cannot say; never guess a network.
CHAIN_ID_OVERRIDE = os.getenv("RUSTCHAIN_CHAIN_ID", "").strip()
_CHAIN_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")


def is_valid_chain_id(value) -> bool:
    return isinstance(value, str) and _CHAIN_ID_RE.fullmatch(value) is not None


def _format_uptime(value) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "N/A"
    return f"{value:,}s (~{value // 3600}h)"


def _format_count(value) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "N/A"
    return f"{value:,}"


def _format_rtc(value) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "N/A"
    return f"{value:.6f} RTC"


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class RustChainAPI:
    """Async wrapper around the RustChain REST API."""

    def __init__(self, base_url: str, timeout: float = 10):
        self.base_url = base_url
        try:
            from node.tls_config import get_async_tls_verify
            _verify = get_async_tls_verify()
        except ImportError:
            _cert = os.path.expanduser("~/.rustchain/node_cert.pem")
            _verify = _cert if os.path.exists(_cert) else True
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            verify=_verify,
            headers={"User-Agent": "rustchain-discord-bot/2.0"},
        )

    async def close(self):
        await self._http.aclose()

    async def _get(self, path: str, **params) -> dict | list | None:
        try:
            r = await self._http.get(f"{self.base_url}{path}", params=params or None)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("API %s failed: %s", path, exc)
            return None

    async def health(self) -> dict | None:
        return await self._get("/health")

    async def epoch(self) -> dict | None:
        return await self._get("/epoch")

    async def balance(self, miner_id: str) -> dict | None:
        return await self._get("/wallet/balance", miner_id=miner_id)

    async def miners(self) -> list | None:
        return await self._get("/api/miners")

    async def network_info(self) -> dict | None:
        return await self._get("/network/info")

    async def transfer(self, payload: dict) -> dict | None:
        try:
            r = await self._http.post(
                f"{self.base_url}/wallet/transfer/signed", json=payload
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("Transfer failed: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

class RustChainBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.api = RustChainAPI(RUSTCHAIN_URL, API_TIMEOUT)

    async def setup_hook(self):
        await self.tree.sync()
        log.info("Slash commands synced")

    async def on_ready(self):
        log.info("Logged in as %s (ID %s)", self.user, self.user.id)

    async def close(self):
        await self.api.close()
        await super().close()


bot = RustChainBot()


def normalize_miners_payload(data: dict | list) -> tuple[list, int]:
    if isinstance(data, list):
        return data, len(data)
    if not isinstance(data, dict):
        return [], 0

    miners = data.get("miners") or data.get("data") or []
    if not isinstance(miners, list):
        miners = []

    pagination = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
    total = pagination.get("total", data.get("total", len(miners)))
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(miners)
    return miners, max(total, len(miners))


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

@bot.tree.command(name="health", description="Check RustChain node health")
async def cmd_health(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.api.health()
    if not data:
        await interaction.followup.send("Could not reach the RustChain node.", ephemeral=True)
        return

    ok = data.get("ok", False)
    version = data.get("version", "unknown")
    uptime = data.get("uptime_s", 0)

    embed = discord.Embed(
        title="RustChain Node Health",
        color=discord.Color.green() if ok else discord.Color.red(),
    )
    embed.add_field(name="Status", value="Online" if ok else "Offline", inline=True)
    embed.add_field(name="Version", value=version, inline=True)
    embed.add_field(name="Uptime", value=_format_uptime(uptime), inline=True)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=RUSTCHAIN_URL)
    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# /epoch
# ---------------------------------------------------------------------------

@bot.tree.command(name="epoch", description="Get current RustChain epoch info")
async def cmd_epoch(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.api.epoch()
    if not data:
        await interaction.followup.send("Could not fetch epoch data.", ephemeral=True)
        return

    embed = discord.Embed(title="RustChain Epoch", color=discord.Color.blue())
    embed.add_field(name="Epoch", value=str(data.get("epoch", "?")), inline=True)
    embed.add_field(name="Slot", value=_format_count(data.get("slot")), inline=True)
    embed.add_field(name="Height", value=_format_count(data.get("height")), inline=True)

    if "blocks_per_epoch" in data:
        embed.add_field(name="Blocks/Epoch", value=str(data["blocks_per_epoch"]), inline=True)
    if "enrolled_miners" in data:
        embed.add_field(name="Enrolled Miners", value=str(data["enrolled_miners"]), inline=True)
    if "epoch_pot" in data:
        embed.add_field(name="Epoch Pot", value=_format_rtc(data["epoch_pot"]), inline=True)

    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=RUSTCHAIN_URL)
    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# /balance
# ---------------------------------------------------------------------------

@bot.tree.command(name="balance", description="Check RTC balance for a miner wallet")
@app_commands.describe(miner_id="Miner wallet ID (e.g. Ivan-houzhiwen)")
async def cmd_balance(interaction: discord.Interaction, miner_id: str):
    await interaction.response.defer()

    if len(miner_id.strip()) < 3:
        await interaction.followup.send("Miner ID must be at least 3 characters.", ephemeral=True)
        return

    data = await bot.api.balance(miner_id.strip())
    if not data:
        await interaction.followup.send(f"Could not fetch balance for `{miner_id}`.", ephemeral=True)
        return

    amount = data.get("amount_rtc", 0.0)
    mid = data.get("miner_id", miner_id)

    embed = discord.Embed(title="Wallet Balance", color=discord.Color.gold())
    embed.add_field(name="Miner", value=mid, inline=True)
    embed.add_field(name="Balance", value=_format_rtc(amount), inline=True)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=RUSTCHAIN_URL)
    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# /miners
# ---------------------------------------------------------------------------

@bot.tree.command(name="miners", description="List active RustChain miners")
async def cmd_miners(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.api.miners()
    if not data:
        await interaction.followup.send("Could not fetch miner list.", ephemeral=True)
        return

    miners, total = normalize_miners_payload(data)

    # Show up to 20 miners in embed fields
    display = miners[:20]

    embed = discord.Embed(
        title=f"Active Miners ({total})",
        color=discord.Color.purple(),
    )

    for m in display:
        name = m.get("miner") or m.get("miner_id") or "unknown"
        arch = m.get("device_arch", "?")
        family = m.get("device_family", "?")
        multiplier = m.get("antiquity_multiplier", 1.0)
        embed.add_field(
            name=name,
            value=f"Arch: {arch} | Family: {family} | Multiplier: {multiplier}x",
            inline=False,
        )

    if total > len(display):
        embed.set_footer(text=f"Showing {len(display)} of {total} miners | {RUSTCHAIN_URL}")
    else:
        embed.set_footer(text=RUSTCHAIN_URL)

    embed.timestamp = datetime.now(timezone.utc)
    await interaction.followup.send(embed=embed)


async def resolve_chain_id(api) -> str | None:
    """chain_id to bind: RUSTCHAIN_CHAIN_ID if set, else the node's. None = unknown (fail closed)."""
    if CHAIN_ID_OVERRIDE:
        if not is_valid_chain_id(CHAIN_ID_OVERRIDE):
            log.error("RUSTCHAIN_CHAIN_ID is not a valid chain_id: %r", CHAIN_ID_OVERRIDE)
            return None
        return CHAIN_ID_OVERRIDE
    info = await api.network_info()
    chain_id = info.get("chain_id") if isinstance(info, dict) else None
    return chain_id if is_valid_chain_id(chain_id) else None


def signed_transfer_template(to_address: str, amount: float, chain_id: str) -> dict:
    """Instructions for a chain-bound POST /wallet/transfer/signed.

    ``message`` is what the node verifies (node/rustchain_v2_integrated_v2.2.1_rip200.py,
    _wallet_transfer_signed_messages, fee-less form): compact sorted JSON, amount
    as a float, nonce as a string, chain_id bound in so the signature is only
    valid on this network. The request body must carry the same chain_id.
    """
    amount = float(amount)
    message = json.dumps(
        {
            "amount": amount,
            "chain_id": chain_id,
            "from": "<your RTC address>",
            "memo": "",
            "nonce": "<nonce>",
            "to": to_address,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    body = {
        "from_address": "<your RTC address>",
        "to_address": to_address,
        "amount_rtc": amount,
        "memo": "",
        "nonce": "<nonce: unique increasing integer, e.g. unix ms>",
        "chain_id": chain_id,
        "public_key": "<ed25519 public key hex>",
        "signature": "<ed25519 signature hex of the message>",
    }
    return {"message": message, "body": body}


# ---------------------------------------------------------------------------
# /tip
# ---------------------------------------------------------------------------

@bot.tree.command(name="tip", description="Tip RTC to another miner (info only)")
@app_commands.describe(
    to_miner="Recipient miner wallet ID",
    amount="Amount of RTC to tip",
)
async def cmd_tip(interaction: discord.Interaction, to_miner: str, amount: float):
    await interaction.response.defer(ephemeral=True)

    if amount <= 0:
        await interaction.followup.send("Amount must be greater than zero.", ephemeral=True)
        return

    if len(to_miner.strip()) < 3:
        await interaction.followup.send("Recipient miner ID must be at least 3 characters.", ephemeral=True)
        return

    # Tipping requires a signed transaction (private key).
    # The bot cannot hold user keys, so we provide transfer instructions.
    chain_id = await resolve_chain_id(bot.api)
    if chain_id is None:
        await interaction.followup.send(
            "Could not determine this node's chain_id (GET /network/info), so no "
            "signing instructions were produced. Set RUSTCHAIN_CHAIN_ID or retry.",
            ephemeral=True,
        )
        return
    template = signed_transfer_template(to_miner.strip(), amount, chain_id)

    embed = discord.Embed(
        title="Tip Transfer",
        description=(
            "RustChain transfers require a signed transaction. "
            "Use the details below with your local wallet CLI to complete the tip."
        ),
        color=discord.Color.teal(),
    )
    embed.add_field(name="Recipient", value=to_miner.strip(), inline=True)
    embed.add_field(name="Amount", value=f"{amount:.6f} RTC", inline=True)
    embed.add_field(name="Chain ID", value=chain_id, inline=True)
    embed.add_field(
        name="Endpoint",
        value=f"`POST {RUSTCHAIN_URL}/wallet/transfer/signed`",
        inline=False,
    )
    embed.add_field(
        name="Sign exactly these bytes (Ed25519)",
        value=f"```json\n{template['message']}\n```",
        inline=False,
    )
    embed.add_field(
        name="Request body",
        value=f"```json\n{json.dumps(template['body'], indent=2)}\n```",
        inline=False,
    )
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text="Sign with your Ed25519 key and POST to the endpoint above.")
    await interaction.followup.send(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not DISCORD_TOKEN:
        log.error("DISCORD_TOKEN environment variable is not set.")
        sys.exit(1)
    log.info("Starting RustChain Discord bot against %s", RUSTCHAIN_URL)
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
