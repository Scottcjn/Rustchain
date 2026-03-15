# RustChain Email Alerts

Email notification service for RustChain blockchain events. Subscribe to on-chain events and receive HTML email alerts via SMTP with support for instant delivery or digest summaries.

## Features

- **Event subscriptions** — new epoch, miner changes, balance changes
- **HTML email templates** — styled, responsive email notifications
- **SMTP support** — Gmail, Outlook, Yahoo presets or custom SMTP servers
- **Digest mode** — instant, hourly, or daily event summaries
- **Unsubscribe management** — HMAC-signed tokens for secure unsubscribe links
- **SQLite storage** — lightweight subscriber and digest queue persistence
- **CLI interface** — manage subscriptions and run the service from the command line

## Quick Start

### 1. Configure SMTP

Set environment variables for your mail server:

```bash
# Gmail example (use App Password, not account password)
export RUSTCHAIN_SMTP_PRESET=gmail
export RUSTCHAIN_SMTP_USER=you@gmail.com
export RUSTCHAIN_SMTP_PASS=your-app-password

# Or use custom SMTP
export RUSTCHAIN_SMTP_HOST=mail.example.com
export RUSTCHAIN_SMTP_PORT=587
export RUSTCHAIN_SMTP_TLS=true
export RUSTCHAIN_SMTP_USER=alerts@example.com
export RUSTCHAIN_SMTP_PASS=secret
export RUSTCHAIN_SMTP_FROM=alerts@example.com

# Unsubscribe token secret (change in production)
export RUSTCHAIN_UNSUB_SECRET=my-secret-key
```

### 2. Add Subscribers

```bash
# Subscribe to all events (instant delivery)
python alerts.py subscribe alice@example.com

# Subscribe to specific events with daily digest
python alerts.py subscribe bob@example.com \
  --events new_epoch balance_change \
  --digest daily \
  --wallet RTC1abc...

# List subscribers
python alerts.py list
```

### 3. Run the Service

```bash
# Start polling (default: every 30 seconds)
python alerts.py run

# Custom node URL and interval
python alerts.py run --node-url http://localhost:8099 --interval 60

# Custom database path
python alerts.py run --db /path/to/alerts.db
```

## Programmatic Usage

```python
from alerts import RustChainEmailAlerts, SMTPConfig

smtp = SMTPConfig(
    host="smtp.gmail.com",
    port=587,
    tls=True,
    username="you@gmail.com",
    password="app-password",
    from_addr="you@gmail.com",
)

svc = RustChainEmailAlerts(
    node_url="https://50.28.86.131",
    smtp=smtp,
    poll_interval=30,
)

# Add subscribers
svc.subscribe("alice@example.com", ["new_epoch", "miner_change"])
svc.subscribe("bob@example.com", ["balance_change"], digest="hourly", wallet="RTC1...")

# Start background polling
svc.start()

# ... later ...
svc.stop()
```

## Event Types

| Event | Description | Payload |
|-------|-------------|---------|
| `new_epoch` | A new epoch begins | `previous_epoch`, `new_epoch`, `epoch_data` |
| `miner_change` | Miners join or leave | `joined`, `left`, `total_miners` |
| `balance_change` | Wallet balance changes | `wallet`, `old_balance`, `new_balance`, `change` |

## Digest Modes

| Mode | Description |
|------|-------------|
| `instant` | Send immediately when an event is detected |
| `hourly` | Batch events and send a summary every hour |
| `daily` | Batch events and send a summary every 24 hours |

## Templates

HTML email templates are in the `templates/` directory:

| File | Purpose |
|------|---------|
| `welcome.html` | Sent on new subscription |
| `new_epoch.html` | New epoch notification |
| `miner_change.html` | Miner join/leave notification |
| `balance_change.html` | Wallet balance change notification |
| `digest.html` | Hourly/daily event summary |
| `generic_event.html` | Fallback for unknown event types |
| `base.html` | Base template with shared styles |

Templates use `{{ variable }}` placeholders that are replaced at render time.

## CLI Reference

```
usage: alerts.py [-h] {run,subscribe,unsubscribe,list} ...

RustChain Email Alert Service

commands:
  run            Start the alert polling service
  subscribe      Add a subscriber
  unsubscribe    Remove a subscriber
  list           List all subscribers
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_SMTP_PRESET` | — | SMTP preset: `gmail`, `outlook`, `yahoo` |
| `RUSTCHAIN_SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `RUSTCHAIN_SMTP_PORT` | `587` | SMTP server port |
| `RUSTCHAIN_SMTP_TLS` | `true` | Enable STARTTLS |
| `RUSTCHAIN_SMTP_USER` | — | SMTP username |
| `RUSTCHAIN_SMTP_PASS` | — | SMTP password |
| `RUSTCHAIN_SMTP_FROM` | `SMTP_USER` | Sender email address |
| `RUSTCHAIN_UNSUB_SECRET` | `change-me-in-production` | HMAC secret for unsubscribe tokens |

## License

Apache-2.0 — same as the RustChain project.
