# RustChain Slack Integration

Slack bot for real-time RustChain node monitoring, wallet balance lookups,
and mining operations visibility.

## Features

### Slash Commands

| Command | Description |
|---------|-------------|
| `/rtc-status` | Node health across all configured endpoints — version, epoch, miner count |
| `/rtc-balance <pubkey>` | Look up RTC balance for a miner public key |
| `/rtc-miners` | List active miners with last-seen times and epoch info |

### Automated Alerts

The bot polls node `/health` endpoints on a configurable interval (default 5 min)
and posts to a designated Slack channel when:

- A node goes **down** or **recovers**
- Active miner count **drops** by 2 or more between checks
- A node is unreachable on first startup

### Daily Mining Summary

A summary is posted every day at **12:00 UTC** with per-node stats:
current epoch, miner count, total RTC distributed, and node version.

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App**
2. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `chat:write`
   - `commands`
3. Under **Slash Commands**, create:
   - `/rtc-status`
   - `/rtc-balance`
   - `/rtc-miners`
4. Install the app to your workspace and copy the **Bot User OAuth Token**.

For **Socket Mode** (no public URL required):
- Enable Socket Mode under **Settings → Socket Mode**
- Generate an **App-Level Token** with `connections:write` scope

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Slack tokens and node URLs
```

### 3. Install & Run

```bash
pip install -r requirements.txt
python slack_bot.py
```

The bot supports two connection modes:

- **Socket Mode** (recommended for private networks): set `SLACK_APP_TOKEN`
- **HTTP Mode**: expose the `PORT` (default 3000) behind a public URL and
  configure it as the Request URL in your Slack app settings

### 4. Docker (optional)

```bash
docker build -t rustchain-slack-bot .
docker run --env-file .env rustchain-slack-bot
```

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes | — | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Yes | — | Signing secret from app settings |
| `SLACK_APP_TOKEN` | No | — | App-level token for Socket Mode |
| `SLACK_ALERT_CHANNEL` | No | — | Channel ID for alerts/summaries |
| `RUSTCHAIN_NODE_URLS` | No | `https://rustchain.org` | Comma-separated node URLs |
| `MONITOR_INTERVAL_SEC` | No | `300` | Polling interval in seconds |
| `REQUEST_TIMEOUT_SEC` | No | `10` | HTTP request timeout |
| `PORT` | No | `3000` | HTTP server port (non-Socket Mode) |

## Architecture

```
slack_bot.py
├── Slash command handlers (/rtc-status, /rtc-balance, /rtc-miners)
├── RustChain API client (health, stats, balance, miners, epoch)
├── NodeMonitor — background health checker with state-change alerts
└── APScheduler — cron-based daily summary + interval-based health polls
```

The bot talks to standard RustChain node endpoints:
- `GET /health` — node liveness
- `GET /api/stats` — version, epoch, miner count
- `GET /api/miners` — active miner list
- `GET /balance/<pk>` — wallet balance
- `GET /epoch` — current epoch details
