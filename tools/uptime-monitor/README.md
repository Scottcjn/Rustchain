# RustChain Uptime Monitor

Standalone uptime monitoring service for RustChain nodes. Tracks node health, response times, and uptime percentages with a public status page and alerting.

## Features

- **HTTP health checks** every 30 seconds (configurable)
- **Response time tracking** per node
- **Uptime percentage** calculated over 24h, 7d, and 30d windows
- **Public status page** with per-node sparkline history (dark theme, responsive)
- **SQLite storage** for historical check data and incident records
- **Email alerts** on downtime and recovery (SMTP)
- **Webhook alerts** for Slack, Discord, or any HTTP endpoint
- **Built-in HTTP server** to serve the status page directly
- **Zero external dependencies** — stdlib only

## Quick Start

```bash
# Monitor default RustChain nodes, serve status page on port 8080
python monitor.py --serve 8080

# Monitor specific nodes
python monitor.py --nodes https://rustchain.org http://localhost:5000

# Custom interval (15 seconds)
python monitor.py --interval 15

# With Slack/Discord webhook alerts
python monitor.py --webhook https://hooks.slack.com/services/T.../B.../xxx

# With email alerts
python monitor.py \
  --alert-email ops@example.com \
  --smtp-host smtp.gmail.com \
  --smtp-user you@gmail.com \
  --smtp-pass "app-password"
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--nodes` | Built-in list | Space-separated node URLs to monitor |
| `--interval` | `30` | Seconds between check rounds |
| `--db` | `uptime.db` | SQLite database file path |
| `--status-out` | `status-page.html` | Output path for generated status page |
| `--serve PORT` | *(disabled)* | Serve status page on this HTTP port |
| `--webhook URL` | *(disabled)* | Webhook URL for down/recovery alerts |
| `--alert-email` | *(disabled)* | Recipient email address for alerts |
| `--smtp-host` | — | SMTP server hostname |
| `--smtp-port` | `587` | SMTP server port |
| `--smtp-user` | — | SMTP auth username |
| `--smtp-pass` | — | SMTP auth password |
| `--smtp-from` | `uptime@rustchain.org` | Sender address for alert emails |
| `-v` | — | Verbose / debug logging |

## Status Page

The monitor regenerates `status-page.html` after every check round. It shows:

- Overall network status (operational / degraded / major outage)
- Per-node status badge and sparkline bar chart (last 90 checks)
- Average response time (last hour)
- Uptime percentages over 24 hours, 7 days, and 30 days

Serve it with the built-in `--serve` flag or deploy behind nginx / Caddy.

## Database Schema

All data lives in a single SQLite file (`uptime.db`):

- **checks** — every health probe result (timestamp, status code, response time, errors)
- **incidents** — downtime incidents with start/end times and duration

## Deployment

### systemd

```ini
[Unit]
Description=RustChain Uptime Monitor
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/rustchain/tools/uptime-monitor/monitor.py --serve 8080
WorkingDirectory=/opt/rustchain/tools/uptime-monitor
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY tools/uptime-monitor/ .
EXPOSE 8080
CMD ["python", "monitor.py", "--serve", "8080"]
```

## Default Monitored Nodes

- `https://rustchain.org`
- `https://50.28.86.153`
- `http://76.8.228.245:8099`
