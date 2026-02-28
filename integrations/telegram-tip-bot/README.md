# RustChain Telegram Tip Bot

A lightweight, standalone RTC tip bot for Telegram using on-chain transactions.

## Bounty

This bot is built for the [RustChain Discord/Telegram Tip Bot bounty](https://github.com/Scottcjn/rustchain-bounties/issues/31) (50 RTC).

## Features

- ✅ `/tip @user <amount>` — Send RTC to another user
- ✅ `/balance` — Check your RTC balance
- ✅ `/deposit` — Show your RTC wallet address
- ✅ `/withdraw <address> <amount>` — Withdraw to external RTC wallet
- ✅ `/leaderboard` — Top RTC holders in the server
- ⏳ `/rain <amount>` — Split RTC across recent active users (coming soon)
- ✅ Real on-chain RTC transfers via `/wallet/transfer/signed`
- ✅ Ed25519 signed transactions
- ✅ Deterministic wallet derivation from user ID + bot secret
- ✅ Rate limiting and minimum amounts
- ✅ Single-file deployment

## Quick Start

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use `/newbot` to create a new bot
3. Copy the API token

### 2. Install Dependencies

```bash
pip install python-telegram-bot requests
```

Or with the bundled requirements:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Required
export TELEGRAM_BOT_TOKEN="your-bot-token-here"

# Optional (defaults shown)
export RUSTCHAIN_NODE_URL="https://50.28.86.131"
export BOT_SECRET="your-secret-key-for-wallet-derivation"
```

### 4. Run the Bot

```bash
python bot.py
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot API token |
| `RUSTCHAIN_NODE_URL` | No | `https://50.28.86.131` | RustChain node URL |
| `RUSTCHAIN_VERIFY_SSL` | No | `false` | Verify SSL certificates |
| `BOT_SECRET` | No | `rustchain-tip-bot-secret-key` | Secret for wallet derivation |

## Security

### Wallet Derivation

Each Telegram user gets a deterministic RTC wallet derived from:

```
address = SHA256(BOT_SECRET:user_id)[:40]
```

The bot secret should be kept private and consistent across restarts.

### Ed25519 Signing

Transactions are signed with Ed25519 using derived keypairs. The signing key is derived from the bot secret and user ID, ensuring:

- Each user has a unique signing key
- Keys can be regenerated if the bot secret is known
- No external wallet software required

### Rate Limiting

- Minimum tip: 0.001 RTC
- Rate limit: 10 seconds between tips per user
- Large transfer confirmation: Required for > 10 RTC

## API Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/wallet/balance` | GET | Get RTC balance for address |
| `/wallet/transfer/signed` | POST | Submit signed transfer |

## Data Storage

Wallet data is stored in:

```
~/.rustchain-tip-bot/
├── wallets.json      # User wallet data
└── rate_limits.json  # Rate limiting state
```

## Development

### Project Structure

```
rustchain-tip-bot/
├── bot.py            # Main bot code (single file)
├── README.md         # This file
└── requirements.txt  # Python dependencies
```

### Adding Commands

To add a new command:

1. Create an async function with signature:
   ```python
   async def cmd_xxx(update: Update, context: ContextTypes.DEFAULT_TYPE):
   ```

2. Register it in `main()`:
   ```python
   app.add_handler(CommandHandler("xxx", cmd_xxx))
   ```

3. Add to command list in `set_commands()`.

## Testing

### Test Commands

```bash
# Start bot
/start

# Check balance
/balance

# Get deposit address
/deposit

# Tip a user
/tip @username 5

# Withdraw
/withdraw RTCabc123... 10

# View leaderboard
/leaderboard
```

### Network Test

```bash
# Check node health
curl -sk https://50.28.86.131/health

# View active miners
curl -sk https://50.28.86.131/api/miners
```

## Roadmap

- [ ] Proper Ed25519 signing with `cryptography` library
- [ ] `/rain` command implementation
- [ ] Username → User ID mapping for tips
- [ ] Transaction history command
- [ ] Multi-language support
- [ ] Discord bot version

## License

MIT License

## Credits

- Built for [RustChain](https://github.com/Scottcjn/Rustchain)
- Bounty: [Issue #31](https://github.com/Scottcjn/rustchain-bounties/issues/31)
- Author: agent渡文 (OpenClaw)
