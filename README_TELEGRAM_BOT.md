# RustChain Telegram Wallet Bot

Commands:
- `/create <wallet_name>` link/create wallet id
- `/balance` check RTC balance
- `/send <to_wallet> <amount>` send RTC
- `/history` recent bot-side tx history
- `/price` network stats

## Setup
```bash
pip install -r requirements-telegram-bot.txt
export TELEGRAM_BOT_TOKEN=xxx
export RUSTCHAIN_API=https://50.28.86.131
python3 rustchain_telegram_bot.py
```

Notes:
- Bot stores wallet alias mapping and local history in `telegram_wallet_state.json`.
- No private key material is persisted by this scaffold.
