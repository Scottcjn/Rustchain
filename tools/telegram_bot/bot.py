#!/usr/bin/env python3
"""RustChain Telegram community bot.

Commands:
- /price
- /miners
- /epoch
- /balance <wallet>
- /health
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

API_BASE = os.getenv("RUSTCHAIN_API_BASE", "http://50.28.86.131")
REQUEST_TIMEOUT = float(os.getenv("RUSTCHAIN_REQUEST_TIMEOUT", "8"))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("rustchain_telegram_bot")


async def api_get(path: str) -> Any:
    url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
    timeout = httpx.Timeout(REQUEST_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


def _pick_number(payload: Any, keys: list[str]) -> Any:
    if isinstance(payload, dict):
        for k in keys:
            if k in payload and payload[k] is not None:
                return payload[k]
    return None


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await api_get("wrtc/price")
        price = _pick_number(data, ["price", "wrtc_price", "usd", "value"])
        if price is None:
            await update.message.reply_text(f"wRTC price payload: {data}")
            return
        await update.message.reply_text(f"wRTC 当前价格: {price}")
    except Exception as exc:
        logger.exception("/price failed")
        await update.message.reply_text(f"获取价格失败: {exc}")


async def cmd_miners(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await api_get("api/miners")
        count = _pick_number(data, ["active_miners", "count", "miners", "total"])
        if count is None and isinstance(data, list):
            count = len(data)
        await update.message.reply_text(f"活跃矿工数: {count if count is not None else data}")
    except Exception as exc:
        logger.exception("/miners failed")
        await update.message.reply_text(f"获取矿工信息失败: {exc}")


async def cmd_epoch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await api_get("epoch")
        await update.message.reply_text(f"当前 Epoch: {data}")
    except Exception as exc:
        logger.exception("/epoch failed")
        await update.message.reply_text(f"获取 epoch 失败: {exc}")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法: /balance <wallet>")
        return
    wallet = context.args[0].strip()
    try:
        data = await api_get(f"wallet/{wallet}")
        balance = _pick_number(data, ["balance", "rtc", "amount"])
        await update.message.reply_text(
            f"钱包 {wallet}\n余额: {balance if balance is not None else data}"
        )
    except Exception as exc:
        logger.exception("/balance failed")
        await update.message.reply_text(f"查询余额失败: {exc}")


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await api_get("health")
        status = _pick_number(data, ["status", "ok", "healthy"])
        await update.message.reply_text(f"节点健康状态: {status if status is not None else data}")
    except Exception as exc:
        logger.exception("/health failed")
        await update.message.reply_text(f"健康检查失败: {exc}")


def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("miners", cmd_miners))
    app.add_handler(CommandHandler("epoch", cmd_epoch))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("health", cmd_health))
    return app


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    app = build_app(token)
    logger.info("Starting RustChain Telegram bot with API base: %s", API_BASE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
