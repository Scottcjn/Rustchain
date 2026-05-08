#!/usr/bin/env python3
"""
RustChain Telegram Query Bot
Issue #1597

A minimal, safe Telegram bot for querying RustChain API endpoints.
Supports health, epoch, and balance queries via environment-configured API.

Commands:
- /start - Welcome message and help
- /help - Show available commands
- /health - Check node health status
- /epoch - Get current epoch information
- /balance <wallet> - Check wallet balance
- /stats - Get network statistics
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

import requests
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

# RustChain API configuration
RUSTCHAIN_API_URL = os.getenv("RUSTCHAIN_API_URL", "https://50.28.86.131")
RUSTCHAIN_VERIFY_SSL = os.getenv("RUSTCHAIN_VERIFY_SSL", "false").lower() == "true"

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Rate limiting (requests per minute per user)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter per user."""

    def __init__(self, max_requests: int = RATE_LIMIT_PER_MINUTE):
        self.max_requests = max_requests
        self.user_requests: Dict[int, list] = {}

    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make a request."""
        import time
        current_time = time.time()
        minute_ago = current_time - 60

        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        # Clean old requests
        self.user_requests[user_id] = [
            t for t in self.user_requests[user_id] if t > minute_ago
        ]

        # Check rate limit
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False

        # Record new request
        self.user_requests[user_id].append(current_time)
        return True


rate_limiter = RateLimiter()

# =============================================================================
# RustChain API Client
# =============================================================================

class RustChainClient:
    """Client for RustChain API endpoints."""

    def __init__(self, base_url: str = RUSTCHAIN_API_URL, verify_ssl: bool = RUSTCHAIN_VERIFY_SSL):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Timeout requesting {url}")
            return {"error": "Request timeout"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            return {"error": "Connection failed"}; import logging; logging.error(f"Connection failed: {e}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from {url}: {e}")
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Unexpected error requesting {url}: {e}")
            return {"error": "Internal server error"}; import logging; logging.error(str(e))

    def health(self) -> Dict[str, Any]:
        """Get node health status."""
        return self._get("/health")

    def epoch(self) -> Dict[str, Any]:
        """Get current epoch information."""
        return self._get("/epoch")

    def balance(self, miner_id: str) -> Dict[str, Any]:
        """Get wallet balance for a miner ID."""
        return self._get("/wallet/balance", params={"miner_id": miner_id})

    def miners(self) -> Dict[str, Any]:
        """Get active miners list."""
        return self._get("/api/miners")


# Global API client instance
api_client = RustChainClient()

# =============================================================================
# Bot Commands
# =============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")

    welcome_text = f"""
🛡️ **Welcome to RustChain Query Bot!**

I can help you query the RustChain network.

**Available Commands:**
/health - Check node health status
/epoch - Get current epoch info
/balance <wallet> - Check wallet balance
/stats - Get network statistics
/help - Show this help message

**API Endpoint:** `{RUSTCHAIN_API_URL}`

Start mining at: rustchain.io
"""
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - show available commands."""
    help_text = """
🛡️ **RustChain Query Bot - Help**

**Commands:**

/health
  Check node health status and version

/epoch
  Get current epoch, slot, and height info

/balance <wallet>
  Check RTC balance for a wallet/miner ID
  Example: /balance Ivan-houzhiwen

/stats
  Get network statistics (miner count)

/help
  Show this help message

**Notes:**
- All queries are read-only and safe
- Rate limit: {rate_limit} requests/minute
- API: `{api_url}`
""".format(
        rate_limit=RATE_LIMIT_PER_MINUTE,
        api_url=RUSTCHAIN_API_URL
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command - check node health."""
    user = update.effective_user

    # Rate limiting
    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested health check")

    await update.message.reply_text("🔍 Checking node health...")

    result = api_client.health()

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    # Format health response
    status = result.get("ok", False)
    version = result.get("version", "N/A")
    uptime = result.get("uptime_s", 0)

    # Format uptime
    if uptime > 0:
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        uptime_str = f"{days}d {hours}h {minutes}m"
    else:
        uptime_str = "N/A"

    status_icon = "✅" if status else "❌"
    health_text = f"""
{status_icon} **Node Health**

Status: *{'Online' if status else 'Offline'}*
Version: `{version}`
Uptime: `{uptime_str}`

API: `{RUSTCHAIN_API_URL}`
"""
    await update.message.reply_text(health_text, parse_mode="Markdown")


async def cmd_epoch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /epoch command - get epoch info."""
    user = update.effective_user

    # Rate limiting
    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested epoch info")

    await update.message.reply_text("📅 Fetching epoch information...")

    result = api_client.epoch()

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    epoch = result.get("epoch", "N/A")
    slot = result.get("slot", "N/A")
    height = result.get("height", "N/A")

    epoch_text = f"""
📅 **Current Epoch**

Epoch: *{epoch}*
Slot: `{slot}`
Height: `{height}`

Network: RustChain Mainnet
"""
    await update.message.reply_text(epoch_text, parse_mode="Markdown")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command - check wallet balance."""
    user = update.effective_user

    # Rate limiting
    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for wallet argument
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /balance <wallet_id>\n\n"
            "Example: /balance Ivan-houzhiwen"
        )
        return

    wallet_id = context.args[0]
    logger.info(f"User {user.id} requested balance for {wallet_id}")

    await update.message.reply_text(f"💰 Checking balance for `{wallet_id}`...")

    result = api_client.balance(wallet_id)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    amount_rtc = result.get("amount_rtc", 0)
    amount_i64 = result.get("amount_i64", 0)
    miner_id = result.get("miner_id", wallet_id)

    balance_text = f"""
💰 **Wallet Balance**

Wallet: `{miner_id}`
Balance: *{amount_rtc} RTC*
(Raw: {amount_i64} units)
"""
    await update.message.reply_text(balance_text, parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - get network statistics."""
    user = update.effective_user

    # Rate limiting
    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested network stats")

    await update.message.reply_text("📊 Fetching network statistics...")

    # Get miners list
    miners_result = api_client.miners()
    miner_count = "N/A"

    if "error" not in miners_result and isinstance(miners_result, list):
        miner_count = len(miners_result)

    # Get epoch info for additional stats
    epoch_result = api_client.epoch()
    current_epoch = epoch_result.get("epoch", "N/A")
    current_height = epoch_result.get("height", "N/A")

    stats_text = f"""
📊 **Network Statistics**

Active Miners: *{miner_count}*
Current Epoch: `{current_epoch}`
Block Height: `{current_height}`

API: `{RUSTCHAIN_API_URL}`
"""
    await update.message.reply_text(stats_text, parse_mode="Markdown")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request."
        )


# =============================================================================
# Bot Initialization
# =============================================================================

def set_bot_commands(application: Application):
    """Set up bot command list for Telegram menu."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show available commands"),
        BotCommand("health", "Check node health"),
        BotCommand("epoch", "Get current epoch info"),
        BotCommand("balance", "Check wallet balance"),
        BotCommand("stats", "Get network statistics"),
    ]
    return commands


async def post_init(application: Application):
    """Post-initialization setup."""
    commands = set_bot_commands(application)
    await application.bot.set_my_commands(commands)
    logger.info(f"Bot commands set: {[c.name for c in commands]}")


def validate_config() -> bool:
    """Validate required configuration."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")
        print("\n❌ Error: TELEGRAM_BOT_TOKEN environment variable is required")
        print("\nTo get a bot token:")
        print("1. Open Telegram and message @BotFather")
        print("2. Send /newbot to create a new bot")
        print("3. Follow the instructions to name your bot")
        print("4. Copy the API token")
        print("5. Set it: export TELEGRAM_BOT_TOKEN='your-token-here'")
        print("\nOr create a .env file with:")
        print("  TELEGRAM_BOT_TOKEN=your-token-here\n")
        return False

    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token")
        print("\n❌ Error: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token")
        return False

    logger.info(f"Configuration validated. API URL: {RUSTCHAIN_API_URL}")
    return True


def main():
    """Main entry point - start the bot."""
    logger.info("Starting RustChain Query Bot...")
    logger.info(f"Python version: {sys.version}")

    # Validate configuration
    if not validate_config():
        sys.exit(1)

    # Build application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("health", cmd_health))
    application.add_handler(CommandHandler("epoch", cmd_epoch))
    application.add_handler(CommandHandler("balance", cmd_balance))
    application.add_handler(CommandHandler("stats", cmd_stats))

    # Register error handler
    application.add_error_handler(error_handler)

    # Set post-init callback
    application.post_init = post_init

    # Start the bot
    print("\n🛡️ RustChain Query Bot starting...")
    print(f"   API: {RUSTCHAIN_API_URL}")
    print(f"   Verify SSL: {RUSTCHAIN_VERIFY_SSL}")
    print(f"   Rate limit: {RATE_LIMIT_PER_MINUTE} req/min")
    print("\nPress Ctrl+C to stop\n")

    # Run polling
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
