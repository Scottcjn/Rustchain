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

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

import discord
import httpx
from discord import app_commands
from discord.ext import commands

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
API_TIMEOUT = float(os.getenv("API_TIMEOUT", "10"))


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class RustChainAPI:
    """Async wrapper around the RustChain REST API."""

    def __init__(self, base_url: str, timeout: float = 10):
        self.base_url = base_url
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            verify=False,  # node uses self-signed cert
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
    embed.add_field(name="Uptime", value=f"{uptime:,}s (~{uptime // 3600}h)", inline=True)
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
    embed.add_field(name="Slot", value=f"{data.get('slot', 0):,}", inline=True)
    embed.add_field(name="Height", value=f"{data.get('height', 0):,}", inline=True)

    if "blocks_per_epoch" in data:
        embed.add_field(name="Blocks/Epoch", value=str(data["blocks_per_epoch"]), inline=True)
    if "enrolled_miners" in data:
        embed.add_field(name="Enrolled Miners", value=str(data["enrolled_miners"]), inline=True)
    if "epoch_pot" in data:
        embed.add_field(name="Epoch Pot", value=f"{data['epoch_pot']:.6f} RTC", inline=True)

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
    embed.add_field(name="Balance", value=f"{amount:.6f} RTC", inline=True)
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

    miners = data if isinstance(data, list) else data.get("miners", [])
    total = len(miners)

    # Show up to 20 miners in embed fields
    display = miners[:20]

    embed = discord.Embed(
        title=f"Active Miners ({total})",
        color=discord.Color.purple(),
    )

    for m in display:
        name = m.get("miner", "unknown")
        arch = m.get("device_arch", "?")
        family = m.get("device_family", "?")
        multiplier = m.get("antiquity_multiplier", 1.0)
        embed.add_field(
            name=name,
            value=f"Arch: {arch} | Family: {family} | Multiplier: {multiplier}x",
            inline=False,
        )

    if total > 20:
        embed.set_footer(text=f"Showing 20 of {total} miners | {RUSTCHAIN_URL}")
    else:
        embed.set_footer(text=RUSTCHAIN_URL)

    embed.timestamp = datetime.now(timezone.utc)
    await interaction.followup.send(embed=embed)


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
    amount_units = int(amount * 1_000_000)

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
    embed.add_field(name="Amount (units)", value=f"{amount_units:,}", inline=True)
    embed.add_field(
        name="Endpoint",
        value=f"`POST {RUSTCHAIN_URL}/wallet/transfer/signed`",
        inline=False,
    )
    embed.add_field(
        name="Payload Template",
        value=(
            "```json\n"
            "{\n"
            f'  "from": "<your_wallet_id>",\n'
            f'  "to": "{to_miner.strip()}",\n'
            f'  "amount": {amount_units},\n'
            '  "fee": 1000,\n'
            '  "signature": "<ed25519_sig>",\n'
            '  "timestamp": <unix_ts>\n'
            "}\n"
            "```"
        ),
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
