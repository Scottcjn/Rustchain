# BoTTube Weekly Digest Bot

> **Issue #2279** - Automated community newsletter bot for RustChain

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

The BoTTube Weekly Digest Bot is an automated community newsletter system that generates and distributes weekly digests containing:

- 📊 **Network Statistics** - Epoch, slot, block height, active miners
- 🏆 **Top Miners** - Leaderboard of top RTC holders
- 🎬 **Video Highlights** - Top content from BoTTube
- ⚙️ **Node Status** - Version, uptime, health metrics

## Features

- **Multi-Channel Delivery**
  - Discord (webhook or bot)
  - Telegram
  - Email (SMTP)

- **Flexible Scheduling**
  - Weekly digests (configurable day/time)
  - Daily digests
  - One-shot mode for testing

- **Configurable Content**
  - Top N miners (default: 10)
  - Top videos (default: 5)
  - Include/exclude sections

- **Dry Run Mode** - Test without sending

## Quick Start

### 1. Install Dependencies

```bash
cd bottube_digest_bot
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your configuration
```

### 3. Run (Dry Run Mode)

```bash
# Test without sending
python bottube_digest_bot.py --dry-run
```

### 4. Run (Send Digest)

```bash
# Send digest through configured channels
python bottube_digest_bot.py
```

## Configuration

All settings are loaded from environment variables:

### RustChain API

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_NODE_URL` | `https://50.28.86.131` | RustChain node URL |
| `RUSTCHAIN_API_TIMEOUT` | `15.0` | API timeout (seconds) |
| `RUSTCHAIN_VERIFY_SSL` | `false` | Verify SSL certificates |

### BoTTube API

| Variable | Default | Description |
|----------|---------|-------------|
| `BOTTUBE_URL` | `https://bottube.ai` | BoTTube base URL |
| `BOTTUBE_API_TIMEOUT` | `10.0` | API timeout (seconds) |

### Discord

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | No | Discord webhook URL for simple posting |
| `DISCORD_BOT_TOKEN` | No | Discord bot token (for bot method) |
| `DISCORD_CHANNEL_ID` | No* | Channel ID (required if using bot token) |

*Required if using bot token method

### Telegram

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | Chat/channel ID to send to |

### Email (SMTP)

| Variable | Required | Description |
|----------|----------|-------------|
| `SMTP_HOST` | Yes | SMTP server hostname |
| `SMTP_PORT` | No | SMTP port (default: 587) |
| `SMTP_USER` | Yes | SMTP username |
| `SMTP_PASSWORD` | Yes | SMTP password |
| `SMTP_FROM` | Yes | From email address |
| `DIGEST_RECIPIENTS` | Yes | Comma-separated recipient list |

### Digest Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DIGEST_TOP_N` | `10` | Number of top miners to include |
| `DIGEST_TOP_VIDEOS` | `5` | Number of top videos to include |
| `INCLUDE_EPOCH_SUMMARY` | `true` | Include epoch summary |
| `INCLUDE_MINER_STATS` | `true` | Include miner statistics |
| `INCLUDE_VIDEO_HIGHLIGHTS` | `true` | Include video highlights |

### Scheduling

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULE_MODE` | `weekly` | `weekly`, `daily`, or `custom` |
| `SCHEDULE_DAY` | `monday` | Day of week (monday-sunday) |
| `SCHEDULE_HOUR` | `9` | UTC hour to send (0-23) |
| `SCHEDULE_MINUTE` | `0` | UTC minute to send (0-59) |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `` | Log file path (optional) |

### Testing

| Variable | Default | Description |
|----------|---------|-------------|
| `DRY_RUN` | `false` | Run without sending messages |

## Usage Examples

### Test Run (Dry Mode)

```bash
# Test configuration and generation without sending
python bottube_digest_bot.py --dry-run
```

### Send Once

```bash
# Generate and send digest immediately
python bottube_digest_bot.py
```

### Scheduled Mode

```bash
# Run continuously with scheduled sends
python bottube_digest_bot.py --schedule
```

### Discord Webhook Only

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxx/yyy"
python bottube_digest_bot.py
```

### Email Digest Only

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export SMTP_FROM="digest@rustchain.io"
export DIGEST_RECIPIENTS="user1@example.com,user2@example.com"
python bottube_digest_bot.py
```

## Example Output

### Discord Message

```
📊 **BoTTube Weekly Digest**

**Period:** 2026-03-15 to 2026-03-22
**Generated:** 2026-03-22T10:00:00 UTC

━━━ NETWORK STATUS ━━━
🔗 **Epoch:** 95
📍 **Slot:** 12,345
📦 **Height:** 67,890
👥 **Active Miners:** 42
⚙️ **Node Version:** 2.2.1
⏱️ **Uptime:** 5d 3h 42m

━━━ TOP MINERS ━━━
1. **scott-miner-001** - 1,500.50 RTC (x86_64)
2. **ivan-miner-002** - 1,200.25 RTC (arm64)
3. **alex-miner-003** - 950.00 RTC (x86_64)

━━━ TOP VIDEOS ━━━
1. **RustChain Tutorial #1** by Scott
2. **Mining Setup Guide** by Ivan
3. **BoTTube Deep Dive** by Alex

━━━
_Generated by BoTTube Digest Bot_ | [BoTTube](https://bottube.ai) | [RustChain](https://rustchain.io)
```

### Email Subject

```
📊 BoTTube Weekly Digest - 2026-03-22
```

## Project Structure

```
bottube_digest_bot/
├── bottube_digest_bot.py   # Main bot implementation
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── .env.example           # Environment configuration template
├── README.md              # This file
└── tests/
    └── test_bottube_digest_bot.py  # Unit tests
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
python -m pytest tests/test_bottube_digest_bot.py -v

# Run with coverage
python -m pytest tests/ -v --cov=bottube_digest_bot --cov-report=html
```

## GitHub Actions Integration

The bot can be run via GitHub Actions on a schedule:

```yaml
name: Weekly Digest Bot

on:
  schedule:
    - cron: '0 9 * * MON'  # Every Monday at 9:00 UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  send-digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r bottube_digest_bot/requirements.txt

      - name: Send weekly digest
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          RUSTCHAIN_NODE_URL: ${{ secrets.RUSTCHAIN_NODE_URL }}
        run: |
          python bottube_digest_bot/bottube_digest_bot.py
```

## API Reference

### RustChainClient

```python
from bottube_digest_bot import RustChainClient
from config import BotConfig

config = BotConfig()
client = RustChainClient(config)

# Health check
health = await client.health()

# Epoch info
epoch = await client.epoch()

# Miners list
miners = await client.miners()

# Wallet balance
balance = await client.wallet_balance("miner-id")

# Close client
await client.close()
```

### BoTTubeClient

```python
from bottube_digest_bot import BoTTubeClient

client = BoTTubeClient(config)

# Get recent videos
videos = await client.videos(limit=20)

# Close client
await client.close()
```

### DigestGenerator

```python
from bottube_digest_bot import DigestGenerator

generator = DigestGenerator(config)

# Generate complete digest
content = await generator.generate()

# Access digest data
print(f"Epoch: {content.current_epoch}")
print(f"Top miners: {len(content.top_miners)}")
print(f"Top videos: {len(content.top_videos)}")

# Close generator
await generator.close()
```

### DigestFormatter

```python
from bottube_digest_bot import DigestFormatter

# Format for Discord
discord_msg = DigestFormatter.format_discord(content, config)

# Format for Telegram
telegram_msg = DigestFormatter.format_telegram(content, config)

# Format for email
email_html = DigestFormatter.format_email_html(content, config)
email_subject = DigestFormatter.format_email_subject(content)
```

### DigestSender

```python
from bottube_digest_bot import DigestSender

sender = DigestSender(config)

# Send through all configured channels
results = await sender.send_all(content)

# Check results
for channel, success in results.items():
    print(f"{channel}: {'✅' if success else '❌'}")
```

## Troubleshooting

### Bot doesn't send messages

1. Check that at least one delivery method is configured
2. Verify API tokens/URLs are correct
3. Check logs for error messages
4. Test with `--dry-run` first

### API connection errors

1. Verify `RUSTCHAIN_NODE_URL` is accessible
2. Check network connectivity
3. Increase `RUSTCHAIN_API_TIMEOUT` if needed
4. Try enabling/disabling SSL verification

### Email delivery failures

1. Verify SMTP credentials are correct
2. Check SMTP server allows your IP
3. For Gmail, use an "App Password" not your regular password
4. Check spam folder for delivered emails

### Rate limiting

If you encounter rate limiting from APIs:

1. Increase timeout values
2. Reduce `DIGEST_TOP_N` to fetch fewer miners
3. Add delays between API calls

## Security Considerations

1. **Never commit `.env` file** - Contains sensitive tokens
2. **Use secrets management** - GitHub Secrets, environment variables
3. **Limit bot permissions** - Only grant necessary Discord/Telegram permissions
4. **Enable SSL verification** - In production, set `RUSTCHAIN_VERIFY_SSL=true`
5. **Rotate tokens regularly** - Especially if exposed accidentally

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest tests/ -v`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Related Links

- [RustChain Official Website](https://rustchain.io)
- [BoTTube](https://bottube.ai)
- [RustChain API Documentation](../API_WALKTHROUGH.md)
- [Discord Bot](../discord_bot/)
- [Telegram Bot](../telegram_bot/)

## Support

For issues or questions:
- Open an issue on GitHub
- Join the RustChain community Discord

---

*Built with ❤️ for the RustChain community*
