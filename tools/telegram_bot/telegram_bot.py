"""
RustChain Telegram Community Bot
Bounty: 50 RTC
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RustChain API Base URL
RUSTCHAIN_API = "https://50.28.86.131"

# Bot token - User needs to set this
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    welcome_text = """
🛡️ *Welcome to RustChain Bot!*

Available commands:
/price - Current wRTC price
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

/price - Get wRTC price from Raydium
/miners - Get active miner count
/epoch - Get current epoch information
/balance <wallet> - Check wallet balance
/health - Check node health status
/help - Show this message

Need help? Join our community!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get wRTC price from Raydium."""
    try:
        # Placeholder - would need actual Raydium API
        await update.message.reply_text("📊 Price feature coming soon!")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get active miner count."""
    try:
        import requests
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
        import requests
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
        import requests
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
        import requests
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
    application.run_polling(ping_interval=30)


if __name__ == "__main__":
    main()
