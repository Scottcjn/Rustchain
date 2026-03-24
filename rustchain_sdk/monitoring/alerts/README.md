# RustChain Miner Alert System

Monitor your RustChain miners and get notified when things go wrong.

## Alert Types

| Alert | Trigger |
|-------|---------|
| **Miner Offline** | No attestation for N minutes (configurable, default: 10) |
| **Back Online** | Miner resumes attestations after being flagged offline |
| **Rewards Received** | Wallet balance increases by ≥ threshold (default: 0.01 RTC) |
| **Large Transfer** | Wallet balance drops by ≥ threshold (default: 10 RTC) |
| **Attestation Failure** | `last_attest` timestamp doesn't advance between two polls |

## Requirements

- Python 3.11+
- Twilio account (optional, for SMS)
- SMTP server or Gmail (optional, for email)

## Installation

```bash
git clone https://github.com/Scottcjn/Rustchain
cd Rustchain/monitoring

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional SMS support
pip install twilio
```

## Configuration

Copy `config.yaml` to your working directory and edit:

```yaml
rustchain:
  base_url: "https://50.28.86.131"
  verify_ssl: false
  poll_interval_seconds: 60   # poll every 60 seconds

thresholds:
  offline_minutes: 10          # alert after 10 min without attestation
  large_transfer_rtc: 10.0     # alert on >10 RTC outbound transfer
  reward_min_rtc: 0.01         # alert on >0.01 RTC reward

miners:
  watch_all: true              # monitor all enrolled miners
  # watch_ids:                 # or specify individual miner IDs
  #   - "my-miner-abc123"

email:
  enabled: true
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "you@gmail.com"
  from_addr: "you@gmail.com"
  to_addrs:
    - "alerts@example.com"
  use_tls: true

sms:
  enabled: false               # requires twilio package
  from_number: "+15551234567"
  to_numbers:
    - "+15559876543"
```

**Secrets via environment variables** (recommended — don't put passwords in YAML):

```bash
export SMTP_PASSWORD="your-app-password"
export SMTP_USER="you@gmail.com"
export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TWILIO_AUTH_TOKEN="your_auth_token"
```

## Usage

```bash
# Run continuously (polls every poll_interval_seconds)
python -m rustchain_alerts

# Custom config file
python -m rustchain_alerts --config /path/to/config.yaml

# Single poll and exit (useful for cron)
python -m rustchain_alerts --once

# View recent alert history
python -m rustchain_alerts --history

# Verbose logging
python -m rustchain_alerts --log-level DEBUG
```

### Run as a systemd service

```ini
# /etc/systemd/system/rustchain-alerts.service
[Unit]
Description=RustChain Miner Alert System
After=network.target

[Service]
User=rustchain
WorkingDirectory=/opt/rustchain-alerts
ExecStart=/opt/rustchain-alerts/.venv/bin/python -m rustchain_alerts
Restart=always
RestartSec=10
Environment=SMTP_PASSWORD=your-password

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable rustchain-alerts
sudo systemctl start rustchain-alerts
sudo journalctl -fu rustchain-alerts
```

## Architecture

```
rustchain_alerts/
├── __main__.py     CLI entry point
├── api.py          RustChain API client (httpx, async)
├── config.py       YAML + env var config (Pydantic)
├── db.py           SQLite alert history + miner state
├── monitor.py      Poll loop + alert detection logic
└── notifiers.py    Email (SMTP) + SMS (Twilio) backends
```

- Polls `/api/miners` to get all enrolled miners and their `last_attest` timestamps
- Polls `/wallet/balance` per miner to track balance changes
- Persists miner state in SQLite to detect changes across polls
- Deduplicates alerts (won't re-fire the same alert type within the cooldown window)

## Running Tests

```bash
pip install pytest pytest-asyncio anyio respx
python -m pytest tests/ -v
```

## Gmail Setup

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833):
1. Enable 2FA on your Google account
2. Go to Security → App passwords → Generate
3. Use the generated password as `SMTP_PASSWORD`
