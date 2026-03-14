# Bounty Contribution

This addresses issue #970: feat: Telegram bot for RustChain API queries (#1597)

## Description
## Summary

- Adds an async Telegram bot (`tools/telegram-bot/`) for querying the RustChain network
- Commands: `/health`, `/epoch`, `/balance <miner_id>`, `/miners`, `/price`, `/help`, `/start`
- Uses `httpx` for async API calls, `python-telegram-bot` for Telegram integration

## Features

- **Async throughout** — non-blocking API calls via httpx
- **Rate limiting** — configurable per-user request limits
- **DexScreener integration** — attempts live RTC price lookup, falls back to reference pri

## Payment
0x4F666e7b4F63637223625FD4e9Ace6055fD6a847
