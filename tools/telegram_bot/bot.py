"""
RustChain Telegram Community Bot
Provides real-time information about RustChain network
"""

import os
import logging
from datetime import datetime
from typing import Optional

import aiohttp
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# RustChain API endpoints
RUSTCHAIN_API = "http://50.28.86.131/api"
RAYDIUM_API = "https://api.raydium.io/v2/main/price"

# Store for price alerts
user_alerts = {}


async def fetch_json(session: aiohttp.ClientSession, url: str) -> Optional[dict]:
    """Fetch JSON data from URL"""
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                return await response.json()
            logger.warning(f"HTTP {response.status} from {url}")
            return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when /start is issued"""
    welcome_text = """
🦀 **Welcome to RustChain Bot!**

I provide real-time information about the RustChain network:

📊 **Commands:**
/price — Current wRTC price from Raydium
/miners — Active miner count
/epoch — Current epoch info
/balance <wallet> — Check RTC balance
/health — Node health status
/alerts — Manage price/mining alerts
/inline — Try inline queries

💡 **Example:**
`/balance 0xD1Bde85fB255d3863a682414393446B143a26152`

Need help? Use /help
    """
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message"""
    help_text = """
🦀 **RustChain Bot Help**

**Available Commands:**

📈 `/price` — Get current wRTC price
📊 `/miners` — See active miner count
⏱️ `/epoch` — View epoch information
💰 `/balance <wallet>` — Check wallet balance
❤️ `/health` — Node health status
🔔 `/alerts` — Set up price/mining alerts
🔍 `@RustChainBot <query>` — Inline search

**Examples:**
```
/balance 0xD1Bde85fB255d3863a682414393446B143a26152
/price
/miners
```

📚 **RustChain Resources:**
• Explorer: https://50.28.86.131/explorer
• Docs: https://github.com/Scottcjn/Rustchain

💬 **Support:** Join @RustChainCommunity
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current wRTC price from Raydium"""
    async with aiohttp.ClientSession() as session:
        # Try to get price from Raydium
        raydium_data = await fetch_json(session, RAYDIUM_API)
        
        if raydium_data:
            # Look for wRTC or RTC price
            wrtc_price = raydium_data.get("wRTC") or raydium_data.get("RTC")
            if wrtc_price:
                price_text = f"""
💰 **wRTC Price**

💵 **Current:** ${wrtc_price:.4f} USD
📊 **Source:** Raydium
⏰ **Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

🔔 Use `/alerts` to set price notifications
                """
                await update.message.reply_text(price_text, parse_mode="Markdown")
                return
        
        # Fallback to RustChain API
        network_data = await fetch_json(session, f"{RUSTCHAIN_API}/network")
        if network_data and "price" in network_data:
            price = network_data["price"]
            price_text = f"""
💰 **wRTC Price**

💵 **Current:** ${price:.4f} USD
📊 **Source:** RustChain API
⏰ **Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

🔔 Use `/alerts` to set price notifications
            """
            await update.message.reply_text(price_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "⚠️ Could not fetch price data. Please try again later."
            )


async def miners_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get active miner count"""
    async with aiohttp.ClientSession() as session:
        miners_data = await fetch_json(session, f"{RUSTCHAIN_API}/miners")
        
        if miners_data:
            active_miners = miners_data.get("active", 0)
            total_miners = miners_data.get("total", 0)
            
            miners_text = f"""
⛏️ **Miner Statistics**

👷 **Active Miners:** {active_miners:,}
📊 **Total Miners:** {total_miners:,}
⚡ **Network Power:** {miners_data.get('hashrate', 'N/A')} H/s

🆕 New miners in last hour: {miners_data.get('new_1h', 0)}
📈 Growth rate: {miners_data.get('growth', '0')}%

⏰ **Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """
            await update.message.reply_text(miners_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "⚠️ Could not fetch miner data. Please try again later."
            )


async def epoch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current epoch information"""
    async with aiohttp.ClientSession() as session:
        epoch_data = await fetch_json(session, f"{RUSTCHAIN_API}/epoch")
        
        if epoch_data:
            current_epoch = epoch_data.get("current", 0)
            blocks_remaining = epoch_data.get("blocks_remaining", 0)
            time_remaining = epoch_data.get("time_remaining", "N/A")
            
            epoch_text = f"""
⏱️ **Epoch Information**

🔢 **Current Epoch:** {current_epoch}
⏳ **Blocks Remaining:** {blocks_remaining:,}
🕐 **Time Remaining:** {time_remaining}

💰 **Epoch Reward:** {epoch_data.get('reward', 'N/A')} RTC
🎯 **Difficulty:** {epoch_data.get('difficulty', 'N/A')}

📝 Epoch settles when blocks reach 0
            """
            await update.message.reply_text(epoch_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "⚠️ Could not fetch epoch data. Please try again later."
            )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check RTC balance for a wallet"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide a wallet address.\n\n"
            "Example: `/balance 0xD1Bde85fB255d3863a682414393446B143a26152`",
            parse_mode="Markdown"
        )
        return
    
    wallet = context.args[0]
    
    # Validate wallet address
    if not wallet.startswith("0x") or len(wallet) != 42:
        await update.message.reply_text(
            "⚠️ Invalid wallet address format.\n\n"
            "Address should be 42 characters starting with 0x"
        )
        return
    
    async with aiohttp.ClientSession() as session:
        balance_data = await fetch_json(session, f"{RUSTCHAIN_API}/balance/{wallet}")
        
        if balance_data:
            balance = balance_data.get("balance", 0)
            staked = balance_data.get("staked", 0)
            
            balance_text = f"""
💰 **Wallet Balance**

📋 **Address:** `{wallet[:10]}...{wallet[-8:]}`

💵 **Available:** {balance:,.4f} RTC
🔒 **Staked:** {staked:,.4f} RTC
💎 **Total:** {balance + staked:,.4f} RTC

📊 USD Value: ~${(balance + staked) * 0.01:.2f}

⏰ **Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
            """
            await update.message.reply_text(balance_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"⚠️ Could not fetch balance for `{wallet[:10]}...`.\n"
                "Please check the address and try again.",
                parse_mode="Markdown"
            )


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get node health status"""
    async with aiohttp.ClientSession() as session:
        health_data = await fetch_json(session, f"{RUSTCHAIN_API}/health")
        
        if health_data:
            status = health_data.get("status", "unknown")
            status_emoji = "🟢" if status == "healthy" else "🔴" if status == "unhealthy" else "🟡"
            
            health_text = f"""
❤️ **Node Health Status**

{status_emoji} **Status:** {status.upper()}

📊 **Block Height:** {health_data.get('block_height', 'N/A'):,}
🔗 **Peers Connected:** {health_data.get('peers', 'N/A')}
⏱️ **Latency:** {health_data.get('latency', 'N/A')} ms
📦 **Version:** {health_data.get('version', 'N/A')}

⏰ **Checked:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

{'✅ Network is operating normally' if status == 'healthy' else '⚠️ Network experiencing issues'}
            """
            await update.message.reply_text(health_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "🔴 **Node Health: UNREACHABLE**\n\n"
                "Could not connect to RustChain API.\n"
                "Network may be experiencing issues.",
                parse_mode="Markdown"
            )


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage alerts"""
    user_id = update.effective_user.id
    
    if user_id not in user_alerts:
        user_alerts[user_id] = {"price": None, "mining": False}
    
    alerts_text = """
🔔 **Alert Management**

Current Alerts:
"""
    
    if user_alerts[user_id].get("price"):
        alerts_text += f"📈 Price alert: {user_alerts[user_id]['price']}% change\n"
    else:
        alerts_text += "📈 Price alert: Not set\n"
    
    if user_alerts[user_id].get("mining"):
        alerts_text += "⛏️ Mining alerts: Enabled\n"
    else:
        alerts_text += "⛏️ Mining alerts: Disabled\n"
    
    alerts_text += """

**Commands:**
`/alert_price 5` — Alert on 5% price change
`/alert_mining on` — Enable mining alerts
`/alert_mining off` — Disable mining alerts

⚠️ Alerts are session-based (reset on restart)
    """
    await update.message.reply_text(alerts_text, parse_mode="Markdown")


async def alert_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set price alert threshold"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide a percentage.\n\n"
            "Example: `/alert_price 5` (alert on 5% change)"
        )
        return
    
    try:
        threshold = float(context.args[0])
        if threshold <= 0 or threshold > 100:
            raise ValueError("Threshold must be between 0 and 100")
        
        user_id = update.effective_user.id
        if user_id not in user_alerts:
            user_alerts[user_id] = {}
        
        user_alerts[user_id]["price"] = threshold
        
        await update.message.reply_text(
            f"✅ Price alert set!\n\n"
            f"You'll be notified when wRTC price changes by {threshold}% or more."
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid percentage. Please use a number between 0 and 100.\n\n"
            "Example: `/alert_price 5`"
        )


async def alert_mining_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle mining alerts"""
    if not context.args or context.args[0].lower() not in ["on", "off"]:
        await update.message.reply_text(
            "⚠️ Please specify 'on' or 'off'.\n\n"
            "Example: `/alert_mining on`"
        )
        return
    
    user_id = update.effective_user.id
    enable = context.args[0].lower() == "on"
    
    if user_id not in user_alerts:
        user_alerts[user_id] = {}
    
    user_alerts[user_id]["mining"] = enable
    
    status = "enabled" if enable else "disabled"
    await update.message.reply_text(
        f"✅ Mining alerts {status}!\n\n"
        f"You'll {'receive' if enable else 'no longer receive'} notifications about new miners and epoch settlements."
    )


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries"""
    query = update.inline_query.query.lower()
    
    results = []
    
    if "price" in query or not query:
        results.append(
            InlineQueryResultArticle(
                id="price",
                title="💰 wRTC Price",
                description="Get current wRTC price",
                input_message_content=InputTextMessageContent(
                    "/price"
                ),
            )
        )
    
    if "miner" in query or not query:
        results.append(
            InlineQueryResultArticle(
                id="miners",
                title="⛏️ Miner Stats",
                description="Get active miner count",
                input_message_content=InputTextMessageContent(
                    "/miners"
                ),
            )
        )
    
    if "epoch" in query or not query:
        results.append(
            InlineQueryResultArticle(
                id="epoch",
                title="⏱️ Epoch Info",
                description="Get current epoch information",
                input_message_content=InputTextMessageContent(
                    "/epoch"
                ),
            )
        )
    
    if "health" in query or not query:
        results.append(
            InlineQueryResultArticle(
                id="health",
                title="❤️ Node Health",
                description="Check network health status",
                input_message_content=InputTextMessageContent(
                    "/health"
                ),
            )
        )
    
    await update.inline_query.answer(results)


def main() -> None:
    """Start the bot"""
    # Get bot token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        print("Error: Please set TELEGRAM_BOT_TOKEN environment variable")
        return
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("miners", miners_command))
    application.add_handler(CommandHandler("epoch", epoch_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("alert_price", alert_price_command))
    application.add_handler(CommandHandler("alert_mining", alert_mining_command))
    
    # Add inline query handler
    application.add_handler(InlineQueryHandler(inline_query))
    
    # Run the bot
    logger.info("Starting RustChain Telegram Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
