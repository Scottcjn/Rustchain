# RustChain Miner Alert System

> Bounty: 75 RTC | Issue: [#28](https://github.com/Scottcjn/Rustchain/issues/28)

Email and SMS alert system that monitors RustChain miners and notifies operators about important events.

## Alert Types

| Alert | Trigger | Default |
|-------|---------|---------|
| **Miner Offline** | No attestation within threshold (default 10 min) | Enabled |
| **Rewards Received** | Balance increase detected | Enabled |
| **Large Transfer** | Balance decrease above threshold (default 10 RTC) | Enabled |
| **Attestation Failure** | Miner dropped from active miners list | Enabled |

## Channels

- **Email** via SMTP (Gmail, SendGrid, any SMTP provider)
- **SMS** via Twilio (optional)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your SMTP credentials

# Subscribe to alerts
python miner_alerts.py subscribe <miner_id> <email>

# Start monitoring
python miner_alerts.py monitor
```

## CLI Commands

```bash
# Subscribe to alerts for a miner
python miner_alerts.py subscribe modern-sophia-Pow-9862e3be user@example.com

# Subscribe with SMS
python miner_alerts.py subscribe <miner_id> <email> --phone +15551234567

# Disable specific alert types
python miner_alerts.py subscribe <miner_id> <email> --no-offline --no-rewards

# List all subscriptions
python miner_alerts.py list

# Unsubscribe
python miner_alerts.py unsubscribe <miner_id> <email>

# Start the monitoring daemon
python miner_alerts.py monitor

# Test email delivery
python miner_alerts.py test-email user@example.com

# Test SMS delivery
python miner_alerts.py test-sms +15551234567
```

## Architecture

```
                                    +------------------+
  RustChain Node                    |  Alert System    |
  /api/miners  ──────────────────── | monitor loop     |
  /balance     ──────────────────── | (polls every 2m) |
                                    +--------+---------+
                                             |
                                    +--------+---------+
                                    |  SQLite DB       |
                                    |  - subscriptions |
                                    |  - miner_state   |
                                    |  - alert_history |
                                    +--------+---------+
                                             |
                               +-------------+-------------+
                               |                           |
                        +------+------+             +------+------+
                        |    SMTP     |             |   Twilio    |
                        |   (email)   |             |   (SMS)     |
                        +-------------+             +-------------+
```

## How It Works

1. **Poll**: Every `POLL_INTERVAL` seconds, fetch `/api/miners` and `/balance` for all subscribed miners
2. **Compare**: Diff current state against stored state in SQLite
3. **Detect**: Identify offline transitions, balance changes, attestation drops
4. **Alert**: Send notifications via email/SMS to all subscribers
5. **Cooldown**: Avoid alert spam with per-type cooldown periods (1 hour for offline, 5 min for rewards)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_API` | `https://rustchain.org` | Node API URL |
| `POLL_INTERVAL` | `120` | Seconds between checks |
| `OFFLINE_THRESHOLD` | `600` | Seconds before offline alert |
| `LARGE_TRANSFER_THRESHOLD` | `10.0` | RTC amount for transfer alert |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | | SMTP username |
| `SMTP_PASS` | | SMTP password (use app password for Gmail) |
| `SMTP_FROM` | | From address |
| `TWILIO_ACCOUNT_SID` | | Twilio SID (optional) |
| `TWILIO_AUTH_TOKEN` | | Twilio auth token (optional) |
| `TWILIO_FROM_NUMBER` | | Twilio from number (optional) |

## Database

SQLite database at `~/.rustchain/alerts.db` with three tables:

- **subscriptions**: Miner ID, email, phone, per-type alert toggles
- **miner_state**: Last attestation time, balance, online status
- **alert_history**: Sent alerts with timestamp for cooldown tracking

## Running as a Service

```ini
# /etc/systemd/system/rustchain-alerts.service
[Unit]
Description=RustChain Miner Alert System
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/rustchain-alerts
ExecStart=/usr/bin/python3 miner_alerts.py monitor
Restart=always
RestartSec=30
EnvironmentFile=/opt/rustchain-alerts/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable rustchain-alerts
sudo systemctl start rustchain-alerts
```

## Dependencies

- [requests](https://github.com/psf/requests) >= 2.28.0
- [python-dotenv](https://github.com/theskumar/python-dotenv) >= 1.0.0
- Python standard library: smtplib, sqlite3, email, argparse

No additional dependencies for email alerts. Twilio SMS uses the REST API directly (no SDK needed).

## License

MIT — Part of the RustChain project.
