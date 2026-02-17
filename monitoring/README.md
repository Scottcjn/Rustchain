# RustChain Grafana Monitoring

Complete monitoring stack for RustChain network with Grafana, Prometheus, and custom exporter.

## Quick Start

```bash
cd monitoring
docker-compose up -d
```

Access Grafana: **http://your-server:3000**
- Username: `admin`
- Password: `rustchain`

## What You Get

### Services

1. **Grafana** (port 3000) - Visualization dashboard
2. **Prometheus** (port 9090) - Metrics database
3. **RustChain Exporter** (port 9100) - Metrics collector

### Metrics Tracked

**Node Health**:
- Health status
- Uptime
- Database status
- Version info

**Network Stats**:
- Current epoch & slot
- Epoch pot size
- Total RTC supply
- Enrolled miners

**Miner Analytics**:
- Active miner count
- Miners by hardware type (PowerPC, Apple Silicon, etc.)
- Miners by architecture
- Average antiquity multiplier
- Last attestation times

### Alerts

Pre-configured alerts for:
- Node down (health = 0)
- Unusual miner drop (>20% decrease in 5min)
- Slow scrape performance (>5s duration)

## Configuration

### Change Grafana Password

Edit `docker-compose.yml`:
```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=your-new-password
```

### Adjust Scrape Interval

Edit `rustchain-exporter.py`:
```python
SCRAPE_INTERVAL = 30  # seconds
```

Edit `prometheus.yml`:
```yaml
global:
  scrape_interval: 30s
```

### Monitor Different Node

Edit `rustchain-exporter.py`:
```python
RUSTCHAIN_NODE = "https://your-node-url"
```

## Metrics Endpoints

- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Exporter**: http://localhost:9100/metrics

## Dashboard Panels

1. **Node Health** - Real-time health indicator
2. **Active Miners** - Current miner count
3. **Current Epoch** - Blockchain epoch number
4. **Epoch Pot** - Reward pool size
5. **Active Miners (24h)** - Time series graph
6. **RTC Total Supply** - Supply over time
7. **Miners by Hardware Type** - Pie chart
8. **Miners by Architecture** - Pie chart
9. **Average Antiquity Multiplier** - Gauge
10. **Node Uptime** - Uptime graph
11. **Scrape Duration** - Performance metric with alert

## Prometheus Queries

Useful queries for custom panels:

```promql
# Active miners
rustchain_active_miners

# Miners with high antiquity
rustchain_miners_by_hardware{hardware_type="PowerPC G4 (Vintage)"}

# Node uptime in hours
rustchain_node_uptime_seconds / 3600

# Scrape errors rate
rate(rustchain_scrape_errors_total[5m])
```

## Troubleshooting

### Exporter Not Working

Check logs:
```bash
docker logs rustchain-exporter
```

Test manually:
```bash
curl http://localhost:9100/metrics
```

### Grafana Shows "No Data"

1. Check Prometheus is scraping:
   - Visit http://localhost:9090/targets
   - Ensure `rustchain-exporter:9100` is UP

2. Check data source:
   - Grafana → Configuration → Data Sources
   - Test connection

### Prometheus Not Scraping

Check config:
```bash
docker exec rustchain-prometheus cat /etc/prometheus/prometheus.yml
```

Reload config:
```bash
docker exec rustchain-prometheus kill -HUP 1
```

## Adding Custom Alerts

Edit `prometheus.yml` and add:

```yaml
rule_files:
  - '/etc/prometheus/alerts.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

Create `alerts.yml`:

```yaml
groups:
  - name: rustchain_alerts
    interval: 1m
    rules:
      - alert: NodeDown
        expr: rustchain_node_health == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "RustChain node is down"
          description: "Node health check failed for 2 minutes"
      
      - alert: MinerDrop
        expr: rate(rustchain_active_miners[5m]) < -0.2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Significant miner drop detected"
          description: "Active miners decreased by >20% in 5 minutes"
```

## Data Retention

- **Prometheus**: 30 days (configurable in docker-compose.yml)
- **Grafana**: Unlimited (uses Prometheus as data source)

To change retention:
```yaml
command:
  - '--storage.tsdb.retention.time=60d'  # 60 days
```

## Backup

### Backup Grafana Dashboards

```bash
docker exec rustchain-grafana grafana-cli admin export > dashboard-backup.json
```

### Backup Prometheus Data

```bash
docker cp rustchain-prometheus:/prometheus ./prometheus-backup
```

## Production Deployment

1. **Change default password** in docker-compose.yml
2. **Enable SSL** via nginx reverse proxy (see main DOCKER_DEPLOYMENT.md)
3. **Set up alerting** to Slack/PagerDuty
4. **Monitor disk usage** (Prometheus data grows over time)
5. **Enable authentication** for Prometheus endpoint

## System Requirements

- **RAM**: 512 MB (1 GB recommended)
- **Disk**: 2 GB (for 30 days retention)
- **CPU**: 1 core

## License

MIT - Same as RustChain
