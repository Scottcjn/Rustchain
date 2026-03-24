# RustChain Telegram Bot

Telegram bot for querying the RustChain network. Created for [Issue #1597](https://github.com/Scottcjn/rustchain-bounties/issues/1597).

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/health` | Node health, version, uptime |
| `/epoch` | Current epoch, slot, supply |
| `/balance <miner_id>` | Wallet balance for a miner |
| `/miners` | Enrolled miners and epoch pot |
| `/price` | RTC price (DexScreener or reference) |
| `/help` | List all commands |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Telegram bot token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the API token

### 3. Configure

Set your bot token as an environment variable:

```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
```

Or create a `.env` file in the bot directory:

```
TELEGRAM_BOT_TOKEN=your-token-here
```

### 4. Run

```bash
python bot.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (required) | Bot token from @BotFather |
| `RUSTCHAIN_API_URL` | `https://rustchain.org` | RustChain API base URL |
| `RTC_PRICE_USD` | `0.10` | Fallback RTC price if DexScreener unavailable |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max requests per user per minute |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints Used

- `GET /health` -- Node health status
- `GET /epoch` -- Epoch info, miner count, supply
- `GET /wallet/balance?miner_id=ID` -- Wallet balance
- DexScreener search API (optional, for live RTC price)

## Requirements

- Python 3.11+
- Network access to rustchain.org
