# RustChain Telegram Bot

A Telegram bot for checking RustChain wallet balances and miner status.

## Features

- `/balance <wallet_id>` - Query wallet balance
- `/miners` - List active miners
- `/epoch` - Show current epoch
- `/price` - Show RTC/USD price ($0.10)
- `/help` - List available commands
- Rate limiting: 1 request per 5 seconds per user
- Error handling for offline nodes

## Configuration

Edit `bot.py` and set your values:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"          # Telegram bot token from @BotFather
NODE_BASE_URL = "http://localhost:8080"    # RustChain node URL
RTC_USD_PRICE = 0.10                        # RTC price in USD
RATE_LIMIT_SECONDS = 5                      # Rate limit per user
```

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables or edit bot.py
export BOT_TOKEN="your_bot_token_here"

# Run the bot
python bot.py
```

## Deployment

### Railway

1. Create a new Railway project
2. Connect your GitHub repository
3. Add environment variables:
   - `BOT_TOKEN` = your Telegram bot token
   - `NODE_BASE_URL` = your RustChain node URL
4. Railway auto-detects Python and installs from `requirements.txt`
5. Set the start command: `python bot.py`

### Fly.io

1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Create `fly.toml`:

```toml
app = "rustchain-telegram-bot"
primary_region = "iad"

[build]
  builder = "python"

[deploy]
  release_command = "pip install -r requirements.txt"

[processes]
  app = "python bot.py"

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
```

4. Deploy: `fly launch && fly deploy`

### systemd Service

1. Create the service file:

```ini
[Unit]
Description=RustChain Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/rustchain-telegram-bot
Environment=BOT_TOKEN=your_bot_token_here
Environment=NODE_BASE_URL=http://localhost:8080
ExecStart=/usr/bin/python3 bot.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

2. Install:

```bash
sudo cp rustchain-telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rustchain-telegram-bot
sudo systemctl start rustchain-telegram-bot
sudo journalctl -u rustchain-telegram-bot -f
```

## Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
```

```bash
docker build -t rustchain-bot .
docker run -d \
  --name rustchain-bot \
  -e BOT_TOKEN=your_token \
  -e NODE_BASE_URL=http://node:8080 \
  rustchain-bot
```

## API Endpoints

The bot expects these RustChain node endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Node health check |
| `GET /wallet/balance?miner_id=<id>` | Wallet balance |
| `GET /api/miners` | List of active miners |
| `GET /epoch` | Current epoch info |

## License

MIT
