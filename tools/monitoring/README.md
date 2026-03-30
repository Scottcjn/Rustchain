# RustChain Prometheus Monitoring Stack

Comprehensive monitoring solution for RustChain nodes using Prometheus metrics collection and Grafana visualization.

## Features

- **Prometheus Exporter**: Python-based exporter collecting RustChain node metrics
- **Pre-built Grafana Dashboard**: Ready-to-import dashboard with 10 panels
- **Docker Compose Setup**: One-command deployment for the entire stack
- **Systemd Service**: Persistent background service for bare-metal deployments

## Quick Start (Docker Compose)

```bash
# Navigate to the RustChain root directory
cd /path/to/Rustchain

# Launch the full monitoring stack
docker-compose -f tools/monitoring/docker-compose.monitoring.yml up -d

# View logs
docker-compose -f tools/monitoring/docker-compose.monitoring.yml logs -f
```

Access services:
- **Grafana**: http://localhost:3000 (admin/rustchain123)
- **Prometheus**: http://localhost:9090

## Standalone Python Setup

### Prerequisites

```bash
pip install requests prometheus_client
```

### Run the Exporter

```bash
python prometheus_exporter.py \
  --node-url http://50.28.86.131 \
  --listen-port 8000 \
  --scrape-interval 30
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RUSTCHAIN_NODE` | `http://50.28.86.131` | RustChain node API URL |
| `EXPORTER_PORT` | `8000` | Port to listen on |
| `SCRAPE_INTERVAL` | `30` | Scrape interval in seconds |
| `TLS_VERIFY` | `false` | Verify TLS certificates |

### Configuration File (JSON)

Create `config.json`:

```json
{
  "node_url": "http://50.28.86.131",
  "listen_port": 8000,
  "scrape_interval": 30,
  "request_timeout": 10
}
```

Run with config:

```bash
python prometheus_exporter.py --config config.json
```

## Systemd Service Setup

### Installation

```bash
# Copy the service file
sudo cp rustchain-exporter.service /etc/systemd/system/

# Edit the service file to set your paths
sudo vim /etc/systemd/system/rustchain-exporter.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter

# Check status
sudo systemctl status rustchain-exporter
```

### Service File Configuration

Edit `/etc/systemd/system/rustchain-exporter.service` and set:
- `WorkingDirectory` to the monitoring directory path
- `Environment` variables for your node URL and port

## Grafana Dashboard Import

1. Open Grafana at http://localhost:3000
2. Login with admin credentials
3. Click **+** → **Import**
4. Upload `grafana_dashboard.json` or paste its contents
5. Select Prometheus datasource (or create one pointing to `http://prometheus:9090`)
6. Click **Import**

### Dashboard Panels

| Panel | Metric | Description |
|---|---|---|
| Node Health | `rustchain_node_up` | Up/Down status indicator |
| Current Epoch | `rustchain_epoch_current` | Current epoch number |
| Current Slot | `rustchain_epoch_slot` | Current slot in epoch |
| Active Miners | `rustchain_active_miners` | Count of active miners |
| RTC Supply | `rustchain_total_rtc_supply` | Total RTC token supply |
| Epoch Pot | `rustchain_epoch_pot` | Current epoch reward pot |
| API Response Time | `rustchain_api_response_time_seconds` | Per-endpoint response times |
| API Requests Total | `rustchain_api_requests_total` | Request count by endpoint/status |
| Scrape Errors | `rustchain_scrape_errors_total` | Error breakdown by type |
| Scrape Duration | `rustchain_scrape_duration_seconds` | Time per scrape cycle |

## Prometheus Configuration

The `prometheus.yml` file configures Prometheus to scrape the exporter:

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: 'rustchain-exporter'
    static_configs:
      - targets: ['rustchain-exporter:8000']
```

## Metrics Reference

| Metric | Type | Labels | Description |
|---|---|---|---|
| `rustchain_node_up` | Gauge | node_url | Node availability (1=up, 0=down) |
| `rustchain_node_version` | Info | node_url, version | Node software version |
| `rustchain_node_uptime_seconds` | Gauge | node_url | Node uptime |
| `rustchain_epoch_current` | Gauge | node_url | Current epoch number |
| `rustchain_epoch_slot` | Gauge | node_url | Current slot |
| `rustchain_epoch_pot` | Gauge | node_url | Epoch reward pot |
| `rustchain_block_height` | Gauge | node_url | Current block height |
| `rustchain_total_miners` | Gauge | node_url | Total registered miners |
| `rustchain_active_miners` | Gauge | node_url | Active miners count |
| `rustchain_total_rtc_supply` | Gauge | node_url | Total RTC supply |
| `rustchain_api_response_time_seconds` | Gauge | node_url, endpoint | API response time |
| `rustchain_scrape_errors_total` | Counter | node_url, error_type | Scrape error count |
| `rustchain_api_requests_total` | Counter | node_url, endpoint, status | Total API requests |
| `rustchain_scrape_duration_seconds` | Gauge | node_url | Scrape cycle duration |
| `rustchain_epoch_block_time_avg` | Gauge | node_url | Average block time in epoch |
| `rustchain_miner_antiquity_distribution` | Histogram | node_url | Miner antiquity score distribution |
| `rustchain_tx_pool_size` | Gauge | node_url | Pending transaction pool size |

## Endpoints Scraped

The exporter queries these RustChain API endpoints:

- `GET /health` - Node health and version
- `GET /epoch` - Epoch info (number, slot, pot, supply)
- `GET /api/miners` - Miner list (active/total counts)
- `GET /tx/pool` - Transaction pool size

## Troubleshooting

### Exporter not responding

Check logs: `docker logs rustchain-exporter` or `journalctl -u rustchain-exporter`

### Prometheus not scraping

Verify target in Prometheus UI: Status → Targets

### Grafana shows no data

Check datasource URL is `http://prometheus:9090` and that Prometheus is successfully scraping the exporter.
