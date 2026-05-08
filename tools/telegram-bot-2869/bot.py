#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
RustChain Telegram Bot — Issue #2869
https://github.com/Scottcjn/rustchain-bounties/issues/2869

Commands:
  /balance <wallet>  — Check RTC wallet balance
  /miners            — List active miners
  /epoch             — Current epoch information
  /price             — RTC/wRTC price
  /help              — Show available commands

Features:
  - Rate limiting: 1 request per 5 seconds per user
  - Error handling for offline/unreachable node
  - Self-signed certificate support for RustChain nodes
  - Deployable on Railway, Fly.io, or systemd

Usage:
  export TELEGRAM_BOT_TOKEN="your-token"
  python bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RUSTCHAIN_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://rustchain.org")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))

# Reference price fallback (USD)
RTC_PRICE_USD_FALLBACK = float(os.getenv("RTC_PRICE_USD", "0.10"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("rustchain_bot_2869")

# ---------------------------------------------------------------------------
# Rate Limiter — 1 request per 5 seconds per user
# ---------------------------------------------------------------------------


@dataclass
class RateLimiter:
    """Enforce 1 request per RATE_LIMIT_SECONDS per user."""

    window: int = RATE_LIMIT_SECONDS
    _last_hit: dict[int, float] = field(default_factory=dict)

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        last = self._last_hit.get(user_id)
        if last is not None and (now - last) < self.window:
            return False
        self._last_hit[user_id] = now
        return True

    def retry_after(self, user_id: int) -> float:
        last = self._last_hit.get(user_id)
        if last is None:
            return float(self.window)
        elapsed = time.monotonic() - last
        return max(0.0, self.window - elapsed)


rate_limiter = RateLimiter()

# ---------------------------------------------------------------------------
# RustChain API Client
# ---------------------------------------------------------------------------


class RustChainAPI:
    """Async HTTP client for RustChain node endpoints."""

    def __init__(self, base_url: str, timeout: int = REQUEST_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        # RustChain nodes use self-signed certs — disable verification
        self.client = httpx.AsyncClient(
            verify=True,  # Enforce TLS certificate validation
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": "RustChainTelegramBot/1.0"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            return {"_error": "Node is unreachable. The RustChain node may be offline."}
        except httpx.TimeoutException:
            return {"_error": "Request timed out. The node may be slow or unreachable."}
        except httpx.HTTPStatusError as exc:
            return {"_error": f"HTTP {exc.response.status_code} from node."}
        except Exception as exc:
            log.error("API error %s: %s", path, exc)
            return {"_error": f"Unexpected error: {exc}"}

    async def health(self) -> dict[str, Any]:
        return await self._get("/health")

    async def epoch(self) -> dict[str, Any]:
        return await self._get("/epoch")

    async def balance(self, miner_id: str) -> dict[str, Any]:
        return await self._get("/wallet/balance", params={"miner_id": miner_id})

    async def miners(self) -> dict[str, Any]:
        return await self._get("/api/miners")

    async def swap_info(self) -> dict[str, Any]:
        return await self._get("/wallet/swap-info")


# Global API client — created in main()
api: RustChainAPI | None = None


def _fmt_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    return f"{d}d {h}h {m}m"


def _error_text(data: dict[str, Any]) -> str:
    """Extract error text from an API response, or None if ok."""
    err = data.get("_error")
    if err:
        return err
    if data.get("error"):
        return str(data["error"])
    return ""


# ---------------------------------------------------------------------------
# Command: /start
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🛡️ *RustChain Wallet & Miner Bot*\n\n"
        "Query the RustChain network directly from Telegram.\n\n"
        "*Commands:*\n"
        "/balance <wallet> — Check RTC balance\n"
        "/miners — Active miners list\n"
        "/epoch — Current epoch info\n"
        "/price — RTC/wRTC price\n"
        "/help — Show this message\n\n"
        "Start mining at rustchain\\.org"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ---------------------------------------------------------------------------
# Command: /help
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🛡️ *RustChain Bot — Help*\n\n"
        "*Available Commands:*\n\n"
        "/balance <wallet\\_id>\n"
        "  Check the RTC balance of a wallet/miner\\.\n"
        "  Example: `/balance Ivan\\-houzhiwen`\n\n"
        "/miners\n"
        "  List currently active miners on the network\\.\n\n"
        "/epoch\n"
        "  Show current epoch, slot, pot, and enrolled miners\\.\n\n"
        "/price\n"
        "  Show the current RTC/wRTC price in USD\\.\n\n"
        "/help\n"
        "  Show this help message\\.\n\n"
        "_Rate limit: 1 request per 5 seconds per user\\._"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ---------------------------------------------------------------------------
# Command: /balance <wallet>
# ---------------------------------------------------------------------------

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not rate_limiter.is_allowed(user_id):
        retry = rate_limiter.retry_after(user_id)
        await update.message.reply_text(
            f"⏳ Rate limited\\. Please wait {retry:.0f}s before the next request\\.",
            parse_mode="MarkdownV2",
        )
        return

    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/balance <wallet_id>`\nExample: `/balance Ivan-houzhiwen`",
            parse_mode="Markdown",
        )
        return

    wallet = ctx.args[0]
    data = await api.balance(wallet)

    err = _error_text(data)
    if err:
        await update.message.reply_text(f"❌ Error: {err}")
        return

    amount_rtc = data.get("amount_rtc", 0.0)
    miner_id = data.get("miner_id", wallet)

    text = (
        f"💰 *Wallet Balance*\n\n"
        f"Wallet: `{miner_id}`\n"
        f"Balance: *{amount_rtc} RTC*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Command: /miners
# ---------------------------------------------------------------------------

async def cmd_miners(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not rate_limiter.is_allowed(user_id):
        retry = rate_limiter.retry_after(user_id)
        await update.message.reply_text(
            f"⏳ Rate limited\\. Please wait {retry:.0f}s before the next request\\.",
            parse_mode="MarkdownV2",
        )
        return

    data = await api.miners()

    err = _error_text(data)
    if err:
        await update.message.reply_text(f"❌ Error: {err}")
        return

    miners = data.get("miners", [])
    if not isinstance(miners, list):
        await update.message.reply_text("Unexpected response from /api/miners.")
        return

    if not miners:
        await update.message.reply_text("No active miners found on the network.")
        return

    lines = [f"⛏️ *Active Miners: {len(miners)}*\n"]
    for m in miners[:15]:
        name = m.get("miner", "?")
        hw = m.get("hardware_type", m.get("device_arch", ""))
        mult = m.get("antiquity_multiplier", "")
        # Escape underscores and special chars for MarkdownV2
        safe_name = _md_escape(name)
        safe_hw = _md_escape(str(hw))
        lines.append(f"  `{safe_name}` — {safe_hw} \\(x{mult}\\)")

    if len(miners) > 15:
        lines.append(f"\n_\\.\\.\\.and {len(miners) - 15} more_")

    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


# ---------------------------------------------------------------------------
# Command: /epoch
# ---------------------------------------------------------------------------

async def cmd_epoch(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not rate_limiter.is_allowed(user_id):
        retry = rate_limiter.retry_after(user_id)
        await update.message.reply_text(
            f"⏳ Rate limited\\. Please wait {retry:.0f}s before the next request\\.",
            parse_mode="MarkdownV2",
        )
        return

    data = await api.epoch()

    err = _error_text(data)
    if err:
        await update.message.reply_text(f"❌ Error: {err}")
        return

    epoch = data.get("epoch", "N/A")
    slot = data.get("slot", "N/A")
    blocks = data.get("blocks_per_epoch", "N/A")
    pot = data.get("epoch_pot", "N/A")
    enrolled = data.get("enrolled_miners", "N/A")
    supply = data.get("total_supply_rtc", "N/A")

    if isinstance(supply, (int, float)):
        supply = f"{supply:,}"

    text = (
        f"📅 *Epoch Info*\n\n"
        f"Epoch: `{epoch}`\n"
        f"Slot: `{slot}`\n"
        f"Blocks/Epoch: `{blocks}`\n"
        f"Epoch Pot: `{pot} RTC`\n"
        f"Enrolled Miners: `{enrolled}`\n"
        f"Total Supply: `{supply} RTC`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Command: /price
# ---------------------------------------------------------------------------

async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not rate_limiter.is_allowed(user_id):
        retry = rate_limiter.retry_after(user_id)
        await update.message.reply_text(
            f"⏳ Rate limited\\. Please wait {retry:.0f}s before the next request\\.",
            parse_mode="MarkdownV2",
        )
        return

    # Try to get price from the node's swap-info endpoint first
    price = RTC_PRICE_USD_FALLBACK
    source = "reference"

    try:
        info = await api.swap_info()
        ref = info.get("reference_price_usd")
        if ref and isinstance(ref, (int, float)) and ref > 0:
            price = ref
            source = "node"
    except Exception:
        pass

    # Also try DexScreener for the Solana wRTC pair
    try:
        async with httpx.AsyncClient(timeout=5) as dx:
            resp = await dx.get(
                "https://api.dexscreener.com/latest/dex/search?q=wRTC%20RustChain"
            )
            if resp.status_code == 200:
                pairs = resp.json().get("pairs", [])
                for pair in pairs:
                    base = pair.get("baseToken", {})
                    if "wrtc" in base.get("symbol", "").lower() or "wrtc" in base.get("name", "").lower():
                        price = float(pair.get("priceUsd", price))
                        source = "DexScreener"
                        break
    except Exception:
        pass  # keep fallback price

    # Get supply from epoch for market cap
    epoch_data = await api.epoch()
    supply = epoch_data.get("total_supply_rtc", 0) if "_error" not in epoch_data else 0
    mcap = price * supply if isinstance(supply, (int, float)) and supply else 0

    text = (
        f"💲 *RTC Price*\n\n"
        f"Price: *${price:.4f}*\n"
        f"Source: `{source}`\n"
        f"Total Supply: `{supply:,} RTC`\n"
        f"Market Cap: `${mcap:,.2f}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def on_error(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Update %s caused error: %s", update, ctx.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred processing your request\\. Please try again later\\.",
            parse_mode="MarkdownV2",
        )


# ---------------------------------------------------------------------------
# MarkdownV2 helper — escape special chars
# ---------------------------------------------------------------------------

def _md_escape(text: str) -> str:
    """Escape characters that are special in Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    result = []
    for ch in text:
        if ch in special:
            result.append(f"\\{ch}")
        else:
            result.append(ch)
    return "".join(result)


# ---------------------------------------------------------------------------
# Bot initialization
# ---------------------------------------------------------------------------

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("balance", "Check wallet balance"),
        BotCommand("miners", "List active miners"),
        BotCommand("epoch", "Current epoch info"),
        BotCommand("price", "RTC/wRTC price"),
        BotCommand("help", "Show all commands"),
    ]
    await application.bot.set_my_commands(commands)
    log.info("Bot commands registered")


def validate_config() -> bool:
    if not BOT_TOKEN:
        print(
            "Error: TELEGRAM_BOT_TOKEN environment variable is not set.\n\n"
            "1. Message @BotFather on Telegram\n"
            "2. Send /newbot to create a bot\n"
            "3. Copy the API token\n"
            "4. export TELEGRAM_BOT_TOKEN='your-token'\n"
            "   or add to .env file"
        )
        return False
    return True


def main() -> None:
    global api

    if not validate_config():
        sys.exit(1)

    api = RustChainAPI(RUSTCHAIN_NODE_URL)

    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    for name, handler in [
        ("start", cmd_start),
        ("help", cmd_help),
        ("balance", cmd_balance),
        ("miners", cmd_miners),
        ("epoch", cmd_epoch),
        ("price", cmd_price),
    ]:
        app.add_handler(CommandHandler(name, handler))

    app.add_error_handler(on_error)
    app.post_init = post_init

    log.info("Starting RustChain Bot | Node: %s | Rate limit: 1 req/%ds per user",
             RUSTCHAIN_NODE_URL, RATE_LIMIT_SECONDS)

    # Cleanup on shutdown
    async def shutdown_cb(application: Application) -> None:
        if api:
            await api.close()

    app.post_shutdown = shutdown_cb

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
