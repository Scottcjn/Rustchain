# RustChain Telegram Bot

Telegram bot for RustChain community with price, miner, and wallet commands.

**Bounty:** #249 - Telegram Community Bot  
**Reward:** 50 RTC

## Features

- `/price` — Current wRTC price from Raydium
- `/miners` — Active miner count
- `/epoch` — Current epoch info
- `/balance <wallet>` — Check RTC balance
- `/health` — Node health status
- `/help` — Show help

## Requirements

- Python 3.8+
- python-telegram-bot
- requests

## Installation

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/telegram_bot

# Install dependencies
pip install -r requirements.txt

# Set your bot token
export TELEGRAM_BOT_TOKEN="your_bot_token_here"

# Run the bot
python telegram_bot.py
```

## Create Your Bot

1. Message @BotFather on Telegram
2. Use /newbot to create a new bot
3. Copy the bot token
4. Set it as TELEGRAM_BOT_TOKEN environment variable

## Deployment

### Systemd Service (Linux)

```ini
[Unit]
Description=RustChain Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/telegram_bot
Environment=TELEGRAM_BOT_TOKEN=your_token
ExecStart=/usr/bin/python3 telegram_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Testing

Send commands to your bot:
- `/start` - Welcome message
- `/help` - Help
- `/price` - Check wRTC price
- `/miners` - Check miner count

## Wallet

**Payout Wallet:** tianlin-rtc
