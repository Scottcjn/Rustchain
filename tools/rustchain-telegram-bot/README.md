# 🦀 RustChain Telegram Bot

A Telegram community bot for the RustChain ecosystem.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/price` | Current wRTC price from Raydium |
| `/miners` | Active miner count + top miners |
| `/epoch` | Current epoch information |
| `/balance <wallet>` | Check RTC wallet balance |
| `/health` | Node health status |

### Bonus Features
- **Inline query** — type `@YourBot price` in any chat
- **Price alerts** — notifies when wRTC moves >5%

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your bot token
export BOT_TOKEN='your_token_from_botfather'

# 3. Run
python3 bot.py
```

## Configuration

| Env Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Telegram Bot Token (required) |
| `RUSTCHAIN_API` | `http://50.28.86.131` | RustChain node URL |

## Project Structure

```
├── bot.py           # Main bot application
├── requirements.txt # Python dependencies
└── setup.py         # Setup helper
```

Part of the [RustChain](https://github.com/Scottcjn/RustChain) ecosystem.
