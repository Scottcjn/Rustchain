#!/usr/bin/env python3
"""
RustChain Telegram Community Bot

A lightweight Telegram bot for RustChain community that provides:
- /price - Current wRTC price from Raydium
- /miners - Active miner count
- /epoch - Current epoch info
- /balance <wallet> - Check RTC balance
- /health - Node health status

Requirements:
    pip install python-telegram-bot requests

Usage:
    python telegram_bot.py --token YOUR_BOT_TOKEN --wallet YOUR_WALLET_ID

Or set environment variables:
    export TELEGRAM_BOT_TOKEN=your_token
    export RUSTCHAIN_WALLET=your_wallet
    python telegram_bot.py
"""

import os
import sys
import argparse
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration
NODE_URL = os.environ.get("NODE_URL", "https://50.28.86.131")
RAYDIUM_API = "https://api.raydium.io/v2/coin/mint"

# Timeout for API calls
REQUEST_TIMEOUT = 10


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Welcome to RustChain Bot!\n\n"
        "Available commands:\n"
        "• /price - Current wRTC price\n"
        "• /miners - Active miner count\n"
        "• /epoch - Current epoch info\n"
        "• /balance <wallet> - Check balance\n"
        "• /health - Node health\n"
        "• /help - Show this help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start_command(update, context)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command - get wRTC price from Raydium."""
    try:
        # Try Raydium API
        response = requests.get(
            "https://api.raydium.io/v2/spot/price",
            params={"mint": "12TAdKXxcGf6oCv4rqDz2NkgxjyHqN6HQKoxKZYGf5i4X"},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            price = data.get("data", {}).get("value", "N/A")
            await update.message.reply_text(
                f"💰 wRTC Price: ${price} USD\n"
                f"(from Raydium)"
            )
        else:
            # Fallback: show manual checking message
            await update.message.reply_text(
                "💰 wRTC: Check on Raydium DEX\n"
                "https://raydium.io/swap/"
            )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error fetching price: {str(e)[:100]}"
        )


async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /miners command - get active miner count."""
    try:
        response = requests.get(
            f"{NODE_URL}/api/miners",
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            miners = response.json()
            count = len(miners.get("miners", []))
            await update.message.reply_text(
                f"⛏️ Active Miners: {count}\n"
                f"Node: {NODE_URL}"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Error: HTTP {response.status_code}"
            )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error: {str(e)[:100]}"
        )


async def epoch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /epoch command - get current epoch info."""
    try:
        response = requests.get(
            f"{NODE_URL}/epoch",
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            epoch = data.get("epoch", "N/A")
            progress = data.get("progress", "N/A")
            await update.message.reply_text(
                f"📅 Current Epoch: {epoch}\n"
                f"Progress: {progress}%"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Error: HTTP {response.status_code}"
            )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error: {str(e)[:100]}"
        )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command - check wallet balance."""
    # Parse wallet from command args
    if not context.args:
        await update.message.reply_text(
            "Usage: /balance <wallet_address>\n"
            "Example: /balance my_wallet_name"
        )
        return
    
    wallet = context.args[0]
    
    try:
        response = requests.get(
            f"{NODE_URL}/wallet/balance",
            params={"miner_id": wallet},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            balance = data.get("balance", "N/A")
            await update.message.reply_text(
                f"💳 Wallet: {wallet}\n"
                f"Balance: {balance} RTC"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Error: HTTP {response.status_code}"
            )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error: {str(e)[:100]}"
        )


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command - check node health."""
    try:
        response = requests.get(
            f"{NODE_URL}/health",
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            await update.message.reply_text(
                f"❤️ Node Health: {status}\n"
                f"Node: {NODE_URL}"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Error: HTTP {response.status_code}"
            )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error: {str(e)[:100]}"
        )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown messages."""
    await update.message.reply_text(
        "Unknown command. Use /help for available commands."
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RustChain Telegram Bot")
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("TELEGRAM_BOT_TOKEN"),
        help="Telegram bot token"
    )
    parser.add_argument(
        "--wallet",
        type=str,
        default=os.environ.get("RUSTCHAIN_WALLET"),
        help="Default wallet for tips"
    )
    args = parser.parse_args()
    
    if not args.token:
        print("Error: Telegram bot token required!")
        print("Set TELEGRAM_BOT_TOKEN env var or use --token")
        sys.exit(1)
    
    # Build application
    application = Application.builder().token(args.token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("miners", miners_command))
    application.add_handler(CommandHandler("epoch", epoch_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # Start polling
    print("🤖 RustChain Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
