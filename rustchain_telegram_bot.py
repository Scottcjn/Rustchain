#!/usr/bin/env python3
"""RustChain Telegram wallet bot."""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

API_BASE = os.getenv("RUSTCHAIN_API", "https://50.28.86.131")
STATE_FILE = Path(os.getenv("TELEGRAM_WALLET_STATE", "telegram_wallet_state.json"))


def now():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"users": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_user_wallet(state, user_id: str):
    return state["users"].get(user_id)


def ensure_history(entry):
    entry.setdefault("history", [])
    return entry


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("RustChain Wallet Bot ready. Use /help")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/create <wallet_name>\n"
        "/balance\n"
        "/send <to_wallet> <amount>\n"
        "/history\n"
        "/price"
    )


async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /create <wallet_name>")
        return
    name = context.args[0].strip()
    if len(name) < 3:
        await update.message.reply_text("Wallet name too short")
        return
    state = load_state()
    uid = str(update.effective_user.id)
    state["users"][uid] = {"wallet": name, "created_at": now(), "history": []}
    save_state(state)
    await update.message.reply_text(f"Wallet linked: {name}")


def api_balance(wallet: str):
    r = requests.get(f"{API_BASE}/wallet/balance", params={"miner_id": wallet}, timeout=20, verify=False)
    if r.status_code != 200:
        return 0.0
    d = r.json()
    return float(d.get("balance", 0) or 0)


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    uid = str(update.effective_user.id)
    w = get_user_wallet(state, uid)
    if not w:
        await update.message.reply_text("No wallet linked. Use /create <wallet_name>")
        return
    bal = api_balance(w["wallet"])
    await update.message.reply_text(f"Wallet: {w['wallet']}\nBalance: {bal:.6f} RTC")


async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /send <to_wallet> <amount>")
        return
    to_wallet = context.args[0].strip()
    try:
        amt = float(context.args[1])
    except Exception:
        await update.message.reply_text("Invalid amount")
        return
    if amt <= 0:
        await update.message.reply_text("Amount must be > 0")
        return

    state = load_state()
    uid = str(update.effective_user.id)
    w = get_user_wallet(state, uid)
    if not w:
        await update.message.reply_text("No wallet linked. Use /create <wallet_name>")
        return

    payload = {"from": w["wallet"], "to": to_wallet, "amount_rtc": amt}
    r = requests.post(f"{API_BASE}/wallet/transfer", json=payload, timeout=30, verify=False)
    if r.status_code != 200:
        await update.message.reply_text(f"Transfer failed: {r.status_code} {r.text[:180]}")
        return

    entry = ensure_history(w)
    entry["history"].append({"ts": now(), "type": "send", "to": to_wallet, "amount": amt})
    entry["history"] = entry["history"][-50:]
    state["users"][uid] = entry
    save_state(state)
    await update.message.reply_text(f"Sent {amt:.6f} RTC to {to_wallet}")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    uid = str(update.effective_user.id)
    w = get_user_wallet(state, uid)
    if not w:
        await update.message.reply_text("No wallet linked. Use /create <wallet_name>")
        return
    hist = (w.get("history") or [])[-10:]
    if not hist:
        await update.message.reply_text("No history yet")
        return
    lines = [f"{h.get('ts','')} | {h.get('type','')} | {h.get('amount',0)} RTC | {h.get('to','')}" for h in hist]
    await update.message.reply_text("\n".join(lines))


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    epoch = {}
    miners = []
    try:
        e = requests.get(f"{API_BASE}/epoch", timeout=15, verify=False)
        if e.status_code == 200:
            epoch = e.json()
    except Exception:
        pass
    try:
        m = requests.get(f"{API_BASE}/api/miners", timeout=15, verify=False)
        if m.status_code == 200:
            j = m.json()
            miners = j if isinstance(j, list) else (j.get("miners") or j.get("items") or [])
    except Exception:
        pass

    pot = float(epoch.get("pot") or 0)
    await update.message.reply_text(
        f"RTC reference: $0.10\nActive miners: {len(miners)}\nEpoch pot: {pot:.2f} RTC"
    )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    requests.packages.urllib3.disable_warnings()
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("create", cmd_create))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("price", cmd_price))
    app.run_polling()


if __name__ == "__main__":
    main()
