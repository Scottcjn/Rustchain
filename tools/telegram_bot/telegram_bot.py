"""
RustChain Telegram Community Bot
Bounty #249 — 50 RTC + Bonuses

Core commands:
  /price   — wRTC price from Raydium (DexScreener)
  /miners  — Active miner list & count
  /epoch   — Current epoch info
  /balance — Check RTC balance
  /health  — Node health status

Bonus features:
  - Mining alerts   (new miner joins / epoch settles)
  - Price alerts    (wRTC moves >5%)
  - Inline queries  (type @bot price/miners/epoch)

Improvements over prior version:
  - Async HTTP (aiohttp) instead of blocking requests in async handlers
  - Correct API field names per REFERENCE.md (amount_rtc, ok, slot, etc.)
  - All three bonus features implemented
"""

import os
import asyncio
import logging

import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CommandHandler,
    InlineQueryHandler,
    ContextTypes,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger("rustchain_bot")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
DEXSCREENER_URL = f"https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}"

# Alert config
PRICE_ALERT_INTERVAL = int(os.getenv("PRICE_ALERT_INTERVAL", "120"))   # seconds
MINER_ALERT_INTERVAL = int(os.getenv("MINER_ALERT_INTERVAL", "60"))    # seconds
PRICE_CHANGE_THRESHOLD = float(os.getenv("PRICE_CHANGE_THRESHOLD", "5.0"))  # percent


# ---------------------------------------------------------------------------
# Async HTTP helpers (non-blocking, self-signed cert safe)
# ---------------------------------------------------------------------------
async def _get_json(url: str, params: dict | None = None, *, verify_ssl: bool = True):
    connector = aiohttp.TCPConnector(ssl=verify_ssl)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def fetch_rustchain(path: str, params: dict | None = None):
    """Fetch from RustChain node (self-signed cert → ssl=False)."""
    return await _get_json(f"{RUSTCHAIN_API}{path}", params, verify_ssl=False)


async def fetch_price_data() -> dict | None:
    """Fetch wRTC price from DexScreener, preferring the Raydium pair."""
    try:
        data = await _get_json(DEXSCREENER_URL)
        pairs = data.get("pairs", [])
        if not pairs:
            return None
        pair = next((p for p in pairs if p.get("dexId") == "raydium"), pairs[0])
        return {
            "price_usd": float(pair.get("priceUsd", 0)),
            "price_sol": pair.get("priceNative", "N/A"),
            "h24_change": pair.get("priceChange", {}).get("h24", 0),
            "liquidity": pair.get("liquidity", {}).get("usd", 0),
            "volume_24h": pair.get("volume", {}).get("h24", 0),
            "url": pair.get("url", "https://dexscreener.com"),
        }
    except Exception as e:
        logger.error("fetch_price_data: %s", e)
        return None


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "*RustChain Community Bot*\n\n"
        "/price — wRTC price (Raydium)\n"
        "/miners — Active miners\n"
        "/epoch — Current epoch\n"
        "/balance <wallet> — Wallet balance\n"
        "/health — Node health\n"
        "/subscribe — Enable alerts in this chat\n"
        "/unsubscribe — Disable alerts"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await fetch_price_data()
    if not data:
        await update.message.reply_text("Could not fetch wRTC price. Try again later.")
        return
    text = (
        f"*wRTC Price*\n\n"
        f"USD: `${data['price_usd']:.6f}`\n"
        f"SOL: `{data['price_sol']}`\n"
        f"24h: `{data['h24_change']}%`\n"
        f"Liquidity: `${data['liquidity']:,.0f}`\n"
        f"Volume 24h: `${data['volume_24h']:,.0f}`\n\n"
        f"[DexScreener]({data['url']})"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown", disable_web_page_preview=True
    )


async def cmd_miners(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        miners = await fetch_rustchain("/api/miners")
        if not isinstance(miners, list):
            await update.message.reply_text("Unexpected response from /api/miners.")
            return
        lines = [f"*Active Miners: {len(miners)}*\n"]
        for m in miners[:15]:
            name = m.get("miner", "?")
            hw = m.get("hardware_type", m.get("device_arch", ""))
            mult = m.get("antiquity_multiplier", "")
            lines.append(f"  `{name}` — {hw} (x{mult})")
        if len(miners) > 15:
            lines.append(f"\n_…and {len(miners) - 15} more_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error("cmd_miners: %s", e)
        await update.message.reply_text(f"Error: {e}")


async def cmd_epoch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ep = await fetch_rustchain("/epoch")
        text = (
            f"*Epoch Info*\n\n"
            f"Epoch: `{ep.get('epoch', 'N/A')}`\n"
            f"Slot: `{ep.get('slot', 'N/A')}`\n"
            f"Blocks/Epoch: `{ep.get('blocks_per_epoch', 'N/A')}`\n"
            f"Epoch Pot: `{ep.get('epoch_pot', 'N/A')} RTC`\n"
            f"Enrolled Miners: `{ep.get('enrolled_miners', 'N/A')}`"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error("cmd_epoch: %s", e)
        await update.message.reply_text(f"Error: {e}")


async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/balance <wallet_name>`", parse_mode="Markdown"
        )
        return
    wallet = ctx.args[0]
    try:
        data = await fetch_rustchain("/wallet/balance", {"miner_id": wallet})
        if not data.get("ok"):
            await update.message.reply_text(
                f"Wallet `{wallet}` not found.", parse_mode="Markdown"
            )
            return
        text = (
            f"*Wallet Balance*\n\n"
            f"Wallet: `{data.get('miner_id', wallet)}`\n"
            f"Balance: `{data.get('amount_rtc', 0)} RTC`"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error("cmd_balance: %s", e)
        await update.message.reply_text(f"Error: {e}")


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        h = await fetch_rustchain("/health")
        status = "Healthy" if h.get("ok") else "Degraded"
        uptime_h = round(h.get("uptime_s", 0) / 3600, 1)
        text = (
            f"*Node Health*\n\n"
            f"Status: `{status}`\n"
            f"Version: `{h.get('version', 'N/A')}`\n"
            f"Uptime: `{uptime_h}h`\n"
            f"DB R/W: `{h.get('db_rw', 'N/A')}`\n"
            f"Tip Age: `{h.get('tip_age_slots', 'N/A')} slots`"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error("cmd_health: %s", e)
        await update.message.reply_text(f"Error: {e}")


# ---------------------------------------------------------------------------
# Subscribe / Unsubscribe for alerts
# ---------------------------------------------------------------------------
_subscribed_chats: set[int] = set()


async def cmd_subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _subscribed_chats.add(update.effective_chat.id)
    await update.message.reply_text(
        "Alerts enabled. Use /unsubscribe to turn off."
    )


async def cmd_unsubscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _subscribed_chats.discard(update.effective_chat.id)
    await update.message.reply_text("Alerts disabled.")


# ---------------------------------------------------------------------------
# Bonus 1: Mining alerts — new miner joins / epoch settles
# ---------------------------------------------------------------------------
_last_known_miners: set[str] = set()
_last_known_epoch: int | None = None


async def mining_alert_loop(app: Application):
    global _last_known_miners, _last_known_epoch
    await asyncio.sleep(5)
    while True:
        try:
            miners = await fetch_rustchain("/api/miners")
            if isinstance(miners, list):
                current = {m.get("miner", "") for m in miners}
                if _last_known_miners:
                    for name in current - _last_known_miners:
                        msg = f"*New Miner Joined!*\n`{name}` is now mining on RustChain."
                        for cid in list(_subscribed_chats):
                            try:
                                await app.bot.send_message(
                                    cid, msg, parse_mode="Markdown"
                                )
                            except Exception:
                                _subscribed_chats.discard(cid)
                _last_known_miners = current

            ep = await fetch_rustchain("/epoch")
            epoch_num = ep.get("epoch")
            if _last_known_epoch is not None and epoch_num != _last_known_epoch:
                msg = (
                    f"*Epoch Settled!*\n"
                    f"New epoch: `{epoch_num}` | Pot: `{ep.get('epoch_pot', '?')} RTC`"
                )
                for cid in list(_subscribed_chats):
                    try:
                        await app.bot.send_message(cid, msg, parse_mode="Markdown")
                    except Exception:
                        _subscribed_chats.discard(cid)
            _last_known_epoch = epoch_num
        except Exception as e:
            logger.warning("mining_alert_loop: %s", e)
        await asyncio.sleep(MINER_ALERT_INTERVAL)


# ---------------------------------------------------------------------------
# Bonus 2: Price alerts — wRTC moves >5%
# ---------------------------------------------------------------------------
_last_alert_price: float | None = None


async def price_alert_loop(app: Application):
    global _last_alert_price
    await asyncio.sleep(10)
    while True:
        try:
            data = await fetch_price_data()
            if data and data["price_usd"] > 0:
                price = data["price_usd"]
                if _last_alert_price is not None and _last_alert_price > 0:
                    pct = abs(price - _last_alert_price) / _last_alert_price * 100
                    if pct >= PRICE_CHANGE_THRESHOLD:
                        direction = "up" if price > _last_alert_price else "down"
                        msg = (
                            f"*wRTC Price Alert!*\n"
                            f"Price moved {direction} {pct:.1f}%\n"
                            f"Now: `${price:.6f}` (was `${_last_alert_price:.6f}`)"
                        )
                        for cid in list(_subscribed_chats):
                            try:
                                await app.bot.send_message(
                                    cid, msg, parse_mode="Markdown"
                                )
                            except Exception:
                                _subscribed_chats.discard(cid)
                        _last_alert_price = price
                else:
                    _last_alert_price = price
        except Exception as e:
            logger.warning("price_alert_loop: %s", e)
        await asyncio.sleep(PRICE_ALERT_INTERVAL)


# ---------------------------------------------------------------------------
# Bonus 3: Inline query support
# ---------------------------------------------------------------------------
async def inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = (update.inline_query.query or "").strip().lower()
    results = []

    if not query or "price" in query:
        data = await fetch_price_data()
        if data:
            results.append(
                InlineQueryResultArticle(
                    id="price",
                    title=f"wRTC ${data['price_usd']:.6f}",
                    description=f"24h change: {data['h24_change']}%",
                    input_message_content=InputTextMessageContent(
                        f"wRTC: ${data['price_usd']:.6f} | 24h: {data['h24_change']}%"
                    ),
                )
            )

    if not query or "miners" in query:
        try:
            miners = await fetch_rustchain("/api/miners")
            count = len(miners) if isinstance(miners, list) else "?"
            results.append(
                InlineQueryResultArticle(
                    id="miners",
                    title=f"Active Miners: {count}",
                    description="Current miner count on RustChain",
                    input_message_content=InputTextMessageContent(
                        f"RustChain has {count} active miners."
                    ),
                )
            )
        except Exception:
            pass

    if not query or "epoch" in query:
        try:
            ep = await fetch_rustchain("/epoch")
            results.append(
                InlineQueryResultArticle(
                    id="epoch",
                    title=f"Epoch {ep.get('epoch', '?')}",
                    description=f"Slot {ep.get('slot', '?')} | Pot {ep.get('epoch_pot', '?')} RTC",
                    input_message_content=InputTextMessageContent(
                        f"Epoch {ep.get('epoch', '?')} — Slot {ep.get('slot', '?')}, "
                        f"Pot {ep.get('epoch_pot', '?')} RTC, "
                        f"{ep.get('enrolled_miners', '?')} enrolled miners"
                    ),
                )
            )
        except Exception:
            pass

    await update.inline_query.answer(results, cache_time=30)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not BOT_TOKEN:
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable.")
        print("  export TELEGRAM_BOT_TOKEN='your_token'")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    for name, handler in [
        ("start", cmd_start),
        ("help", cmd_start),
        ("price", cmd_price),
        ("miners", cmd_miners),
        ("epoch", cmd_epoch),
        ("balance", cmd_balance),
        ("health", cmd_health),
        ("subscribe", cmd_subscribe),
        ("unsubscribe", cmd_unsubscribe),
    ]:
        app.add_handler(CommandHandler(name, handler))

    app.add_handler(InlineQueryHandler(inline_query))

    async def post_init(application: Application):
        asyncio.create_task(mining_alert_loop(application))
        asyncio.create_task(price_alert_loop(application))

    app.post_init = post_init

    print(f"RustChain Telegram Bot starting — API: {RUSTCHAIN_API}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
