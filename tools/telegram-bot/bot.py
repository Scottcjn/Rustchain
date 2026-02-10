import os
import json
import time
import hashlib
import base64
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv
from mnemonic import Mnemonic
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("RTC_TELEGRAM_TOKEN")
NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://50.28.86.131")
# Data directory for bot wallets (different from CLI for security/separation)
BOT_DATA_DIR = Path.home() / ".rustchain" / "bot_wallets"
BOT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# KDF iterations from CLI
KDF_ITERATIONS = 100000

# Conversation states
SET_PASSWORD, CREATE_IMPORT, ENTER_MNEMONIC, SEND_TO, SEND_AMOUNT, CONFIRM_SEND = range(6)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================================================
# WALLET CRYPTO LOGIC (Mirroring CLI)
# =============================================================================

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode())

def encrypt_data(data: bytes, password: str) -> dict:
    salt = os.urandom(16)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "salt": base64.b64encode(salt).decode(),
        "kdf": "pbkdf2",
        "iterations": KDF_ITERATIONS
    }

def decrypt_data(encrypted: dict, password: str) -> bytes:
    try:
        salt = base64.b64decode(encrypted["salt"])
        nonce = base64.b64decode(encrypted["nonce"])
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        key = derive_key(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Invalid password or corrupted data")

def get_address_from_pubkey(pubkey_hex: str) -> str:
    pubkey_hash = hashlib.sha256(bytes.fromhex(pubkey_hex)).hexdigest()[:40]
    return f"RTC{pubkey_hash}"

class BotWalletManager:
    def __init__(self, user_id: int):
        self.user_id = str(user_id)
        self.path = BOT_DATA_DIR / f"{self.user_id}.json"

    def exists(self) -> bool:
        return self.path.exists()

    def create(self, password: str, mnemonic_str: str = None) -> tuple:
        mnemo = Mnemonic("english")
        if mnemonic_str:
            if not mnemo.check(mnemonic_str):
                raise ValueError("Invalid seed phrase")
        else:
            mnemonic_str = mnemo.generate(strength=256)

        seed = mnemo.to_seed(mnemonic_str)
        sk = SigningKey(seed[:32])
        vk = sk.verify_key
        pubkey_hex = vk.encode().hex()
        address = get_address_from_pubkey(pubkey_hex)
        
        wallet_data = {
            "address": address,
            "public_key": pubkey_hex,
            "encrypted_private_key": encrypt_data(sk.encode(), password)
        }
        
        with open(self.path, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        os.chmod(self.path, 0o600)
        return address, mnemonic_str

    def get_info(self) -> dict:
        with open(self.path, 'r') as f:
            return json.load(f)

    def load_private_key(self, password: str) -> SigningKey:
        data = self.get_info()
        sk_bytes = decrypt_data(data["encrypted_private_key"], password)
        return SigningKey(sk_bytes)

# =============================================================================
# BOT HANDLERS
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wm = BotWalletManager(user.id)
    
    if wm.exists():
        info = wm.get_info()
        await update.message.reply_text(
            f"Welcome back, {user.first_name}! 🎩\n\n"
            f"Your RTC Address:\n`{info['address']}`\n\n"
            "Use /balance, /history, or /send.",
            parse_mode="Markdown"
        )
    else:
        reply_keyboard = [["Create New Wallet", "Import Mnemonic"]]
        await update.message.reply_text(
            f"Hello {user.first_name}! I am the RustChain Wallet Bot. 🧱\n\n"
            "I don't see a wallet linked to your Telegram account. "
            "Would you like to create a new one or import an existing mnemonic?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
        )
        return CREATE_IMPORT

async def create_import_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    context.user_data["choice"] = choice
    await update.message.reply_text(
        "Please set an encryption password for your wallet. "
        "This will be required to send transactions.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_PASSWORD

async def set_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    user_id = update.effective_user.id
    wm = BotWalletManager(user_id)
    
    if context.user_data["choice"] == "Create New Wallet":
        address, mnemonic = wm.create(password)
        await update.message.reply_text(
            "✅ Wallet created successfully!\n\n"
            f"Your Address: `{address}`\n\n"
            "**IMPORTANT: WRITE DOWN YOUR 24-WORD SEED PHRASE:**\n"
            f"`{mnemonic}`\n\n"
            "Delete this message after saving it. Anyone with these words can access your funds!",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        context.user_data["password"] = password
        await update.message.reply_text("Please enter your 24-word seed phrase:")
        return ENTER_MNEMONIC

async def enter_mnemonic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mnemonic = update.message.text.strip().lower()
    password = context.user_data["password"]
    user_id = update.effective_user.id
    wm = BotWalletManager(user_id)
    
    try:
        address, _ = wm.create(password, mnemonic)
        await update.message.reply_text(
            f"✅ Wallet imported successfully!\n\nYour Address: `{address}`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Error importing: {str(e)}. Please try again or /cancel.")
        return ENTER_MNEMONIC

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wm = BotWalletManager(user_id)
    if not wm.exists():
        await update.message.reply_text("You don't have a wallet yet. Use /start to create one.")
        return

    address = wm.get_info()["address"]
    try:
        resp = requests.get(f"{NODE_URL}/wallet/balance?miner_id={address}", timeout=10, verify=False)
        if resp.status_code == 200:
            bal = resp.json().get("amount_rtc", 0)
            await update.message.reply_text(f"💰 **Balance**\n`{address}`\n\n**{bal:.8f} RTC**", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Error: Node returned status " + str(resp.status_code))
    except Exception as e:
        await update.message.reply_text(f"❌ Connection error: {str(e)}")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Node API doesn't have a dedicated /history but we can infer from ledger or list
    # For now, let's just show a placeholder or basic info
    await update.message.reply_text("📜 Transaction history is being indexed. Check the explorer for now: https://50.28.86.131/explorer")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(f"{NODE_URL}/api/stats", timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            epoch = data.get("epoch", 0)
            miners = data.get("total_miners", 0)
            await update.message.reply_text(
                f"📊 **RustChain Stats**\n\n"
                f"Current Epoch: `{epoch}`\n"
                f"Active Miners: `{miners}`\n"
                "Reference Rate: `$0.10 USD / 1 RTC`",
                parse_mode="Markdown"
            )
    except Exception as e:
        await update.message.reply_text("❌ Could not fetch stats.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# =============================================================================
# SEND FLOW
# =============================================================================

async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wm = BotWalletManager(user_id)
    if not wm.exists():
        await update.message.reply_text("You don't have a wallet yet. Use /start.")
        return ConversationHandler.END
    
    await update.message.reply_text("Who are you sending RTC to? Enter address (RTC...):")
    return SEND_TO

async def send_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["recipient"] = update.message.text.strip()
    await update.message.reply_text("How much RTC would you like to send?")
    return SEND_AMOUNT

async def send_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        context.user_data["amount"] = amount
        await update.message.reply_text(
            f"Confirm sending **{amount} RTC** to `{context.user_data['recipient']}`?\n\n"
            "Enter your wallet password to sign and send:",
            parse_mode="Markdown"
        )
        return CONFIRM_SEND
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number:")
        return SEND_AMOUNT

async def confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    user_id = update.effective_user.id
    wm = BotWalletManager(user_id)
    
    try:
        info = wm.get_info()
        sk = wm.load_private_key(password)
        
        recipient = context.user_data["recipient"]
        amount = context.user_data["amount"]
        nonce = int(time.time() * 1000)
        
        tx_data = {
            "from": info["address"],
            "to": recipient,
            "amount": amount,
            "memo": "Sent via Telegram Bot",
            "nonce": nonce
        }
        
        message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
        signature = sk.sign(message).signature.hex()
        
        payload = {
            "from_address": info["address"],
            "to_address": recipient,
            "amount_rtc": amount,
            "nonce": nonce,
            "signature": signature,
            "public_key": info["public_key"],
            "memo": "Sent via Telegram Bot"
        }
        
        resp = requests.post(f"{NODE_URL}/wallet/transfer/signed", json=payload, timeout=15, verify=False)
        result = resp.json()
        
        if resp.status_code == 200 and result.get("ok"):
            await update.message.reply_text(
                f"✅ **Success!** Transaction sent.\n\n"
                f"Amount: `{amount} RTC` to `{recipient}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown node error')}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    return ConversationHandler.END

def main():
    if not TELEGRAM_TOKEN:
        print("Error: RTC_TELEGRAM_TOKEN not found in .env")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Wallet setup conversation
    wallet_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CREATE_IMPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_import_choice)],
            SET_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_password)],
            ENTER_MNEMONIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_mnemonic)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Send conversation
    send_conv = ConversationHandler(
        entry_points=[CommandHandler("send", send_start)],
        states={
            SEND_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_to)],
            SEND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_amount)],
            CONFIRM_SEND: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(wallet_conv)
    application.add_handler(send_conv)
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("price", price))

    print("Bot started...")
    application.run_polling()

if __name__ == "__main__":
    main()
