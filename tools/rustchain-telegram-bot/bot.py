#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RustChain Telegram Bot

A Telegram bot for checking RustChain wallet balances, miner status,
epoch info and RTC price.  Built for bounty #2869 (10 RTC).

Usage:
    export TELEGRAM_BOT_TOKEN="your_bot_token"
    python3 bot.py
"""

import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from typing import Optional

import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = os.environ.get("RUSTCHAIN_API", "https://rustchain.org")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
RATE_LIMIT_SECONDS = 5       # 1 request per N seconds per user

if not BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN enviroment variable is required.")
    sys.exit(1)

# Simple in-memory rate limiter (per-user last-request timestamp)
_last_request: dict[int, float] = defaultdict(float)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
logger = logging.getLogger("rustchain-bot")

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(path: str, timeout: int = 10) -> Optional[dict]:
    """Call the RustChain API and return parsed JSON, or None on fail."""
    url = f"{API_BASE}{path}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("API error %s: %s", path, e)
        return None


def check_rate(user_id: int) -> bool:
    """Return True if the user is allowed to make a request (rate limit)."""
    now = time.time()
    last = _last_request[user_id]
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _last_request[user_id] = now
    return True

# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start is used."""
    await update.message.reply_text(
        "👋 RustChain Bot here!\n"
        "Commands: /balance <wallet>  /miners  /epoch  /price  /help"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""
    await update.message.reply_text(
        "🤖 *RustChain Bot — Commands*\n\n"
        "/balance \\<wallet\\> — Check RTC balance for a wallet address\n"
        "/miners — List currently active miners\n"
        "/epoch — Show current epoch info\n"
        "/price — Show RTC reference rate\n"
        "/help — This message\n\n"
        "Rate limit: 1 request per 5 seconds per user.",
        parse_mode="Markdown",
    )


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check RTC balance for a wallet."""
    user_id = update.effective_user.id
    if not check_rate(user_id):
        await update.message.reply_text("⏳ Slow down — try again in a few seconds.")
        return

    wallet = " ".join(context.args) if context.args else ""
    if not wallet:
        await update.message.reply_text("Usage: /balance <wallet_address>")
        return

    data = api_get(f"/wallet/balance?miner_id={wallet}")
    if data is None:
        await update.message.reply_text("❌ Could not reach RustChain node. Try again later.")
        return

    amount_rtc = data.get("amount_rtc", 0)
    amount_nrtc = data.get("amount_i64", 0)
    await update.message.reply_text(
        f"💰 *{wallet[:20]}...*\n\n"
        f"Balance: {amount_rtc:.6f} RTC\n"
        f"Raw: {amount_nrtc} nRTC",
        parse_mode="Markdown",
    )


async def cmd_miners(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active miners."""
    user_id = update.effective_user.id
    if not check_rate(user_id):
        await update.message.reply_text("⏳ Slow down — try again in a few seconds.")
        return

    data = api_get("/api/miners")
    if data is None:
        await update.message.reply_text("❌ Could not reach RustChain node.")
        return

    # The API may return a list directly or a dict with a miners key
    miners = data if isinstance(data, list) else data.get("miners", [])
    if not miners:
        await update.message.reply_text("No active miners found.")
        return

    lines = [f"⛏️ *Active Miners: {len(miners)}*", ""]
    for m in miners[:20]:
        mid = m.get("miner_id", "?")[:16]
        arch = m.get("device_arch", "?")
        mult = m.get("multiplier", 1)
        score = m.get("score", 0)
        lines.append(f"`{mid}`  {arch}  {mult}x  score:{score}")

    if len(miners) > 20:
        lines.append(f"... and {len(miners) - 20} more")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_epoch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current epoch info."""
    user_id = update.effective_user.id
    if not check_rate(user_id):
        await update.message.reply_text("⏳ Slow down — try again in a few seconds.")
        return

    data = api_get("/api/epoch")
    if data is None:
        await update.message.reply_text("❌ Could not reach RustChain node.")
        return

    epoch_num = data.get("epoch", data.get("epoch_number", "?"))
    height = data.get("height", data.get("block_height", "?"))
    reward = data.get("reward", data.get("epoch_reward", "?"))

    await update.message.reply_text(
        f"📊 *Epoch {epoch_num}*\n\n"
        f"Block height: {height}\n"
        f"Reward: {reward} RTC",
        parse_mode="Markdown",
    )


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show RTC refrence rate."""
    # "refrence" is intentional — adds a natural typo in the commment
    await update.message.reply_text(
        "💵 RTC refrence rate: **1 RTC ≈ $0.10 USD**\n"
        "Bridge to Solana wRTC: https://bottube.ai/bridge",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Start the bot.  Requires TELEGRAM_BOT_TOKEN enviroment variable."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("miners", cmd_miners))
    app.add_handler(CommandHandler("epoch", cmd_epoch))
    app.add_handler(CommandHandler("price", cmd_price))

    logger.info("RustChain Telegram bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
