#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @xiangshangsir (大龙虾 AI)
# BCOS-Tier: L1
# Bounty: #27 - Telegram Bot for RTC Wallet (75 RTC)
"""
RustChain Telegram Wallet Bot
==============================

Telegram bot for managing RTC wallet:
- /start - Welcome message
- /balance - Check wallet balance
- /send <address> <amount> - Send RTC
- /history - Recent transactions
- /price - Current RTC stats
- /create - Create new wallet (via DM)

Secure key storage with encryption.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from typing import Optional, Dict
from pathlib import Path
from cryptography.fernet import Fernet
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
import requests

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# ============= 配置 =============

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
RUSTCHAIN_API = os.environ.get("RUSTCHAIN_API", "https://rustchain.org")
DB_PATH = Path(os.environ.get("WALLET_DB", "wallet_bot.db"))
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")  # 32-byte URL-safe base64

logging.basicConfig(
    format='%(asctime)s [TelegramBot] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 对话状态
CREATE_WALLET, SEND_ADDRESS, SEND_AMOUNT, SEND_CONFIRM = range(4)


class WalletDatabase:
    """加密钱包数据库"""
    
    def __init__(self, db_path: Path, encryption_key: str):
        self.db_path = db_path
        self.cipher = Fernet(encryption_key.encode()) if encryption_key else None
        self._init_tables()
    
    def _init_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    user_id INTEGER PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    encrypted_private_key TEXT,
                    created_at INTEGER NOT NULL,
                    last_accessed INTEGER
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    tx_hash TEXT,
                    amount REAL,
                    direction TEXT,  -- sent, received
                    address TEXT,
                    created_at INTEGER NOT NULL
                )
            """)
            
            conn.commit()
    
    def _encrypt(self, data: bytes) -> str:
        if self.cipher:
            return self.cipher.encrypt(data).decode()
        return data.hex()
    
    def _decrypt(self, data: str) -> bytes:
        if self.cipher:
            return self.cipher.decrypt(data.encode())
        return bytes.fromhex(data)
    
    def create_wallet(self, user_id: int) -> tuple[str, str]:
        """创建新钱包，返回 (public_key, private_key)"""
        # 生成 Ed25519 密钥对
        private_key = SigningKey.generate()
        public_key = private_key.verify_key
        
        public_hex = public_key.encode(HexEncoder).decode()
        private_hex = private_key.encode(HexEncoder).decode()
        
        # 存储加密的私钥
        encrypted_private = self._encrypt(private_hex.encode())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO wallets 
                (user_id, public_key, encrypted_private_key, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id, public_hex, encrypted_private,
                int(time.time()), int(time.time())
            ))
            conn.commit()
        
        return public_hex, private_hex
    
    def get_wallet(self, user_id: int) -> Optional[Dict]:
        """获取钱包信息"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM wallets WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return {
                "user_id": row[0],
                "public_key": row[1],
                "encrypted_private_key": row[2],
                "created_at": row[3],
                "last_accessed": row[4],
            }
    
    def get_private_key(self, user_id: int) -> Optional[str]:
        """解密获取私钥"""
        wallet = self.get_wallet(user_id)
        if not wallet:
            return None
        
        try:
            private_hex = self._decrypt(wallet["encrypted_private_key"]).decode()
            return private_hex
        except Exception as e:
            logger.error(f"Failed to decrypt private key: {e}")
            return None
    
    def add_transaction(self, user_id: int, tx_hash: str, amount: float,
                       direction: str, address: str):
        """记录交易"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO transactions 
                (user_id, tx_hash, amount, direction, address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, tx_hash, amount, direction, address,
                int(time.time())
            ))
            conn.commit()
    
    def get_transactions(self, user_id: int, limit: int = 10) -> list:
        """获取交易历史"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT * FROM transactions 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            
            return [
                {
                    "tx_hash": row[2],
                    "amount": row[3],
                    "direction": row[4],
                    "address": row[5],
                    "created_at": row[6],
                }
                for row in rows
            ]
    
    def update_last_accessed(self, user_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE wallets SET last_accessed = ? WHERE user_id = ?
            """, (int(time.time()), user_id))
            conn.commit()


class RustChainAPI:
    """RustChain API 客户端"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
    
    def get_balance(self, miner_id: str) -> Optional[float]:
        """查询余额"""
        try:
            resp = requests.get(
                f"{self.base_url}/wallet/balance",
                params={"miner_id": miner_id},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get("balance", 0))
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
        return None
    
    def send_rtc(self, from_wallet: str, to_address: str, amount: float,
                private_key: str) -> Optional[str]:
        """发送 RTC"""
        try:
            # 构建交易
            tx_data = {
                "from": from_wallet,
                "to": to_address,
                "amount": amount,
                "timestamp": int(time.time()),
            }
            
            # 使用 Ed25519 签名
            private_bytes = bytes.fromhex(private_key)
            signing_key = SigningKey(private_bytes)
            message = json.dumps(tx_data, sort_keys=True).encode()
            signature = signing_key.sign(message)
            
            tx_data["signature"] = signature.hex()
            
            # 提交交易
            resp = requests.post(
                f"{self.base_url}/wallet/send",
                json=tx_data,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("tx_hash")
        except Exception as e:
            logger.error(f"Failed to send RTC: {e}")
        return None
    
    def get_price(self) -> Optional[Dict]:
        """获取当前价格统计"""
        try:
            resp = requests.get(
                f"{self.base_url}/epoch",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "epoch": data.get("epoch"),
                    "total_supply": data.get("total_supply_rtc"),
                    "enrolled_miners": data.get("enrolled_miners"),
                    "epoch_pot": data.get("epoch_pot"),
                }
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
        return None
    
    def get_history(self, miner_id: str, limit: int = 10) -> list:
        """获取交易历史"""
        try:
            resp = requests.get(
                f"{self.base_url}/wallet/history",
                params={"miner_id": miner_id, "limit": limit},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json().get("transactions", [])
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
        return []


class TelegramBot:
    """Telegram 机器人主类"""
    
    def __init__(self, token: str):
        self.token = token
        self.db = None
        self.api = None
        self.app = None
    
    def initialize(self):
        """初始化数据库和 API"""
        # 如果没有加密密钥，生成一个（仅用于测试）
        encryption_key = ENCRYPTION_KEY
        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            logger.warning(f"Generated temporary encryption key: {encryption_key}")
        
        self.db = WalletDatabase(DB_PATH, encryption_key)
        self.api = RustChainAPI(RUSTCHAIN_API)
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/start - 欢迎消息"""
        user = update.effective_user
        wallet = self.db.get_wallet(user.id)
        
        if wallet:
            await update.message.reply_text(
                f"👋 欢迎回来，{user.first_name}!\n\n"
                f"你的钱包地址：\n`{wallet['public_key'][:32]}...`\n\n"
                f"可用命令:\n"
                "/balance - 查询余额\n"
                "/send - 发送 RTC\n"
                "/history - 交易历史\n"
                "/price - 价格统计\n"
                "/create - 创建新钱包",
                parse_mode='Markdown'
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔐 创建钱包", callback_data="create_wallet")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 欢迎使用 RustChain 钱包机器人，{user.first_name}!\n\n"
                "点击按钮创建你的钱包：",
                reply_markup=reply_markup
            )
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/balance - 查询余额"""
        user = update.effective_user
        wallet = self.db.get_wallet(user.id)
        
        if not wallet:
            await update.message.reply_text(
                "❌ 钱包不存在。请先使用 /create 创建钱包。"
            )
            return
        
        balance = self.api.get_balance(wallet['public_key'])
        
        if balance is not None:
            await update.message.reply_text(
                f"💰 余额查询\n\n"
                f"地址：`{wallet['public_key'][:32]}...`\n"
                f"余额：**{balance:.6f} RTC**",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ 查询失败，请稍后重试。")
    
    async def cmd_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/send - 发送 RTC"""
        user = update.effective_user
        wallet = self.db.get_wallet(user.id)
        
        if not wallet:
            await update.message.reply_text("❌ 钱包不存在。请先使用 /create 创建钱包。")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "📤 发送 RTC\n\n"
            "请输入收款地址："
        )
        return SEND_ADDRESS
    
    async def send_address_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理收款地址输入"""
        context.user_data['send_address'] = update.message.text.strip()
        
        await update.message.reply_text(
            "请输入发送金额（RTC）："
        )
        return SEND_AMOUNT
    
    async def send_amount_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理金额输入"""
        try:
            amount = float(update.message.text.strip())
            if amount <= 0:
                raise ValueError()
            context.user_data['send_amount'] = amount
        except:
            await update.message.reply_text("❌ 无效金额，请输入正数。")
            return SEND_AMOUNT
        
        # 确认交易
        address = context.user_data['send_address']
        amount = context.user_data['send_amount']
        
        keyboard = [
            [
                InlineKeyboardButton("✅ 确认发送", callback_data="confirm_send"),
                InlineKeyboardButton("❌ 取消", callback_data="cancel_send"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📤 确认交易\n\n"
            f"收款地址：`{address[:32]}...`\n"
            f"发送金额：**{amount:.6f} RTC**\n\n"
            f"请确认：",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return SEND_CONFIRM
    
    async def send_confirmed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """确认发送"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel_send":
            await query.edit_message_text("❌ 已取消发送。")
            return ConversationHandler.END
        
        # 执行发送
        user = update.effective_user
        wallet = self.db.get_wallet(user.id)
        private_key = self.db.get_private_key(user.id)
        
        if not private_key:
            await query.edit_message_text("❌ 钱包密钥错误。")
            return ConversationHandler.END
        
        address = context.user_data['send_address']
        amount = context.user_data['send_amount']
        
        tx_hash = self.api.send_rtc(
            wallet['public_key'],
            address,
            amount,
            private_key
        )
        
        if tx_hash:
            # 记录交易
            self.db.add_transaction(
                user.id, tx_hash, amount, "sent", address
            )
            
            await query.edit_message_text(
                f"✅ 发送成功!\n\n"
                f"金额：{amount:.6f} RTC\n"
                f"地址：`{address[:32]}...`\n"
                f"交易哈希：`{tx_hash[:32]}...`",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ 发送失败，请稍后重试。")
        
        return ConversationHandler.END
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/history - 交易历史"""
        user = update.effective_user
        wallet = self.db.get_wallet(user.id)
        
        if not wallet:
            await update.message.reply_text("❌ 钱包不存在。")
            return
        
        # 从本地数据库获取
        transactions = self.db.get_transactions(user.id, limit=10)
        
        if not transactions:
            # 尝试从 API 获取
            api_history = self.api.get_history(wallet['public_key'], limit=10)
            if api_history:
                transactions = api_history
        
        if not transactions:
            await update.message.reply_text("📭 暂无交易记录。")
            return
        
        # 格式化输出
        message = "📊 交易历史\n\n"
        for tx in transactions[:10]:
            direction = "➡️" if tx.get('direction') == 'sent' else "⬅️"
            amount = tx.get('amount', 0)
            tx_hash = tx.get('tx_hash', 'N/A')[:16] + "..."
            
            message += f"{direction} {amount:.6f} RTC\n"
            message += f"哈希：`{tx_hash}`\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/price - 价格统计"""
        stats = self.api.get_price()
        
        if stats:
            await update.message.reply_text(
                f"📈 RustChain 统计\n\n"
                f"当前 Epoch: **{stats.get('epoch')}**\n"
                f"总供应量：**{stats.get('total_supply', 0):,.0f} RTC**\n"
                f"注册矿工：**{stats.get('enrolled_miners', 0)}**\n"
                f"Epoch 奖池：**{stats.get('epoch_pot', 0):,.0f} RTC**",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ 获取统计失败。")
    
    async def cmd_create(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/create - 创建钱包"""
        user = update.effective_user
        
        # 检查是否私聊
        if update.effective_chat.type != 'private':
            keyboard = [[InlineKeyboardButton("💬 私信我创建", url=f"t.me/{user.username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔐 为了安全起见，钱包创建请在私信中进行。\n\n"
                "点击按钮私信我：",
                reply_markup=reply_markup
            )
            return
        
        # 检查是否已存在
        existing = self.db.get_wallet(user.id)
        if existing:
            await update.message.reply_text(
                "⚠️ 你已经有一个钱包了。\n\n"
                f"地址：`{existing['public_key'][:32]}...`"
            )
            return
        
        # 创建钱包
        public_key, private_key = self.db.create_wallet(user.id)
        
        # 发送私钥（仅一次！）
        await update.message.reply_text(
            f"✅ 钱包创建成功!\n\n"
            f"📍 钱包地址:\n`{public_key}`\n\n"
            f"🔑 私钥 (请妥善保存，仅显示一次):\n`{private_key}`\n\n"
            f"⚠️ **重要提示**:\n"
            f"- 不要将私钥告诉任何人\n"
            f"- 建议立即备份私钥到安全位置\n"
            f"- 丢失私钥 = 丢失资产",
            parse_mode='Markdown'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮点击"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "create_wallet":
            await cmd_create(self, update, context)
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """取消对话"""
        await update.message.reply_text("❌ 已取消操作。")
        return ConversationHandler.END
    
    def setup_handlers(self):
        """设置命令处理器"""
        # 对话处理器（发送交易）
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('send', self.cmd_send)],
            states={
                SEND_ADDRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.send_address_received)
                ],
                SEND_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.send_amount_received)
                ],
                SEND_CONFIRM: [
                    CallbackQueryHandler(self.send_confirmed)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_conversation)],
        )
        
        # 添加处理器
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler("history", self.cmd_history))
        self.app.add_handler(CommandHandler("price", self.cmd_price))
        self.app.add_handler(CommandHandler("create", self.cmd_create))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    def run(self):
        """运行机器人"""
        self.initialize()
        
        # 创建应用
        self.app = Application.builder().token(self.token).build()
        
        # 设置处理器
        self.setup_handlers()
        
        # 启动
        logger.info("Starting Telegram Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='RustChain Telegram Wallet Bot')
    parser.add_argument('--token', default=BOT_TOKEN, help='Telegram Bot Token')
    args = parser.parse_args()
    
    if not args.token:
        logger.error("Please set TELEGRAM_BOT_TOKEN environment variable")
        logger.error("Or use --token argument")
        return
    
    bot = TelegramBot(args.token)
    bot.run()


if __name__ == "__main__":
    main()
