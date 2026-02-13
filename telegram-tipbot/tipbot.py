#!/usr/bin/env python3
"""
RustChain Telegram Tip Bot
Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/31

Features:
- /tip @user <amount> - Send RTC to another user
- /balance - Check your RTC balance
- /deposit - Show your RTC wallet address
- /withdraw <address> <amount> - Withdraw to external wallet
- /leaderboard - Top RTC holders in the group
- /rain <amount> - Split RTC among recent active users

All transfers are on-chain via /wallet/transfer/signed endpoint.
Ed25519 signed transactions (not mock signatures).
"""

import os
import json
import time
import logging
import hashlib
import base64
import secrets
import re
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_DOWN

import httpx
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import Base64Encoder, HexEncoder
from nacl.secret import SecretBox
from nacl.exceptions import CryptoError
from nacl.utils import random as nacl_random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Configuration
NODE_URL = "https://50.28.86.131"
BOT_TOKEN = os.environ.get("RUSTCHAIN_BOT_TOKEN", "")
BOT_SECRET = os.environ.get("RUSTCHAIN_BOT_SECRET", "")
DATA_DIR = Path(__file__).parent / "data"
WALLETS_FILE = DATA_DIR / "wallets.json"
ACTIVITY_FILE = DATA_DIR / "activity.json"

# TLS / trust settings (fail-closed by default)
HTTP_VERIFY_SSL = os.environ.get("RUSTCHAIN_HTTP_VERIFY", "true").strip().lower() not in ("0", "false", "no")
HTTP_CA_BUNDLE = os.environ.get("RUSTCHAIN_HTTP_CA_BUNDLE", "").strip() or None

# Wallet encryption key (recommended; protects custodial private keys at rest)
# Accept either hex(64) or base64(32 bytes).
WALLET_ENC_KEY = os.environ.get("RUSTCHAIN_WALLET_ENC_KEY", "").strip() or os.environ.get("RUSTCHAIN_BOT_KEY_ENC_KEY", "").strip()

# Rate limiting
MIN_TIP_AMOUNT = 0.001  # Minimum tip in RTC
MAX_TIP_AMOUNT = 10.0   # Require confirmation above this
RATE_LIMIT_SECONDS = 10  # Seconds between tips per user

PENDING_TTL_SECONDS = 300  # confirmation window for risky actions
STRONG_WALLET_RE = re.compile(r"^[0-9a-fA-F]{40}RTC$")

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def _parse_secretbox_key(raw: str) -> Optional[bytes]:
    raw = (raw or "").strip()
    if not raw:
        return None
    # hex(64 chars) -> 32 bytes
    if re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        return bytes.fromhex(raw)
    # base64 -> 32 bytes
    try:
        b = base64.b64decode(raw, validate=True)
        if len(b) == SecretBox.KEY_SIZE:
            return b
    except Exception:
        pass
    raise ValueError("Invalid RUSTCHAIN_WALLET_ENC_KEY: provide hex(64) or base64(32 bytes).")


_SECRETBOX_KEY = _parse_secretbox_key(WALLET_ENC_KEY) if WALLET_ENC_KEY else None


def _get_verify_setting() -> object:
    # httpx accepts bool or path to CA bundle.
    if HTTP_CA_BUNDLE:
        return HTTP_CA_BUNDLE
    return HTTP_VERIFY_SSL


def _encrypt_private_key_hex(private_key_hex: str) -> str:
    if not _SECRETBOX_KEY:
        raise RuntimeError("Wallet encryption key not configured (RUSTCHAIN_WALLET_ENC_KEY).")
    box = SecretBox(_SECRETBOX_KEY)
    nonce = nacl_random(SecretBox.NONCE_SIZE)
    ct = box.encrypt(bytes.fromhex(private_key_hex), nonce)
    return "sbx1:" + base64.b64encode(ct).decode()


def _decrypt_private_key_to_hex(enc: str) -> str:
    if enc is None:
        raise RuntimeError("Missing private key material.")
    if enc.startswith("sbx1:"):
        if not _SECRETBOX_KEY:
            raise RuntimeError("Encrypted wallets present but RUSTCHAIN_WALLET_ENC_KEY is not set.")
        box = SecretBox(_SECRETBOX_KEY)
        try:
            raw = base64.b64decode(enc[len("sbx1:"):])
            pt = box.decrypt(raw)
            return pt.hex()
        except (CryptoError, ValueError) as e:
            raise RuntimeError(f"Failed to decrypt wallet key: {e}")
    # legacy plaintext hex
    return enc


def _parse_rtc_amount_to_i64(s: str) -> int:
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError("Invalid amount.")
    d = d.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    if d <= 0:
        raise ValueError("Amount must be positive.")
    return int(d * Decimal(1_000_000))


def _i64_to_rtc(i64: int) -> str:
    return f"{Decimal(i64) / Decimal(1_000_000):.6f}"


@dataclass
class UserWallet:
    """User's custodial wallet."""
    telegram_id: int
    username: str
    miner_id: str  # RTC wallet address
    # Prefer encrypted storage at rest. `private_key_hex` is legacy plaintext.
    private_key_hex: Optional[str] = None
    private_key_enc: Optional[str] = None
    created_at: str
    nonce: int = 0
    known_destinations: Optional[List[str]] = None


class WalletManager:
    """Manages user wallets with Ed25519 keypairs."""
    
    def __init__(self):
        self.wallets: Dict[int, UserWallet] = {}
        self.load_wallets()
    
    def load_wallets(self):
        """Load wallets from disk."""
        if WALLETS_FILE.exists():
            try:
                with open(WALLETS_FILE) as f:
                    data = json.load(f)
                    for tid, wallet_data in data.items():
                        w = UserWallet(**wallet_data)
                        # Refuse to run if encrypted wallets exist but the key is missing.
                        if w.private_key_enc and not _SECRETBOX_KEY:
                            raise RuntimeError("wallets.json contains encrypted keys but RUSTCHAIN_WALLET_ENC_KEY is not set.")
                        self.wallets[int(tid)] = w
            except Exception as e:
                logger.error(f"Failed to load wallets: {e}")
    
    def save_wallets(self):
        """Save wallets to disk."""
        try:
            with open(WALLETS_FILE, 'w') as f:
                data = {}
                for tid, w in self.wallets.items():
                    wd = asdict(w)
                    if _SECRETBOX_KEY:
                        # Ensure we never persist plaintext when encryption key is configured.
                        if wd.get("private_key_hex") and not wd.get("private_key_enc"):
                            wd["private_key_enc"] = _encrypt_private_key_hex(wd["private_key_hex"])
                        wd["private_key_hex"] = None
                    data[str(tid)] = wd
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save wallets: {e}")
    
    def get_or_create_wallet(self, telegram_id: int, username: str) -> UserWallet:
        """Get existing wallet or create new one for user."""
        if telegram_id in self.wallets:
            return self.wallets[telegram_id]
        
        # Generate an Ed25519 keypair for this user.
        # If BOT_SECRET is provided, the keypair is deterministic (recoverable);
        # otherwise we generate a random seed and persist it (recommended with encryption at rest).
        if BOT_SECRET:
            seed_material = f"{BOT_SECRET}:{telegram_id}".encode()
            seed = hashlib.sha256(seed_material).digest()
        else:
            logger.warning("RUSTCHAIN_BOT_SECRET is not set; generating random wallet keys (persisted to wallets.json).")
            seed = secrets.token_bytes(32)
        
        # Create Ed25519 signing key from seed
        signing_key = SigningKey(seed)
        verify_key = signing_key.verify_key
        
        # Derive miner_id from public key
        pubkey_hex = verify_key.encode(encoder=HexEncoder).decode()
        miner_id = f"{pubkey_hex[:40]}RTC"
        
        wallet = UserWallet(
            telegram_id=telegram_id,
            username=username or f"user_{telegram_id}",
            miner_id=miner_id,
            private_key_hex=None if _SECRETBOX_KEY else signing_key.encode(encoder=HexEncoder).decode(),
            private_key_enc=_encrypt_private_key_hex(signing_key.encode(encoder=HexEncoder).decode()) if _SECRETBOX_KEY else None,
            created_at=datetime.utcnow().isoformat(),
            nonce=0
        )
        
        self.wallets[telegram_id] = wallet
        self.save_wallets()
        logger.info(f"Created wallet for user {telegram_id}: {miner_id}")
        
        return wallet
    
    def get_signing_key(self, wallet: UserWallet) -> SigningKey:
        """Get signing key from wallet."""
        if wallet.private_key_enc:
            return SigningKey(bytes.fromhex(_decrypt_private_key_to_hex(wallet.private_key_enc)))
        if wallet.private_key_hex:
            return SigningKey(bytes.fromhex(wallet.private_key_hex))
        raise RuntimeError("Wallet has no usable private key material.")
    
    def increment_nonce(self, telegram_id: int) -> int:
        """Increment and return the next nonce for a user."""
        if telegram_id in self.wallets:
            self.wallets[telegram_id].nonce += 1
            self.save_wallets()
            return self.wallets[telegram_id].nonce
        return 0


class RustChainAPI:
    """Interface to RustChain node API."""
    
    def __init__(self):
        self.client = httpx.Client(verify=_get_verify_setting(), timeout=30.0)
    
    def get_balance(self, miner_id: str) -> Optional[float]:
        """Get RTC balance for a wallet."""
        try:
            resp = self.client.get(f"{NODE_URL}/wallet/balance", params={"miner_id": miner_id})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("amount_rtc", 0.0)
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
        return None
    
    def transfer_signed(self, from_id: str, to_id: str, amount_rtc: float, 
                       signing_key: SigningKey, nonce: int) -> Dict:
        """Execute a signed transfer."""
        amount_i64 = int(amount_rtc * 1_000_000)  # 6 decimal places
        
        # Create message to sign
        message = f"{from_id}:{to_id}:{amount_i64}:{nonce}".encode()
        
        # Sign with Ed25519
        signed = signing_key.sign(message)
        signature_b64 = Base64Encoder.encode(signed.signature).decode()
        
        # Submit transfer
        try:
            resp = self.client.post(
                f"{NODE_URL}/wallet/transfer/signed",
                json={
                    "from": from_id,
                    "to": to_id,
                    "amount_i64": amount_i64,
                    "nonce": nonce,
                    "signature": signature_b64
                }
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_epoch(self) -> Optional[Dict]:
        """Get current epoch info."""
        try:
            resp = self.client.get(f"{NODE_URL}/epoch")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Failed to get epoch: {e}")
        return None


class ActivityTracker:
    """Track recent activity for /rain command."""
    
    def __init__(self):
        self.activity: Dict[int, Dict[int, float]] = {}  # chat_id -> {user_id: timestamp}
        self.load_activity()
    
    def load_activity(self):
        if ACTIVITY_FILE.exists():
            try:
                with open(ACTIVITY_FILE) as f:
                    data = json.load(f)
                    self.activity = {int(k): {int(uk): uv for uk, uv in v.items()} 
                                    for k, v in data.items()}
            except:
                pass
    
    def save_activity(self):
        try:
            with open(ACTIVITY_FILE, 'w') as f:
                json.dump(self.activity, f)
        except:
            pass
    
    def record_activity(self, chat_id: int, user_id: int):
        """Record user activity in a chat."""
        if chat_id not in self.activity:
            self.activity[chat_id] = {}
        self.activity[chat_id][user_id] = time.time()
        self.save_activity()
    
    def get_recent_users(self, chat_id: int, minutes: int = 60) -> List[int]:
        """Get users active in the last N minutes."""
        if chat_id not in self.activity:
            return []
        
        cutoff = time.time() - (minutes * 60)
        return [uid for uid, ts in self.activity.get(chat_id, {}).items() if ts > cutoff]


# Global instances
wallet_manager = WalletManager()
api = RustChainAPI()
activity_tracker = ActivityTracker()
rate_limits: Dict[int, float] = {}
pending_actions: Dict[int, Dict[str, object]] = {}


def check_rate_limit(user_id: int) -> bool:
    """Check if user is rate limited. Returns True if allowed."""
    now = time.time()
    if user_id in rate_limits:
        if now - rate_limits[user_id] < RATE_LIMIT_SECONDS:
            return False
    rate_limits[user_id] = now
    return True


def _is_valid_miner_id(s: str) -> bool:
    return bool(STRONG_WALLET_RE.fullmatch((s or "").strip()))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    
    await update.message.reply_text(
        f"🦀 Welcome to RustChain Tip Bot!\n\n"
        f"Your wallet: `{wallet.miner_id}`\n\n"
        f"Commands:\n"
        f"/tip @user <amount> - Send RTC\n"
        f"/balance - Check balance\n"
        f"/deposit - Get deposit address\n"
        f"/withdraw <address> <amount> - Withdraw RTC\n"
        f"/leaderboard - Top holders\n"
        f"/rain <amount> - Split among active users\n",
        parse_mode='Markdown'
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command."""
    user = update.effective_user
    wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    
    bal = api.get_balance(wallet.miner_id)
    if bal is not None:
        await update.message.reply_text(f"💰 Balance: `{bal:.6f} RTC`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed to fetch balance. Try again later.")


async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deposit command."""
    user = update.effective_user
    wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    
    await update.message.reply_text(
        f"📥 Deposit Address:\n\n`{wallet.miner_id}`\n\n"
        f"Send RTC to this address to fund your tip wallet.",
        parse_mode='Markdown'
    )


async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tip command."""
    user = update.effective_user
    
    # Check rate limit
    if not check_rate_limit(user.id):
        await update.message.reply_text(f"⏳ Please wait {RATE_LIMIT_SECONDS}s between tips.")
        return
    
    # Parse arguments
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /tip @username <amount>")
        return
    
    # Get recipient
    target_text = context.args[0]
    if target_text.startswith('@'):
        target_username = target_text[1:]
    else:
        await update.message.reply_text("Please mention the user with @username")
        return
    
    # Get amount
    try:
        amount_i64 = _parse_rtc_amount_to_i64(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid amount. Use a number like 1.5")
        return
    
    # Validate amount
    min_i64 = int(Decimal(str(MIN_TIP_AMOUNT)) * Decimal(1_000_000))
    max_i64 = int(Decimal(str(MAX_TIP_AMOUNT)) * Decimal(1_000_000))
    if amount_i64 < min_i64:
        await update.message.reply_text(f"Minimum tip: {MIN_TIP_AMOUNT} RTC")
        return
    
    if amount_i64 > max_i64:
        pending_actions[user.id] = {
            "type": "tip",
            "to_username": target_username,
            "amount_i64": amount_i64,
            "created_at": time.time(),
        }
        await update.message.reply_text(f"⚠️ Large tip! Reply with /confirm_tip within {PENDING_TTL_SECONDS}s to proceed.")
        return
    
    # Get sender wallet
    sender_wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    
    # Check balance
    bal = api.get_balance(sender_wallet.miner_id)
    amount_rtc = float(Decimal(amount_i64) / Decimal(1_000_000))
    if bal is None or bal < amount_rtc:
        await update.message.reply_text(f"❌ Insufficient balance. You have {bal or 0:.6f} RTC")
        return
    
    # Find recipient (they need to have interacted with the bot)
    recipient = None
    for tid, wallet in wallet_manager.wallets.items():
        if wallet.username.lower() == target_username.lower():
            recipient = wallet
            break
    
    if not recipient:
        await update.message.reply_text(
            f"❌ User @{target_username} hasn't set up their wallet yet.\n"
            f"They need to use /start first."
        )
        return
    
    # Execute transfer
    signing_key = wallet_manager.get_signing_key(sender_wallet)
    nonce = wallet_manager.increment_nonce(user.id)
    
    result = api.transfer_signed(
        sender_wallet.miner_id,
        recipient.miner_id,
        amount_rtc,
        signing_key,
        nonce
    )
    
    if result.get("success"):
        await update.message.reply_text(
            f"✅ Sent {_i64_to_rtc(amount_i64)} RTC to @{target_username}!\n"
            f"TX: `{result.get('tx_hash', 'confirmed')}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ Transfer failed: {result.get('error', 'Unknown error')}")


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /withdraw command."""
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /withdraw <address> <amount>")
        return
    
    address = context.args[0]
    try:
        amount_i64 = _parse_rtc_amount_to_i64(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return

    if not _is_valid_miner_id(address):
        await update.message.reply_text("Invalid destination wallet format.")
        return
    
    min_i64 = int(Decimal(str(MIN_TIP_AMOUNT)) * Decimal(1_000_000))
    if amount_i64 < min_i64:
        await update.message.reply_text(f"Minimum withdrawal: {MIN_TIP_AMOUNT} RTC")
        return
    
    # Get wallet
    wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    
    # Check balance
    bal = api.get_balance(wallet.miner_id)
    amount_rtc = float(Decimal(amount_i64) / Decimal(1_000_000))
    if bal is None or bal < amount_rtc:
        await update.message.reply_text(f"❌ Insufficient balance. You have {bal or 0:.6f} RTC")
        return

    # Require confirmation for first-time destinations.
    dests = getattr(wallet, "known_destinations", None)
    if dests is None:
        wallet.known_destinations = []
        dests = wallet.known_destinations
    if address not in dests:
        pending_actions[user.id] = {
            "type": "withdraw",
            "to": address,
            "amount_i64": amount_i64,
            "created_at": time.time(),
        }
        await update.message.reply_text(f"⚠️ First time withdrawing to this address. Reply with /confirm_withdraw within {PENDING_TTL_SECONDS}s to proceed.")
        return
    
    # Execute withdrawal
    signing_key = wallet_manager.get_signing_key(wallet)
    nonce = wallet_manager.increment_nonce(user.id)
    
    result = api.transfer_signed(wallet.miner_id, address, amount_rtc, signing_key, nonce)
    
    if result.get("success"):
        await update.message.reply_text(
            f"✅ Withdrew {_i64_to_rtc(amount_i64)} RTC to `{address}`\n"
            f"TX: `{result.get('tx_hash', 'confirmed')}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ Withdrawal failed: {result.get('error')}")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command."""
    # Get balances for all wallets
    balances = []
    for tid, wallet in wallet_manager.wallets.items():
        bal = api.get_balance(wallet.miner_id)
        if bal and bal > 0:
            balances.append((wallet.username, bal))
    
    # Sort by balance
    balances.sort(key=lambda x: x[1], reverse=True)
    
    if not balances:
        await update.message.reply_text("No balances found yet!")
        return
    
    # Format leaderboard
    lines = ["🏆 RTC Leaderboard\n"]
    for i, (username, bal) in enumerate(balances[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} @{username}: {bal:.4f} RTC")
    
    await update.message.reply_text("\n".join(lines))


async def rain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rain command - distribute RTC to recent active users."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /rain <total_amount>")
        return
    
    try:
        total_amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return
    
    if total_amount < MIN_TIP_AMOUNT * 2:
        await update.message.reply_text(f"Minimum rain: {MIN_TIP_AMOUNT * 2} RTC")
        return
    
    # Get sender wallet
    sender_wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    
    # Check balance
    bal = api.get_balance(sender_wallet.miner_id)
    if bal is None or bal < total_amount:
        await update.message.reply_text(f"❌ Insufficient balance. You have {bal or 0:.6f} RTC")
        return
    
    # Get recent active users (excluding sender)
    active_users = [uid for uid in activity_tracker.get_recent_users(chat_id, 60) 
                   if uid != user.id and uid in wallet_manager.wallets]
    
    if not active_users:
        await update.message.reply_text("❌ No active users to rain on! Need users with wallets who've been active recently.")
        return
    
    # Calculate split
    per_user = total_amount / len(active_users)
    if per_user < MIN_TIP_AMOUNT:
        await update.message.reply_text(f"❌ Amount too small to split among {len(active_users)} users.")
        return
    
    # Execute transfers
    signing_key = wallet_manager.get_signing_key(sender_wallet)
    success_count = 0
    
    for uid in active_users:
        recipient = wallet_manager.wallets.get(uid)
        if recipient:
            nonce = wallet_manager.increment_nonce(user.id)
            result = api.transfer_signed(sender_wallet.miner_id, recipient.miner_id, per_user, signing_key, nonce)
            if result.get("success"):
                success_count += 1
    
    await update.message.reply_text(
        f"🌧️ Rained {total_amount:.4f} RTC!\n"
        f"Split {per_user:.6f} RTC to {success_count}/{len(active_users)} users"
    )


async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track user activity for rain command."""
    if update.effective_user and update.effective_chat:
        activity_tracker.record_activity(update.effective_chat.id, update.effective_user.id)


async def confirm_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending = pending_actions.get(user.id)
    if not pending or pending.get("type") != "tip":
        await update.message.reply_text("No pending tip to confirm.")
        return
    if time.time() - float(pending.get("created_at", 0)) > PENDING_TTL_SECONDS:
        pending_actions.pop(user.id, None)
        await update.message.reply_text("Pending tip expired.")
        return

    target_username = str(pending["to_username"])
    amount_i64 = int(pending["amount_i64"])
    pending_actions.pop(user.id, None)

    sender_wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    recipient = None
    for _, wallet in wallet_manager.wallets.items():
        if wallet.username.lower() == target_username.lower():
            recipient = wallet
            break
    if not recipient:
        await update.message.reply_text(f"❌ User @{target_username} hasn't set up their wallet yet. They need to use /start first.")
        return

    amount_rtc = float(Decimal(amount_i64) / Decimal(1_000_000))
    bal = api.get_balance(sender_wallet.miner_id)
    if bal is None or bal < amount_rtc:
        await update.message.reply_text(f"❌ Insufficient balance. You have {bal or 0:.6f} RTC")
        return

    signing_key = wallet_manager.get_signing_key(sender_wallet)
    nonce = wallet_manager.increment_nonce(user.id)
    result = api.transfer_signed(sender_wallet.miner_id, recipient.miner_id, amount_rtc, signing_key, nonce)
    if result.get("success"):
        await update.message.reply_text(
            f"✅ Sent {_i64_to_rtc(amount_i64)} RTC to @{target_username}!\nTX: `{result.get('tx_hash', 'confirmed')}`",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(f"❌ Transfer failed: {result.get('error', 'Unknown error')}")


async def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending = pending_actions.get(user.id)
    if not pending or pending.get("type") != "withdraw":
        await update.message.reply_text("No pending withdraw to confirm.")
        return
    if time.time() - float(pending.get("created_at", 0)) > PENDING_TTL_SECONDS:
        pending_actions.pop(user.id, None)
        await update.message.reply_text("Pending withdraw expired.")
        return

    address = str(pending["to"])
    amount_i64 = int(pending["amount_i64"])
    pending_actions.pop(user.id, None)

    if not _is_valid_miner_id(address):
        await update.message.reply_text("Invalid destination wallet format.")
        return

    wallet = wallet_manager.get_or_create_wallet(user.id, user.username)
    amount_rtc = float(Decimal(amount_i64) / Decimal(1_000_000))
    bal = api.get_balance(wallet.miner_id)
    if bal is None or bal < amount_rtc:
        await update.message.reply_text(f"❌ Insufficient balance. You have {bal or 0:.6f} RTC")
        return

    signing_key = wallet_manager.get_signing_key(wallet)
    nonce = wallet_manager.increment_nonce(user.id)
    result = api.transfer_signed(wallet.miner_id, address, amount_rtc, signing_key, nonce)
    if result.get("success"):
        if wallet.known_destinations is None:
            wallet.known_destinations = []
        if address not in wallet.known_destinations:
            wallet.known_destinations.append(address)
            wallet_manager.save_wallets()
        await update.message.reply_text(
            f"✅ Withdrew {_i64_to_rtc(amount_i64)} RTC to `{address}`\nTX: `{result.get('tx_hash', 'confirmed')}`",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(f"❌ Withdrawal failed: {result.get('error')}")


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        print("Error: RUSTCHAIN_BOT_TOKEN environment variable not set")
        print("Get a token from @BotFather on Telegram")
        return
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("deposit", deposit))
    app.add_handler(CommandHandler("tip", tip))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("rain", rain))
    app.add_handler(CommandHandler("confirm_tip", confirm_tip))
    app.add_handler(CommandHandler("confirm_withdraw", confirm_withdraw))
    
    # Track activity for all messages
    app.add_handler(MessageHandler(filters.ALL, track_activity), group=1)
    
    # Start polling
    print("🦀 RustChain Tip Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
