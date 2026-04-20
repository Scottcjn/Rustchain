#!/usr/bin/env python3
"""
RustChain Telegram Bot
Directly queries the RustChain node at https://50.28.86.131

Commands:
  /start    - Welcome message
  /balance  - Check wallet balance
  /stats    - Network statistics
  /epoch    - Current epoch info
  /price    - Show RTC reference rate
  /help     - List all commands

Rate limit: 1 request per 5 seconds per user
"""

import asyncio
import logging
import os
import time
import urllib.error
import urllib.request
import json
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)
from telegram.constants import ParseMode

# Configuration via environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
NODE_BASE_URL = os.environ.get("NODE_BASE_URL", "https://50.28.86.131")
RTC_USD_PRICE = 0.10
RATE_LIMIT_SECONDS = 5

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# --- Rate Limiting ---
user_last_request: dict[int, float] = {}
lock = asyncio.Lock()


async def is_rate_limited(user_id: int) -> bool:
    """Check if user is rate limited. Returns True if limited."""
    async with lock:
        now = time.time()
        if user_id in user_last_request:
            elapsed = now - user_last_request[user_id]
            if elapsed < RATE_LIMIT_SECONDS:
                return True
        user_last_request[user_id] = now
        return False


# --- API Helpers ---


async def fetch_json(endpoint: str, timeout: int = 10) -> Optional[dict]:
    """Fetch JSON from RustChain node API with error handling."""
    url = f"{NODE_BASE_URL}{endpoint}"
    try:
        req = urllib.request.Request(url)
        with await asyncio.to_thread(
            urllib.request.urlopen, req, timeout=timeout
        ) as response:
            body = response.read().decode()
            return json.loads(body)
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error {e.code} for {url}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"Node unreachable {url}: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from {url}: {e}")
        return None


async def check_node_health() -> bool:
    """Check if RustChain node is online."""
    data = await fetch_json("/health")
    return data is not None


# --- Command Handlers ---


async def cmd_start(update: Update, context: CallbackContext) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Welcome to RustChain Bot!\n"
        "Your vintage hardware earns more as it ages.\n\n"
        "Use /help to see all commands."
    )


async def cmd_help(update: Update, context: CallbackContext) -> None:
    """Handle /help command."""
    help_text = (
        "<b>RustChain Bot Commands</b>\n\n"
        "/balance <i>&lt;wallet_id&gt;</i> - Check wallet balance\n"
        "/stats - Network statistics (miners, supply)\n"
        "/epoch - Current epoch and slot info\n"
        "/price - Show RTC/USD reference rate\n"
        "/help - Show this help message\n\n"
        "<i>Rate limit: 1 request per 5 seconds</i>"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def cmd_balance(update: Update, context: CallbackContext) -> None:
    """Handle /balance <wallet> command."""
    user_id = update.effective_user.id

    if await is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ Rate limited. Please wait 5 seconds between requests."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /balance <wallet_id>\n"
            "Example: /balance Ivan-houzhiwen"
        )
        return

    wallet_id = context.args[0]

    if not await check_node_health():
        await update.message.reply_text(
            "❌ Node is offline. Please try again later."
        )
        return

    data = await fetch_json(f"/wallet/balance?miner_id={wallet_id}")
    if data is None:
        await update.message.reply_text(
            f"❌ Could not fetch balance for: <code>{wallet_id}</code>\n"
            "Check the wallet ID and try again.",
            parse_mode=ParseMode.HTML,
        )
        return

    balance = data.get("amount_rtc", 0)
    amount_i64 = data.get("amount_i64", 0)
    miner_id = data.get("miner_id", wallet_id)

    await update.message.reply_text(
        f"💰 <b>Wallet:</b> <code>{miner_id}</code>\n"
        f"💵 <b>Balance:</b> {balance} RTC\n"
        f"🔢 <b>Raw units:</b> {amount_i64}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_stats(update: Update, context: CallbackContext) -> None:
    """Handle /stats command - network statistics."""
    user_id = update.effective_user.id

    if await is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ Rate limited. Please wait 5 seconds between requests."
        )
        return

    if not await check_node_health():
        await update.message.reply_text(
            "❌ Node is offline. Please try again later."
        )
        return

    epoch_data = await fetch_json("/epoch")
    if epoch_data is None:
        await update.message.reply_text(
            "❌ Could not fetch network statistics."
        )
        return

    enrolled = epoch_data.get("enrolled_miners", "N/A")
    total_supply = epoch_data.get("total_supply_rtc", 0)
    blocks_per_epoch = epoch_data.get("blocks_per_epoch", "N/A")
    epoch_pot = epoch_data.get("epoch_pot", "N/A")

    health_data = await fetch_json("/health")
    version = "N/A"
    uptime_h = "N/A"
    if health_data:
        version = health_data.get("version", "N/A")
        uptime_s = health_data.get("uptime_s", 0)
        uptime_h = round(uptime_s / 3600, 1)

    text = (
        f"📊 <b>RustChain Network Stats</b>\n\n"
        f"⛏️  <b>Active Miners:</b> {enrolled}\n"
        f"📦 <b>Blocks/Epoch:</b> {blocks_per_epoch}\n"
        f"💰 <b>Total Supply:</b> {total_supply} RTC\n"
        f"🎯 <b>Epoch Pot:</b> {epoch_pot} RTC\n"
        f"⏱️  <b>Node Uptime:</b> {uptime_h} hours\n"
        f"🔧 <b>Node Version:</b> <code>{version}</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_epoch(update: Update, context: CallbackContext) -> None:
    """Handle /epoch command."""
    user_id = update.effective_user.id

    if await is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ Rate limited. Please wait 5 seconds between requests."
        )
        return

    if not await check_node_health():
        await update.message.reply_text(
            "❌ Node is offline. Please try again later."
        )
        return

    data = await fetch_json("/epoch")
    if data is None:
        await update.message.reply_text(
            "❌ Could not fetch epoch info."
        )
        return

    epoch = data.get("epoch", "N/A")
    slot = data.get("slot", "N/A")
    height = data.get("height", "N/A")
    blocks_per_epoch = data.get("blocks_per_epoch", "N/A")

    await update.message.reply_text(
        f"📈 <b>Epoch Info</b>\n\n"
        f"🔢 <b>Epoch:</b> {epoch}\n"
        f"🔪 <b>Slot:</b> {slot}\n"
        f"📦 <b>Block Height:</b> {height}\n"
        f"📊 <b>Blocks/Epoch:</b> {blocks_per_epoch}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_price(update: Update, context: CallbackContext) -> None:
    """Handle /price command."""
    user_id = update.effective_user.id

    if await is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ Rate limited. Please wait 5 seconds between requests."
        )
        return

    await update.message.reply_text(
        f"💲 <b>RTC Reference Rate</b>\n\n"
        f"${RTC_USD_PRICE:.2f} per RTC\n\n"
        f"<i>RTC is earned through mining on the RustChain network.\n"
        f"The best hardware to mine? Old hardware.\n"
        f"A PowerBook G4 from 2003 earns 2.5x more than a Threadripper.</i>",
        parse_mode=ParseMode.HTML,
    )


async def error_handler(
    update: object, context: CallbackContext
) -> None:
    """Handle unexpected errors."""
    logger.error(f"Exception: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again."
        )


def main() -> None:
    """Start the bot."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN not set! Set the BOT_TOKEN environment variable.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("balance", cmd_balance))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("epoch", cmd_epoch))
    application.add_handler(CommandHandler("price", cmd_price))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_error_handler(error_handler)

    # Start polling
    logger.info("RustChain Telegram Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
