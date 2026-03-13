# 截图指南

## 需要截图的内容

完成以下截图以证明机器人功能正常：

### 1. 机器人启动截图

**内容**: 终端/命令行显示机器人成功启动

**Node.js 版本**:
```bash
npm start
```

期望输出：
```
[INFO] 2026-03-13T03:00:00.000Z - 启动 RustChain Telegram Bot...
[INFO] 2026-03-13T03:00:00.000Z - 区块链连接初始化成功
[INFO] 2026-03-13T03:00:01.000Z - 机器人已启动，正在轮询更新...
[INFO] 2026-03-13T03:00:01.000Z - 交易监控已启动，间隔：30000ms
```

**Python 版本**:
```bash
python bot.py
```

期望输出：
```
2026-03-13 11:00:00,000 - __main__ - INFO - 启动 RustChain Telegram Bot...
2026-03-13 11:00:01,000 - __main__ - INFO - 机器人已启动，正在轮询更新...
```

---

### 2. /start 命令截图

**操作**: 在 Telegram 中向机器人发送 `/start`

**期望响应**:
```
👋 欢迎使用 RustChain 通知机器人！

我是您的 RustChain 区块链助手，可以提供以下服务：

• 查询钱包余额
• 查看节点状态
• 交易确认推送

发送 /help 查看完整命令列表。
```

---

### 3. /help 命令截图

**操作**: 在 Telegram 中向机器人发送 `/help`

**期望响应**:
```
📖 RustChain Bot 帮助

可用命令：

/start - 启动机器人
/balance - 查询钱包余额
/status - 查看节点状态
/help - 显示此帮助信息

监控的钱包地址：
RTC4325af95d26d59c3ef025963656d22af638bb96b

💡 提示：机器人会自动推送交易确认通知。
```

---

### 4. /balance 命令截图

**操作**: 在 Telegram 中向机器人发送 `/balance`

**期望响应**:
```
⏳ 正在查询余额...

💰 钱包余额

地址：RTC4325af95d26d59c3ef025963656d22af638bb96b
余额：XXX.XXXXXX RTC
美元价值：$X.XX

更新时间：2026-03-13 11:00:00
```

**注意**: 如果 RPC 节点不可用，可能显示错误信息，这也是正常的功能演示。

---

### 5. /status 命令截图

**操作**: 在 Telegram 中向机器人发送 `/status`

**期望响应**:
```
⏳ 正在获取节点状态...

📊 RustChain 节点状态

🔗 网络 ID：XXX
📦 最新区块：XXXXXX
⚡ Gas 价格：XX.XX Gwei
🖥️ RPC 节点：https://rpc.rustchain.io
✅ 连接状态：正常

更新时间：2026-03-13 11:00:00
```

---

### 6. 交易通知截图（可选）

**说明**: 如果有真实交易发生，机器人会自动推送通知

**期望响应**:
```
🔔 交易确认通知

⬇️ 转入（或 ⬆️ 转出）
金额：X.XXXXXX RTC
区块：XXXXXX
哈希：0x...

发送方：0x...
接收方：0x...

时间：2026-03-13 11:00:00
```

---

### 7. 代码结构截图

**操作**: 展示项目文件结构

**Windows (PowerShell)**:
```powershell
tree /F
```

**Linux/Mac**:
```bash
tree -L 2
```

期望显示：
```
rustchain-telegram-bot/
├── index.js
├── package.json
├── .env.example
├── .gitignore
├── README.md
├── DEPLOYMENT.md
├── Dockerfile
├── ecosystem.config.js
└── python/
    ├── bot.py
    ├── requirements.txt
    └── README.md
```

---

### 8. 运行状态截图

**PM2 (Node.js 生产环境)**:
```bash
pm2 status
pm2 logs rustchain-bot --lines 50
```

**Systemd (Python 生产环境)**:
```bash
sudo systemctl status rustchain-bot
sudo journalctl -u rustchain-bot --lines 50
```

**Docker**:
```bash
docker ps
docker logs rustchain-bot --tail 50
```

---

## 截图工具推荐

### Windows

- **Snip & Sketch**: Win + Shift + S
- **ShareX**: 开源截图工具
- **Greenshot**: 轻量级截图

### Linux

- **Flameshot**: 功能强大的截图工具
- **Shutter**: 支持编辑的截图工具
- **系统自带**: PrintScreen 键

### Mac

- **系统自带**: Cmd + Shift + 4
- **Snip**: 第三方截图工具

---

## 截图上传

将截图保存到以下位置：

```
rustchain-telegram-bot/screenshots/
├── 01-bot-started.png
├── 02-start-command.png
├── 03-help-command.png
├── 04-balance-command.png
├── 05-status-command.png
├── 06-transaction-notification.png (可选)
├── 07-code-structure.png
└── 08-running-status.png
```

---

## 注意事项

1. **隐私保护**: 截图前删除或模糊化敏感信息
   - Bot Token
   - 个人聊天 ID
   - 私钥或助记词

2. **时间戳**: 确保截图包含当前时间，证明是实时运行

3. **清晰度**: 确保文字清晰可读

4. **完整性**: 包含完整的响应内容，不要裁剪

---

## 提交清单

- [ ] 机器人启动截图
- [ ] /start 命令响应
- [ ] /help 命令响应
- [ ] /balance 命令响应
- [ ] /status 命令响应
- [ ] 交易通知响应（可选）
- [ ] 代码结构截图
- [ ] 运行状态截图

---

最后更新：2026-03-13
