#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
RustChain Telegram Bot
Issue #1597 — https://github.com/Scottcjn/rustchain-bounties/issues/1597

Commands:
  /start   - Welcome message
  /help    - Show all commands
  /health  - Check RustChain node health
  /epoch   - Current epoch info
  /balance - Check wallet balance for a miner
  /miners  - Active miners info
  /price   - RTC reference price
"""

import logging
import os
import sys
import time
from typing import Any, Optional

import requests
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RUSTCHAIN_API = os.getenv("RUSTCHAIN_API_URL", "https://rustchain.org")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
RTC_PRICE_USD = float(os.getenv("RTC_PRICE_USD", "0.10"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("rustchain_bot")

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_user_hits: dict[int, list[float]] = {}


def _rate_ok(user_id: int) -> bool:
    now = time.time()
    hits = _user_hits.setdefault(user_id, [])
    hits[:] = [t for t in hits if t > now - 60]
    if len(hits) >= RATE_LIMIT_RPM:
        return False
    hits.append(now)
    return True


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.verify = False


def _api_get(path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Make a GET request to the RustChain API."""
    url = f"{RUSTCHAIN_API.rstrip('/')}{path}"
    try:
        r = _session.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        log.error("API error %s: %s", path, exc)
        return {"error": str(exc)}


def _fmt_uptime(seconds: float) -> str:
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    return f"{d}d {h}h {m}m"


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*RustChain Query Bot*\n\n"
        "Query the RustChain network directly from Telegram.\n\n"
        "*Commands:*\n"
        "/health  - Node health status\n"
        "/epoch   - Current epoch info\n"
        "/balance <miner_id> - Wallet balance\n"
        "/miners  - Active miners\n"
        "/price   - RTC price\n"
        "/help    - Show this list\n\n"
        "Start mining at rustchain.org"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*Available Commands*\n\n"
        "/health  - Check node health and version\n"
        "/epoch   - Current epoch, slot, supply info\n"
        "/balance <miner_id> - Check RTC balance\n"
        "  Example: `/balance Ivan-houzhiwen`\n"
        "/miners  - Enrolled miners count and epoch pot\n"
        "/price   - Current RTC reference price\n"
        "/help    - This message\n\n"
        f"Rate limit: {RATE_LIMIT_RPM} requests/min"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _rate_ok(update.effective_user.id):
        await update.message.reply_text("Rate limit exceeded. Try again in a minute.")
        return

    data = _api_get("/health")
    if "error" in data:
        await update.message.reply_text(f"Error: {data['error']}")
        return

    ok = data.get("ok", False)
    status = "Online" if ok else "Offline"
    version = data.get("version", "N/A")
    uptime = _fmt_uptime(data.get("uptime_s", 0))
    tip_age = data.get("tip_age_slots", "N/A")
    db_rw = "Yes" if data.get("db_rw") else "No"

    text = (
        f"*Node Health*\n\n"
        f"Status: *{status}*\n"
        f"Version: `{version}`\n"
        f"Uptime: `{uptime}`\n"
        f"Tip age (slots): `{tip_age}`\n"
        f"DB writable: `{db_rw}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /epoch
# ---------------------------------------------------------------------------

async def cmd_epoch(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _rate_ok(update.effective_user.id):
        await update.message.reply_text("Rate limit exceeded. Try again in a minute.")
        return

    data = _api_get("/epoch")
    if "error" in data:
        await update.message.reply_text(f"Error: {data['error']}")
        return

    supply = data.get("total_supply_rtc", "N/A")
    if isinstance(supply, (int, float)):
        supply = f"{supply:,}"

    text = (
        f"*Epoch Info*\n\n"
        f"Epoch: *{data.get('epoch', 'N/A')}*\n"
        f"Slot: `{data.get('slot', 'N/A')}`\n"
        f"Blocks/epoch: `{data.get('blocks_per_epoch', 'N/A')}`\n"
        f"Enrolled miners: `{data.get('enrolled_miners', 'N/A')}`\n"
        f"Epoch pot: `{data.get('epoch_pot', 'N/A')} RTC`\n"
        f"Total supply: `{supply} RTC`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /balance <miner_id>
# ---------------------------------------------------------------------------

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _rate_ok(update.effective_user.id):
        await update.message.reply_text("Rate limit exceeded. Try again in a minute.")
        return

    if not ctx.args:
        await update.message.reply_text(
            "Usage: /balance <miner_id>\nExample: `/balance Ivan-houzhiwen`",
            parse_mode="Markdown",
        )
        return

    miner_id = ctx.args[0]
    data = _api_get("/wallet/balance", params={"miner_id": miner_id})
    if "error" in data:
        await update.message.reply_text(f"Error: {data['error']}")
        return

    amount_rtc = data.get("amount_rtc", 0.0)
    usd_val = amount_rtc * RTC_PRICE_USD

    text = (
        f"*Wallet Balance*\n\n"
        f"Miner: `{data.get('miner_id', miner_id)}`\n"
        f"Balance: *{amount_rtc} RTC*\n"
        f"USD value: ~${usd_val:,.2f} (@ ${RTC_PRICE_USD}/RTC)"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /miners
# ---------------------------------------------------------------------------

async def cmd_miners(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _rate_ok(update.effective_user.id):
        await update.message.reply_text("Rate limit exceeded. Try again in a minute.")
        return

    data = _api_get("/epoch")
    if "error" in data:
        await update.message.reply_text(f"Error: {data['error']}")
        return

    enrolled = data.get("enrolled_miners", "N/A")
    epoch_pot = data.get("epoch_pot", "N/A")
    blocks = data.get("blocks_per_epoch", 144)

    per_miner = ""
    if isinstance(enrolled, (int, float)) and enrolled > 0 and isinstance(epoch_pot, (int, float)):
        est = epoch_pot / enrolled
        per_miner = f"\nEst. per miner: `~{est:.4f} RTC/epoch`"

    text = (
        f"*Miners*\n\n"
        f"Enrolled miners: *{enrolled}*\n"
        f"Epoch pot: `{epoch_pot} RTC`\n"
        f"Blocks/epoch: `{blocks}`"
        f"{per_miner}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /price
# ---------------------------------------------------------------------------

async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _rate_ok(update.effective_user.id):
        await update.message.reply_text("Rate limit exceeded. Try again in a minute.")
        return

    price = RTC_PRICE_USD
    source = "reference"

    try:
        r = requests.get(
            "https://api.dexscreener.com/latest/dex/search?q=RTC%20RustChain",
            timeout=5,
        )
        if r.status_code == 200:
            pairs = r.json().get("pairs") or []
            for pair in pairs:
                if "rustchain" in (pair.get("baseToken", {}).get("name", "")).lower():
                    price = float(pair["priceUsd"])
                    source = "DexScreener"
                    break
    except Exception:
        pass

    epoch_data = _api_get("/epoch")
    supply = epoch_data.get("total_supply_rtc", 0)
    mcap = price * supply if supply else 0

    text = (
        f"*RTC Price*\n\n"
        f"Price: *${price:.4f}*\n"
        f"Source: `{source}`\n"
        f"Total supply: `{supply:,} RTC`\n"
        f"Market cap: `${mcap:,.2f}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def on_error(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Update %s caused error: %s", update, ctx.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "An error occurred processing your request."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def post_init(app: Application) -> None:
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("health", "Node health status"),
        BotCommand("epoch", "Current epoch info"),
        BotCommand("balance", "Check wallet balance"),
        BotCommand("miners", "Active miners info"),
        BotCommand("price", "RTC price"),
        BotCommand("help", "Show all commands"),
    ]
    await app.bot.set_my_commands(commands)
    log.info("Bot commands registered")


def main() -> None:
    if not BOT_TOKEN:
        print(
            "Error: TELEGRAM_BOT_TOKEN not set.\n\n"
            "1. Message @BotFather on Telegram\n"
            "2. /newbot to create a bot\n"
            "3. Copy the token\n"
            "4. export TELEGRAM_BOT_TOKEN='your-token'\n"
            "   or add to .env file"
        )
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("epoch", cmd_epoch))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("miners", cmd_miners))
    app.add_handler(CommandHandler("price", cmd_price))

    app.add_error_handler(on_error)
    app.post_init = post_init

    log.info("Starting RustChain Bot | API: %s", RUSTCHAIN_API)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
