# RustChain Slack Bot

Real-time RustChain notifications and slash commands for Slack.

## Features

| Feature | Description |
|---------|-------------|
| `/rtc-status` | Current epoch, slot, height, and node health |
| `/rtc-balance <wallet>` | Check RTC balance for any wallet |
| New block notifications | Posted to channel when a new slot is produced |
| Epoch change alerts | Fires on epoch settlement with reward pot and miner count |
| Miner join/leave | Tracks the active miner roster and announces changes |

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** > **From scratch**.
2. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `chat:write`
   - `commands`
3. Under **Slash Commands**, create two commands:
   - `/rtc-status` — Request URL: `https://<your-host>/slack/events`
   - `/rtc-balance` — Request URL: `https://<your-host>/slack/events`
4. Install the app to your workspace and copy the **Bot User OAuth Token** (`xoxb-...`).

For **Socket Mode** (no public URL required):
1. Enable Socket Mode under **Settings > Socket Mode**.
2. Generate an **App-Level Token** with `connections:write` scope.

### 2. Configure Environment

```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_SIGNING_SECRET="your-signing-secret"
export SLACK_CHANNEL="C07XXXXXXXX"           # Channel ID for notifications
export RUSTCHAIN_NODE_URL="https://50.28.86.131"  # Default node

# Socket Mode (optional — skip for HTTP mode)
export SLACK_APP_TOKEN="xapp-your-app-token"

# Tuning
export POLL_INTERVAL="5"  # seconds between node polls
```

### 3. Install & Run

```bash
pip install -r requirements.txt
python bot.py
```

In HTTP mode the bot listens on port 3000 (override with `PORT` env var).
In Socket Mode it connects via WebSocket — no inbound port needed.

### 4. Docker (optional)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
```

```bash
docker build -t rustchain-slack-bot .
docker run -d --env-file .env --name rtc-slack rustchain-slack-bot
```

## Architecture

```
┌─────────────┐  poll /epoch, /api/miners  ┌──────────────────┐
│  Slack Bot   │ ◄─────────────────────────► │  RustChain Node  │
│  (bot.py)    │        every N seconds      │  50.28.86.131    │
└──────┬───────┘                             └──────────────────┘
       │
       │  chat.postMessage / command responses
       ▼
┌─────────────┐
│   Slack      │
│   Workspace  │
└─────────────┘
```

The bot runs a background `ChainMonitor` thread that polls the node for epoch,
block, and miner data. When state changes are detected (new block, epoch
transition, miner join/leave), it posts formatted messages to the configured
Slack channel.

Slash commands (`/rtc-status`, `/rtc-balance`) query the node on demand and
return ephemeral responses to the invoking user.

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes | — | Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | Yes | — | Signing secret from app settings |
| `SLACK_CHANNEL` | No | — | Channel ID for notifications |
| `SLACK_APP_TOKEN` | No | — | App-level token for Socket Mode |
| `RUSTCHAIN_NODE_URL` | No | `https://50.28.86.131` | RustChain node URL |
| `POLL_INTERVAL` | No | `5` | Seconds between polls |
| `PORT` | No | `3000` | HTTP listener port |
