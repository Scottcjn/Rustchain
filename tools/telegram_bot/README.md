# RustChain Telegram Community Bot

A feature-rich Telegram bot providing real-time information about the RustChain network.

## Features

### Core Commands
- 💰 `/price` — Current wRTC price from Raydium
- ⛏️ `/miners` — Active miner count
- ⏱️ `/epoch` — Current epoch info
- 💰 `/balance <wallet>` — Check RTC balance
- ❤️ `/health` — Node health status

### Bonus Features
- 🔔 Mining alerts (new miner joins, epoch settles)
- 📈 Price alerts (wRTC moves >5%)
- 🔍 Inline query support

## Quick Start

### 1. Install Dependencies

```bash
cd tools/telegram_bot
pip install -r requirements.txt
```

### 2. Create Bot with BotFather

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` command
3. Follow instructions to create bot
4. Copy the bot token

### 3. Configure Environment

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

Or create a `.env` file:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 4. Run the Bot

```bash
python bot.py
```

## Usage Examples

```
/start — Show welcome message
/help — Show help

/price — Get wRTC price
/miners — Get miner stats
/epoch — Get epoch info
/balance 0xD1Bde85fB255d3863a682414393446B143a26152 — Check balance
/health — Check node health

/alerts — Manage alerts
/alert_price 5 — Set 5% price alert
/alert_mining on — Enable mining alerts

@RustChainBot price — Inline query
```

## API Endpoints Used

- RustChain API: `http://50.28.86.131/api`
- Raydium API: `https://api.raydium.io/v2/main/price`

## Technical Stack

- Python 3.10+
- python-telegram-bot 20.8
- aiohttp for async API calls
- python-dotenv for environment management

## RTC Wallet

**RTC-andygoodluck**

## License

MIT

## Links

- RustChain: https://github.com/Scottcjn/Rustchain
- Explorer: https://50.28.86.131/explorer
