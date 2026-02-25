# RustChain Telegram Bot

A Telegram bot for the RustChain community.

## Features

- `/price` - Current wRTC price from Raydium
- `/miners` - Active miner count from API
- `/epoch` - Current epoch info
- `/balance <wallet>` - Check wallet balance
- `/health` - Node health status

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Get a Telegram Bot Token from @BotFather

3. Edit `telegram_bot.py` and replace `YOUR_BOT_TOKEN_HERE` with your token

4. Run the bot:
```bash
python telegram_bot.py
```

## Deployment

### Using Docker

```bash
docker build -t rustchain-telegram-bot .
docker run -d rustchain-telegram-bot
```

### Using Systemd

```bash
sudo cp rustchain-telegram-bot.service /etc/systemd/system/
sudo systemctl enable rustchain-telegram-bot
sudo systemctl start rustchain-telegram-bot
```

## Bounty

This bot was built for the RustChain Bounty Program.
Reward: 50 RTC

Issue: https://github.com/Scottcjn/rustchain-bounties/issues/249
