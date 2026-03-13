# RustChain Telegram Bot - Python 版本

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置环境变量

复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

## 启动机器人

```bash
python bot.py
```

## 功能特性

与 Node.js 版本相同：
- ✅ 查询钱包余额 (`/balance`)
- ✅ 查看节点状态 (`/status`)
- ✅ 帮助信息 (`/help`)
- ✅ 交易确认推送通知

## 依赖说明

- `python-telegram-bot`: Telegram Bot 框架
- `web3`: 区块链交互库
- `python-dotenv`: 环境变量管理
