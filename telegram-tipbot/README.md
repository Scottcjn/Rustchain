# RustChain Telegram Tip Bot

A lightweight tip bot for RTC (RustChain Token) on Telegram.

**Bounty:** [#31 - RustChain Discord/Telegram Tip Bot](https://github.com/Scottcjn/rustchain-bounties/issues/31)

## Features

- `/tip @user <amount>` — Send RTC to another user
- `/balance` — Check your RTC balance  
- `/deposit` — Show your wallet address for deposits
- `/withdraw <address> <amount>` — Withdraw to external RTC wallet
- `/leaderboard` — Top RTC holders in the server
- `/rain <amount>` — Split RTC among recently active users

## Technical Details

### On-Chain Transfers
All transfers use the RustChain `/wallet/transfer/signed` endpoint with real Ed25519 signatures — **not mock signatures or local ledger**.

### Custodial Wallets
This bot is custodial: it generates and stores user signing keys on the bot host.

Recommended: configure `RUSTCHAIN_WALLET_ENC_KEY` so private keys are encrypted at rest in `data/wallets.json`.

### Security Features
- **Rate limiting**: 10 seconds between tips per user
- **Minimum amounts**: 0.001 RTC minimum tip
- **Large transfer warnings**: Confirmation required for >10 RTC
- **Confirm flows**: `/confirm_tip` and `/confirm_withdraw` required for higher-risk actions
- **Encrypted key storage (recommended)**: private keys encrypted at rest with `RUSTCHAIN_WALLET_ENC_KEY`

## Setup

### 1. Get a Bot Token
Message [@BotFather](https://t.me/BotFather) on Telegram:
```
/newbot
```
Save the token it gives you.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
export RUSTCHAIN_BOT_TOKEN="your_telegram_bot_token"
export RUSTCHAIN_BOT_SECRET="your_secret"                 # Optional (deterministic key derivation)
export RUSTCHAIN_WALLET_ENC_KEY="hex64_or_base64_32bytes" # Recommended (encrypt keys at rest)
export RUSTCHAIN_HTTP_VERIFY="true"                       # Default true
export RUSTCHAIN_HTTP_CA_BUNDLE="/path/to/ca-bundle.pem"  # Optional for self-signed certs
```

### 4. Run
```bash
python tipbot.py
```

## File Structure
```
rustchain-tipbot/
├── tipbot.py           # Main bot code
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── data/              # Created at runtime
    ├── wallets.json   # User wallet data
    └── activity.json  # Activity tracking for /rain
```

## API Integration

Uses RustChain node at `https://50.28.86.131`:
- `GET /wallet/balance?miner_id=...` — Check balance
- `POST /wallet/transfer/signed` — Execute signed transfer
- `GET /epoch` — Get network status

### Signed Transfer Format
```json
{
  "from": "sender_miner_id",
  "to": "recipient_miner_id", 
  "amount_i64": 1000000,
  "nonce": 1,
  "signature": "base64_ed25519_signature"
}
```

Message format for signing:
```
{from}:{to}:{amount_i64}:{nonce}
```

## Security Considerations

1. If you use **BOT_SECRET**, keep it secret (it affects key derivation)
2. TLS verification is enabled by default; use a CA bundle to trust self-signed certs
3. Custodial model — operator controls all user funds
4. Rate limits prevent spam but not Sybil attacks within limits

## Author

Built by [darkflobi](https://github.com/heyzoos123-blip) — autonomous AI agent 🤖

---

*"Your vintage hardware earns rewards. Make tipping meaningful."*
