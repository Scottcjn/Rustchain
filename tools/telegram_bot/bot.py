"""
RustChain Telegram Community Bot
Bounty: 50 RTC
Issue: #249
"""

import asyncio
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RustChain API Base URL
RUSTCHAIN_API = "https://50.28.86.131"

# Bot token - User needs to set this from @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🛡️ *RustChain Bot*

/price - wRTC price
/miners - Active miners
/epoch - Epoch info
/balance <addr> - Wallet balance
/health - Node health
/help - Commands"""
    await update.message.reply_text(welcome, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🛡️ *Commands*

/price - wRTC price
/miners - Miner count
/epoch - Epoch info
/balance <wallet> - Check balance
/health - Node status"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Price feature - coming soon!")


async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get(f"{RUSTCHAIN_API}/api/miners", verify=False, timeout=10)
        miners = r.json() if r.status_code == 200 else []
        count = len(miners) if isinstance(miners, list) else "N/A"
        await update.message.reply_text(f"⛏️ *Miners:* {count}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def epoch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get(f"{RUSTCHAIN_API}/epoch", verify=False, timeout=10)
        if r.status_code == 200:
            data = r.json()
            epoch = data.get('epoch', 'N/A')
            await update.message.reply_text(f"📅 *Epoch:* {epoch}", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Could not fetch epoch")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /balance <wallet_address>")
        return
    wallet = context.args[0]
    try:
        r = requests.get(f"{RUSTCHAIN_API}/wallet/balance", params={"miner_id": wallet}, verify=False, timeout=10)
        data = r.json() if r.status_code == 200 else {}
        balance = data.get('balance', 'N/A')
        await update.message.reply_text(f"💰 *Balance:* {balance} wRTC", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get(f"{RUSTCHAIN_API}/health", verify=False, timeout=10)
        if r.status_code == 200:
            await update.message.reply_text("❤️ *Node: Healthy*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Node: Unhealthy")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("miners", miners_command))
    app.add_handler(CommandHandler("epoch", epoch_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("health", health_command))
    print("🤖 RustChain Bot starting...")
    app.run_polling(ping_interval=30)


if __name__ == "__main__":
    main()
