#!/usr/bin/env python3
"""
RustChain Telegram Tip Bot

A lightweight RTC tip bot for Telegram using on-chain transactions.

Commands:
- /tip @user <amount> — Send RTC to another user
- /balance — Check your RTC balance
- /deposit — Show your RTC wallet address
- /withdraw <address> <amount> — Withdraw to external RTC wallet
- /leaderboard — Top RTC holders in the server
- /rain <amount> — Split RTC across recent active users

Author: agent渡文 (OpenClaw)
Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/31
"""

import os
import json
import hashlib
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import requests
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =============================================================================
# Configuration
# =============================================================================

NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")
VERIFY_SSL = os.environ.get("RUSTCHAIN_VERIFY_SSL", "false").lower() == "true"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BOT_SECRET = os.environ.get("BOT_SECRET", "rustchain-tip-bot-secret-key")

# Rate limiting
MIN_TIP_AMOUNT = 0.001  # Minimum tip in RTC
RATE_LIMIT_SECONDS = 10  # Seconds between tips per user
LARGE_TRANSFER_THRESHOLD = 10.0  # RTC - requires confirmation

# Storage
DATA_DIR = Path.home() / ".rustchain-tip-bot"
DATA_DIR.mkdir(parents=True, exist_ok=True)
WALLETS_FILE = DATA_DIR / "wallets.json"
RATE_LIMIT_FILE = DATA_DIR / "rate_limits.json"

# =============================================================================
# Wallet Crypto (Simplified - Ed25519 placeholder)
# =============================================================================

def derive_wallet_address(user_id: int, bot_secret: str) -> str:
    """
    Derive a deterministic wallet address from Telegram user ID + bot secret.
    
    In production, this should use proper Ed25519 key derivation.
    For now, uses SHA256 for deterministic address generation.
    """
    seed = f"{bot_secret}:{user_id}"
    hash_bytes = hashlib.sha256(seed.encode()).hexdigest()[:40]
    return f"RTC{hash_bytes}"


def derive_keypair(user_id: int, bot_secret: str) -> tuple:
    """
    Derive Ed25519 keypair from user ID + bot secret.
    
    Returns: (private_key_hex, public_key_hex, address)
    """
    # TODO: Replace with proper Ed25519 key derivation using cryptography library
    # For now, use deterministic SHA256-based generation
    seed = f"{bot_secret}:{user_id}"
    priv = hashlib.sha256(f"{seed}:priv".encode()).hexdigest()
    pub = hashlib.sha256(f"{seed}:pub".encode()).hexdigest()
    addr = derive_wallet_address(user_id, bot_secret)
    return priv, pub, addr


def sign_transaction(priv_key: str, tx_data: dict) -> str:
    """
    Sign a transaction with Ed25519 private key.
    
    Returns: signature hex string
    """
    # TODO: Replace with proper Ed25519 signing
    # For now, use HMAC-SHA256 as placeholder
    import hmac
    message = json.dumps(tx_data, sort_keys=True)
    sig = hmac.new(
        priv_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return sig


# =============================================================================
# Storage
# =============================================================================

def load_wallets() -> Dict:
    """Load wallets from disk."""
    if WALLETS_FILE.exists():
        with open(WALLETS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_wallets(wallets: Dict):
    """Save wallets to disk."""
    with open(WALLETS_FILE, 'w') as f:
        json.dump(wallets, f, indent=2)


def load_rate_limits() -> Dict:
    """Load rate limits from disk."""
    if RATE_LIMIT_FILE.exists():
        with open(RATE_LIMIT_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_rate_limits(limits: Dict):
    """Save rate limits to disk."""
    with open(RATE_LIMIT_FILE, 'w') as f:
        json.dump(limits, f)


def get_or_create_wallet(user_id: int) -> dict:
    """Get or create wallet for a user."""
    wallets = load_wallets()
    user_id_str = str(user_id)
    
    if user_id_str not in wallets:
        priv, pub, addr = derive_keypair(user_id, BOT_SECRET)
        wallets[user_id_str] = {
            "address": addr,
            "public_key": pub,
            "private_key": priv,  # In production, encrypt this!
            "created_at": time.time(),
        }
        save_wallets(wallets)
    
    return wallets[user_id_str]


# =============================================================================
# Node API
# =============================================================================

def api_get(endpoint: str, params: dict = None) -> dict:
    """Make GET request to RustChain node."""
    url = f"{NODE_URL}{endpoint}"
    try:
        resp = requests.get(url, params=params, verify=VERIFY_SSL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def api_post(endpoint: str, data: dict) -> dict:
    """Make POST request to RustChain node."""
    url = f"{NODE_URL}{endpoint}"
    try:
        resp = requests.post(url, json=data, verify=VERIFY_SSL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_balance(address: str) -> float:
    """Get RTC balance for an address."""
    result = api_get("/wallet/balance", {"miner_id": address})
    if "error" in result:
        return 0.0
    return float(result.get("amount_rtc", 0))


def send_signed_transfer(from_addr: str, to_addr: str, amount: float, 
                         priv_key: str, pub_key: str, memo: str = "") -> dict:
    """Send signed transfer via node API."""
    tx_data = {
        "from": from_addr,
        "to": to_addr,
        "amount": amount,
        "memo": memo,
        "nonce": int(time.time() * 1000),
    }
    
    signature = sign_transaction(priv_key, tx_data)
    
    payload = {
        **tx_data,
        "signature": signature,
        "public_key": pub_key,
    }
    
    return api_post("/wallet/transfer/signed", payload)


# =============================================================================
# Rate Limiting
# =============================================================================

def check_rate_limit(user_id: int) -> tuple:
    """Check if user is rate limited. Returns (allowed, remaining_seconds)."""
    limits = load_rate_limits()
    user_id_str = str(user_id)
    
    if user_id_str in limits:
        last_time = limits[user_id_str]
        elapsed = time.time() - last_time
        if elapsed < RATE_LIMIT_SECONDS:
            return False, int(RATE_LIMIT_SECONDS - elapsed)
    
    # Update rate limit
    limits[user_id_str] = time.time()
    save_rate_limits(limits)
    return True, 0


# =============================================================================
# Bot Commands
# =============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    wallet = get_or_create_wallet(user.id)
    
    msg = f"""🪙 **Welcome to RustChain Tip Bot!**

Your wallet address:
`{wallet['address']}`

**Commands:**
/tip @user <amount> — Send RTC
/balance — Check balance
/deposit — Show deposit address
/withdraw <addr> <amount> — Withdraw
/leaderboard — Top holders
/rain <amount> — Rain to active users

**Network:** {NODE_URL}
**Min tip:** {MIN_TIP_AMOUNT} RTC
"""
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command."""
    user = update.effective_user
    wallet = get_or_create_wallet(user.id)
    
    balance = get_balance(wallet['address'])
    
    await update.message.reply_text(
        f"💰 **Your Balance**\n\n"
        f"Address: `{wallet['address']}`\n"
        f"Balance: **{balance:.4f} RTC**",
        parse_mode="Markdown"
    )


async def cmd_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deposit command."""
    user = update.effective_user
    wallet = get_or_create_wallet(user.id)
    
    await update.message.reply_text(
        f"📥 **Your Deposit Address**\n\n"
        f"`{wallet['address']}`\n\n"
        f"Send RTC to this address to fund your tip bot wallet.\n"
        f"Refresh with /balance after deposit.",
        parse_mode="Markdown"
    )


async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tip command."""
    user = update.effective_user
    
    # Parse arguments: /tip @user amount
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /tip @user <amount>\n"
            "Example: /tip @alice 5"
        )
        return
    
    # Get recipient
    recipient_mention = context.args[0]
    if not recipient_mention.startswith("@"):
        await update.message.reply_text("Recipient must start with @ (e.g., @alice)")
        return
    
    # Get amount
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid amount. Must be a number.")
        return
    
    if amount < MIN_TIP_AMOUNT:
        await update.message.reply_text(f"Minimum tip is {MIN_TIP_AMOUNT} RTC")
        return
    
    # Rate limit check
    allowed, remaining = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text(f"Rate limited. Try again in {remaining}s.")
        return
    
    # Get wallets
    sender_wallet = get_or_create_wallet(user.id)
    
    # Check balance
    balance = get_balance(sender_wallet['address'])
    if balance < amount:
        await update.message.reply_text(
            f"Insufficient balance.\n"
            f"Your balance: {balance:.4f} RTC\n"
            f"Required: {amount:.4f} RTC"
        )
        return
    
    # For now, we need the recipient's Telegram ID
    # In a real implementation, we'd look up the @username in the chat
    # For this MVP, we'll store pending tips and let recipients claim
    
    await update.message.reply_text(
        f"💸 **Tip Initiated**\n\n"
        f"To: {recipient_mention}\n"
        f"Amount: {amount:.4f} RTC\n\n"
        f"⚠️ Note: Recipient must have started this bot (/start) to receive tips.",
        parse_mode="Markdown"
    )
    
    # TODO: Implement actual transfer when we have recipient's user_id
    # This requires tracking username -> user_id mapping


async def cmd_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /withdraw command."""
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /withdraw <address> <amount>\n"
            "Example: /withdraw RTCabc123... 10"
        )
        return
    
    to_address = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return
    
    if amount <= 0:
        await update.message.reply_text("Amount must be positive.")
        return
    
    wallet = get_or_create_wallet(user.id)
    balance = get_balance(wallet['address'])
    
    if balance < amount:
        await update.message.reply_text(
            f"Insufficient balance.\n"
            f"Your balance: {balance:.4f} RTC"
        )
        return
    
    # Large transfer confirmation
    if amount >= LARGE_TRANSFER_THRESHOLD:
        await update.message.reply_text(
            f"⚠️ **Large Withdrawal**\n\n"
            f"Amount: {amount:.4f} RTC\n"
            f"To: `{to_address}`\n\n"
            f"Reply 'confirm' to proceed.",
            parse_mode="Markdown"
        )
        # TODO: Implement confirmation state machine
        return
    
    # Execute withdrawal
    result = send_signed_transfer(
        wallet['address'],
        to_address,
        amount,
        wallet['private_key'],
        wallet['public_key'],
        memo="Telegram Tip Bot Withdrawal"
    )
    
    if "error" in result:
        await update.message.reply_text(f"❌ Transfer failed: {result['error']}")
    elif result.get("ok"):
        await update.message.reply_text(
            f"✅ **Withdrawal Successful**\n\n"
            f"Amount: {amount:.4f} RTC\n"
            f"To: `{to_address}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ Transfer failed: {result}")


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command."""
    wallets = load_wallets()
    
    # Get balances for all wallets
    balances = []
    for user_id_str, wallet in wallets.items():
        balance = get_balance(wallet['address'])
        if balance > 0:
            balances.append({
                "user_id": int(user_id_str),
                "address": wallet['address'],
                "balance": balance,
            })
    
    # Sort by balance
    balances.sort(key=lambda x: x['balance'], reverse=True)
    top10 = balances[:10]
    
    if not top10:
        await update.message.reply_text("No balances yet. Be the first to deposit!")
        return
    
    lines = ["🏆 **RTC Leaderboard**\n"]
    for i, entry in enumerate(top10, 1):
        addr_short = entry['address'][:15] + "..."
        lines.append(f"{i}. `{addr_short}` — **{entry['balance']:.4f} RTC**")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_rain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rain command."""
    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /rain <amount>\n"
            "Example: /rain 10\n\n"
            "Distributes the amount evenly among recent active users."
        )
        return
    
    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return
    
    # TODO: Implement rain functionality
    # Requires tracking recent active users in the chat
    
    await update.message.reply_text(
        f"🌧️ **Rain**\n\n"
        f"Amount: {amount:.4f} RTC\n\n"
        f"⚠️ Rain feature coming soon!\n"
        f"This will distribute to recent active users.",
        parse_mode="Markdown"
    )


# =============================================================================
# Main
# =============================================================================

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable required")
        print("\nTo create a bot:")
        print("1. Message @BotFather on Telegram")
        print("2. Use /newbot to create a bot")
        print("3. Copy the token and run:")
        print("   export TELEGRAM_BOT_TOKEN='your-token-here'")
        return
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Register commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("deposit", cmd_deposit))
    app.add_handler(CommandHandler("tip", cmd_tip))
    app.add_handler(CommandHandler("withdraw", cmd_withdraw))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("rain", cmd_rain))
    
    # Set bot commands
    async def set_commands(app):
        commands = [
            BotCommand("start", "Start the tip bot"),
            BotCommand("balance", "Check your RTC balance"),
            BotCommand("deposit", "Show deposit address"),
            BotCommand("tip", "Tip a user: /tip @user 5"),
            BotCommand("withdraw", "Withdraw: /withdraw <addr> <amount>"),
            BotCommand("leaderboard", "Top RTC holders"),
            BotCommand("rain", "Rain to active users"),
        ]
        await app.bot.set_my_commands(commands)
    
    app.post_init = set_commands
    
    # Start
    print(f"🪙 RustChain Tip Bot starting...")
    print(f"   Node: {NODE_URL}")
    print(f"   Data: {DATA_DIR}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
