# SPDX-License-Identifier: MIT
import os
import json
import time
import sqlite3
import logging
import asyncio
import requests
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, InlineQueryHandler, ContextTypes
from flask import Flask

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
RUSTCHAIN_API_BASE = "http://50.28.86.131"
RAYDIUM_API = "https://api.raydium.io/v2/sdk/token/mint"
WRTC_MINT = "your_wrtc_mint_address_here"
DB_PATH = "rustchain_bot.db"

# Flask app for health checks
app = Flask(__name__)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class RustchainBot:
    def __init__(self):
        self.last_price = None
        self.last_miners_count = 0
        self.price_alerts = {}
        self.mining_alerts = {}
        self.init_database()

    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    chat_id INTEGER,
                    price_alerts BOOLEAN DEFAULT 0,
                    mining_alerts BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    async def register_user(self, user_id: int, username: str, chat_id: int):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users (user_id, username, chat_id)
                VALUES (?, ?, ?)
            ''', (user_id, username, chat_id))
            conn.commit()

    def fetch_api_data(self, endpoint: str) -> Optional[Dict]:
        try:
            response = requests.get(f"{RUSTCHAIN_API_BASE}{endpoint}", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"API request failed for {endpoint}: {e}")
        return None

    def get_wrtc_price(self) -> Optional[float]:
        try:
            # Placeholder for actual Raydium API call
            # In real implementation, would fetch from Raydium with proper mint address
            response = requests.get(f"{RAYDIUM_API}?mint={WRTC_MINT}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data.get('price', 0))
        except Exception as e:
            logger.error(f"Price fetch failed: {e}")

        # Fallback mock price for demo
        return 0.0245

    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.register_user(update.effective_user.id, update.effective_user.username, update.effective_chat.id)

        price = self.get_wrtc_price()
        if price:
            price_change = ""
            if self.last_price:
                change = ((price - self.last_price) / self.last_price) * 100
                price_change = f" ({change:+.2f}%)"

            message = f"💰 wRTC Price: ${price:.6f}{price_change}\n"
            message += f"🕒 Updated: {datetime.now().strftime('%H:%M:%S UTC')}"

            self.last_price = price
        else:
            message = "❌ Unable to fetch price data. Please try again later."

        await update.message.reply_text(message)

    async def miners_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.register_user(update.effective_user.id, update.effective_user.username, update.effective_chat.id)

        data = self.fetch_api_data("/api/miners")
        if data:
            miners_count = len(data.get('miners', []))
            total_hashrate = sum(miner.get('hashrate', 0) for miner in data.get('miners', []))

            message = f"⛏️ Active Miners: {miners_count}\n"
            message += f"🔥 Total Hashrate: {total_hashrate:.2f} H/s\n"

            if miners_count > 0:
                avg_hashrate = total_hashrate / miners_count
                message += f"📊 Average Hashrate: {avg_hashrate:.2f} H/s"
        else:
            message = "❌ Unable to fetch miners data. Node may be offline."

        await update.message.reply_text(message)

    async def epoch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.register_user(update.effective_user.id, update.effective_user.username, update.effective_chat.id)

        data = self.fetch_api_data("/epoch")
        if data:
            current_epoch = data.get('current_epoch', 0)
            blocks_in_epoch = data.get('blocks_in_epoch', 0)
            time_remaining = data.get('time_remaining', 0)

            message = f"🌐 Current Epoch: {current_epoch}\n"
            message += f"🧱 Blocks: {blocks_in_epoch}\n"

            if time_remaining > 0:
                hours = time_remaining // 3600
                minutes = (time_remaining % 3600) // 60
                message += f"⏰ Time Remaining: {hours}h {minutes}m"
        else:
            message = "❌ Unable to fetch epoch data. Node may be offline."

        await update.message.reply_text(message)

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.register_user(update.effective_user.id, update.effective_user.username, update.effective_chat.id)

        if not context.args:
            await update.message.reply_text("❌ Please provide a wallet address: /balance <wallet_address>")
            return

        wallet_address = context.args[0]
        data = self.fetch_api_data(f"/api/balance/{wallet_address}")

        if data:
            balance = data.get('balance', 0)
            pending = data.get('pending', 0)

            message = f"💳 Wallet: {wallet_address[:8]}...{wallet_address[-8:]}\n"
            message += f"💰 Balance: {balance:.6f} RTC\n"

            if pending > 0:
                message += f"⏳ Pending: {pending:.6f} RTC"
        else:
            message = f"❌ Unable to fetch balance for wallet {wallet_address[:8]}..."

        await update.message.reply_text(message)

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.register_user(update.effective_user.id, update.effective_user.username, update.effective_chat.id)

        health_data = self.fetch_api_data("/api/health")
        if health_data:
            status = health_data.get('status', 'unknown')
            uptime = health_data.get('uptime', 0)
            sync_status = health_data.get('sync_status', 'unknown')

            status_emoji = "🟢" if status == "healthy" else "🔴"

            message = f"{status_emoji} Node Status: {status.title()}\n"
            message += f"⏱️ Uptime: {uptime//3600}h {(uptime%3600)//60}m\n"
            message += f"🔄 Sync Status: {sync_status}"
        else:
            message = "🔴 Node appears to be offline or unreachable"

        await update.message.reply_text(message)

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.register_user(update.effective_user.id, update.effective_user.username, update.effective_chat.id)

        if not context.args:
            message = "🔔 Alert Settings:\n"
            message += "/alerts price on/off - Price movement alerts\n"
            message += "/alerts mining on/off - Mining activity alerts"
            await update.message.reply_text(message)
            return

        alert_type = context.args[0].lower()
        setting = context.args[1].lower() if len(context.args) > 1 else None

        if alert_type not in ['price', 'mining'] or setting not in ['on', 'off']:
            await update.message.reply_text("❌ Usage: /alerts <price|mining> <on|off>")
            return

        user_id = update.effective_user.id
        enabled = setting == 'on'

        with sqlite3.connect(DB_PATH) as conn:
            if alert_type == 'price':
                conn.execute('UPDATE users SET price_alerts = ? WHERE user_id = ?', (enabled, user_id))
                self.price_alerts[user_id] = enabled
            else:
                conn.execute('UPDATE users SET mining_alerts = ? WHERE user_id = ?', (enabled, user_id))
                self.mining_alerts[user_id] = enabled
            conn.commit()

        emoji = "🔔" if enabled else "🔕"
        await update.message.reply_text(f"{emoji} {alert_type.title()} alerts {setting.upper()}")

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.inline_query.query.lower()
        results = []

        if 'price' in query:
            price = self.get_wrtc_price()
            if price:
                results.append(
                    InlineQueryResultArticle(
                        id="price",
                        title="wRTC Price",
                        description=f"${price:.6f}",
                        input_message_content=InputTextMessageContent(
                            f"💰 wRTC Price: ${price:.6f}"
                        )
                    )
                )

        if 'miners' in query:
            data = self.fetch_api_data("/api/miners")
            if data:
                miners_count = len(data.get('miners', []))
                results.append(
                    InlineQueryResultArticle(
                        id="miners",
                        title="Active Miners",
                        description=f"{miners_count} miners online",
                        input_message_content=InputTextMessageContent(
                            f"⛏️ Active Miners: {miners_count}"
                        )
                    )
                )

        await update.inline_query.answer(results)

    async def check_price_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        if not self.price_alerts:
            return

        current_price = self.get_wrtc_price()
        if not current_price or not self.last_price:
            self.last_price = current_price
            return

        price_change = abs((current_price - self.last_price) / self.last_price) * 100

        if price_change >= 5.0:
            direction = "📈" if current_price > self.last_price else "📉"
            message = f"{direction} wRTC Price Alert!\n"
            message += f"Price moved {price_change:.1f}% to ${current_price:.6f}"

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('SELECT chat_id FROM users WHERE price_alerts = 1')
                for (chat_id,) in cursor.fetchall():
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=message)
                    except Exception as e:
                        logger.error(f"Failed to send price alert to {chat_id}: {e}")

        self.last_price = current_price

    async def check_mining_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        if not self.mining_alerts:
            return

        data = self.fetch_api_data("/api/miners")
        if not data:
            return

        current_miners = len(data.get('miners', []))

        if current_miners != self.last_miners_count:
            if current_miners > self.last_miners_count:
                message = f"⛏️ New miner joined! Total miners: {current_miners}"
            else:
                message = f"⛏️ Miner left. Total miners: {current_miners}"

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('SELECT chat_id FROM users WHERE mining_alerts = 1')
                for (chat_id,) in cursor.fetchall():
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=message)
                    except Exception as e:
                        logger.error(f"Failed to send mining alert to {chat_id}: {e}")

        self.last_miners_count = current_miners

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    bot = RustchainBot()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("price", bot.price_command))
    application.add_handler(CommandHandler("miners", bot.miners_command))
    application.add_handler(CommandHandler("epoch", bot.epoch_command))
    application.add_handler(CommandHandler("balance", bot.balance_command))
    application.add_handler(CommandHandler("health", bot.health_command))
    application.add_handler(CommandHandler("alerts", bot.alerts_command))

    # Inline query handler
    application.add_handler(InlineQueryHandler(bot.inline_query))

    # Periodic tasks
    job_queue = application.job_queue
    job_queue.run_repeating(bot.check_price_alerts, interval=300, first=10)
    job_queue.run_repeating(bot.check_mining_alerts, interval=180, first=20)

    logger.info("RustChain Telegram Bot starting...")
    application.run_polling()

@app.route('/health')
def health_check():
    return {'status': 'healthy', 'service': 'rustchain-telegram-bot'}

if __name__ == '__main__':
    main()
