# RustChain Slack Integration

Slack bot for monitoring the RustChain network. Provides slash commands, automated alerts, and daily summaries.

## Commands

| Command | Description |
|---------|-------------|
| `/rtc-status` | Network status — block height, epoch, peers, TPS |
| `/rtc-balance <address>` | Check wallet balance for a given address |
| `/rtc-miners` | Active miners, hashrate, and architecture breakdown |

## Auto-Alerts

The bot monitors the network and posts alerts to `#rustchain-alerts` when:

- **Fork detected** — block height decreases (possible chain reorg)
- **Peer drop** — connected peers drop by 5+ within a single check interval

## Daily Summary

A network summary is posted to `#rustchain-daily` every day at 14:00 UTC (configurable). Includes block height, epoch, miner count, hashrate, and wRTC price.

## Setup

### 1. Create the Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**
2. Name it `RustChain Bot` and select your workspace
3. Under **Socket Mode**, enable it and generate an app-level token (`xapp-...`) — save this as `SLACK_APP_TOKEN`
4. Under **OAuth & Permissions**, add these bot scopes:
   - `chat:write`
   - `commands`
5. Install the app to your workspace and copy the Bot User OAuth Token (`xoxb-...`) — save this as `SLACK_BOT_TOKEN`
6. Under **Slash Commands**, create:
   - `/rtc-status` → "RustChain network status"
   - `/rtc-balance` → "Check RTC wallet balance"
   - `/rtc-miners` → "Active RustChain miners"

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your tokens:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
RUSTCHAIN_API_URL=https://rustchain.org
SLACK_ALERTS_CHANNEL=#rustchain-alerts
SLACK_SUMMARY_CHANNEL=#rustchain-daily
DAILY_SUMMARY_HOUR_UTC=14
```

### 3. Install & Run

```bash
pip install -r requirements.txt
python slack_bot.py
```

### 4. Run with Docker (optional)

```bash
docker build -t rustchain-slack .
docker run --env-file .env rustchain-slack
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | — | Bot OAuth token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | — | App-level token for Socket Mode (`xapp-...`) |
| `SLACK_SIGNING_SECRET` | — | Signing secret from app settings |
| `RUSTCHAIN_API_URL` | `https://rustchain.org` | RustChain node API endpoint |
| `SLACK_ALERTS_CHANNEL` | `#rustchain-alerts` | Channel for auto-alerts |
| `SLACK_SUMMARY_CHANNEL` | `#rustchain-daily` | Channel for daily summary |
| `DAILY_SUMMARY_HOUR_UTC` | `14` | Hour (UTC) to post daily summary |
| `MONITOR_INTERVAL_SECONDS` | `60` | Seconds between alert checks |
| `MISSED_BLOCK_THRESHOLD` | `3` | Missed blocks before alerting |
| `PEER_DROP_THRESHOLD` | `5` | Peer drop count to trigger alert |
| `RATE_LIMIT_PER_MINUTE` | `15` | Max commands per user per minute |
