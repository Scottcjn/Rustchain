# RustChain Telegram Community Bot

A Telegram bot for the RustChain Proof-of-Antiquity blockchain community.

**Bounty:** #249 — https://github.com/Scottcjn/rustchain-bounties/issues/249

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + inline menu |
| `/help` | Help |
| `/price` | Current wRTC price from Raydium |
| `/miners` | Active miner count + top miners |
| `/epoch` | Current epoch info |
| `/balance <address>` | Check RTC wallet balance |
| `/health` | Node health, uptime, peers |
| `/stats` | Full network dashboard |
| `/alerts` | Subscribe to mining alerts |

---

## Setup

### 1. Get a Telegram Bot Token

1. Open Telegram and talk to **@BotFather**
2. Send `/newbot`
3. Follow prompts (name, username)
4. Copy the token — looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxYZ`

### 2. Install

```bash
# Clone the repo
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/telegram_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate.ps1  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and add your TELEGRAM_BOT_TOKEN
```

```env
# .env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxYZ
RUSTCHAIN_API_URL=https://explorer.rustchain.org
LOG_LEVEL=INFO
```

### 4. Run

```bash
# Activate venv and run
source venv/bin/activate
python bot.py
```

### 5. Add the Bot to Your Group

1. Add the bot to your Telegram group
2. Make it an admin (or at least give it "Message Members" permission)
3. For group use, you may need to enable `/setprivacy` via BotFather to allow group messages

---

## Deployment

### Systemd Service (Linux)

```bash
sudo cp rustchain_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rustchain_bot
sudo systemctl start rustchain_bot
sudo journalctl -u rustchain_bot -f  # view logs
```

### Docker

```bash
# Build
docker build -t rustchain-telegram-bot .

# Run
docker run -d \
  --name rustchain_bot \
  --env-file .env \
  rustchain-telegram-bot
```

### Hosting on Railway / Render / Fly.io

Set the `TELEGRAM_BOT_TOKEN` environment variable in your dashboard and deploy using Docker or the Python start command.

---

## Architecture

```
tools/telegram_bot/
├── bot.py           # Main Telegram bot (python-telegram-bot v20)
├── api.py           # Async RustChain API client (aiohttp)
├── requirements.txt # Dependencies
├── .env.example     # Environment template
├── Dockerfile       # Container build
├── README.md        # This file
└── rustchain_bot.service  # systemd unit file
```

### API Integration

| Telegram Command | RustChain API |
|-----------------|----------------|
| `/price` | Raydium DEX (wRTC/SOL) |
| `/miners` | `GET /api/miners` |
| `/epoch` | `GET /epoch` |
| `/balance` | `GET /balance/<wallet>` |
| `/health` | `GET /health` |
| `/stats` | `GET /api/stats` |

---

## Bot Features

- **All commands return styled HTML** — bold, code blocks, emojis
- **Error resilience** — graceful fallbacks if API is unavailable
- **Alert system** — background job polls every 60s, notifies subscribers of epoch changes
- **Inline keyboard menus** — quick-access stats from any reply
- **Logging** — structured logs with configurable level

---

## Troubleshooting

**"Bot not found" errors:**
Make sure you added the bot token correctly in `.env`.

**Commands not working in group:**
1. Go to @BotFather → `/setprivacy` → disable
2. Make the bot an admin in your group (or at minimum: Can read messages)

**API errors:**
Check that `explorer.rustchain.org` is reachable from your server.

**Price not showing:**
Raydium price API may be rate-limited. The bot falls back to a manual message if unavailable.

---

## License

MIT — Built for the RustChain community 🦀
