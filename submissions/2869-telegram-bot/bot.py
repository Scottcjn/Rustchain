#!/usr/bin/env python3
"""
RustChain Telegram Bot — @RustChainBot
Bounty #2869 — 10 RTC

Commands:
  /balance <wallet>  — Check RTC balance
  /miners            — List active miners
  /epoch             — Current epoch info
  /price             — Show RTC reference rate
  /help              — Show commands
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Dict, List, Optional

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RUSTCHAIN_BASE = "https://rustchain.org"
RTC_USD_RATE = 0.10  # Reference rate per bounty spec
RATE_LIMIT_SECONDS = 5  # 1 request per 5s per user

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("RustChainBot")

# ---------------------------------------------------------------------------
# Rate limiter (per-user, in-memory)
# ---------------------------------------------------------------------------
_user_last_call: Dict[int, float] = {}


def rate_limited(func):
    """Decorator: allow 1 call per RATE_LIMIT_SECONDS per user."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        now = time.monotonic()
        last = _user_last_call.get(user_id, 0)
        if now - last < RATE_LIMIT_SECONDS:
            wait = RATE_LIMIT_SECONDS - (now - last)
            await update.message.reply_text(
                f"⏳ Rate limited — please wait {wait:.0f}s before next command."
            )
            return
        _user_last_call[user_id] = now
        return await func(update, context, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# RustChain API helpers
# ---------------------------------------------------------------------------

def _api_get(path: str, params: Optional[Dict] = None, timeout: int = 10) -> Any:
    """GET from RustChain API. Returns parsed JSON or raises on error."""
    url = f"{RUSTCHAIN_BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "RustChain node is offline. Please try again later."}
    except requests.exceptions.Timeout:
        return {"error": "RustChain node timed out. Please try again later."}
    except requests.exceptions.HTTPError as e:
        return {"error": f"API error: {e.response.status_code}"}


def _fmt_miners(miners: List[Dict], total: int = 0) -> str:
    """Format miner list for display."""
    if not miners:
        return "No active miners found."
    lines = []
    for m in miners[:20]:  # Cap at 20 for message length
        name = m.get("miner", "unknown")
        hw = m.get("hardware_type", m.get("device_family", "?"))
        mult = m.get("antiquity_multiplier", 0)
        lines.append(f"⛏ {name}\n   {hw} | {mult}x multiplier")
    shown = min(len(miners), 20)
    footer = f"\nShowing {shown}/{total or len(miners)} miners" if (total or len(miners)) > 20 else ""
    return "\n".join(lines) + footer


# ---------------------------------------------------------------------------
# Bot command handlers
# ---------------------------------------------------------------------------

@rate_limited
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""
    text = (
        "🦀 *RustChain Bot Commands*\n\n"
        "/balance <wallet\\> — Check RTC wallet balance\n"
        "/miners — List active miners on the network\n"
        "/epoch — Current epoch info and reward pot\n"
        "/price — RTC reference rate (USD)\n"
        "/help — Show this message\n\n"
        "_Powered by RustChain Proof of Antiquity_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@rate_limited
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check RTC balance for a wallet."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /balance <wallet_name_or_address>\n"
            "Example: /balance Xeophon"
        )
        return

    wallet = " ".join(context.args)
    data = _api_get("/wallet/balance", {"miner_id": wallet})

    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return

    amount_rtc = data.get("amount_rtc", 0)
    amount_usd = amount_rtc * RTC_USD_RATE
    text = (
        f"💰 *Balance for* `{wallet}`\n\n"
        f"• {amount_rtc:.6f} RTC\n"
        f"• ≈ ${amount_usd:.4f} USD\n\n"
        f"_Reference rate: 1 RTC = ${RTC_USD_RATE}_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@rate_limited
async def miners_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active miners."""
    data = _api_get("/api/miners")

    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return

    # API returns {miners: [...], pagination: {total: N}}
    if isinstance(data, dict) and "miners" in data:
        miners = data["miners"]
        total = data.get("pagination", {}).get("total", len(miners))
    elif isinstance(data, list):
        miners = data
        total = len(miners)
    else:
        miners = []
        total = 0
    text = f"⛏ *Active Miners* ({total} total)\n\n{_fmt_miners(miners, total)}"
    await update.message.reply_text(text, parse_mode="Markdown")


@rate_limited
async def epoch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current epoch info."""
    data = _api_get("/epoch")

    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return

    epoch = data.get("epoch", "?")
    slot = data.get("slot", "?")
    bpe = data.get("blocks_per_epoch", "?")
    pot = data.get("epoch_pot", 0)
    enrolled = data.get("enrolled_miners", 0)
    supply = data.get("total_supply_rtc", "?")

    progress = (slot % bpe / bpe * 100) if isinstance(slot, int) and isinstance(bpe, int) and bpe > 0 else 0

    text = (
        f"📊 *Epoch {epoch}*\n\n"
        f"• Slot: {slot} / {bpe} ({progress:.0f}% complete)\n"
        f"• Reward pot: {pot} RTC\n"
        f"• Enrolled miners: {enrolled}\n"
        f"• Total supply: {supply:,} RTC"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@rate_limited
async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show RTC reference rate."""
    text = (
        f"💵 *RTC Reference Rate*\n\n"
        f"• 1 RTC = ${RTC_USD_RATE} USD\n"
        f"• 10 RTC = ${RTC_USD_RATE * 10} USD\n"
        f"• 100 RTC = ${RTC_USD_RATE * 100} USD\n\n"
        f"_Reference rate from RustChain bounty spec_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import os
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set. Get one from @BotFather.")
        raise SystemExit(1)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", help_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("miners", miners_cmd))
    app.add_handler(CommandHandler("epoch", epoch_cmd))
    app.add_handler(CommandHandler("price", price_cmd))

    logger.info("RustChain Telegram Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
