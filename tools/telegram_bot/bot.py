#!/usr/bin/env python3
"""RustChain Telegram Community Bot — Bounty #249"""

import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = "http://50.28.86.131"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def fetch(session, path):
    async with session.get(f"{API_BASE}{path}", timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status == 200:
            return await r.json()
    return None

async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Current wRTC price from Raydium"""
    async with aiohttp.ClientSession() as s:
        data = await fetch(s, "/api/price")
    if data:
        price = data.get("price", "N/A")
        change = data.get("change_24h", "N/A")
        await update.message.reply_text(
            f"💰 *wRTC Price*\n"
            f"Price: `${price}`\n"
            f"24h Change: `{change}%`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Could not fetch price data.")

async def cmd_miners(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Active miner count"""
    async with aiohttp.ClientSession() as s:
        data = await fetch(s, "/api/miners")
    if data:
        count = data.get("active", data.get("count", len(data) if isinstance(data, list) else "N/A"))
        await update.message.reply_text(
            f"⛏️ *Active Miners*\nCount: `{count}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Could not fetch miner data.")

async def cmd_epoch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Current epoch info"""
    async with aiohttp.ClientSession() as s:
        data = await fetch(s, "/epoch")
    if data:
        epoch = data.get("epoch", data.get("current", "N/A"))
        await update.message.reply_text(
            f"🔄 *Epoch Info*\n"
            f"Current Epoch: `{epoch}`\n"
            f"Details: `{data}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Could not fetch epoch data.")

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Check RTC balance for a wallet"""
    if not ctx.args:
        await update.message.reply_text("Usage: `/balance <wallet_address>`", parse_mode="Markdown")
        return
    wallet = ctx.args[0]
    async with aiohttp.ClientSession() as s:
        data = await fetch(s, f"/api/balance/{wallet}")
    if data:
        bal = data.get("balance", "N/A")
        await update.message.reply_text(
            f"💳 *Wallet Balance*\n"
            f"Address: `{wallet[:8]}...{wallet[-6:]}`\n"
            f"Balance: `{bal} RTC`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Could not fetch balance. Check wallet address.")

async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Node health status"""
    async with aiohttp.ClientSession() as s:
        data = await fetch(s, "/api/health")
    if data:
        status = data.get("status", "unknown")
        emoji = "🟢" if status == "ok" else "🔴"
        await update.message.reply_text(
            f"{emoji} *Node Health*\nStatus: `{status}`\nDetails: `{data}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Node unreachable or unhealthy.")

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⛓️ *RustChain Community Bot*\n\n"
        "Commands:\n"
        "/price — wRTC price from Raydium\n"
        "/miners — Active miner count\n"
        "/epoch — Current epoch info\n"
        "/balance <wallet> — Check RTC balance\n"
        "/health — Node health status\n",
        parse_mode="Markdown"
    )

async def inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Inline query support (bonus)"""
    query = update.inline_query.query.lower()
    results = []
    if "price" in query or not query:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()), title="wRTC Price",
            input_message_content=InputTextMessageContent("Fetching wRTC price... Use /price in the bot chat."),
            description="Get current wRTC price"
        ))
    if "miners" in query or not query:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()), title="Active Miners",
            input_message_content=InputTextMessageContent("Use /miners in the bot chat to see active miners."),
            description="Check active miner count"
        ))
    await update.inline_query.answer(results[:5])

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("miners", cmd_miners))
    app.add_handler(CommandHandler("epoch", cmd_epoch))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(InlineQueryHandler(inline_query))
    logger.info("RustChain bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
