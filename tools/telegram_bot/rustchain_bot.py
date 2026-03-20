// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
import sqlite3
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler
from telegram.constants import ParseMode

# Configuration
API_BASE = "http://50.28.86.131"
DB_PATH = "rustchain_bot.db"

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class RustChainBot:
    def __init__(self, token: str):
        self.token = token
        self.app = None
        self.last_price = None
        self.last_miner_count = 0
        self.last_epoch = None
        self.price_alerts = {}
        self.mining_alerts = set()

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for bot data"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    user_id INTEGER PRIMARY KEY,
                    threshold_percent REAL DEFAULT 5.0,
                    enabled INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mining_alerts (
                    user_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    async def _fetch_api(self, endpoint: str) -> Optional[Dict]:
        """Fetch data from RustChain API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE}{endpoint}", timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"API returned status {response.status} for {endpoint}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            return None

    async def _get_price_data(self) -> Optional[Dict]:
        """Get wRTC price data"""
        # Try multiple endpoints for price
        endpoints = ["/api/price", "/price", "/api/stats"]

        for endpoint in endpoints:
            data = await self._fetch_api(endpoint)
            if data and ('price' in data or 'wrtc_price' in data):
                return data

        # If no price endpoint works, try Raydium directly
        try:
            async with aiohttp.ClientSession() as session:
                # This would be the actual Raydium API call
                raydium_url = "https://api.raydium.io/v2/sdk/price?tokens=YOUR_WRTC_TOKEN"
                async with session.get(raydium_url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            logger.error(f"Error fetching Raydium price: {e}")

        return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_msg = """
🦀 Welcome to RustChain Bot! 🦀

Available commands:
/price - Current wRTC price
/miners - Active miner count
/epoch - Current epoch information
/balance <wallet> - Check RTC balance
/health - Node health status
/alerts - Manage price and mining alerts

Use inline queries (@rustchain_bot search) for bonus rewards!
        """
        await update.message.reply_text(welcome_msg)

    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /price command"""
        await update.message.reply_text("🔍 Fetching wRTC price...")

        data = await self._get_price_data()
        if not data:
            await update.message.reply_text("❌ Unable to fetch price data")
            return

        price = data.get('price') or data.get('wrtc_price', 0)
        change_24h = data.get('change_24h', 0)
        volume = data.get('volume_24h', 0)

        price_msg = f"""
💰 <b>wRTC Price</b>
Price: ${price:.6f}
24h Change: {change_24h:+.2f}%
24h Volume: ${volume:,.2f}

📊 Last updated: {datetime.now().strftime('%H:%M UTC')}
        """

        await update.message.reply_text(price_msg, parse_mode=ParseMode.HTML)

        # Update last price for alerts
        if self.last_price and abs(price - self.last_price) / self.last_price * 100 > 5:
            await self._send_price_alerts(price, self.last_price)
        self.last_price = price

    async def miners_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /miners command"""
        await update.message.reply_text("⛏️ Checking active miners...")

        data = await self._fetch_api("/api/miners")
        if not data:
            await update.message.reply_text("❌ Unable to fetch miner data")
            return

        active_miners = len(data.get('miners', []))
        total_hashrate = sum(m.get('hashrate', 0) for m in data.get('miners', []))

        miners_msg = f"""
⛏️ <b>Mining Network</b>
Active Miners: {active_miners}
Total Hashrate: {total_hashrate:.2f} H/s
Network Difficulty: {data.get('difficulty', 'N/A')}

📈 Last updated: {datetime.now().strftime('%H:%M UTC')}
        """

        await update.message.reply_text(miners_msg, parse_mode=ParseMode.HTML)

        # Check for new miners
        if active_miners > self.last_miner_count:
            await self._send_mining_alerts(f"🎉 New miner joined! Total miners: {active_miners}")
        self.last_miner_count = active_miners

    async def epoch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /epoch command"""
        await update.message.reply_text("📅 Fetching epoch data...")

        data = await self._fetch_api("/epoch")
        if not data:
            await update.message.reply_text("❌ Unable to fetch epoch data")
            return

        current_epoch = data.get('current_epoch', 0)
        blocks_remaining = data.get('blocks_remaining', 0)
        est_time = data.get('estimated_time_remaining', 'N/A')

        epoch_msg = f"""
📅 <b>Epoch Information</b>
Current Epoch: {current_epoch}
Blocks Remaining: {blocks_remaining}
Est. Time Left: {est_time}
Block Height: {data.get('block_height', 'N/A')}

⏰ Last updated: {datetime.now().strftime('%H:%M UTC')}
        """

        await update.message.reply_text(epoch_msg, parse_mode=ParseMode.HTML)

        # Check for epoch settlement
        if self.last_epoch and current_epoch > self.last_epoch:
            await self._send_mining_alerts(f"🎊 Epoch {current_epoch} settled! New epoch started.")
        self.last_epoch = current_epoch

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        if not context.args:
            await update.message.reply_text("❌ Please provide a wallet address: /balance <wallet>")
            return

        wallet = context.args[0]
        await update.message.reply_text(f"🔍 Checking balance for {wallet[:12]}...")

        data = await self._fetch_api(f"/api/balance/{wallet}")
        if not data:
            await update.message.reply_text("❌ Unable to fetch balance data")
            return

        balance = data.get('balance', 0)
        staked = data.get('staked', 0)
        rewards = data.get('pending_rewards', 0)

        balance_msg = f"""
💎 <b>RTC Balance</b>
Wallet: <code>{wallet[:12]}...{wallet[-4:]}</code>
Available: {balance:.4f} RTC
Staked: {staked:.4f} RTC
Pending Rewards: {rewards:.4f} RTC

💰 Total Value: {balance + staked + rewards:.4f} RTC
        """

        await update.message.reply_text(balance_msg, parse_mode=ParseMode.HTML)

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /health command"""
        await update.message.reply_text("🏥 Checking node health...")

        data = await self._fetch_api("/api/health")
        if not data:
            await update.message.reply_text("❌ Node appears to be offline")
            return

        status = data.get('status', 'unknown')
        uptime = data.get('uptime', 0)
        peers = data.get('peers', 0)
        sync_status = data.get('sync_status', 'unknown')

        health_icon = "🟢" if status == "healthy" else "🟡" if status == "warning" else "🔴"

        health_msg = f"""
{health_icon} <b>Node Health</b>
Status: {status.upper()}
Uptime: {uptime // 3600}h {(uptime % 3600) // 60}m
Connected Peers: {peers}
Sync Status: {sync_status}

📡 API Response: {datetime.now().strftime('%H:%M:%S UTC')}
        """

        await update.message.reply_text(health_msg, parse_mode=ParseMode.HTML)

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /alerts command"""
        user_id = update.effective_user.id

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT threshold_percent, enabled FROM price_alerts WHERE user_id = ?", (user_id,))
            price_alert = cursor.fetchone()

            cursor.execute("SELECT enabled FROM mining_alerts WHERE user_id = ?", (user_id,))
            mining_alert = cursor.fetchone()

        price_status = "✅ Enabled" if price_alert and price_alert[1] else "❌ Disabled"
        mining_status = "✅ Enabled" if mining_alert and mining_alert[1] else "❌ Disabled"
        threshold = price_alert[0] if price_alert else 5.0

        alerts_msg = f"""
🔔 <b>Alert Settings</b>
Price Alerts: {price_status} ({threshold}% threshold)
Mining Alerts: {mining_status}

Commands:
/enable_price_alerts [threshold] - Enable price alerts
/disable_price_alerts - Disable price alerts
/enable_mining_alerts - Enable mining alerts
/disable_mining_alerts - Disable mining alerts
        """

        await update.message.reply_text(alerts_msg, parse_mode=ParseMode.HTML)

    async def enable_price_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable price alerts"""
        user_id = update.effective_user.id
        threshold = 5.0

        if context.args:
            try:
                threshold = float(context.args[0])
                if threshold <= 0 or threshold > 50:
                    await update.message.reply_text("❌ Threshold must be between 0.1% and 50%")
                    return
            except ValueError:
                await update.message.reply_text("❌ Invalid threshold value")
                return

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO price_alerts (user_id, threshold_percent, enabled)
                VALUES (?, ?, 1)
            """, (user_id, threshold))
            conn.commit()

        await update.message.reply_text(f"✅ Price alerts enabled with {threshold}% threshold")

    async def disable_price_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable price alerts"""
        user_id = update.effective_user.id

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE price_alerts SET enabled = 0 WHERE user_id = ?", (user_id,))
            conn.commit()

        await update.message.reply_text("❌ Price alerts disabled")

    async def enable_mining_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable mining alerts"""
        user_id = update.effective_user.id

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mining_alerts (user_id, enabled)
                VALUES (?, 1)
            """, (user_id,))
            conn.commit()

        await update.message.reply_text("✅ Mining alerts enabled")

    async def disable_mining_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable mining alerts"""
        user_id = update.effective_user.id

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE mining_alerts SET enabled = 0 WHERE user_id = ?", (user_id,))
            conn.commit()

        await update.message.reply_text("❌ Mining alerts disabled")

    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries"""
        query = update.inline_query.query.lower()
        results = []

        if "price" in query or query == "":
            price_data = await self._get_price_data()
            if price_data:
                price = price_data.get('price', 0)
                results.append(
                    InlineQueryResultArticle(
                        id="price",
                        title="💰 wRTC Price",
                        description=f"${price:.6f}",
                        input_message_content=InputTextMessageContent(
                            f"💰 wRTC Price: ${price:.6f}\n🎁 Bonus reward for using inline query!"
                        )
                    )
                )

        if "miners" in query or query == "":
            miner_data = await self._fetch_api("/api/miners")
            if miner_data:
                count = len(miner_data.get('miners', []))
                results.append(
                    InlineQueryResultArticle(
                        id="miners",
                        title="⛏️ Active Miners",
                        description=f"{count} miners online",
                        input_message_content=InputTextMessageContent(
                            f"⛏️ Active Miners: {count}\n🎁 Bonus reward for using inline query!"
                        )
                    )
                )

        if "health" in query:
            health_data = await self._fetch_api("/api/health")
            if health_data:
                status = health_data.get('status', 'unknown')
                icon = "🟢" if status == "healthy" else "🟡" if status == "warning" else "🔴"
                results.append(
                    InlineQueryResultArticle(
                        id="health",
                        title=f"{icon} Node Health",
                        description=f"Status: {status}",
                        input_message_content=InputTextMessageContent(
                            f"{icon} Node Status: {status.upper()}\n🎁 Bonus reward for using inline query!"
                        )
                    )
                )

        await update.inline_query.answer(results)

    async def _send_price_alerts(self, new_price: float, old_price: float):
        """Send price alerts to subscribed users"""
        change_percent = abs(new_price - old_price) / old_price * 100
        direction = "📈" if new_price > old_price else "📉"

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM price_alerts
                WHERE enabled = 1 AND threshold_percent <= ?
            """, (change_percent,))
            users = cursor.fetchall()

        alert_msg = f"""
{direction} <b>Price Alert!</b>
wRTC moved {change_percent:.2f}%
New Price: ${new_price:.6f}
Previous: ${old_price:.6f}
        """

        for user_id, in users:
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=alert_msg,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send price alert to {user_id}: {e}")

    async def _send_mining_alerts(self, message: str):
        """Send mining alerts to subscribed users"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM mining_alerts WHERE enabled = 1")
            users = cursor.fetchall()

        for user_id, in users:
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send mining alert to {user_id}: {e}")

    def run(self):
        """Start the bot"""
        self.app = Application.builder().token(self.token).build()

        # Add command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("miners", self.miners_command))
        self.app.add_handler(CommandHandler("epoch", self.epoch_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("health", self.health_command))
        self.app.add_handler(CommandHandler("alerts", self.alerts_command))
        self.app.add_handler(CommandHandler("enable_price_alerts", self.enable_price_alerts))
        self.app.add_handler(CommandHandler("disable_price_alerts", self.disable_price_alerts))
        self.app.add_handler(CommandHandler("enable_mining_alerts", self.enable_mining_alerts))
        self.app.add_handler(CommandHandler("disable_mining_alerts", self.disable_mining_alerts))

        # Add inline query handler
        self.app.add_handler(InlineQueryHandler(self.inline_query))

        logger.info("🦀 RustChain Telegram Bot starting...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import os

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Please set TELEGRAM_BOT_TOKEN environment variable")
        exit(1)

    bot = RustChainBot(token)
    bot.run()
