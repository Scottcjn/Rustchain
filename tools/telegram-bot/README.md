# RustChain Telegram Bot

> **Deprecated feature:** the price lookup in this tool queried third-party market-data services. It is deprecated: do not use, extend, or advertise it — RustChain official materials do not reference market prices. The code is left in place pending removal. The wRTC bridge is disabled; RTC is earned for contributions and spent on services in the ecosystem, with no off-ramp. See [Earn & Spend RTC](https://github.com/Scottcjn/rustchain-bounties/blob/main/docs/EARN_AND_SPEND.md).

Telegram bot for querying the RustChain network. Created for [Issue #1597](https://github.com/Scottcjn/rustchain-bounties/issues/1597).

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/health` | Node health, version, uptime |
| `/epoch` | Current epoch, slot, supply |
| `/balance <miner_id>` | Wallet balance for a miner |
| `/miners` | Enrolled miners and epoch pot |
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
| `RATE_LIMIT_PER_MINUTE` | `10` | Max requests per user per minute |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints Used

- `GET /health` -- Node health status
- `GET /epoch` -- Epoch info, miner count, supply
- `GET /wallet/balance?miner_id=ID` -- Wallet balance

## Requirements

- Python 3.11+
- Network access to rustchain.org
