# RustChain Telegram Bot 快速启动指南

## 🚀 5 分钟快速开始

### 步骤 1: 创建 Telegram 机器人 (2 分钟)

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot` 命令
3. 输入机器人名称（例如：`RustChain Bot`）
4. 输入机器人用户名（例如：`rustchain_notify_bot`）
5. **保存返回的 Token**（格式：`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 步骤 2: 获取你的聊天 ID (1 分钟)

1. 在 Telegram 中搜索并启动刚创建的机器人
2. 发送 `/start` 命令
3. 在浏览器打开（替换 YOUR_BOT_TOKEN）：
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. 找到 `"chat":{"id":123456789}`，**保存这个 ID**

### 步骤 3: 配置环境变量 (1 分钟)

在项目根目录创建 `.env` 文件：

```bash
# 复制示例文件
cp .env.example .env
```

编辑 `.env` 文件，填入：

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ALLOWED_CHAT_IDS=123456789
WATCHED_WALLET=RTC4325af95d26d59c3ef025963656d22af638bb96b
RUSTCHAIN_RPC_URL=https://rpc.rustchain.io
CHECK_INTERVAL=30000
LOG_LEVEL=info
```

**必填项**:
- `TELEGRAM_BOT_TOKEN`: 步骤 1 获取的 Token
- `ALLOWED_CHAT_IDS`: 步骤 2 获取的聊天 ID

### 步骤 4: 启动机器人 (1 分钟)

#### Node.js 版本（推荐）

```bash
# 安装依赖（首次运行）
npm install

# 启动机器人
npm start
```

看到以下输出表示成功：
```
[INFO] 启动 RustChain Telegram Bot...
[INFO] 机器人已启动，正在轮询更新...
[INFO] 交易监控已启动，间隔：30000ms
```

#### Python 版本

```bash
cd python

# 安装依赖（首次运行）
pip install -r requirements.txt

# 启动机器人
python bot.py
```

### 步骤 5: 测试命令

在 Telegram 中向机器人发送：

- `/start` - 欢迎消息
- `/help` - 帮助信息
- `/balance` - 查询余额
- `/status` - 节点状态

## ✅ 验证清单

- [ ] 机器人回复 `/start` 命令
- [ ] 机器人回复 `/help` 命令
- [ ] 机器人回复 `/balance` 命令（可能显示错误，如果 RPC 节点不可用）
- [ ] 机器人回复 `/status` 命令（可能显示错误，如果 RPC 节点不可用）
- [ ] 控制台显示 "机器人已启动" 日志

## 🔧 常见问题

### Q: 机器人没有响应？

**A**: 检查以下几点：
1. Token 是否正确（复制时不要有多余空格）
2. `.env` 文件是否在正确位置
3. 查看控制台是否有错误日志
4. 确认网络连接正常

### Q: 余额查询显示错误？

**A**: 这是正常的，可能原因：
1. RustChain 公共 RPC 节点不可用
2. 钱包地址格式需要调整
3. 需要配置正确的 RPC 节点 URL

即使余额查询失败，机器人仍可正常运行，只是无法获取链上数据。

### Q: 如何限制只有我能使用机器人？

**A**: 在 `.env` 中配置 `ALLOWED_CHAT_IDS`：
```env
ALLOWED_CHAT_IDS=123456789
```

多个用户用逗号分隔：
```env
ALLOWED_CHAT_IDS=123456789,987654321
```

### Q: 如何停止机器人？

**A**: 
- 开发环境：按 `Ctrl+C`
- PM2: `pm2 stop rustchain-bot`
- Docker: `docker stop rustchain-bot`

## 📱 下一步

1. **部署到服务器**: 参考 `DEPLOYMENT.md`
2. **自定义功能**: 修改 `index.js` 或 `bot.py`
3. **监控交易**: 配置 `WATCHED_WALLET` 接收交易通知
4. **设置开机自启**: 使用 PM2 或 Systemd

## 📞 获取帮助

- 查看 `README.md` 了解完整功能
- 查看 `DEPLOYMENT.md` 了解部署选项
- 查看 `SCREENSHOTS.md` 了解如何截图证明

---

**提示**: 如果是第一次使用，建议先用 Node.js 版本在本地测试，熟悉后再部署到服务器。
