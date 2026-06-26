"""
RustChain Telegram Community Bot
Bounty #249 — 50 RTC + Bonuses

Core commands:
  /price   — wRTC price from Raydium
  /miners  — Active miner list & count
  /epoch   — Current epoch info
  /balance — Check RTC balance
  /health  — Node health status

Bonus features:
  - Mining alerts   (new miner joins / epoch settles)
  - Price alerts    (wRTC moves >5%)
  - Inline queries  (type @bot price/miners/epoch)

Improvements over prior version:
  - HTTP calls run off the event loop with asyncio.to_thread
  - Correct API field names per REFERENCE.md (amount_rtc, ok, slot, etc.)
  - All three bonus features implemented
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any

import requests
import urllib3
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
RUSTCHAIN_VERIFY_SSL = os.getenv("RUSTCHAIN_VERIFY_SSL", "true").lower() not in {
    "0",
    "false",
    "no",
}
if not RUSTCHAIN_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
WSOL_MINT = "So11111111111111111111111111111111111111112"
RAYDIUM_MINT_PRICE_URL = os.getenv(
    "RAYDIUM_MINT_PRICE_URL", "https://api-v3.raydium.io/mint/price"
)
RAYDIUM_POOL_INFO_URL = os.getenv(
    "RAYDIUM_POOL_INFO_URL", "https://api-v3.raydium.io/pools/info/mint"
)
RAYDIUM_SWAP_URL = (
    "https://raydium.io/swap/?inputMint=sol&outputMint="
    f"{WRTC_MINT}"
)

# Alert config
PRICE_ALERT_INTERVAL = int(os.getenv("PRICE_ALERT_INTERVAL", "120"))   # seconds
MINER_ALERT_INTERVAL = int(os.getenv("MINER_ALERT_INTERVAL", "60"))    # seconds
PRICE_CHANGE_THRESHOLD = float(os.getenv("PRICE_CHANGE_THRESHOLD", "5.0"))  # percent
HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "RustChain-Telegram-Bot/1.0 (+https://github.com/Scottcjn/Rustchain)",
}


# ---------------------------------------------------------------------------
# Async HTTP helpers (non-blocking, self-signed cert safe)
# ---------------------------------------------------------------------------
async def _get_json(url: str, params: dict | None = None, *, verify_ssl: bool = True):
    def fetch():
        resp = requests.get(
            url,
            params=params,
            headers=HTTP_HEADERS,
            timeout=10,
            verify=verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()

    return await asyncio.to_thread(fetch)


async def fetch_rustchain(path: str, params: dict | None = None):
    """Fetch from RustChain node; set RUSTCHAIN_VERIFY_SSL=false for self-signed nodes."""
    return await _get_json(f"{RUSTCHAIN_API}{path}", params, verify_ssl=RUSTCHAIN_VERIFY_SSL)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_raydium_mint_price(payload: dict, mint: str = WRTC_MINT) -> float | None:
    """Return Raydium's USD price for the requested mint."""
    if not isinstance(payload, dict) or payload.get("success") is False:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    return _to_float(data.get(mint))


def parse_raydium_pool_info(payload: dict, mint: str = WRTC_MINT) -> dict:
    """Extract the most liquid Raydium pool details for display."""
    empty = {
        "price_sol": None,
        "liquidity": 0.0,
        "volume_24h": 0.0,
        "pool_id": "",
        "url": RAYDIUM_SWAP_URL,
    }
    if not isinstance(payload, dict) or payload.get("success") is False:
        return empty

    data = payload.get("data")
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return empty

    expected_mints = {mint, WSOL_MINT}
    pool = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and {
                (row.get("mintA") or {}).get("address"),
                (row.get("mintB") or {}).get("address"),
            }
            == expected_mints
        ),
        None,
    )
    if not isinstance(pool, dict):
        return empty

    mint_a = (pool.get("mintA") or {}).get("address")
    mint_b = (pool.get("mintB") or {}).get("address")
    raw_price = _to_float(pool.get("price"))
    price_sol = None
    if raw_price and raw_price > 0:
        if mint_a == mint:
            price_sol = raw_price
        elif mint_b == mint:
            price_sol = 1 / raw_price

    day = pool.get("day") if isinstance(pool.get("day"), dict) else {}
    return {
        "price_sol": price_sol,
        "liquidity": _to_float(pool.get("tvl")) or 0.0,
        "volume_24h": _to_float(day.get("volume")) or 0.0,
        "pool_id": str(pool.get("id") or ""),
        "url": RAYDIUM_SWAP_URL,
    }


async def fetch_price_data() -> dict | None:
    """Fetch wRTC price from Raydium price and pool APIs."""
    try:
        price_request = _get_json(RAYDIUM_MINT_PRICE_URL, {"mints": WRTC_MINT})
        pool_request = _get_json(
            RAYDIUM_POOL_INFO_URL,
            {
                "mint1": WRTC_MINT,
                "mint2": WSOL_MINT,
                "poolType": "all",
                "poolSortField": "liquidity",
                "sortType": "desc",
                "pageSize": "1",
                "page": "1",
            },
        )
        price_payload, pool_payload = await asyncio.gather(price_request, pool_request)
        price_usd = parse_raydium_mint_price(price_payload)
        pool = parse_raydium_pool_info(pool_payload)
        if price_usd is None:
            return None
        return {
            "price_usd": price_usd,
            "price_sol": pool["price_sol"],
            "liquidity": pool["liquidity"],
            "volume_24h": pool["volume_24h"],
            "pool_id": pool["pool_id"],
            "url": pool["url"],
        }
    except Exception as e:
        logger.error("fetch_price_data: %s", e)
        return None


def normalize_miners_payload(data: dict | list) -> tuple[list, int] | None:
    """Return miner rows and advertised total from legacy lists or API envelopes."""
    if isinstance(data, list):
        return data, len(data)
    if not isinstance(data, dict):
        return None

    miners = data.get("miners") or data.get("data") or []
    if not isinstance(miners, list):
        miners = []

    pagination = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
    total = pagination.get("total", data.get("total", len(miners)))
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(miners)
    return miners, max(total, len(miners))


def miner_name(row: dict) -> str:
    return row.get("miner") or row.get("miner_id") or "?"


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
        f"SOL: `{data['price_sol'] or 'N/A'}`\n"
        f"Raydium TVL: `${data['liquidity']:,.0f}`\n"
        f"Raydium 24h Volume: `{data['volume_24h']:,.4f}`\n"
        f"Pool: `{data['pool_id'] or 'N/A'}`\n\n"
        f"[Raydium]({data['url']})"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown", disable_web_page_preview=True
    )


async def cmd_miners(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        payload = await fetch_rustchain("/api/miners")
        normalized = normalize_miners_payload(payload)
        if normalized is None:
            await update.message.reply_text("Unexpected response from /api/miners.")
            return
        miners, total = normalized
        lines = [f"*Active Miners: {total}*\n"]
        for m in miners[:15]:
            name = miner_name(m)
            hw = m.get("hardware_type", m.get("device_arch", ""))
            mult = m.get("antiquity_multiplier", "")
            lines.append(f"  `{name}` — {hw} (x{mult})")
        if total > len(miners[:15]):
            lines.append(f"\n_…and {total - len(miners[:15])} more_")
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
            payload = await fetch_rustchain("/api/miners")
            normalized = normalize_miners_payload(payload)
            if normalized is not None:
                miners, _total = normalized
                current = {miner_name(m) for m in miners if miner_name(m) != "?"}
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
                    description=f"Raydium TVL: ${data['liquidity']:,.0f}",
                    input_message_content=InputTextMessageContent(
                        f"wRTC: ${data['price_usd']:.6f} | Raydium TVL: ${data['liquidity']:,.0f}"
                    ),
                )
            )

    if not query or "miners" in query:
        try:
            payload = await fetch_rustchain("/api/miners")
            normalized = normalize_miners_payload(payload)
            count = normalized[1] if normalized is not None else "?"
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
            logger.warning("Failed to fetch RustChain miner stats for inline query", exc_info=True)

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
            logger.warning("Failed to fetch RustChain epoch for inline query", exc_info=True)

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
