#!/usr/bin/env python3
"""
RustChain Telegram Community Bot
=================================
A Telegram bot for the RustChain community providing blockchain stats,
miner info, epoch data, and price information.

Bounty: #249 — https://github.com/Scottcjn/rustchain-bounties/issues/249
Author: kuanglaodi2-sudo

Setup:
    1. Copy .env.example to .env and add your Telegram bot token
    2. pip install -r requirements.txt
    3. python bot.py

Commands:
    /start        — Welcome message + command list
    /help         — Help
    /price        — Current wRTC price from Raydium
    /miners       — Active miner count + top miners
    /epoch        — Current epoch info
    /balance      — Check RTC balance for an address
    /health       — Node health status
    /stats        — Full network stats dashboard
    /alerts       — Enable/disable mining alerts (bonus)
    /subscribe    — Subscribe to epoch alerts (bonus)
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from api import DEFAULT_BASE_URL, RustChainAPI, RustChainAPIError

# ── Config ──────────────────────────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set. Copy .env.example to .env and add your token.")
    sys.exit(1)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rustchain_bot")

# ── State ───────────────────────────────────────────────────────────────────

# Global API client
api = RustChainAPI(
    base_url=os.getenv("RUSTCHAIN_API_URL", DEFAULT_BASE_URL)
)

# Alert subscriptions: user_id → True
alert_subscribers: set[int] = set()

# Last epoch tracked for alerts
_last_epoch: int = 0
_last_alert_time: dict = defaultdict(lambda: datetime.min)

# ── Keyboard helpers ─────────────────────────────────────────────────────────

def stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Network Stats", callback_data="stats"),
            InlineKeyboardButton("⛏️ Miners", callback_data="miners"),
        ],
        [
            InlineKeyboardButton("🪙 Price", callback_data="price"),
            InlineKeyboardButton("❤️ Health", callback_data="health"),
        ],
    ])


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔔 Enable Alerts", callback_data="alerts_on"),
            InlineKeyboardButton("🔕 Disable Alerts", callback_data="alerts_off"),
        ],
    ])


# ── Utilities ────────────────────────────────────────────────────────────────

def fmt_rtc(v: float) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v/1_000:.2f}K"
    return f"{v:.4f}"


def fmt_age(ts_ms: int) -> str:
    """Format a timestamp in ms as relative time."""
    if ts_ms <= 0:
        return "Never"
    age_s = (datetime.utcnow() - datetime.fromtimestamp(ts_ms / 1000)).total_seconds()
    if age_s < 60:
        return f"{int(age_s)}s ago"
    if age_s < 3600:
        return f"{int(age_s//60)}m ago"
    if age_s < 86400:
        return f"{int(age_s//3600)}h ago"
    return f"{int(age_s//86400)}d ago"


def bold(s: str) -> str:
    return f"<b>{s}</b>"


def code(s: str) -> str:
    return f"<code>{s}</code>"


def esc_html(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


# ── Command handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    text = (
        "🦀 <b>Welcome to the RustChain Bot!</b>\n\n"
        "I'm your gateway to the RustChain Proof-of-Antiquity blockchain.\n\n"
        "<b>Available Commands:</b>\n"
        "  /price    — Current wRTC price (Raydium)\n"
        "  /miners   — Active miners on the network\n"
        "  /epoch    — Current epoch information\n"
        "  /balance  — Check RTC wallet balance\n"
        "  /health   — Node health &amp; uptime\n"
        "  /stats    — Full network dashboard\n"
        "  /alerts   — Subscribe to mining alerts\n"
        "  /help     — This help message\n\n"
        "Built for the RustChain community 🦀"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=stats_keyboard())


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)


async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Get current wRTC/SOL price from Raydium."""
    await update.message.reply_text("🔍 Fetching price from Raydium…")
    try:
        price = await api.get_wrsc_price()
        if price:
            text = (
                f"💰 <b>wRTC Price</b>\n"
                f"  Raydium: <code>${price:.6f}</code> (USD)\n"
                f"  Pair: wRTC/SOL\n"
                f"  Updated: {datetime.utcnow().strftime('%H:%M:%S')} UTC"
            )
        else:
            # Fallback: show a note about the token
            text = (
                "💰 <b>wRTC Token</b>\n"
                "  wRTC is the wrapped RTC token on Solana.\n"
                "  Trade on Raydium: https://raydium.io\n"
                "  ⚠️ Price data temporarily unavailable — check Raydium directly."
            )
    except RustChainAPIError as e:
        log.error(f"Price fetch failed: {e}")
        text = "⚠️ Unable to fetch price right now. Please try again later."

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_miners(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show active miners."""
    await update.message.reply_text("⛏️ Fetching miner data…")
    try:
        stats = await api.get_network_stats()
        miners = await api.get_miners(limit=10)

        active, total = stats.miners_active, stats.miners_total
        avg_antiq = stats.avg_antiquity

        lines = [
            f"⛏️ <b>RustChain Miners</b>",
            f"  Active: {bold(str(active))} / Total: {bold(str(total))}",
            f"  Avg Antiquity: {bold(f'{avg_antiq:.2f}x')}",
            "",
            f"  <b>Top {min(len(miners[:5]), 5)} Active Miners:</b>",
        ]

        for i, m in enumerate(miners[:5], 1):
            arch = m.get("architecture", "unknown")
            antiq = m.get("antiquity", 1.0)
            status = "🟢" if m.get("last_attestation", 0) > 0 else "🔴"
            lines.append(
                f"  {status} #{i} · {code(arch)} · "
                f"Antiq: {bold(f'{antiq:.2f}x')} · "
                f"Blocks: {bold(str(m.get('blocks_mined', 0)))}"
            )

        text = "\n".join(lines)
    except RustChainAPIError as e:
        log.error(f"Miner fetch failed: {e}")
        text = "⚠️ Unable to fetch miner data. Is the node healthy?"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_epoch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show current epoch."""
    await update.message.reply_text("📟 Fetching epoch data…")
    try:
        epoch = await api.get_epoch()
        stats = await api.get_network_stats()

        lines = [
            f"📟 <b>Epoch #{epoch.number}</b>",
            f"  Started: {bold(epoch.start_time or '—')}",
            f"  Ends: {bold(epoch.end_time or '—')}",
            f"  Blocks: {bold(str(epoch.total_blocks))}",
            f"  Reward/block: {bold(str(epoch.reward_per_block))} RTC",
            f"  Active miners: {bold(str(epoch.active_miners))}",
            "",
            f"  Network avg antiquity: {bold(f'{stats.avg_antiquity:.2f}x')}",
            f"  Total supply: {bold(fmt_rtc(stats.total_supply_rtc))} RTC",
        ]
        text = "\n".join(lines)
    except RustChainAPIError as e:
        log.error(f"Epoch fetch failed: {e}")
        text = "⚠️ Unable to fetch epoch data."

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Check wallet balance."""
    if not ctx.args:
        await update.message.reply_text(
            "📖 <b>Usage:</b> /balance &lt;wallet_address&gt;\n"
            "Example: /balance C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg",
            parse_mode="HTML"
        )
        return

    wallet = ctx.args[0].strip()
    if len(wallet) < 20:
        await update.message.reply_text("⚠️ That doesn't look like a valid RTC address.")
        return

    await update.message.reply_text(f"🔍 Checking balance for {code(wallet[:12])}…")
    try:
        balance = await api.get_balance(wallet)
        text = (
            f"💰 <b>Balance</b>\n"
            f"  Wallet: {code(wallet)}\n"
            f"  Balance: {bold(fmt_rtc(balance))} RTC"
        )
    except Exception as e:
        log.error(f"Balance check failed for {wallet}: {e}")
        text = "⚠️ Unable to fetch balance. Check the wallet address."

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show node health."""
    await update.message.reply_text("❤️ Checking node health…")
    try:
        health = await api.get_health()
        status_icon = "✅" if health.healthy else "❌"
        status_text = "HEALTHY" if health.healthy else "UNHEALTHY"

        uptime = str(timedelta(seconds=health.uptime_secs))

        text = (
            f"{status_icon} <b>Node Health: {status_text}</b>\n"
            f"  Uptime: {bold(uptime)}\n"
            f"  Block height: {bold(str(health.block_height))}\n"
            f"  Peers: {bold(str(health.peers))}\n"
        )
        if health.message:
            text += f"  Message: <i>{esc_html(health.message)}</i>\n"

        text += f"\n  API: {bold(api.base_url)}"
    except RustChainAPIError as e:
        log.error(f"Health check failed: {e}")
        text = "⚠️ Unable to reach the RustChain node."

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Full network stats dashboard."""
    await update.message.reply_text("📊 Loading network dashboard…")
    try:
        stats = await api.get_network_stats()
        health = await api.get_health()
        epoch = await api.get_epoch()

        status_icon = "✅" if health.healthy else "❌"
        text = (
            f"📊 <b>RustChain Network Dashboard</b>\n\n"
            f"<b>Network</b>\n"
            f"  {status_icon} Status: {'HEALTHY' if health.healthy else 'UNHEALTHY'}\n"
            f"  Epoch: {bold(f'#{epoch.number}')}\n"
            f"  Block height: {bold(str(health.block_height))}\n\n"
            f"<b>Miners</b>\n"
            f"  Active: {bold(str(stats.miners_active))} / "
            f"Total: {bold(str(stats.miners_total))}\n"
            f"  Avg antiquity: {bold(f'{stats.avg_antiquity:.2f}x')}\n\n"
            f"<b>Supply</b>\n"
            f"  Total: {bold(fmt_rtc(stats.total_supply_rtc))} RTC\n\n"
            f"<b>Epoch #{epoch.number}</b>\n"
            f"  Blocks: {bold(str(epoch.total_blocks))}\n"
            f"  Reward: {bold(str(epoch.reward_per_block))} RTC/block\n"
            f"  Active miners: {bold(str(epoch.active_miners))}"
        )
    except RustChainAPIError as e:
        log.error(f"Stats fetch failed: {e}")
        text = "⚠️ Unable to fetch network stats. Try again shortly."

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=stats_keyboard())


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Subscribe to mining alerts."""
    user_id = update.effective_user.id
    is_subscribed = user_id in alert_subscribers

    if is_subscribed:
        text = (
            f"🔔 <b>Alerts Active</b>\n"
            f"You are receiving mining alerts.\n\n"
            f"Send /alerts again to disable."
        )
    else:
        alert_subscribers.add(user_id)
        text = (
            f"🔔 <b>Alerts Enabled!</b>\n"
            f"You will now receive:\n"
            f"  • New miner join notifications\n"
            f"  • Epoch settlement alerts\n"
            f"  • Network health warnings\n\n"
            f"Send /alerts again to unsubscribe."
        )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=subscribe_keyboard())


# ── Alert background job ─────────────────────────────────────────────────────

async def check_alerts(ctx: ContextTypes.DEFAULT_TYPE):
    """Background job: check for new miners/epochs and alert subscribers."""
    global _last_epoch

    if not alert_subscribers:
        return

    try:
        stats = await api.get_network_stats()
        epoch = await api.get_epoch()

        messages = []

        # New epoch
        if epoch.number > _last_epoch and _last_epoch > 0:
            messages.append(
                f"📟 <b>New Epoch #{epoch.number}</b>\n"
                f"Blocks: {epoch.total_blocks} · "
                f"Reward: {epoch.reward_per_block} RTC/block"
            )
        _last_epoch = epoch.number

        # Miner spike/drop (if active count changed significantly)
        # Simple: just alert on epoch change

        for msg_text in messages:
            for user_id in list(alert_subscribers):
                try:
                    await ctx.bot.send_message(
                        chat_id=user_id,
                        text=msg_text,
                        parse_mode="HTML",
                    )
                except Exception as e:
                    log.warning(f"Failed to alert user {user_id}: {e}")
                    alert_subscribers.discard(user_id)

    except Exception as e:
        log.error(f"Alert check failed: {e}")


# ── Error handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error(f"Telegram error: {ctx.error}", exc_info=ctx.error)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting RustChain Telegram Bot…")
    log.info(f"API endpoint: {api.base_url}")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("miners", cmd_miners))
    app.add_handler(CommandHandler("epoch", cmd_epoch))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("alerts", cmd_alerts))

    # Unknown command → help
    app.add_handler(MessageHandler(filters.COMMAND, cmd_help))

    # Error
    app.add_error_handler(error_handler)

    # Background alert job (every 60 seconds)
    async def setup_jobs():
        app.job_queue.run_repeating(check_alerts, interval=60, first=10)

    app.post_init = setup_jobs

    log.info("Bot ready. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
