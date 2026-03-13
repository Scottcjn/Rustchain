"""
RustChain Discord Bot

A Discord bot that queries the RustChain API for:
- Node health status
- Current epoch information
- Wallet balance lookups

Commands (prefix configurable, default: !):
    !health - Check node health status
    !epoch  - Get current epoch information
    !balance <miner_id> - Check RTC balance for a miner
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import httpx

from config import BotConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rustchain-bot")


class RustChainAPI:
    """Client for interacting with the RustChain REST API."""

    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            verify=False,  # Self-signed cert on node
            headers={"User-Agent": "rustchain-discord-bot/1.0"},
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_json(self, endpoint: str) -> dict:
        """Fetch JSON from an API endpoint."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"API request failed for {endpoint}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching {endpoint}: {e}")
            return {}

    async def get_health(self) -> dict:
        """Get node health status."""
        return await self.get_json("/health")

    async def get_epoch(self) -> dict:
        """Get current epoch information."""
        return await self.get_json("/epoch")

    async def get_balance(self, miner_id: str) -> dict:
        """Get balance for a specific miner."""
        return await self.get_json(f"/wallet/balance?miner_id={miner_id}")


class RustChainBot(commands.Bot):
    """Discord bot for RustChain API queries."""

    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=config.prefix,
            intents=intents,
            description="RustChain API Discord Bot",
        )
        self.config = config
        self.api: Optional[RustChainAPI] = None

    async def setup_hook(self):
        """Initialize bot components on startup."""
        self.api = RustChainAPI(
            base_url=self.config.rustchain_node_url,
            timeout=self.config.api_timeout,
        )
        logger.info(f"Connected to RustChain node: {self.config.rustchain_node_url}")

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_close(self):
        """Cleanup on bot shutdown."""
        if self.api:
            await self.api.close()

    def format_rtc(self, value: float) -> str:
        """Format RTC amount with 6 decimal places."""
        return f"{value:.6f}"

    def short_id(self, s: str, keep: int = 12) -> str:
        """Truncate long IDs for display."""
        if len(s) <= keep:
            return s
        return s[:keep] + "..."


async def main():
    """Entry point for the bot."""
    config = BotConfig.from_env()

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        sys.exit(1)

    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    bot = RustChainBot(config)

    # Register slash commands
    @bot.tree.command(name="health", description="Check RustChain node health status")
    async def health(interaction: discord.Interaction):
        """Check node health status."""
        await interaction.response.defer()

        health_data = await bot.api.get_health()

        if not health_data:
            await interaction.followup.send(
                "Failed to fetch health data from the node.", ephemeral=True
            )
            return

        ok = health_data.get("ok", False)
        version = health_data.get("version", "unknown")
        uptime_s = health_data.get("uptime_s", 0)
        db_rw = health_data.get("db_rw", False)
        tip_age = health_data.get("tip_age_slots", -1)

        status_emoji = "🟢" if ok else "🔴"

        embed = discord.Embed(
            title=f"{status_emoji} RustChain Node Health",
            color=discord.Color.green() if ok else discord.Color.red(),
        )
        embed.add_field(name="Status", value="OK" if ok else "Unhealthy", inline=True)
        embed.add_field(name="Version", value=version, inline=True)
        embed.add_field(
            name="Uptime", value=f"{uptime_s:,}s ({uptime_s // 3600}h)", inline=True
        )
        embed.add_field(
            name="Database", value="Read/Write" if db_rw else "Read-Only", inline=True
        )
        embed.add_field(
            name="Sync Status",
            value="Synced" if tip_age == 0 else f"{tip_age} slots behind",
            inline=True,
        )
        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text=f"Node: {bot.config.rustchain_node_url}")

        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="epoch", description="Get current epoch information")
    async def epoch(interaction: discord.Interaction):
        """Get current epoch information."""
        await interaction.response.defer()

        epoch_data = await bot.api.get_epoch()

        if not epoch_data:
            await interaction.followup.send(
                "Failed to fetch epoch data from the node.", ephemeral=True
            )
            return

        epoch_num = epoch_data.get("epoch", -1)
        slot = epoch_data.get("slot", -1)
        blocks_per_epoch = epoch_data.get("blocks_per_epoch", 144)
        epoch_pot = epoch_data.get("epoch_pot", 0.0)
        enrolled_miners = epoch_data.get("enrolled_miners", 0)

        embed = discord.Embed(
            title="⏱️ RustChain Epoch Info",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Epoch", value=str(epoch_num), inline=True)
        embed.add_field(name="Slot", value=f"{slot:,}", inline=True)
        embed.add_field(
            name="Blocks/Epoch", value=str(blocks_per_epoch), inline=True
        )
        embed.add_field(
            name="Epoch POT", value=bot.format_rtc(epoch_pot), inline=True
        )
        embed.add_field(name="Enrolled Miners", value=str(enrolled_miners), inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text=f"Node: {bot.config.rustchain_node_url}")

        await interaction.followup.send(embed=embed)

    @bot.tree.command(
        name="balance", description="Check RTC balance for a miner wallet"
    )
    @app_commands.describe(miner_id="The miner wallet ID to check")
    async def balance(interaction: discord.Interaction, miner_id: str):
        """Check balance for a specific miner."""
        await interaction.response.defer()

        if not miner_id or len(miner_id) < 3:
            await interaction.followup.send(
                "Please provide a valid miner ID (at least 3 characters).",
                ephemeral=True,
            )
            return

        balance_data = await bot.api.get_balance(miner_id)

        if not balance_data:
            await interaction.followup.send(
                f"Failed to fetch balance for `{miner_id}`.", ephemeral=True
            )
            return

        if not balance_data.get("ok", False):
            error = balance_data.get("error", "Unknown error")
            await interaction.followup.send(
                f"Balance lookup failed: {error}", ephemeral=True
            )
            return

        amount_rtc = balance_data.get("amount_rtc", 0.0)
        returned_miner_id = balance_data.get("miner_id", miner_id)

        embed = discord.Embed(
            title="💰 RustChain Wallet Balance",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Miner ID", value=bot.short_id(returned_miner_id, 16), inline=True
        )
        embed.add_field(
            name="Balance", value=f"{bot.format_rtc(amount_rtc)} RTC", inline=True
        )
        embed.timestamp = datetime.now(timezone.utc)
        embed.set_footer(text=f"Node: {bot.config.rustchain_node_url}")

        await interaction.followup.send(embed=embed)

    # Legacy text commands for backward compatibility
    @bot.command(name="health", help="Check node health status")
    async def text_health(ctx):
        """Legacy text command for health check."""
        async with ctx.typing():
            health_data = await bot.api.get_health()
            if not health_data:
                await ctx.send("Failed to fetch health data.")
                return

            ok = health_data.get("ok", False)
            version = health_data.get("version", "unknown")
            uptime_s = health_data.get("uptime_s", 0)

            status = "🟢 OK" if ok else "🔴 Unhealthy"
            await ctx.send(
                f"**RustChain Node Health**\n"
                f"Status: {status}\n"
                f"Version: {version}\n"
                f"Uptime: {uptime_s:,}s"
            )

    @bot.command(name="epoch", help="Get current epoch information")
    async def text_epoch(ctx):
        """Legacy text command for epoch info."""
        async with ctx.typing():
            epoch_data = await bot.api.get_epoch()
            if not epoch_data:
                await ctx.send("Failed to fetch epoch data.")
                return

            epoch_num = epoch_data.get("epoch", -1)
            slot = epoch_data.get("slot", -1)
            enrolled = epoch_data.get("enrolled_miners", 0)

            await ctx.send(
                f"**RustChain Epoch Info**\n"
                f"Epoch: {epoch_num}\n"
                f"Slot: {slot:,}\n"
                f"Enrolled Miners: {enrolled}"
            )

    @bot.command(name="balance", help="Check balance for a miner ID")
    async def text_balance(ctx, miner_id: str):
        """Legacy text command for balance lookup."""
        async with ctx.typing():
            balance_data = await bot.api.get_balance(miner_id)
            if not balance_data or not balance_data.get("ok", False):
                error = balance_data.get("error", "Unknown error")
                await ctx.send(f"Balance lookup failed: {error}")
                return

            amount_rtc = balance_data.get("amount_rtc", 0.0)
            await ctx.send(
                f"**Balance for `{miner_id}`**\n"
                f"{bot.format_rtc(amount_rtc)} RTC"
            )

    # Run the bot
    await bot.start(config.discord_token)


if __name__ == "__main__":
    try:
        discord.utils.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)
