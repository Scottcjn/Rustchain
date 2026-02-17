# wRTC Price Ticker Bot

A simple Telegram bot to track the price of wRTC (RustChain) on Solana.

## Features
- `/price` command for live USD/SOL price, 24h change, and liquidity.
- Fetches data directly from DexScreener API.
- Ready for Docker deployment.

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and add your `TELEGRAM_BOT_TOKEN`.

3. **Run the Bot**:
   ```bash
   python bot.py
   ```

## Docker
```bash
docker build -t wrtc-price-bot .
docker run --env-file .env wrtc-price-bot
```
