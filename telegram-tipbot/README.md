# RustChain Telegram Tip Bot 🦀

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
Each Telegram user gets a deterministic Ed25519 keypair derived from:
```
seed = SHA256(BOT_SECRET + telegram_user_id)
```

This ensures:
- Wallets are reproducible (no backup needed for bot operator)
- Each user has a unique wallet
- Private keys never leave the server

### Security Features
- **Rate limiting**: 10 seconds between tips per user
- **Minimum amounts**: 0.001 RTC minimum tip
- **Large transfer warnings**: Confirmation required for >10 RTC
- **No private key exposure**: Keys derived on-demand, never stored in plaintext

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
export RUSTCHAIN_BOT_SECRET="your_random_32_char_secret"  # Optional, auto-generated if not set
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

1. **BOT_SECRET** must be kept secret — it derives all wallet private keys
2. Self-signed SSL cert on RustChain node — using `verify=False`
3. Custodial model — operator controls all user funds
4. Rate limits prevent spam but not Sybil attacks within limits

## Author

Built by [darkflobi](https://github.com/heyzoos123-blip) — autonomous AI agent 🤖

---

*"Your vintage hardware earns rewards. Make tipping meaningful."*
