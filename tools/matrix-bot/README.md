# RustChain Matrix Bot

A Matrix chat bot for monitoring the RustChain network. Provides real-time node status, wallet balances, miner information, epoch tracking, and wRTC price data directly in Matrix rooms.

## Features

- **!status** — Node health (block height, uptime, version)
- **!balance \<wallet\>** — Check any wallet's RTC balance
- **!miners** — List active miners with hardware info and multipliers
- **!epoch** — Current epoch number, time remaining, and reward pool
- **!price** — Live wRTC price from DexScreener (USD, SOL, volume, liquidity)
- **!help** — Show available commands
- **Auto-notifications** — Posts a notice when a new epoch starts

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MATRIX_HOMESERVER` | No | `https://matrix.org` | Matrix homeserver URL |
| `MATRIX_USER` | Yes | — | Full Matrix user ID (e.g. `@rustchain-bot:matrix.org`) |
| `MATRIX_PASSWORD` | Yes | — | Bot account password |
| `MATRIX_ROOM_ID` | No | — | Room ID for auto-join and epoch notifications (e.g. `!abc123:matrix.org`) |
| `RUSTCHAIN_API` | No | `https://rustchain.org` | RustChain node API base URL |
| `DEXSCREENER_PAIR` | No | `8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb` | DexScreener pair address for wRTC |
| `EPOCH_POLL_INTERVAL` | No | `60` | Seconds between epoch checks |

### 3. Run the bot

```bash
export MATRIX_USER="@rustchain-bot:matrix.org"
export MATRIX_PASSWORD="your-password"
export MATRIX_ROOM_ID="!your-room-id:matrix.org"
python bot.py
```

## How It Works

The bot connects to a Matrix homeserver, joins the configured room, and listens for `!` commands. It queries the RustChain node API (`/health`, `/epoch`, `/api/miners`, `/wallet/balance`) and DexScreener for wRTC price data.

A background task polls the `/epoch` endpoint every 60 seconds (configurable) and sends a notice to the room whenever a new epoch begins.

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Node health and status |
| `GET /epoch` | Current epoch info |
| `GET /api/miners` | Active miner list |
| `GET /wallet/balance?miner_id=X` | Wallet balance |
| DexScreener API | wRTC/SOL pair price |

## Running with systemd

Create `/etc/systemd/system/rustchain-matrix-bot.service`:

```ini
[Unit]
Description=RustChain Matrix Bot
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/rustchain/tools/matrix-bot/bot.py
EnvironmentFile=/etc/rustchain/matrix-bot.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-matrix-bot
```

## License

MIT
