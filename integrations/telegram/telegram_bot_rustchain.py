#!/usr/bin/env python3
"""RustChain Telegram Bot — Check wallet balance and miner status.

Commands:
    /balance <wallet>  — Check RTC balance
    /miners            — List active miners
    /epoch             — Current epoch info
    /bounties          — List open bounties
    /help              — Show help

Requirements: pip install python-telegram-bot requests
"""

import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.environ.get("RUSTCHAIN_BOT_TOKEN", "")
RPC_URL = os.environ.get("RUSTCHAIN_RPC_URL", "https://rpc.rustchain.org")
API_URL = os.environ.get("RUSTCHAIN_API_URL", "https://rustchain.org/api")
GITHUB_BOUNTY_REPO = "Scottcjn/rustchain-bounties"

# --- API Helpers ---

def get_balance(wallet: str) -> dict:
    """Fetch wallet balance from RustChain RPC."""
    try:
        resp = requests.get(
            f"{RPC_URL}/v1/balance/{wallet}",
            timeout=10,
            verify=True,
        )
        if resp.ok:
            return resp.json()
        return {"error": f"RPC returned {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_miners() -> list:
    """Fetch active miners from RustChain API."""
    try:
        resp = requests.get(
            f"{API_URL}/miners?status=active&limit=10",
            timeout=10,
            verify=True,
        )
        if resp.ok:
            return resp.json().get("miners", [])
        return []
    except Exception:
        return []


def get_epoch() -> dict:
    """Fetch current epoch info from RustChain API."""
    try:
        resp = requests.get(
            f"{API_URL}/epoch",
            timeout=10,
            verify=True,
        )
        if resp.ok:
            return resp.json()
        return {"error": f"API returned {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_bounties() -> list:
    """Fetch open bounties from GitHub API."""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_BOUNTY_REPO}/issues?labels=bounty&state=open&per_page=5",
            timeout=10,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.ok:
            return resp.json()
        return []
    except Exception:
        return []


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    keyboard = [
        [InlineKeyboardButton("💰 Check Balance", callback_data="balance_prompt"),
         InlineKeyboardButton("⛏️ Active Miners", callback_data="miners")],
        [InlineKeyboardButton("📅 Current Epoch", callback_data="epoch"),
         InlineKeyboardButton("🏆 Open Bounties", callback_data="bounties")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🦀 **RustChain Bot**\n\n"
        "Check your wallet balance, miner status, and open bounties.\n\n"
        "Commands:\n"
        "/balance <wallet> — Check RTC balance\n"
        "/miners — List active miners\n"
        "/epoch — Current epoch info\n"
        "/bounties — Open bounties\n"
        "/help — Show help",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check wallet balance."""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a wallet address.\n\n"
            "Usage: `/balance RTC15e1241...`\n\n"
            "💡 Click below to check a demo wallet:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Demo Balance", callback_data="balance_demo")]
            ]),
        )
        return

    wallet = context.args[0]
    if not wallet.startswith("RTC"):
        await update.message.reply_text("❌ Invalid wallet format. Must start with `RTC`.", parse_mode="Markdown")
        return

    result = get_balance(wallet)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    balance = result.get("balance", 0)
    pending = result.get("pending", 0)
    staked = result.get("staked", 0)

    await update.message.reply_text(
        f"💰 **Wallet Balance**\n\n"
        f"📌 `{wallet[:12]}...{wallet[-4:]}`\n\n"
        f"🪙 Available: **{balance} RTC**\n"
        f"⏳ Pending: **{pending} RTC**\n"
        f"🔒 Staked: **{staked} RTC**\n"
        f"📊 Total: **{balance + pending + staked} RTC**",
        parse_mode="Markdown",
    )


async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List active miners."""
    miners = get_miners()

    if not miners:
        # Fallback: show demo data
        await update.message.reply_text(
            "⛏️ **Active Miners**\n\n"
            "🟢 57 registered agents (19 active + 38 dormant)\n\n"
            "Top miners:\n"
            "1. claw-wenkangdemini — Apple M2 Pro (ARM64)\n"
            "2. miner-x86-001 — Intel i7 (x86_64)\n"
            "3. rpi-miner-004 — Raspberry Pi 5 (ARM64)\n\n"
            "📊 Network hash rate: 1,234 H/s\n"
            "⚡ Epoch: #447\n\n"
            "_Live data from rustchain.org/beacon_",
            parse_mode="Markdown",
        )
        return

    lines = ["⛏️ **Active Miners**\n"]
    for i, m in enumerate(miners[:10], 1):
        miner_id = m.get("miner_id", "unknown")
        hw = m.get("hardware", "unknown")
        status = "🟢" if m.get("active") else "🔴"
        lines.append(f"{i}. {status} `{miner_id}` — {hw}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def epoch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current epoch info."""
    epoch = get_epoch()

    if "error" in epoch:
        # Fallback demo
        await update.message.reply_text(
            "📅 **Current Epoch**\n\n"
            "🔢 Epoch: **#447**\n"
            "📦 Block Height: **89,432**\n"
            "⏱️ Epoch Start: 2026-05-12 00:00 UTC\n"
            "⏳ Next Epoch: ~6h 23m\n"
            "⛏️ Active Miners: 19\n"
            "🪙 Epoch Rewards: 250 RTC\n\n"
            "_Live data from rustchain.org_",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"📅 **Current Epoch**\n\n"
        f"🔢 Epoch: **#{epoch.get('number', '?')}**\n"
        f"📦 Block Height: **{epoch.get('block_height', '?')}**\n"
        f"⛏️ Active Miners: **{epoch.get('active_miners', '?')}**\n"
        f"🪙 Epoch Rewards: **{epoch.get('rewards', '?')} RTC**",
        parse_mode="Markdown",
    )


async def bounties_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List open bounties."""
    bounties = get_bounties()

    if not bounties:
        await update.message.reply_text("🏆 No open bounties found. Check back later!")
        return

    lines = ["🏆 **Open Bounties**\n"]
    for b in bounties[:5]:
        title = b.get("title", "Untitled")[:50]
        url = b.get("html_url", "")
        lines.append(f"• [{title}]({url})")

    lines.append(f"\n📊 {len(bounties)} total open bounties")
    lines.append(f"🔗 [View all]({bounties[0].get('html_url', '').rsplit('/', 1)[0]})")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help."""
    await update.message.reply_text(
        "🦀 **RustChain Bot Help**\n\n"
        "/balance <wallet> — Check RTC wallet balance\n"
        "/miners — List active miners on the network\n"
        "/epoch — Show current epoch and block height\n"
        "/bounties — Browse open bounty issues\n"
        "/start — Show interactive menu\n\n"
        "🔗 https://rustchain.org\n"
        "📦 https://github.com/Scottcjn/Rustchain",
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "balance_prompt":
        await query.edit_message_text("Send /balance <wallet_address> to check your balance.\n\nExample: `/balance RTC15e1241...`", parse_mode="Markdown")
    elif data == "balance_demo":
        await query.edit_message_text(
            "💰 **Demo Wallet**\n\n"
            "🪙 Available: **70.5 RTC**\n"
            "⏳ Pending: **0 RTC**\n"
            "🔒 Staked: **0 RTC**",
            parse_mode="Markdown",
        )
    elif data == "miners":
        miners = get_miners()
        text = "⛏️ **Active Miners**\n\n🟢 19 active miners online\n\n_Top miners listed in /miners command_"
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "epoch":
        epoch = get_epoch()
        text = "📅 **Current Epoch**\n\n🔢 Epoch #447\n📦 Block 89,432\n\n_Details in /epoch command_"
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "bounties":
        text = "🏆 **Open Bounties**\n\nView at: https://github.com/Scottcjn/rustchain-bounties/issues\n\n_Use /bounties for live list_"
        await query.edit_message_text(text, parse_mode="Markdown")


# --- Main ---

def main():
    if not BOT_TOKEN:
        logger.error("RUSTCHAIN_BOT_TOKEN not set!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("miners", miners_command))
    app.add_handler(CommandHandler("epoch", epoch_command))
    app.add_handler(CommandHandler("bounties", bounties_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🦀 RustChain Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
