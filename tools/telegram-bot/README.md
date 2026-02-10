# RustChain Telegram Wallet Bot

Implemention of Bounty #27 - A Telegram-based wallet manager for RTC tokens.

## Features
- **Wallet Management**: Create a new 24-word mnemonic wallet or import an existing one directly in Telegram DM.
- **Secure Storage**: Private keys are encrypted using AES-256-GCM with PBKDF2 key derivation (mirroring the official CLI wallet security).
- **Balance & Stats**: Check RTC balance and network statistics.
- **Transactions**: Send RTC to any address with on-device (bot-side) Ed25519 signing.

## Commands
- `/start` - Initialize the bot and setup/import your wallet.
- `/balance` - View your current RTC balance.
- `/send` - Transfer RTC to another address (requires password).
- `/history` - View transaction history.
- `/price` - Show network stats and reference price.
- `/cancel` - Cancel any active conversation.

## Setup
1. Create a bot via `@BotFather` and get your `API TOKEN`.
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file:
   ```
   RTC_TELEGRAM_TOKEN=your_token_here
   RUSTCHAIN_NODE_URL=https://50.28.86.131
   ```
4. Run the bot: `python bot.py`
