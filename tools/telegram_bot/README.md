# RustChain Telegram Community Bot

实现 `rustchain-bounties#249` 要求的社区机器人命令：

- `/price`：wRTC 价格
- `/miners`：活跃矿工数
- `/epoch`：当前 epoch 信息
- `/balance <wallet>`：钱包余额
- `/health`：节点健康状态

## 1) 安装依赖

```bash
cd tools/telegram_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) 配置环境变量

```bash
export TELEGRAM_BOT_TOKEN="<your_bot_token>"
export RUSTCHAIN_API_BASE="http://50.28.86.131"
# 可选：请求超时（秒）
export RUSTCHAIN_REQUEST_TIMEOUT="8"
```

## 3) 启动

```bash
python bot.py
```

## 说明

- 默认请求 `http://50.28.86.131`，可用 `RUSTCHAIN_API_BASE` 覆盖。
- 各命令对返回 payload 做了宽松字段兼容（不同字段名也尽量解析）。
- 发生请求错误时会直接回显错误，方便群组调试。
