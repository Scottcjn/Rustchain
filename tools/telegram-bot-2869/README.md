# RustChain Telegram Bot — Issue #2869

A complete Telegram bot for querying RustChain wallet and miner status.

## Features

- **`/balance <wallet>`** — Check RTC wallet balance
- **`/miners`** — List active miners with hardware details
- **`/epoch`** — Current epoch info (slot, pot, enrolled miners, supply)
- **`/price`** — RTC/wRTC price in USD (from node + DexScreener)
- **`/help`** — Show available commands
- **Rate limiting** — 1 request per 5 seconds per user (configurable)
- **Error handling** — Graceful messages when node is offline or unreachable
- **Self-signed cert support** — Works with RustChain node TLS out of the box

## Quick Start

```bash
# 1. Clone / navigate to the directory
cd tools/telegram-bot-2869

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env and set your TELEGRAM_BOT_TOKEN

# 5. Run
python bot.py
```

## Getting a Telegram Bot Token

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the instructions
3. Copy the API token
4. Set it in your `.env` file: `TELEGRAM_BOT_TOKEN=your-token-here`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from @BotFather |
| `RUSTCHAIN_NODE_URL` | `https://rustchain.org` | RustChain node URL |
| `RATE_LIMIT_SECONDS` | `5` | Min seconds between requests per user |
| `REQUEST_TIMEOUT` | `15` | HTTP request timeout in seconds |
| `RTC_PRICE_USD` | `0.10` | Fallback price when DexScreener is down |

## Deployment

### Option 1: Railway

1. Push this directory to a GitHub repo
2. Create a new project on [Railway](https://railway.app)
3. Connect your repo
4. Set environment variables in Railway dashboard:
   - `TELEGRAM_BOT_TOKEN` — your bot token
   - `RUSTCHAIN_NODE_URL` — `https://rustchain.org`
5. Railway auto-deploys using the `requirements.txt`
6. Set the start command: `python bot.py`

**railway.json** (optional, for clarity):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python bot.py",
    "healthcheckPath": "/",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### Option 2: Fly.io

1. Install [flyctl](https://fly.io/docs/hands-on/install-flyctl/)
2. Run `fly launch` in this directory
3. Set secrets:
   ```bash
   fly secrets set TELEGRAM_BOT_TOKEN="your-token"
   fly secrets set RUSTCHAIN_NODE_URL="https://rustchain.org"
   ```
4. Deploy:
   ```bash
   fly deploy
   ```

**Dockerfile** for Fly.io:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

**fly.toml**:
```toml
app = "rustchain-telegram-bot"
primary_region = "sjc"

[build]

[env]
  RUSTCHAIN_NODE_URL = "https://rustchain.org"

[processes]
  app = "python bot.py"
```

### Option 3: systemd (VPS / Dedicated Server)

1. Copy files to `/opt/rustchain-telegram-bot/`:
   ```bash
   sudo mkdir -p /opt/rustchain-telegram-bot
   sudo cp -r * /opt/rustchain-telegram-bot/
   ```

2. Create virtual environment:
   ```bash
   cd /opt/rustchain-telegram-bot
   sudo python3 -m venv venv
   sudo venv/bin/pip install -r requirements.txt
   ```

3. Create `.env` file:
   ```bash
   sudo cp .env.example .env
   sudo nano .env  # set your token and config
   ```

4. Create a dedicated user:
   ```bash
   sudo useradd --system --no-create-home rustchain
   sudo chown -R rustchain:rustchain /opt/rustchain-telegram-bot
   ```

5. Install systemd service:
   ```bash
   sudo cp rustchain-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable rustchain-bot
   sudo systemctl start rustchain-bot
   ```

6. Check status:
   ```bash
   sudo systemctl status rustchain-bot
   sudo journalctl -u rustchain-bot -f
   ```

## Architecture

```
User → Telegram → Bot → httpx → RustChain Node
                          ↓
                    DexScreener (price)
```

- **Async I/O**: Uses `python-telegram-bot` v20+ (async) + `httpx` for non-blocking HTTP
- **Rate limiter**: In-memory per-user token bucket (1 req / 5s)
- **Error handling**: Catches connection errors, timeouts, HTTP errors — all return user-friendly messages
- **TLS**: Self-signed certificates disabled by default (RustChain nodes use self-signed certs)

## Testing

Run the smoke tests:

```bash
pip install -r requirements.txt
python test_bot.py
```

Tests cover:
- Rate limiter logic
- API response parsing
- Error handling for offline nodes
- Markdown escaping
- Command handler registration

## License

Apache-2.0 (same as RustChain)
