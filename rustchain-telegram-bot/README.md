# RustChain Telegram Bot

一个用于 RustChain 区块链通知的 Telegram 机器人。

## 功能特性

- ✅ 查询钱包余额 (`/balance`)
- ✅ 查看节点状态 (`/status`)
- ✅ 帮助信息 (`/help`)
- ✅ 交易确认推送通知

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
RUSTCHAIN_RPC_URL=https://rpc.rustchain.io
WATCHED_WALLET=RTC4325af95d26d59c3ef025963656d22af638bb96b
CHECK_INTERVAL=30000
```

### 3. 创建 Telegram Bot

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 命令
3. 按照提示设置机器人名称和用户名
4. 获取 API Token

### 4. 启动机器人

```bash
node index.js
```

## 命令说明

| 命令 | 说明 |
|------|------|
| `/balance` | 查询指定钱包的 RTC 余额 |
| `/status` | 查看 RustChain 节点状态 |
| `/help` | 显示帮助信息 |

## 部署到服务器

### 使用 PM2（推荐）

```bash
# 安装 PM2
npm install -g pm2

# 启动应用
pm2 start index.js --name rustchain-bot

# 设置开机自启
pm2 startup
pm2 save
```

### 使用 Docker

```bash
# 构建镜像
docker build -t rustchain-telegram-bot .

# 运行容器
docker run -d --name rustchain-bot \
  --env-file .env \
  rustchain-telegram-bot
```

## 获取聊天 ID

1. 启动机器人后，在 Telegram 中发送 `/start`
2. 查看控制台日志，会输出聊天 ID
3. 如需限制特定用户，可在 `.env` 中设置 `ALLOWED_CHAT_IDS`

## 注意事项

- 确保服务器时间同步，避免交易时间戳问题
- 建议设置 `CHECK_INTERVAL` 不低于 30 秒，避免触发 API 限流
- 生产环境请使用 HTTPS 的 RPC 节点

## 技术栈

- Node.js 18+
- telegraf (Telegram Bot 框架)
- ethers.js (区块链交互)
- dotenv (环境变量管理)

## 许可证

MIT
