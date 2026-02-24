"""
RustChain Telegram Bot
Bounty: #249 - Telegram Community Bot
Reward: 50 RTC
"""

import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
RPC_URL = "https://50.28.86.131"

# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - welcome message"""
    await update.message.reply_text(
        "👋 Welcome to RustChain Bot!\n\n"
        "Available commands:\n"
        "/price - Current wRTC price\n"
        "/miners - Active miner count\n"
        "/epoch - Current epoch info\n"
        "/balance <wallet> - Check RTC balance\n"
        "/health - Node health status\n"
        "/help - Show this help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "📖 Available Commands:\n\n"
        "/price - Current wRTC price from Raydium\n"
        "/miners - Active miner count from /api/miners\n"
        "/epoch - Current epoch info from /epoch\n"
        "/balance <wallet> - Check RTC balance\n"
        "/health - Node health status\n"
        "/help - Show this help\n\n"
        "Bonus features:\n"
        "⛏️ Mining alerts\n"
        "💰 Price alerts"
    )

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get current wRTC price"""
    try:
        # Raydium API for wRTC/SOL pair
        response = requests.get(
            "https://api.raydium.io/v2/main/pool/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            price = data.get("price", "N/A")
            await update.message.reply_text(f"💰 wRTC Price: ${price}")
        else:
            await update.message.reply_text("❌ Could not fetch price")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get active miner count"""
    try:
        response = requests.get(f"{RPC_URL}/api/miners", timeout=10)
        if response.status_code == 200:
            data = response.json()
            count = data.get("active_miners", data.get("count", "N/A"))
            await update.message.reply_text(f"⛏️ Active Miners: {count}")
        else:
            await update.message.reply_text("❌ Could not fetch miner count")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def epoch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get current epoch info"""
    try:
        response = requests.get(f"{RPC_URL}/epoch", timeout=10)
        if response.status_code == 200:
            data = response.json()
            epoch = data.get("epoch", "N/A")
            progress = data.get("progress", "N/A")
            await update.message.reply_text(f"📊 Epoch: {epoch}\nProgress: {progress}%")
        else:
            await update.message.reply_text("❌ Could not fetch epoch info")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check RTC balance"""
    try:
        wallet = " ".join(context.args)
        if not wallet:
            await update.message.reply_text("Usage: /balance <wallet_address>")
            return
        
        response = requests.get(
            f"{RPC_URL}/wallet/balance?miner_id={wallet}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            balance = data.get("amount_rtc", "N/A")
            await update.message.reply_text(f"💰 Balance: {balance} RTC")
        else:
            await update.message.reply_text("❌ Could not fetch balance")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check node health status"""
    try:
        response = requests.get(f"{RPC_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            await update.message.reply_text(f"🏥 Node Status: {status.upper()}")
        else:
            await update.message.reply_text("❌ Node unhealthy")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    print(f"Error: {context.error}")

def main():
    """Run the bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("miners", miners_command))
    app.add_handler(CommandHandler("epoch", epoch_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("health", health_command))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    print("🤖 RustChain Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
