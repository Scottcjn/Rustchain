# RustChain Telegram Community Bot

Telegram bot for the RustChain community. Provides real-time chain data.

## Commands
- `/price` — Current wRTC price from Raydium
- `/miners` — Active miner count
- `/epoch` — Current epoch info
- `/balance <wallet>` — Check RTC balance
- `/health` — Node health status

## Setup
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-bot-token"
python bot.py
```

## Features
- Async (aiohttp + python-telegram-bot v21)
- Error handling with graceful fallbacks
- Inline query support (bonus)
- Markdown formatted responses

## API Endpoints Used
- `GET /api/price` — wRTC price
- `GET /api/miners` — Miner data
- `GET /epoch` — Epoch info
- `GET /api/balance/<wallet>` — Wallet balance
- `GET /api/health` — Node health
