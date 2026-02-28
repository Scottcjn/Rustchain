"""
RustChain Telegram Wallet Bot
Bounty: 75 RTC
Issue: #27

A secure Telegram bot for managing RTC wallets:
- /start      - Welcome & setup instructions
- /create     - Create a new wallet via DM (password-encrypted keystore)
- /balance    - Check your RTC balance
- /send       - Send RTC to another address (Ed25519 signed)
- /history    - Recent transactions
- /price      - Current wRTC market stats
- /address    - Show your wallet address
- /export     - Export public key (for external verification)
- /help       - Command reference

Security:
- Ed25519 keypairs generated locally
- Private keys encrypted with Argon2id + XSalsa20-Poly1305
- Wallet creation & send commands only work in DMs (never in groups)
- Password never stored; required per-transaction for signing
"""

import os
import logging
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from crypto_utils import (
    KeystoreManager,
    pubkey_to_address,
    sign_transaction,
)

# Load .env if present
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
VERIFY_SSL = os.getenv("RUSTCHAIN_VERIFY_SSL", "false").lower() == "true"
KEYSTORE_DIR = os.getenv("KEYSTORE_DIR", None)  # defaults to ~/.rustchain/telegram_wallets

# DexScreener wRTC
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
DEXSCREENER_API = f"https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}"

# Conversation states
CREATE_PASSWORD, CREATE_CONFIRM = range(2)
SEND_ADDR, SEND_AMOUNT, SEND_MEMO, SEND_PASSWORD = range(10, 14)

# Logging
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("wallet_bot")

# Keystore manager (singleton)
ks_mgr = KeystoreManager(base_dir=KEYSTORE_DIR)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _api_get(endpoint: str, params: dict = None, timeout: int = 10) -> dict:
    """GET request to RustChain API with error handling."""
    url = f"{RUSTCHAIN_API}/{endpoint.lstrip('/')}"
    resp = requests.get(url, params=params, verify=VERIFY_SSL, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _api_post(endpoint: str, payload: dict, timeout: int = 15) -> dict:
    """POST request to RustChain API."""
    url = f"{RUSTCHAIN_API}/{endpoint.lstrip('/')}"
    resp = requests.post(url, json=payload, verify=VERIFY_SSL, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _is_private(update: Update) -> bool:
    """Check if the message is in a private chat (DM)."""
    return update.effective_chat.type == "private"


def _rtc_from_urtc(urtc: int) -> float:
    """Convert micro-RTC to RTC."""
    return urtc / 1_000_000


def _urtc_from_rtc(rtc: float) -> int:
    """Convert RTC to micro-RTC."""
    return int(rtc * 1_000_000)


# ─── /start ───────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    has_wallet = ks_mgr.has_wallet(user_id)

    if has_wallet:
        addr = ks_mgr.get_address(user_id)
        text = (
            f"Welcome back to *RustChain Wallet Bot*!\n\n"
            f"Your wallet: `{addr}`\n\n"
            f"Commands:\n"
            f"/balance - Check balance\n"
            f"/send - Send RTC\n"
            f"/history - Recent transactions\n"
            f"/price - wRTC market stats\n"
            f"/address - Show address\n"
            f"/help - All commands"
        )
    else:
        text = (
            "Welcome to *RustChain Wallet Bot*!\n\n"
            "You don't have a wallet yet.\n"
            "Use /create in this DM to set one up.\n\n"
            "Your private key will be encrypted with a\n"
            "password you choose (Argon2id + XSalsa20).\n\n"
            "Commands:\n"
            "/create - Create wallet\n"
            "/price  - wRTC market stats\n"
            "/help   - All commands"
        )

    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /help ────────────────────────────────────────────────────────────────────

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*RustChain Wallet Bot - Commands*\n\n"
        "/create  - Create a new wallet (DM only)\n"
        "/balance - Check your RTC balance\n"
        "/send    - Send RTC to an address (DM only)\n"
        "/history - Recent transactions\n"
        "/price   - wRTC market price & stats\n"
        "/address - Show your wallet address\n"
        "/export  - Show your public key\n"
        "/help    - This message\n\n"
        "Security: Private keys are encrypted locally.\n"
        "Your password is never stored."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /create (conversation) ──────────────────────────────────────────────────

async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_private(update):
        await update.message.reply_text(
            "Wallet creation is only available in DMs for security.\n"
            "Please message me directly."
        )
        return ConversationHandler.END

    user_id = update.effective_user.id
    if ks_mgr.has_wallet(user_id):
        addr = ks_mgr.get_address(user_id)
        await update.message.reply_text(
            f"You already have a wallet!\n"
            f"Address: `{addr}`\n\n"
            f"Use /balance to check your balance.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Let's create your RustChain wallet.\n\n"
        "Choose a strong password to encrypt your private key.\n"
        "You'll need this password every time you send RTC.\n\n"
        "**Send your password now** (it will be deleted after setup):",
        parse_mode="Markdown",
    )
    return CREATE_PASSWORD


async def create_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()

    # Delete the user's password message for safety
    try:
        await update.message.delete()
    except Exception:
        pass

    if len(password) < 6:
        await update.message.reply_text(
            "Password must be at least 6 characters. Try again:"
        )
        return CREATE_PASSWORD

    context.user_data["_create_pw"] = password
    await update.effective_chat.send_message(
        "Good. Now **send the same password again** to confirm:",
        parse_mode="Markdown",
    )
    return CREATE_CONFIRM


async def create_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    confirm = update.message.text.strip()

    # Delete confirmation message
    try:
        await update.message.delete()
    except Exception:
        pass

    password = context.user_data.pop("_create_pw", None)
    if password is None or confirm != password:
        await update.effective_chat.send_message(
            "Passwords don't match. Please start over with /create."
        )
        return ConversationHandler.END

    user_id = update.effective_user.id

    try:
        address = ks_mgr.create_wallet(user_id, password)
    except FileExistsError:
        await update.effective_chat.send_message("You already have a wallet!")
        return ConversationHandler.END

    pub_key = ks_mgr.get_public_key(user_id)

    await update.effective_chat.send_message(
        f"Wallet created successfully!\n\n"
        f"*Address:* `{address}`\n"
        f"*Public Key:* `{pub_key}`\n\n"
        f"Your private key is encrypted and stored securely.\n"
        f"*Never share your password with anyone.*\n\n"
        f"Use /balance to check your balance.",
        parse_mode="Markdown",
    )
    logger.info(f"Wallet created for user {user_id}: {address}")
    return ConversationHandler.END


async def create_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("_create_pw", None)
    await update.message.reply_text("Wallet creation cancelled.")
    return ConversationHandler.END


# ─── /balance ─────────────────────────────────────────────────────────────────

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Allow checking any address: /balance <addr>
    if context.args:
        addr = context.args[0]
    else:
        addr = ks_mgr.get_address(user_id)
        if addr is None:
            await update.message.reply_text(
                "You don't have a wallet yet. Use /create to make one.\n"
                "Or: /balance <address> to check any address."
            )
            return

    try:
        data = _api_get("/balance", params={"miner_id": addr})
        balance = data.get("balance", data.get("balance_rtc", "N/A"))

        text = (
            f"*Wallet Balance*\n\n"
            f"Address: `{addr}`\n"
            f"Balance: *{balance} RTC*"
        )
        if "epoch_rewards" in data:
            text += f"\nEpoch Rewards: {data['epoch_rewards']} RTC"
        if "total_earned" in data:
            text += f"\nTotal Earned: {data['total_earned']} RTC"

    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            text = f"Address `{addr}` not found on the network."
        else:
            text = f"Error fetching balance: {e}"
    except Exception as e:
        text = f"Error: {e}"

    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /send (conversation) ────────────────────────────────────────────────────

async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_private(update):
        await update.message.reply_text(
            "Sending RTC is only available in DMs for security."
        )
        return ConversationHandler.END

    user_id = update.effective_user.id
    if not ks_mgr.has_wallet(user_id):
        await update.message.reply_text("No wallet found. Use /create first.")
        return ConversationHandler.END

    # Support shorthand: /send <addr> <amount> [memo]
    if context.args and len(context.args) >= 2:
        context.user_data["_send_to"] = context.args[0]
        try:
            amount = float(context.args[1])
            if amount <= 0:
                raise ValueError
            context.user_data["_send_amount"] = amount
        except ValueError:
            await update.message.reply_text("Invalid amount. Usage: /send <address> <amount> [memo]")
            return ConversationHandler.END
        memo = " ".join(context.args[2:]) if len(context.args) > 2 else ""
        context.user_data["_send_memo"] = memo

        from_addr = ks_mgr.get_address(user_id)
        text = (
            f"*Confirm Transaction*\n\n"
            f"From: `{from_addr}`\n"
            f"To:   `{context.user_data['_send_to']}`\n"
            f"Amount: *{amount} RTC*\n"
        )
        if memo:
            text += f"Memo: {memo}\n"
        text += "\nSend your wallet password to sign & submit:"

        await update.message.reply_text(text, parse_mode="Markdown")
        return SEND_PASSWORD

    await update.message.reply_text("Enter the recipient's RTC address:")
    return SEND_ADDR


async def send_addr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    if len(addr) < 10:
        await update.message.reply_text("That doesn't look like a valid address. Try again:")
        return SEND_ADDR

    context.user_data["_send_to"] = addr
    await update.message.reply_text("Enter the amount of RTC to send:")
    return SEND_AMOUNT


async def send_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid amount. Enter a positive number:")
        return SEND_AMOUNT

    context.user_data["_send_amount"] = amount
    await update.message.reply_text(
        "Enter an optional memo (or send /skip for none):"
    )
    return SEND_MEMO


async def send_memo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    memo = "" if text == "/skip" else text
    context.user_data["_send_memo"] = memo

    user_id = update.effective_user.id
    from_addr = ks_mgr.get_address(user_id)
    to_addr = context.user_data["_send_to"]
    amount = context.user_data["_send_amount"]

    summary = (
        f"*Confirm Transaction*\n\n"
        f"From: `{from_addr}`\n"
        f"To:   `{to_addr}`\n"
        f"Amount: *{amount} RTC*\n"
    )
    if memo:
        summary += f"Memo: {memo}\n"
    summary += "\nSend your wallet password to sign & submit:"

    await update.message.reply_text(summary, parse_mode="Markdown")
    return SEND_PASSWORD


async def send_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()

    # Delete password message immediately
    try:
        await update.message.delete()
    except Exception:
        pass

    user_id = update.effective_user.id
    to_addr = context.user_data.pop("_send_to")
    amount = context.user_data.pop("_send_amount")
    memo = context.user_data.pop("_send_memo", "")

    # Unlock wallet
    try:
        priv_key, pub_key = ks_mgr.unlock(user_id, password)
    except ValueError:
        await update.effective_chat.send_message(
            "Incorrect password. Transaction cancelled."
        )
        return ConversationHandler.END
    except FileNotFoundError:
        await update.effective_chat.send_message("No wallet found.")
        return ConversationHandler.END

    from_addr = pubkey_to_address(pub_key)
    amount_urtc = _urtc_from_rtc(amount)
    nonce = int(time.time() * 1000)  # millisecond timestamp as nonce

    # Sign the transaction
    signature = sign_transaction(priv_key, from_addr, to_addr, amount_urtc, nonce, memo)

    # Submit to the node
    payload = {
        "from_addr": from_addr,
        "to_addr": to_addr,
        "amount_urtc": amount_urtc,
        "nonce": nonce,
        "memo": memo,
        "signature": signature,
        "public_key": pub_key,
    }

    status_msg = await update.effective_chat.send_message("Signing and submitting...")

    try:
        result = _api_post("/tx/submit", payload)

        if result.get("success") or result.get("tx_hash"):
            tx_hash = result.get("tx_hash", "N/A")
            text = (
                f"*Transaction Submitted!*\n\n"
                f"TX Hash: `{tx_hash}`\n"
                f"Amount: {amount} RTC\n"
                f"To: `{to_addr}`\n"
                f"Status: {result.get('status', 'pending')}"
            )
        else:
            error = result.get("error", result.get("message", "Unknown error"))
            text = f"Transaction failed: {error}"

    except requests.HTTPError as e:
        try:
            err_body = e.response.json()
            error = err_body.get("error", str(e))
        except Exception:
            error = str(e)
        text = f"Transaction failed: {error}"
    except Exception as e:
        text = f"Error submitting transaction: {e}"

    try:
        await status_msg.edit_text(text, parse_mode="Markdown")
    except Exception:
        await update.effective_chat.send_message(text, parse_mode="Markdown")

    return ConversationHandler.END


async def send_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for key in ("_send_to", "_send_amount", "_send_memo"):
        context.user_data.pop(key, None)
    await update.message.reply_text("Transaction cancelled.")
    return ConversationHandler.END


# ─── /history ─────────────────────────────────────────────────────────────────

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.args:
        addr = context.args[0]
    else:
        addr = ks_mgr.get_address(user_id)
        if addr is None:
            await update.message.reply_text(
                "No wallet found. Use /create or /history <address>."
            )
            return

    try:
        data = _api_get("/wallet/history", params={"miner_id": addr, "limit": 10})

        if not data or (isinstance(data, list) and len(data) == 0):
            await update.message.reply_text(
                f"No transactions found for `{addr}`.",
                parse_mode="Markdown",
            )
            return

        lines = [f"*Recent Transactions for* `{addr}`\n"]
        txs = data if isinstance(data, list) else data.get("transactions", [])

        for tx in txs[:10]:
            ts = tx.get("timestamp", 0)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            from_a = tx.get("from_addr", tx.get("from", "?"))
            to_a = tx.get("to_addr", tx.get("to", "?"))
            amt = tx.get("amount", tx.get("amount_urtc", 0))
            if isinstance(amt, int) and amt > 10000:
                amt = _rtc_from_urtc(amt)
            status = tx.get("status", "confirmed")

            if from_a == addr:
                direction = f"-> `{to_a[:16]}...`"
                sign = "-"
            else:
                direction = f"<- `{from_a[:16]}...`"
                sign = "+"

            lines.append(f"`{dt}` {sign}{amt} RTC {direction} ({status})")

        text = "\n".join(lines)

    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            text = f"No history available for `{addr}`."
        else:
            text = f"Error fetching history: {e}"
    except Exception as e:
        text = f"Error: {e}"

    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /price ───────────────────────────────────────────────────────────────────

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(DEXSCREENER_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        pairs = data.get("pairs", [])
        if not pairs:
            await update.message.reply_text("No wRTC trading pairs found.")
            return

        # Prefer Raydium pair
        pair = next((p for p in pairs if p.get("dexId") == "raydium"), pairs[0])

        price_usd = float(pair.get("priceUsd", 0))
        price_sol = pair.get("priceNative", "N/A")
        change_24h = pair.get("priceChange", {}).get("h24", 0)
        liquidity = pair.get("liquidity", {}).get("usd", 0)
        volume_24h = pair.get("volume", {}).get("h24", 0)
        url = pair.get("url", "https://dexscreener.com")

        text = (
            f"*wRTC Market Stats*\n\n"
            f"Price: `${price_usd:.6f}`\n"
            f"SOL: `{price_sol} SOL`\n"
            f"24h Change: `{change_24h}%`\n"
            f"Liquidity: `${liquidity:,.0f}`\n"
            f"24h Volume: `${volume_24h:,.0f}`\n\n"
            f"[DexScreener]({url})"
        )
    except Exception as e:
        text = f"Error fetching price: {e}"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


# ─── /address ─────────────────────────────────────────────────────────────────

async def address_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    addr = ks_mgr.get_address(user_id)
    if addr is None:
        await update.message.reply_text("No wallet. Use /create to make one.")
        return

    await update.message.reply_text(
        f"*Your RTC Address:*\n`{addr}`",
        parse_mode="Markdown",
    )


# ─── /export ──────────────────────────────────────────────────────────────────

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pub = ks_mgr.get_public_key(user_id)
    addr = ks_mgr.get_address(user_id)

    if pub is None:
        await update.message.reply_text("No wallet found. Use /create first.")
        return

    await update.message.reply_text(
        f"*Public Key:*\n`{pub}`\n\n"
        f"*Address:*\n`{addr}`\n\n"
        f"You can share this safely. Never share your password.",
        parse_mode="Markdown",
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable")
        print("  export TELEGRAM_BOT_TOKEN='your_token_here'")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation: wallet creation
    create_conv = ConversationHandler(
        entry_points=[CommandHandler("create", create_start)],
        states={
            CREATE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_password)],
            CREATE_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, create_confirm)],
        },
        fallbacks=[CommandHandler("cancel", create_cancel)],
        per_user=True,
        per_chat=True,
    )

    # Conversation: send RTC
    send_conv = ConversationHandler(
        entry_points=[CommandHandler("send", send_start)],
        states={
            SEND_ADDR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, send_addr)],
            SEND_AMOUNT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, send_amount)],
            SEND_MEMO:     [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_memo),
                CommandHandler("skip", send_memo),
            ],
            SEND_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_password)],
        },
        fallbacks=[CommandHandler("cancel", send_cancel)],
        per_user=True,
        per_chat=True,
    )

    # Register handlers (order matters)
    app.add_handler(create_conv)
    app.add_handler(send_conv)
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("address", address_cmd))
    app.add_handler(CommandHandler("export", export_cmd))

    print("RustChain Wallet Bot starting...")
    print(f"API: {RUSTCHAIN_API}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
