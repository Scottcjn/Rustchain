# RustChain Telegram Community Bot

> **Deprecated feature:** the price lookup in this tool queried third-party market-data services. It is deprecated: do not use, extend, or advertise it — RustChain official materials do not reference market prices. The code is left in place pending removal. The wRTC bridge is disabled; RTC is earned for contributions and spent on services in the ecosystem, with no off-ramp. See [Earn & Spend RTC](https://github.com/Scottcjn/rustchain-bounties/blob/main/docs/EARN_AND_SPEND.md).

Telegram bot for RustChain community — Bounty #249 (50 RTC + bonuses).

## Commands

| Command | Description |
|---------|-------------|
| `/price` | Deprecated — see notice above |
| `/miners` | Active miner list and count |
| `/epoch` | Current epoch, slot, pot, enrolled miners |
| `/balance <wallet>` | Check RTC balance for a wallet |
| `/health` | Node health, version, uptime, DB status |
| `/subscribe` | Enable mining alerts in this chat |
| `/unsubscribe` | Disable alerts |

## Bonus Features

- **Mining alerts** — notifies subscribed chats when a new miner joins or an epoch settles
- **Inline queries** — type `@YourBot miners` or `epoch` in any chat

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
| `RUSTCHAIN_VERIFY_SSL` | `true` | Set to `false` only for self-signed test nodes |
| `MINER_ALERT_INTERVAL` | `60` | Seconds between miner checks |

## Docker

```bash
docker build -t rustchain-tg-bot .
docker run --env-file .env rustchain-tg-bot
```

## Key Improvements

- **Non-blocking handlers** — uses `asyncio.to_thread` so live HTTP calls do not block Telegram polling
- **Correct API fields** — uses `amount_rtc`, `ok`, `slot`, `enrolled_miners` per API docs
- **All bonus features** — mining alerts, inline queries
