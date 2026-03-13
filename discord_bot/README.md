# RustChain Discord Bot

A Discord bot that provides read-only access to RustChain network information through slash commands and text commands.

## Features

- **Health Check**: Query node health status (uptime, version, sync status)
- **Epoch Info**: Get current epoch number, slot, and enrolled miners
- **Balance Lookup**: Check RTC balance for any miner wallet
- **Dual Command Interface**: Both slash commands (`/health`) and text commands (`!health`)
- **Environment-based Configuration**: Easy deployment with `.env` files
- **Self-signed Certificate Support**: Works with RustChain's self-signed HTTPS certificates

## Commands

### Slash Commands

| Command | Description |
|---------|-------------|
| `/health` | Check RustChain node health status |
| `/epoch` | Get current epoch information |
| `/balance <miner_id>` | Check RTC balance for a miner wallet |

### Text Commands (Legacy)

| Command | Description |
|---------|-------------|
| `!health` | Check node health status |
| `!epoch` | Get current epoch information |
| `!balance <miner_id>` | Check balance for a miner ID |

## Quick Start

### 1. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token
5. Enable "Message Content Intent" under Privileged Gateway Intents
6. Invite bot to your server using OAuth2 URL Generator (select `bot` and `applications.commands` scopes)

### 2. Install Dependencies

```bash
cd discord_bot
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN
```

### 4. Run

```bash
python bot.py
```

## Configuration

All settings are loaded from environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | - | Discord bot token |
| `DISCORD_GUILD_ID` | No | - | Restrict bot to specific guild |
| `RUSTCHAIN_NODE_URL` | No | `https://rustchain.org` | RustChain API base URL |
| `RUSTCHAIN_API_TIMEOUT` | No | `10.0` | HTTP request timeout (seconds) |
| `BOT_PREFIX` | No | `!` | Prefix for text commands |
| `BOT_OWNER_ID` | No | - | Discord user ID of bot owner |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## Usage Examples

### Health Check

```
/health
```

Response shows:
- Node status (OK/Unhealthy)
- Software version
- Uptime
- Database read/write status
- Sync status (slots behind tip)

### Epoch Information

```
/epoch
```

Response shows:
- Current epoch number
- Current slot
- Blocks per epoch
- Epoch POT (reward pool)
- Number of enrolled miners

### Balance Lookup

```
/balance miner_id:scott
```

Response shows:
- Miner ID (truncated if long)
- Balance in RTC (6 decimal places)

## Development

### Running Tests

```bash
cd discord_bot/tests
python -m pytest test_bot.py -v
```

### Project Structure

```
discord_bot/
├── bot.py              # Main bot implementation
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
├── .env.example        # Example environment file
├── README.md           # This file
└── tests/
    └── test_bot.py     # Unit tests for command handlers
```

## Docker Deployment (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Build and run:

```bash
docker build -t rustchain-discord-bot .
docker run -d --env-file .env rustchain-discord-bot
```

## Security Notes

- **Never commit your `.env` file** - it contains sensitive tokens
- The bot uses read-only API endpoints only
- Self-signed certificates are accepted for the RustChain node (intentional for internal nodes)
- Consider restricting the bot to specific guilds in production

## Troubleshooting

### Bot doesn't respond to commands

1. Ensure "Message Content Intent" is enabled in Discord Developer Portal
2. Check bot has proper permissions in your server
3. Verify `DISCORD_TOKEN` is correct in `.env`

### Commands not appearing

1. Wait a few minutes for Discord to sync slash commands
2. Try kicking and re-inviting the bot
3. Check bot has `applications.commands` scope in invite URL

### API connection errors

1. Verify `RUSTCHAIN_NODE_URL` is accessible
2. Check network connectivity to the node
3. Increase `RUSTCHAIN_API_TIMEOUT` if node is slow

## License

Same license as the main RustChain project.

## Contributing

See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
