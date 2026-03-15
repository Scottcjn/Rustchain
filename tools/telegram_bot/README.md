# RustChain Telegram Community Bot

Telegram bot for RustChain community — Bounty #249 (50 RTC + bonuses).

## Commands

| Command | Description |
|---------|-------------|
| `/price` | wRTC price from Raydium via DexScreener |
| `/miners` | Active miner list and count |
| `/epoch` | Current epoch, slot, pot, enrolled miners |
| `/balance <wallet>` | Check RTC balance for a wallet |
| `/health` | Node health, version, uptime, DB status |
| `/subscribe` | Enable mining & price alerts in this chat |
| `/unsubscribe` | Disable alerts |

## Bonus Features

- **Mining alerts** — notifies subscribed chats when a new miner joins or an epoch settles
- **Price alerts** — notifies when wRTC price moves >5% (configurable)
- **Inline queries** — type `@YourBot price`, `miners`, or `epoch` in any chat

## Setup

```bash
pip install -r requirements.txt
```

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.
2. Enable inline mode via BotFather (`/setinline`) for inline queries.
3. Configure environment:

```bash
cp .env.example .env
# Edit .env with your bot token
```

4. Run:

```bash
python telegram_bot.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | _(required)_ | Bot token from BotFather |
| `RUSTCHAIN_API` | `https://rustchain.org` | RustChain node URL |
| `PRICE_ALERT_INTERVAL` | `120` | Seconds between price checks |
| `MINER_ALERT_INTERVAL` | `60` | Seconds between miner checks |
| `PRICE_CHANGE_THRESHOLD` | `5.0` | % change to trigger price alert |

## Docker

```bash
docker build -t rustchain-tg-bot .
docker run --env-file .env rustchain-tg-bot
```

## Key Improvements

- **Async HTTP** — uses `aiohttp` instead of blocking `requests` in async handlers
- **Correct API fields** — uses `amount_rtc`, `ok`, `slot`, `enrolled_miners` per API docs
- **All bonus features** — mining alerts, price alerts, inline queries
