/**
 * RustChain Telegram Bot
 * 
 * 功能:
 * - 查询钱包余额
 * - 查看节点状态
 * - 交易确认推送通知
 */

require('dotenv').config();
const { Telegraf } = require('telegraf');
const { ethers } = require('ethers');

// 配置
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const RPC_URL = process.env.RUSTCHAIN_RPC_URL || 'https://rpc.rustchain.io';
const WATCHED_WALLET = process.env.WATCHED_WALLET || 'RTC4325af95d26d59c3ef025963656d22af638bb96b';
const CHECK_INTERVAL = parseInt(process.env.CHECK_INTERVAL) || 30000;
const ALLOWED_CHAT_IDS = process.env.ALLOWED_CHAT_IDS 
  ? process.env.ALLOWED_CHAT_IDS.split(',').map(id => parseInt(id.trim()))
  : null;

// 日志配置
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';
const logger = {
  info: (msg) => ['info', 'debug'].includes(LOG_LEVEL) && console.log(`[INFO] ${new Date().toISOString()} - ${msg}`),
  debug: (msg) => LOG_LEVEL === 'debug' && console.log(`[DEBUG] ${new Date().toISOString()} - ${msg}`),
  warn: (msg) => console.warn(`[WARN] ${new Date().toISOString()} - ${msg}`),
  error: (msg) => console.error(`[ERROR] ${new Date().toISOString()} - ${msg}`)
};

// 初始化机器人
const bot = new Telegraf(BOT_TOKEN);

// 初始化区块链连接
// RustChain 基于 Ethereum，使用 ethers.js 连接
let provider;
try {
  provider = new ethers.JsonRpcProvider(RPC_URL);
  logger.info('区块链连接初始化成功');
} catch (error) {
  logger.error(`区块链连接失败：${error.message}`);
}

// 交易监控状态
let lastBlockNumber = 0;
let recentTransactions = new Set();

// 中间件：检查权限
bot.use((ctx, next) => {
  if (ALLOWED_CHAT_IDS && !ALLOWED_CHAT_IDS.includes(ctx.chat.id)) {
    logger.warn(`未授权的访问尝试：chat_id=${ctx.chat.id}`);
    return ctx.reply('⛔ 未授权访问\n\n请联系管理员添加您的聊天 ID。');
  }
  return next();
});

// 命令：/start
bot.start((ctx) => {
  logger.info(`用户启动：chat_id=${ctx.chat.id}, username=${ctx.from.username}`);
  ctx.reply(
    '👋 欢迎使用 RustChain 通知机器人！\n\n' +
    '我是您的 RustChain 区块链助手，可以提供以下服务：\n\n' +
    '• 查询钱包余额\n' +
    '• 查看节点状态\n' +
    '• 交易确认推送\n\n' +
    '发送 /help 查看完整命令列表。'
  );
});

// 命令：/help
bot.help((ctx) => {
  ctx.reply(
    '📖 RustChain Bot 帮助\n\n' +
    '可用命令：\n\n' +
    '/start - 启动机器人\n' +
    '/balance - 查询钱包余额\n' +
    '/status - 查看节点状态\n' +
    '/help - 显示此帮助信息\n\n' +
    '监控的钱包地址：\n' +
    `<code>${WATCHED_WALLET}</code>\n\n` +
    '💡 提示：机器人会自动推送交易确认通知。'
  );
});

// 命令：/balance
bot.command('balance', async (ctx) => {
  logger.debug(`查询余额：chat_id=${ctx.chat.id}`);
  
  try {
    ctx.reply('⏳ 正在查询余额...');
    
    // 获取余额（以太坊兼容链）
    const balance = await provider.getBalance(WATCHED_WALLET);
    const balanceInEther = ethers.formatEther(balance);
    
    // 获取当前 RTC 价格（模拟，实际可集成 API）
    const rtcPrice = 0.0; // 需要集成价格 API
    
    ctx.reply(
      '💰 钱包余额\n\n' +
      `地址：${WATCHED_WALLET}\n` +
      `余额：${parseFloat(balanceInEther).toFixed(6)} RTC\n` +
      `美元价值：$${rtcPrice.toFixed(2)}\n\n` +
      `更新时间：${new Date().toLocaleString('zh-CN')}`
    );
    
    logger.info(`余额查询成功：${balanceInEther} RTC`);
  } catch (error) {
    logger.error(`余额查询失败：${error.message}`);
    ctx.reply(
      '❌ 查询失败\n\n' +
      `错误信息：${error.message}\n\n` +
      '请检查网络连接或稍后重试。'
    );
  }
});

// 命令：/status
bot.command('status', async (ctx) => {
  logger.debug(`查询状态：chat_id=${ctx.chat.id}`);
  
  try {
    ctx.reply('⏳ 正在获取节点状态...');
    
    // 获取区块高度
    const blockNumber = await provider.getBlockNumber();
    
    // 获取 Gas 价格
    const feeData = await provider.getFeeData();
    const gasPrice = ethers.formatUnits(feeData.gasPrice || 0, 'gwei');
    
    // 获取网络信息
    const network = await provider.getNetwork();
    
    ctx.reply(
      '📊 RustChain 节点状态\n\n' +
      `🔗 网络 ID：${network.chainId}\n` +
      `📦 最新区块：${blockNumber}\n` +
      `⚡ Gas 价格：${parseFloat(gasPrice).toFixed(2)} Gwei\n` +
      `🖥️ RPC 节点：${RPC_URL}\n` +
      `✅ 连接状态：正常\n\n` +
      `更新时间：${new Date().toLocaleString('zh-CN')}`
    );
    
    logger.info(`状态查询成功：block=${blockNumber}`);
  } catch (error) {
    logger.error(`状态查询失败：${error.message}`);
    ctx.reply(
      '❌ 获取状态失败\n\n' +
      `错误信息：${error.message}\n\n` +
      '请检查 RPC 节点是否可用。'
    );
  }
});

// 交易监控循环
async function monitorTransactions() {
  try {
    if (!provider) {
      logger.warn('Provider 未初始化，跳过监控');
      return;
    }
    
    const currentBlock = await provider.getBlockNumber();
    
    if (lastBlockNumber === 0) {
      lastBlockNumber = currentBlock;
      logger.info(`初始区块高度：${lastBlockNumber}`);
      return;
    }
    
    // 检查新区块
    if (currentBlock > lastBlockNumber) {
      logger.debug(`检测到新区块：${lastBlockNumber} → ${currentBlock}`);
      
      // 检查每个新区块的交易
      for (let blockNum = lastBlockNumber + 1; blockNum <= currentBlock; blockNum++) {
        try {
          const block = await provider.getBlock(blockNum, true);
          if (block && block.transactions) {
            for (const txHash of block.transactions) {
              if (!recentTransactions.has(txHash)) {
                const tx = await provider.getTransaction(txHash);
                
                // 检查是否涉及监控的钱包
                if (tx && (
                  tx.from.toLowerCase() === WATCHED_WALLET.toLowerCase() ||
                  (tx.to && tx.to.toLowerCase() === WATCHED_WALLET.toLowerCase())
                )) {
                  // 记录交易
                  recentTransactions.add(txHash);
                  
                  // 发送通知
                  await notifyTransaction(tx, blockNum);
                  
                  // 清理旧交易记录（保留最近 100 条）
                  if (recentTransactions.size > 100) {
                    const iterator = recentTransactions.values();
                    recentTransactions.delete(iterator.next().value);
                  }
                }
              }
            }
          }
        } catch (error) {
          logger.debug(`获取区块 ${blockNum} 失败：${error.message}`);
        }
      }
      
      lastBlockNumber = currentBlock;
    }
  } catch (error) {
    logger.error(`监控循环错误：${error.message}`);
  }
}

// 发送交易通知
async function notifyTransaction(tx, blockNumber) {
  try {
    const isOutgoing = tx.from.toLowerCase() === WATCHED_WALLET.toLowerCase();
    const direction = isOutgoing ? '⬆️ 转出' : '⬇️ 转入';
    const amount = ethers.formatEther(tx.value || 0);
    
    const message = 
      `🔔 交易确认通知\n\n` +
      `${direction}\n` +
      `金额：${parseFloat(amount).toFixed(6)} RTC\n` +
      `区块：${blockNumber}\n` +
      `哈希：\`${tx.hash}\`\n\n` +
      `发送方：\`${tx.from}\`\n` +
      `接收方：\`${tx.to || '合约创建'}\`\n\n` +
      `时间：${new Date().toLocaleString('zh-CN')}`;
    
    // 广播给所有授权的聊天
    if (ALLOWED_CHAT_IDS) {
      for (const chatId of ALLOWED_CHAT_IDS) {
        try {
          await bot.telegram.sendMessage(chatId, message, { parse_mode: 'Markdown' });
        } catch (error) {
          logger.warn(`发送到 chat ${chatId} 失败：${error.message}`);
        }
      }
    } else {
      logger.info(`交易通知：${tx.hash} (未发送，ALLOWED_CHAT_IDS 未配置)`);
    }
    
    logger.info(`交易通知已发送：${tx.hash}`);
  } catch (error) {
    logger.error(`发送交易通知失败：${error.message}`);
  }
}

// 错误处理
bot.catch((err, ctx) => {
  logger.error(`机器人错误：${err.message}`);
  console.error(err);
});

// 启动函数
async function startBot() {
  logger.info('启动 RustChain Telegram Bot...');
  
  // 启动机器人
  await bot.launch();
  logger.info('机器人已启动，正在轮询更新...');
  
  // 启动交易监控
  setInterval(monitorTransactions, CHECK_INTERVAL);
  logger.info(`交易监控已启动，间隔：${CHECK_INTERVAL}ms`);
  
  // 优雅关闭
  process.once('SIGINT', () => {
    logger.info('收到 SIGINT 信号，正在关闭...');
    bot.stop('SIGINT');
  });
  
  process.once('SIGTERM', () => {
    logger.info('收到 SIGTERM 信号，正在关闭...');
    bot.stop('SIGTERM');
  });
}

// 运行机器人
startBot().catch(error => {
  logger.error(`启动失败：${error.message}`);
  process.exit(1);
});
