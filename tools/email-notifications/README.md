# RustChain Email Notification Service

Email notification daemon for RustChain miners. Monitors on-chain activity and delivers alerts for balance changes, epoch rewards, attestation failures, and daily mining summaries.

## Features

- **Balance Monitoring** — Detects deposits and withdrawals, notifies on any balance change above a configurable threshold.
- **Epoch Reward Alerts** — Watches for new epoch settlements and emails your per-miner reward breakdown.
- **Attestation Failure Detection** — Alerts when your miner stops attesting (goes offline) and sends a recovery notice when it comes back.
- **Daily Mining Digest** — Scheduled summary of the previous day's activity: RTC earned, attestation count, uptime percentage, and current balance.
- **Configurable SMTP** — Works with Gmail, SendGrid, AWS SES, or any standard SMTP provider. Supports TLS and SSL.
- **HTML Email Templates** — Clean, responsive templates in `templates/`. Easy to customize.
- **SQLite Persistence** — Tracks subscriber preferences, miner state snapshots, epoch history, daily stats, and delivery logs.
- **Retry Logic** — Automatic SMTP retry with exponential backoff on transient failures.

## Quick Start

```bash
cd tools/email-notifications
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your SMTP credentials and RustChain API endpoint
```

### Subscribe a miner

```bash
python notifier.py subscribe -m YOUR_MINER_ADDRESS -e you@example.com
```

### Start the daemon

```bash
python notifier.py run
```

### Send a test email

```bash
python notifier.py test -e you@example.com
```

### Unsubscribe

```bash
python notifier.py unsubscribe -m YOUR_MINER_ADDRESS -e you@example.com
```

## Configuration

All settings are read from environment variables (or a `.env` file). See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `RUSTCHAIN_API` | `https://rustchain.org` | Node API base URL |
| `POLL_INTERVAL` | `60` | Seconds between poll cycles |
| `OFFLINE_THRESHOLD` | `600` | Seconds without attestation before marking offline |
| `BALANCE_CHANGE_MIN` | `0.01` | Minimum RTC change to trigger an alert |
| `DIGEST_HOUR_UTC` | `8` | Hour (0-23 UTC) for daily digest delivery |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | — | SMTP login username |
| `SMTP_PASS` | — | SMTP login password / app password |
| `SMTP_FROM` | — | Sender address |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `SMTP_USE_SSL` | `false` | Use implicit SSL (port 465) |

## Notification Types

Subscribers can opt in/out of each notification type independently:

- `balance` — Balance increase or decrease
- `epoch` — New epoch reward distribution
- `attestation` — Miner offline / back online
- `digest` — Daily summary email

```bash
# Subscribe to everything except daily digest
python notifier.py subscribe -m MINER_ID -e you@example.com --no-digest
```

## Templates

HTML templates live in `templates/`. Each template uses Python `string.Template` substitution (`$variable`). Available templates:

| Template | Trigger |
|---|---|
| `balance_change.html` | Balance delta detected |
| `epoch_reward.html` | New epoch settled |
| `attestation_failure.html` | Miner went offline |
| `attestation_recovery.html` | Miner came back online |
| `daily_digest.html` | Scheduled daily summary |

To customize, edit the HTML directly. Template variables are documented inline.

## Running as a System Service

### systemd

```ini
[Unit]
Description=RustChain Email Notifier
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/opt/rustchain/tools/email-notifications
ExecStart=/usr/bin/python3 notifier.py run
Restart=on-failure
RestartSec=10
EnvironmentFile=/opt/rustchain/tools/email-notifications/.env

[Install]
WantedBy=multi-user.target
```

## Directory Structure

```
email-notifications/
  notifier.py          Main service and CLI
  requirements.txt     Python dependencies
  .env.example         Configuration template
  README.md            This file
  templates/
    base.html          Base layout (reference)
    balance_change.html
    epoch_reward.html
    attestation_failure.html
    attestation_recovery.html
    daily_digest.html
```
