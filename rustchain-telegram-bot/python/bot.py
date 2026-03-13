"""
RustChain Telegram Bot - Python 版本

功能:
- 查询钱包余额
- 查看节点状态
- 交易确认推送通知
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from web3 import Web3

# 加载环境变量
load_dotenv()

# 配置
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RPC_URL = os.getenv('RUSTCHAIN_RPC_URL', 'https://rpc.rustchain.io')
WATCHED_WALLET = os.getenv('WATCHED_WALLET', 'RTC4325af95d26d59c3ef025963656d22af638bb96b')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 30000))
ALLOWED_CHAT_IDS = os.getenv('ALLOWED_CHAT_IDS')

if ALLOWED_CHAT_IDS:
    ALLOWED_CHAT_IDS = [int(id.strip()) for id in ALLOWED_CHAT_IDS.split(',')]

# 日志配置
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 初始化 Web3 连接
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# 交易监控状态
last_block_number = 0
recent_transactions = set()


def check_access(chat_id: int) -> bool:
    """检查聊天 ID 是否有访问权限"""
    if ALLOWED_CHAT_IDS is None:
        return True
    return chat_id in ALLOWED_CHAT_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    logger.info(f"用户启动：chat_id={update.effective_chat.id}")
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "👋 欢迎使用 RustChain 通知机器人！\n\n"
            "我是您的 RustChain 区块链助手，可以提供以下服务：\n\n"
            "• 查询钱包余额\n"
            "• 查看节点状态\n"
            "• 交易确认推送\n\n"
            "发送 /help 查看完整命令列表。"
        )
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "📖 RustChain Bot 帮助\n\n"
            "可用命令：\n\n"
            "/start - 启动机器人\n"
            "/balance - 查询钱包余额\n"
            "/status - 查看节点状态\n"
            "/help - 显示此帮助信息\n\n"
            f"监控的钱包地址：\n"
            f"<code>{WATCHED_WALLET}</code>\n\n"
            "💡 提示：机器人会自动推送交易确认通知。"
        ),
        parse_mode='HTML'
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /balance 命令"""
    logger.debug(f"查询余额：chat_id={update.effective_chat.id}")
    
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ 正在查询余额..."
        )
        
        # 获取余额
        balance_wei = w3.eth.get_balance(WATCHED_WALLET)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        # 模拟价格（实际可集成 API）
        rtc_price = 0.0
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"💰 钱包余额\n\n"
                f"地址：{WATCHED_WALLET}\n"
                f"余额：{float(balance_eth):.6f} RTC\n"
                f"美元价值：${rtc_price:.2f}\n\n"
                f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        
        logger.info(f"余额查询成功：{balance_eth} RTC")
    except Exception as e:
        logger.error(f"余额查询失败：{str(e)}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"❌ 查询失败\n\n"
                f"错误信息：{str(e)}\n\n"
                "请检查网络连接或稍后重试。"
            )
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /status 命令"""
    logger.debug(f"查询状态：chat_id={update.effective_chat.id}")
    
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ 正在获取节点状态..."
        )
        
        # 获取区块高度
        block_number = w3.eth.block_number
        
        # 获取 Gas 价格
        gas_price = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price, 'gwei')
        
        # 获取网络 ID
        chain_id = w3.eth.chain_id
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"📊 RustChain 节点状态\n\n"
                f"🔗 网络 ID：{chain_id}\n"
                f"📦 最新区块：{block_number}\n"
                f"⚡ Gas 价格：{float(gas_price_gwei):.2f} Gwei\n"
                f"🖥️ RPC 节点：{RPC_URL}\n"
                f"✅ 连接状态：正常\n\n"
                f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        
        logger.info(f"状态查询成功：block={block_number}")
    except Exception as e:
        logger.error(f"状态查询失败：{str(e)}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"❌ 获取状态失败\n\n"
                f"错误信息：{str(e)}\n\n"
                "请检查 RPC 节点是否可用。"
            )
        )


async def notify_transaction(context: ContextTypes.DEFAULT_TYPE, tx_hash, tx, block_number):
    """发送交易通知"""
    try:
        is_outgoing = tx['from'].lower() == WATCHED_WALLET.lower()
        direction = "⬆️ 转出" if is_outgoing else "⬇️ 转入"
        amount = w3.from_wei(tx.get('value', 0), 'ether')
        
        message = (
            f"🔔 交易确认通知\n\n"
            f"{direction}\n"
            f"金额：{float(amount):.6f} RTC\n"
            f"区块：{block_number}\n"
            f"哈希：`{tx_hash}`\n\n"
            f"发送方：`{tx['from']}`\n"
            f"接收方：`{tx.get('to', '合约创建')}`\n\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if ALLOWED_CHAT_IDS:
            for chat_id in ALLOWED_CHAT_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.warning(f"发送到 chat {chat_id} 失败：{str(e)}")
        else:
            logger.info(f"交易通知：{tx_hash} (未发送，ALLOWED_CHAT_IDS 未配置)")
        
        logger.info(f"交易通知已发送：{tx_hash}")
    except Exception as e:
        logger.error(f"发送交易通知失败：{str(e)}")


async def monitor_transactions(context: ContextTypes.DEFAULT_TYPE):
    """交易监控循环"""
    global last_block_number, recent_transactions
    
    try:
        if not w3.is_connected():
            logger.warning("Web3 未连接，跳过监控")
            return
        
        current_block = w3.eth.block_number
        
        if last_block_number == 0:
            last_block_number = current_block
            logger.info(f"初始区块高度：{last_block_number}")
            return
        
        # 检查新区块
        if current_block > last_block_number:
            logger.debug(f"检测到新区块：{last_block_number} → {current_block}")
            
            # 检查每个新区块的交易
            for block_num in range(last_block_number + 1, current_block + 1):
                try:
                    block = w3.eth.get_block(block_num, full_transactions=False)
                    transactions = block.get('transactions', [])
                    
                    for tx_hash in transactions:
                        if tx_hash not in recent_transactions:
                            tx = w3.eth.get_transaction(tx_hash)
                            
                            # 检查是否涉及监控的钱包
                            if tx and (
                                tx['from'].lower() == WATCHED_WALLET.lower() or
                                (tx.get('to') and tx['to'].lower() == WATCHED_WALLET.lower())
                            ):
                                # 记录交易
                                recent_transactions.add(tx_hash)
                                
                                # 发送通知
                                await notify_transaction(context, tx_hash, tx, block_num)
                                
                                # 清理旧交易记录（保留最近 100 条）
                                if len(recent_transactions) > 100:
                                    recent_transactions.pop()
                except Exception as e:
                    logger.debug(f"获取区块 {block_num} 失败：{str(e)}")
            
            last_block_number = current_block
    except Exception as e:
        logger.error(f"监控循环错误：{str(e)}")


async def post_init(application: Application):
    """应用初始化后的钩子"""
    logger.info("启动 RustChain Telegram Bot...")
    logger.info(f"交易监控已启动，间隔：{CHECK_INTERVAL}ms")


def main():
    """主函数"""
    # 创建应用
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # 添加命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("status", status))
    
    # 启动交易监控
    async def start_monitoring(application: Application):
        job_queue = application.job_queue
        job_queue.run_repeating(
            monitor_transactions,
            interval=CHECK_INTERVAL / 1000.0,
            first=0
        )
    
    application.post_init = lambda app: asyncio.create_task(start_monitoring(app))
    
    # 启动机器人
    logger.info("机器人已启动，正在轮询更新...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
