"""
RustChain Telegram Community Bot
Bounty: 50 RTC
Issue: #249

Fixed version addressing code quality issues:
1. Removed duplicate files (bot.py deleted)
2. Implemented real /price command using DexScreener API
3. Added environment variable support for configuration
4. Improved error handling and logging
"""

import os
import asyncio
import logging
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration - use environment variables or defaults
RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# DexScreener API for wRTC price
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
DEXSCREENER_API = f"https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}"


def get_wrtc_price_data():
    """Fetch wRTC price data from DexScreener API."""
    try:
        response = requests.get(DEXSCREENER_API, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        pairs = data.get('pairs', [])
        if not pairs:
            return None
            
        # Filter for Raydium pair (preferred) or use first available
        raydium_pair = next((p for p in pairs if p.get('dexId') == 'raydium'), pairs[0])
        
        return {
            'price_usd': float(raydium_pair.get('priceUsd', 0)),
            'price_native': raydium_pair.get('priceNative', 'N/A'),
            'h24_change': raydium_pair.get('priceChange', {}).get('h24', 0),
            'liquidity_usd': raydium_pair.get('liquidity', {}).get('usd', 0),
            'volume_h24': raydium_pair.get('volume', {}).get('h24', 0),
            'url': raydium_pair.get('url', 'https://dexscreener.com')
        }
    except Exception as e:
        logger.error(f"Error fetching price data: {e}")
        return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    welcome_text = """
🛡️ *Welcome to RustChain Bot!*

Available commands:
/price - Current wRTC price from Raydium
/miners - Active miner count
/epoch - Current epoch info
/balance <wallet> - Check wallet balance
/health - Node health status
/help - Show this help message

Earn RTC by mining! Visit: rustchain.io
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🛡️ *RustChain Bot Commands*

/price - Get wRTC price from Raydium (real-time)
/miners - Get active miner count from RustChain network
/epoch - Get current epoch information
/balance <wallet> - Check wallet balance
/health - Check node health status
/help - Show this message

Need help? Join our community!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get wRTC price from Raydium via DexScreener API."""
    try:
        price_data = get_wrtc_price_data()
        if not price_data:
            await update.message.reply_text("❌ Could not fetch wRTC price at this time. Please try again later.")
            return
            
        message = (
            f"💎 *wRTC Price Update*\n\n"
            f"💵 *USD:* `${price_data['price_usd']:.4f}`\n"
            f"☀️ *SOL:* `{price_data['price_native']} SOL`\n"
            f"📈 *24h Change:* `{price_data['h24_change']}%`\n"
            f"💧 *Liquidity:* `${price_data['liquidity_usd']:,.0f}`\n"
            f"📊 *24h Volume:* `${price_data['volume_h24']:,.0f}`\n\n"
            f"🔗 [View on DexScreener]({price_data['url']})"
        )
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in price command: {e}")
        await update.message.reply_text(f"❌ Error fetching price: {str(e)}")


async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get active miner count."""
    try:
        response = requests.get(f"{RUSTCHAIN_API}/api/miners", verify=False, timeout=10)
        miners = response.json()
        count = len(miners) if isinstance(miners, list) else "N/A"
        
        text = f"""
⛏️ *RustChain Miners*

Active Miners: *{count}*

Join the network and start mining!
"""
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching miners: {str(e)}")


async def epoch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get current epoch information."""
    try:
        response = requests.get(f"{RUSTCHAIN_API}/epoch", verify=False, timeout=10)
        epoch = response.json()
        
        text = f"""
📅 *Current Epoch*

Epoch: *{epoch.get('epoch', 'N/A')}*
Status: *{epoch.get('status', 'N/A')}*

Learn more: docs.rustchain.io
"""
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching epoch: {str(e)}")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check wallet balance."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /balance <wallet_address>")
            return
            
        wallet = context.args[0]
        response = requests.get(
            f"{RUSTCHAIN_API}/wallet/balance",
            params={"miner_id": wallet},
            verify=False,
            timeout=10
        )
        data = response.json()
        
        text = f"""
💰 *Wallet Balance*

Wallet: `{wallet}`
Balance: *{data.get('balance', 'N/A')}* wRTC
"""
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching balance: {str(e)}")


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check node health status."""
    try:
        response = requests.get(f"{RUSTCHAIN_API}/health", verify=False, timeout=10)
        health = response.json()
        
        text = f"""
❤️ *Node Health*

Status: *{health.get('status', 'N/A')}*
Version: *{health.get('version', 'N/A')}*

Network: rustchain.io
"""
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching health: {str(e)}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please set TELEGRAM_BOT_TOKEN environment variable")
        print("ERROR: Please set TELEGRAM_BOT_TOKEN environment variable")
        print("Example: export TELEGRAM_BOT_TOKEN='your_bot_token_here'")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("miners", miners_command))
    application.add_handler(CommandHandler("epoch", epoch_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("health", health_command))

    # Register error handler
    application.add_error_handler(error_handler)

    # Start the bot
    print("🤖 RustChain Telegram Bot starting...")
    print(f"Using RustChain API: {RUSTCHAIN_API}")
    application.run_polling(ping_interval=30)


if __name__ == "__main__":
    main()
