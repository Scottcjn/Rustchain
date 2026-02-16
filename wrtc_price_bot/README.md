# wRTC Price Ticker Bot

A Telegram bot that posts the current wRTC/SOL price from Raydium DEX.

## Installation

```bash
# Clone repository
cd wrtc-price-bot

# Install dependencies
pip install -r requirements.txt

# Set bot token
export TELEGRAM_BOT_TOKEN='your_bot_token_here'

# Run bot
python3 wrtc_price_bot.py
```

## Usage

### Getting a Bot Token

1. Open [Telegram](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token (e.g., `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Running the Bot

```bash
# Set your bot token
export TELEGRAM_BOT_TOKEN='your_bot_token'

# Run the bot
python3 wrtc_price_bot.py
```

### Bot Commands

- `/price` - Get current wRTC price

## Features

- ✅ Real-time wRTC price from Raydium DEX
- ✅ Price in USD and SOL
- ✅ 24-hour price change percentage
- ✅ Liquidity information
- ✅ Direct links to Raydium swap and DexScreener
- ✅ Multiple API sources (Jupiter, DexScreener) with fallback
- ✅ Price change detection (>10% in 1 hour)

## Token Details

- **Mint:** `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- **Supply:** 8,300,000 wRTC
- **Raydium Pool:** `8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb`

## Example Output

```
🪙 **wRTC Price**

💰 **Price (USD):** `$0.123456`
💎 **Price (SOL):** `0.00500000`

📊 **24h Change:** 📈 +5.23%
💧 **Liquidity:** `$10,500`

🔗 [Swap on Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
📊 [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)

---
🤖 *Powered by RustChain Price Bot*
```

## API Sources

The bot uses multiple APIs for reliability:

1. **DexScreener API** (primary)
   - URL: `https://api.dexscreener.com/latest/dex/tokens/{mint}`
   - Provides: Price in USD/SOL, 24h change, liquidity

2. **Jupiter API** (fallback)
   - URL: `https://price.jup.ag/v2/price?ids={mint}`
   - Provides: Price in USD

## Price Alerts

The bot tracks price changes and can alert when the price moves more than 10% in one hour.

Alert format:
```
⚠️ **Price Alert!** wRTC 📈 UP 15.23% in last hour!
```

## Running with Auto-Update

For continuous monitoring, you can run the bot with a process manager:

```bash
# Using screen
screen -S wrtc-bot
export TELEGRAM_BOT_TOKEN='your_bot_token'
python3 wrtc_price_bot.py

# Using nohup
nohup python3 wrtc_price_bot.py > bot.log 2>&1 &
```

## Systemd Service (Linux)

Create a systemd service for auto-start:

```ini
# /etc/systemd/system/wrtc-price-bot.service
[Unit]
Description=wRTC Price Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/wrtc-price-bot
Environment="TELEGRAM_BOT_TOKEN=your_bot_token"
ExecStart=/usr/bin/python3 /path/to/wrtc-price-bot/wrtc_price_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable wrtc-price-bot
sudo systemctl start wrtc-price-bot
sudo systemctl status wrtc-price-bot
```

## Troubleshooting

### Bot doesn't respond to commands
- Make sure you've started a chat with the bot
- Check your bot token is correct
- Check bot logs for errors

### Price fetching fails
- Check internet connection
- API may be temporarily unavailable
- Bot uses fallback APIs automatically

### Bot keeps stopping
- Use a process manager (screen, nohup, systemd)
- Check logs for error messages
- Ensure bot token is not expired

## Links

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [wRTC on Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
- [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)
- [Jupiter](https://jup.ag/)

## License

MIT

## Requirements

- Python 3.7+
- requests library
- python-telegram-bot library
- Telegram bot token from @BotFather
