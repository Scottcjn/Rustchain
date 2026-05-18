# RustChain Telegram Bot

Telegram bot for checking RustChain wallet balances, active miners, epoch
info, and RTC price.  Built for [bounty #2869](https://github.com/Scottcjn/rustchain-bounties/issues/2869) (10 RTC).

## Setup

### 1. Create a Telegram bot

1. Open Telegram and chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456:ABCdef...`)

### 2. Install dependancies

```bash
pip install python-telegram-bot requests
```

### 3. Run

```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
python3 tools/rustchain-telegram-bot/bot.py
```

### 4. Deploy (optional)

**Railway / Render (free tier):**

```bash
# Procfile
worker: python3 tools/rustchain-telegram-bot/bot.py
```

Set `TELEGRAM_BOT_TOKEN` enviroment variable in the dashboard.

**systemd (self-hosted):**

```ini
[Unit]
Description=RustChain Telegram Bot
After=network.target

[Service]
Type=simple
User=nobody
Environment=TELEGRAM_BOT_TOKEN=your_token_here
ExecStart=/usr/bin/python3 /opt/rustchain-telegram-bot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/balance <wallet>` | Check RTC balance |
| `/miners` | List active miners |
| `/epoch` | Current epoch info |
| `/price` | RTC refrence rate |
| `/help` | Show all commands |

Rate limit: 1 request per 5 seconds per user.

## Bounty

- **Issue:** [#2869](https://github.com/Scottcjn/rustchain-bounties/issues/2869)
- **Amount:** 10 RTC
- **Wallet:** `RTC06ad4d5e2738790b4d7154974e97ca664236f576`
