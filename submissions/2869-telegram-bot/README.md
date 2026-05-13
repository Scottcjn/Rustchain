# RustChain Telegram Bot

A Telegram bot that checks RustChain wallet balances, miner status, and epoch info.

## Commands

| Command | Description |
|---------|-------------|
| `/balance <wallet>` | Check RTC balance |
| `/miners` | List active miners |
| `/epoch` | Current epoch info |
| `/price` | Show RTC reference rate ($0.10) |
| `/help` | Show commands |

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Install & Run

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token-here"
python bot.py
```

### 3. Deploy (systemd)

```ini
[Unit]
Description=RustChain Telegram Bot
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/opt/rustchain-bot
Environment=TELEGRAM_BOT_TOKEN=your-token
ExecStart=/usr/bin/python3 bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Deploy (Railway)

```bash
railway init
railway add
railway variables set TELEGRAM_BOT_TOKEN=your-token
railway up
```

## Features

- **Rate limiting**: 1 request per 5 seconds per user
- **Error handling**: Graceful messages when RustChain node is offline
- **No API key required**: Uses public RustChain API endpoints
- **Lightweight**: Single file, minimal dependencies

## Wallet

RTC Wallet: `RTC9d7caca3039130d3b26d41f7343d8f4ef4592360`

## License

MIT
