#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# RustChain Telegram Community Bot
# Bounty: 50 RTC (https://github.com/Scottcjn/rustchain-bounties/issues/249)
# Contributions: Check balances, miners, epochs, and node health via Telegram.

import os, sys, json, time, asyncio, logging, urllib.request, urllib.error, ssl

try:
    from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
    from telegram.ext import (
        Application, CommandHandler, ContextTypes,
        InlineQueryHandler, CallbackContext
    )
except ImportError:
    print("Missing python-telegram-bot. Install: pip install python-telegram-bot")
    sys.exit(1)

RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
BOT_TOKEN = os.getenv("BOT_TOKEN")
REQUEST_TIMEOUT = 15

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def api_get(path: str) -> dict | None:
    url = f"{RUSTCHAIN_API.rstrip('/')}/{path.lstrip('/')}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP {e.code} on {url}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None


def fmt_num(n: float | int) -> str:
    if isinstance(n, float):
        return f"{n:,.4f}"
    return f"{n:,}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "RustChain Community Bot\n\n"
        "Available commands:\n"
        "- /price - Current wRTC price\n"
        "- /miners - Active miner count\n"
        "- /epoch - Current epoch info\n"
        "- /balance <wallet> - Check RTC balance\n"
        "- /health - Node health status\n\n"
        "Built for the RustChain ecosystem.",
        parse_mode="Markdown",
    )


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    data = api_get("api/price")
    if not data:
        await update.message.reply_text("Could not fetch price data. Node may be unreachable.")
        return
    price = data.get("price", "N/A")
    change_24h = data.get("change_24h", data.get("change24h"))
    volume_24h = data.get("volume_24h", data.get("volume24h"))

    msg = f"wRTC Price\n\nPrice: ${price}\n"
    if change_24h is not None:
        emoji = "" if float(change_24h) >= 0 else ""
        msg += f"24h Change: {emoji} {change_24h}%\n"
    if volume_24h is not None:
        msg += f"24h Volume: ${fmt_num(float(volume_24h))}\n"
    msg += "\n_Data from Raydium via RustChain API_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_miners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    data = api_get("api/miners")
    if not data:
        await update.message.reply_text("Could not fetch miner data.")
        return

    pagination = data.get("pagination", {})
    total = pagination.get("total", None)
    miners_list = data.get("miners", [])

    if total is None:
        total = len(miners_list) or "N/A"

    top_miners = miners_list[:5]
    extra = max(0, total - len(top_miners)) if isinstance(total, int) else 0

    msg = f"*RustChain Miners*\n\n*Active Miners:* `{total}`\n"

    if top_miners:
        msg += "\n*Top Miners:*\n"
        for i, m in enumerate(top_miners, 1):
            name = m.get("miner", m.get("name", m.get("wallet", f"Miner {i}")))
            arch = m.get("device_arch", m.get("arch", "?"))
            mult = m.get("antiquity_multiplier", m.get("multiplier", "?"))
            msg += f"  {i}. `{name}` — {arch} ({mult}x)\n"

    if extra > 0:
        msg += f"\n_... and {extra} more_"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_epoch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    data = api_get("epoch")
    if not data:
        await update.message.reply_text("Could not fetch epoch data.")
        return
    epoch = data.get("epoch", data.get("current_epoch", "N/A"))
    progress = data.get("progress", data.get("epoch_progress"))
    blocks = data.get("blocks", data.get("total_blocks"))
    difficulty = data.get("difficulty")

    msg = f"RustChain Epoch\n\nEpoch: {epoch}\n"
    if progress is not None:
        msg += f"Progress: {progress}%\n"
    if blocks is not None:
        msg += f"Blocks: {blocks}\n"
    if difficulty is not None:
        msg += f"Difficulty: {difficulty}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /balance <wallet_address>\n\nExample: /balance MyWallet",
            parse_mode="Markdown",
        )
        return
    wallet = " ".join(context.args)
    await update.message.reply_chat_action("typing")

    data = api_get(f"api/balance/{wallet}") or api_get(f"balance/{wallet}")
    if not data:
        await update.message.reply_text(
            f"Could not fetch balance for {wallet}.",
            parse_mode="Markdown",
        )
        return
    balance = data.get("balance", data.get("amount", "N/A"))
    pending = data.get("pending", data.get("pending_balance"))

    msg = f"Wallet: {wallet}\n\nBalance: {balance} RTC\n"
    if pending is not None:
        msg += f"Pending: {pending} RTC\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    data = api_get("api/health") or api_get("")
    if not data:
        await update.message.reply_text(
            f"Node Unreachable\n\nCould not connect to {RUSTCHAIN_API}.",
            parse_mode="Markdown",
        )
        return

    status = data.get("status", data.get("message", "healthy"))
    uptime = data.get("uptime", data.get("uptime_seconds"))
    block_height = data.get("block_height", data.get("height"))
    peers = data.get("peers", data.get("peer_count"))
    version = data.get("version", data.get("node_version"))
    emoji = "" if str(status).lower() in ("healthy", "ok", "running", "alive") else ""

    msg = f"{emoji} RustChain Node Health\n\nStatus: {status}\n"
    if version:
        msg += f"Version: {version}\n"
    if block_height:
        msg += f"Block Height: {block_height}\n"
    if peers is not None:
        msg += f"Peers: {peers}\n"
    if uptime:
        msg += f"Uptime: {uptime}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.lower().strip()
    results = []

    if not query or query == "price":
        data = api_get("api/price")
        price = data.get("price", "N/A") if data else "N/A"
        results.append(InlineQueryResultArticle(
            id="price", title="wRTC Price",
            description=f"Current price: ${price}",
            input_message_content=InputTextMessageContent(
                f"wRTC Price: ${price}", parse_mode="Markdown",
            ),
        ))
    if not query or query == "miners":
        data = api_get("api/miners")
        if data:
            count = data.get("count", data.get("active_miners", "N/A"))
            results.append(InlineQueryResultArticle(
                id="miners", title="Active Miners",
                description=f"{count} miners active",
                input_message_content=InputTextMessageContent(
                    f"Active Miners: {count}", parse_mode="Markdown",
                ),
            ))
    if not query or query == "health":
        data = api_get("api/health")
        status = data.get("status", "unknown") if data else "offline"
        results.append(InlineQueryResultArticle(
            id="health", title="Node Health",
            description=f"Status: {status}",
            input_message_content=InputTextMessageContent(
                f"Node Health: {status}", parse_mode="Markdown",
            ),
        ))
    if not query or query == "epoch":
        data = api_get("epoch")
        epoch = data.get("epoch", data.get("current_epoch", "N/A")) if data else "N/A"
        results.append(InlineQueryResultArticle(
            id="epoch", title="Current Epoch",
            description=f"Epoch: {epoch}",
            input_message_content=InputTextMessageContent(
                f"Current Epoch: {epoch}", parse_mode="Markdown",
            ),
        ))
    await update.inline_query.answer(results, cache_time=30)


class PriceMonitor:
    def __init__(self):
        self.last_price = None
        self.alert_threshold = 5.0

    def check_price(self) -> str | None:
        data = api_get("api/price")
        if not data:
            return None
        try:
            current_price = float(data.get("price", 0))
        except (ValueError, TypeError):
            return None
        if self.last_price is None:
            self.last_price = current_price
            return None
        if self.last_price > 0:
            change = ((current_price - self.last_price) / self.last_price) * 100
            if abs(change) >= self.alert_threshold:
                emoji = "" if change > 0 else ""
                alert = (
                    f"{emoji} Price Alert!\n\n"
                    f"wRTC moved {change:+.2f}% in the last check\n"
                    f"Previous: ${self.last_price:.4f}\n"
                    f"Current: ${current_price:.4f}"
                )
                self.last_price = current_price
                return alert
        self.last_price = current_price
        return None


def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable is required.")
        print("Get one from @BotFather on Telegram.")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("miners", cmd_miners))
    app.add_handler(CommandHandler("epoch", cmd_epoch))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(InlineQueryHandler(inline_query))

    logger.info(f"RustChain Bot starting... API: {RUSTCHAIN_API}")
    print("RustChain Telegram Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
