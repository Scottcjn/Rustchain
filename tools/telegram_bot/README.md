# RustChain Telegram Bot

Telegram bot for RustChain community.

## Commands

- `/price` - Get real-time wRTC price from Raydium via DexScreener API
- `/miners` - Get active miner count from RustChain network
- `/epoch` - Get current epoch information
- `/balance <wallet>` - Check wallet balance
- `/health` - Check node health status
- `/help` - Show all available commands

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create a Telegram Bot
1. Talk to @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token provided

### 3. Configure environment variables
Create a `.env` file:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
RUSTCHAIN_API=https://rustchain.org  # Optional, default is used
```

### 4. Run the bot
```bash
# Option 1: Using .env file
python telegram_bot.py

# Option 2: Set environment variables directly
export TELEGRAM_BOT_TOKEN=your_bot_token_here
python telegram_bot.py
```

## Docker Deployment

Create a Dockerfile:
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "telegram_bot.py"]
```

Build and run:
```bash
docker build -t rustchain-telegram-bot .
docker run --env-file .env rustchain-telegram-bot
```

## Features

- ✅ Real-time wRTC price fetching from DexScreener API
- ✅ Active miner count from RustChain network
- ✅ Wallet balance checking
- ✅ Node health monitoring
- ✅ Environment variable configuration
- ✅ Comprehensive error handling

## Technical Details

- Uses `python-telegram-bot` library (v20.0+)
- Fetches wRTC price from DexScreener API
- Connects to RustChain API at `https://rustchain.org`
- Supports both Raydium and other DEXs for price data

## Bounty

50 RTC - Issue #249
Fixed version addressing code quality issues:
1. Removed duplicate files
2. Implemented real /price command (no placeholder)
3. Added environment variable support
4. Improved error handling and logging
