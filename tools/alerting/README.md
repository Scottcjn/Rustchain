# RustChain Monitoring & Alerting

Production-ready alerting system for RustChain nodes, built on Prometheus Alertmanager with a standalone fallback notifier.

## Components

| File | Purpose |
|---|---|
| `alert-rules.yml` | Prometheus recording/alert rules for all RustChain-specific conditions |
| `alertmanager.yml` | Alertmanager routing, receivers (email/Slack/webhook), and inhibit rules |
| `notify.py` | Standalone Python notifier — works as an Alertmanager webhook receiver **or** an independent node poller |

## Alert Coverage

| Alert | Condition | Severity |
|---|---|---|
| **Node Down** | `/health` returns unhealthy or exporter unreachable for 2 min | Critical |
| **Epoch Stalled** | No slot change in 10 minutes | Critical |
| **Low Miner Count** | Fewer than 3 active miners for 5 min | Warning |
| **No Miners** | Zero active miners for 2 min | Critical |
| **High API Latency** | Exporter scrape exceeds 5 seconds for 3 min | Warning |
| **Very High API Latency** | Exporter scrape exceeds 15 seconds for 2 min | Critical |
| **Disk Space Low** | Root filesystem below 15% free for 5 min | Warning |
| **Disk Space Critical** | Root filesystem below 5% free for 2 min | Critical |
| **Scrape Errors** | Elevated error rate against the node API | Warning |

## Quick Start

### Option A — Full Prometheus Stack

1. Copy the alert rules into your Prometheus config directory:

```bash
cp alert-rules.yml /etc/prometheus/alert-rules.yml
```

2. Reference the rules file in `prometheus.yml`:

```yaml
rule_files:
  - '/etc/prometheus/alert-rules.yml'
```

3. Deploy Alertmanager with the provided config:

```bash
alertmanager --config.file=alertmanager.yml
```

4. Update the Alertmanager target in `prometheus.yml`:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

5. Start the webhook receiver so Alertmanager can forward to email/Slack:

```bash
python notify.py --mode webhook --port 9095
```

### Option B — Standalone Poller (no Prometheus required)

```bash
# Configure at least one notification channel
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
# or
export SMTP_USER="alerts@example.com"
export SMTP_PASS="app-password"
export SMTP_TO="ops@example.com"

# Start polling
python notify.py --mode poll --node https://rustchain.org --interval 60
```

## Environment Variables

| Variable | Description |
|---|---|
| `RUSTCHAIN_NODE` | Node URL (default: `https://rustchain.org`) |
| `SMTP_HOST` | SMTP server (default: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default: `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASS` | SMTP password / app password |
| `SMTP_FROM` | Sender address (defaults to `SMTP_USER`) |
| `SMTP_TO` | Comma-separated recipient list |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL |
| `WEBHOOK_URL` | Generic webhook endpoint for alert payloads |

## Integration with Existing Monitoring

This builds on the existing `monitoring/rustchain-exporter.py` which exposes the following Prometheus metrics:

- `rustchain_node_health` — binary health status
- `rustchain_epoch_slot` / `rustchain_epoch_number` — epoch progress
- `rustchain_active_miners` — current miner count
- `rustchain_scrape_duration_seconds` — API response time
- `rustchain_scrape_errors_total` — error counter

The alert rules in `alert-rules.yml` query these metrics directly. For disk space alerts, the standard `node_exporter` must also be running on the host.
