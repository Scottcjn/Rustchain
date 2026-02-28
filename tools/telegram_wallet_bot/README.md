# RustChain Telegram Wallet Bot

> Bounty: 75 RTC | Issue: [#27](https://github.com/Scottcjn/Rustchain/issues/27)

A secure Telegram bot for managing RTC wallets with Ed25519 signed transactions.

## Features

| Command | Description |
|---------|-------------|
| `/create` | Create a new wallet (DM only) |
| `/balance [addr]` | Check RTC balance |
| `/send <addr> <amount> [memo]` | Send RTC (DM only, password-signed) |
| `/history [addr]` | Recent transaction history |
| `/price` | wRTC market stats via DexScreener |
| `/address` | Show your wallet address |
| `/export` | Show your public key |
| `/help` | Command reference |

## Security Model

- **Ed25519** keypairs generated with PyNaCl (libsodium)
- Private keys encrypted at rest with **Argon2id** KDF + **XSalsa20-Poly1305** AEAD
- Wallet creation and sending only work in **DMs** (never in group chats)
- Passwords are **never stored** — required per-transaction for signing
- Password messages are **auto-deleted** from chat after processing
- Address derivation matches the node: `RTC` + SHA256(pubkey)[:40]

## Architecture

```
User (Telegram DM)
  │
  ├── /create ─→ Generate Ed25519 keypair
  │               Encrypt with Argon2id + password
  │               Save to ~/.rustchain/telegram_wallets/
  │
  ├── /send ─→ Prompt for recipient, amount, memo
  │             Ask for password (auto-deleted)
  │             Decrypt private key
  │             Sign transaction (Ed25519)
  │             POST /tx/submit to RustChain node
  │
  ├── /balance ─→ GET /balance?miner_id=<addr>
  │
  ├── /history ─→ GET /wallet/history?miner_id=<addr>
  │
  └── /price ─→ GET DexScreener API for wRTC/SOL pair
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your bot token

# Run
python wallet_bot.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (required) | Bot token from @BotFather |
| `RUSTCHAIN_API` | `https://rustchain.org` | RustChain node URL |
| `RUSTCHAIN_VERIFY_SSL` | `false` | Verify SSL certificates |
| `KEYSTORE_DIR` | `~/.rustchain/telegram_wallets` | Encrypted keystore location |

## Keystore Format

Each user's wallet is stored as an encrypted JSON file:

```json
{
  "version": 1,
  "address": "RTC<sha256_prefix>",
  "public_key": "<ed25519_pubkey_hex>",
  "crypto": {
    "cipher": "xsalsa20-poly1305",
    "kdf": "argon2id",
    "salt": "<hex>",
    "ciphertext": "<hex>"
  },
  "created_at": 1709136000,
  "telegram_user_id": 123456789
}
```

## Transaction Signing

Transactions are signed offline before submission:

1. Build message: `{from}:{to}:{amount_urtc}:{nonce}:{memo}`
2. Sign with Ed25519 private key
3. Submit `{from_addr, to_addr, amount_urtc, nonce, memo, signature, public_key}` to `/tx/submit`

The nonce is a millisecond timestamp to prevent replay attacks.

## Dependencies

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) >= 20.0
- [PyNaCl](https://github.com/pyca/pynacl) >= 1.5.0 (libsodium bindings)
- [requests](https://github.com/psf/requests) >= 2.28.0
- [python-dotenv](https://github.com/theskumar/python-dotenv) >= 1.0.0

## License

MIT — Part of the RustChain project.
