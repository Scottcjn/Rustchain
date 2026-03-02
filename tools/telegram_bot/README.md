# RustChain Telegram Wallet Bot

**Bounty**: #27 - Telegram Bot for RTC Wallet  
**Author**: @xiangshangsir (大龙虾 AI)  
**Wallet**: `0x76AD8c0bef0a99eEb761c3B20b590D60b20964Dc`  
**Reward**: 75 RTC

---

## 概述

RustChain 官方 Telegram 钱包机器人，提供便捷的钱包管理和交易功能。

### 功能特性

- 🔐 **钱包创建** - BIP39 助记词 + Ed25519 密钥对
- 💰 **余额查询** - 实时查询 RTC 余额
- 📤 **发送交易** - 向任意地址发送 RTC
- 📊 **交易历史** - 查看最近的交易记录
- 📈 **价格统计** - 当前 epoch、总供应量等
- 🔒 **安全存储** - 私钥加密存储于 SQLite

---

## 快速启动

### 1. 创建 Telegram Bot

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新机器人
3. 获取 Bot Token（类似：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 安装依赖

```bash
pip install python-telegram-bot pynacl cryptography requests
```

### 3. 配置环境变量

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-here"
export RUSTCHAIN_API="https://rustchain.org"
export WALLET_DB="wallet_bot.db"
export ENCRYPTION_KEY="your-32-byte-key"  # 可选，自动生成
```

### 4. 运行机器人

```bash
cd /home/node/.openclaw/workspace/rustchain-code/tools/telegram_bot
python3 telegram_wallet_bot.py
```

### 5. Systemd 服务（可选）

```bash
sudo cp telegram_bot.service /etc/systemd/system/
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

---

## 机器人命令

| 命令 | 说明 | 权限 |
|------|------|------|
| `/start` | 欢迎消息和主菜单 | 所有人 |
| `/create` | 创建新钱包 | 所有人 |
| `/balance` | 查询余额 | 钱包用户 |
| `/send` | 发送 RTC（交互式） | 钱包用户 |
| `/history` | 交易历史 | 钱包用户 |
| `/price` | 价格统计 | 所有人 |
| `/cancel` | 取消当前操作 | 所有人 |

---

## 使用流程

### 创建钱包

1. 私信机器人 `/start`
2. 点击 "🔐 创建钱包" 按钮
3. 或直接在私信中发送 `/create`
4. **保存私钥**（仅显示一次！）

### 发送 RTC

1. 发送 `/send` 命令
2. 输入收款地址
3. 输入发送金额
4. 确认交易详情
5. 点击 "✅ 确认发送"

### 查询余额

直接发送 `/balance` 即可看到当前余额。

### 查看交易历史

发送 `/history` 查看最近 10 笔交易。

---

## 安全特性

### 私钥加密存储

- 使用 Fernet 对称加密（AES-128-CBC）
- 私钥永不明文存储
- 加密密钥可通过环境变量配置

### Ed25519 签名

- 所有交易使用 Ed25519 数字签名
- 符合 RustChain 协议规范
- 防止交易篡改

### 私聊模式

- 敏感操作（如创建钱包）强制私聊
- 群聊中仅提供有限功能
- 防止私钥泄露

### 对话确认

- 发送交易需要二次确认
- 可取消操作
- 防止误操作

---

## 数据库结构

### `wallets` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | INTEGER | Telegram 用户 ID（主键） |
| `public_key` | TEXT | Ed25519 公钥（16 进制） |
| `encrypted_private_key` | TEXT | 加密的私钥 |
| `created_at` | INTEGER | 创建时间戳 |
| `last_accessed` | INTEGER | 最后访问时间 |

### `transactions` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `user_id` | INTEGER | 用户 ID |
| `tx_hash` | TEXT | 交易哈希 |
| `amount` | REAL | 金额 |
| `direction` | TEXT | `sent` 或 `received` |
| `address` | TEXT | 对方地址 |
| `created_at` | INTEGER | 时间戳 |

---

## API 端点

机器人调用以下 RustChain API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/wallet/balance` | GET | 查询余额 |
| `/wallet/send` | POST | 发送交易 |
| `/wallet/history` | GET | 交易历史 |
| `/epoch` | GET | Epoch 统计 |

---

## 配置选项

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TELEGRAM_BOT_TOKEN` | (必填) | Telegram Bot Token |
| `RUSTCHAIN_API` | `https://rustchain.org` | RustChain API 地址 |
| `WALLET_DB` | `wallet_bot.db` | 数据库文件路径 |
| `ENCRYPTION_KEY` | (自动生成) | Fernet 加密密钥 |

### 生成加密密钥

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key().decode()
print(key)  # 保存到此环境变量
```

---

## 错误处理

### 常见问题

**1. 机器人无响应**
```bash
# 检查 Token 是否正确
echo $TELEGRAM_BOT_TOKEN

# 检查网络连接
curl https://api.telegram.org
```

**2. 钱包创建失败**
```bash
# 检查数据库权限
ls -la wallet_bot.db

# 查看日志
journalctl -u telegram-bot -f
```

**3. 交易发送失败**
- 确认余额充足
- 检查收款地址格式
- 查看 RustChain API 状态

---

## 开发调试

### 启用调试日志

```bash
export PYTHONDEBUG=1
python3 telegram_wallet_bot.py
```

### 测试模式

```python
# 在代码中添加测试函数
async def test_balance():
    api = RustChainAPI("https://rustchain.org")
    balance = api.get_balance("test_miner_id")
    print(f"Balance: {balance}")
```

---

## 部署建议

### 生产环境

1. **使用反向代理** - Nginx + HTTPS
2. **配置 Webhook** - 比 polling 更高效
3. **数据库备份** - 定期备份 wallet_bot.db
4. **监控日志** - 设置日志告警
5. **限流保护** - 防止 API 滥用

### Webhook 配置

```python
# 替代 run_polling()
app.run_webhook(
    listen='0.0.0.0',
    port=8443,
    url_path=BOT_TOKEN,
    webhook_url=f"https://your-domain.com/{BOT_TOKEN}"
)
```

---

## 文件结构

```
tools/telegram_bot/
├── telegram_wallet_bot.py    # 主程序
├── telegram_bot.service      # Systemd 服务
├── requirements.txt          # Python 依赖
└── README.md                 # 本文档
```

---

## 依赖包

**requirements.txt**:
```
python-telegram-bot>=20.0
pynacl>=1.5.0
cryptography>=40.0.0
requests>=2.28.0
```

---

## 许可证

SPDX-License-Identifier: MIT

---

*安全、便捷的 Telegram 钱包管理* 🤖💰
