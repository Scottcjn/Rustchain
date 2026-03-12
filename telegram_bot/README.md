# RustChain Telegram Query Bot

> Issue #1597 - A minimal, safe Telegram bot for querying RustChain API

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This Telegram bot provides a simple interface to query the RustChain blockchain network. It supports read-only operations for checking node health, epoch information, wallet balances, and network statistics.

## Features

- ✅ **Safe & Read-Only**: All commands are query-only, no write operations
- ✅ **Environment Configuration**: Easy setup via environment variables
- ✅ **Rate Limiting**: Built-in protection against API abuse
- ✅ **Error Handling**: Graceful error handling with user-friendly messages
- ✅ **Minimal Dependencies**: Lightweight with only essential packages

## Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message and introduction | `/start` |
| `/help` | Show available commands and usage | `/help` |
| `/health` | Check node health status | `/health` |
| `/epoch` | Get current epoch information | `/epoch` |
| `/balance` | Check wallet balance | `/balance Ivan-houzhiwen` |
| `/stats` | Get network statistics | `/stats` |

## Quick Start

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` to create a new bot
3. Follow the instructions to name your bot
4. Copy the API token provided

### 2. Install Dependencies

```bash
cd telegram_bot
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your bot token
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

Or set environment variables directly:

```bash
export TELEGRAM_BOT_TOKEN='your_bot_token_here'
export RUSTCHAIN_API_URL='https://50.28.86.131'
```

### 4. Run the Bot

```bash
python rustchain_query_bot.py
```

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (required) | Bot token from @BotFather |
| `RUSTCHAIN_API_URL` | `https://50.28.86.131` | RustChain API endpoint |
| `RUSTCHAIN_VERIFY_SSL` | `false` | Verify SSL certificates |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max requests per user per minute |
| `LOG_LEVEL` | `INFO` | Logging level |

## Command Examples

### Check Node Health

```
/health
```

Response:
```
✅ Node Health

Status: Online
Version: 2.2.1-rip200
Uptime: 5d 3h 42m

API: https://50.28.86.131
```

### Get Epoch Information

```
/epoch
```

Response:
```
📅 Current Epoch

Epoch: 95
Slot: 12345
Height: 67890

Network: RustChain Mainnet
```

### Check Wallet Balance

```
/balance Ivan-houzhiwen
```

Response:
```
💰 Wallet Balance

Wallet: Ivan-houzhiwen
Balance: 155.0 RTC
(Raw: 155000000 units)
```

### Get Network Statistics

```
/stats
```

Response:
```
📊 Network Statistics

Active Miners: 42
Current Epoch: 95
Block Height: 67890

API: https://50.28.86.131
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=telegram_bot --cov-report=html
```

## Development

### Code Style

This project uses `ruff` for linting:

```bash
pip install ruff
ruff check telegram_bot/
```

### Type Checking

Optional type checking with `mypy`:

```bash
pip install mypy
mypy telegram_bot/
```

## Project Structure

```
telegram_bot/
├── __init__.py                 # Package initialization
├── rustchain_query_bot.py      # Main bot implementation
├── requirements.txt            # Python dependencies
├── .env.example               # Environment configuration template
└── README.md                  # This file
```

## API Reference

### RustChainClient

The bot uses a simple client for the RustChain API:

```python
from rustchain_query_bot import RustChainClient

client = RustChainClient()

# Health check
health = client.health()

# Epoch info
epoch = client.epoch()

# Wallet balance
balance = client.balance("Ivan-houzhiwen")

# Miners list
miners = client.miners()
```

## Security Considerations

1. **Bot Token**: Never commit your `.env` file or expose your bot token
2. **SSL Verification**: Enable SSL verification in production (`RUSTCHAIN_VERIFY_SSL=true`)
3. **Rate Limiting**: Adjust rate limits based on your API capacity
4. **Read-Only**: This bot only performs read operations - no private keys needed

## Troubleshooting

### Bot doesn't respond

1. Check if the bot token is correct
2. Verify the bot is added to a group (if using in groups)
3. Check logs for error messages

### API connection errors

1. Verify `RUSTCHAIN_API_URL` is accessible
2. Check network connectivity
3. Try enabling/disabling SSL verification

### Rate limit errors

- Wait a minute before sending more commands
- Increase `RATE_LIMIT_PER_MINUTE` if needed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Related Links

- [RustChain Official Website](https://rustchain.io)
- [RustChain API Documentation](../API_WALKTHROUGH.md)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)

## Support

For issues or questions:
- Open an issue on GitHub
- Join the RustChain community Telegram group

---

*Built with ❤️ for the RustChain community*
