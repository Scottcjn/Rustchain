# RustChain Prometheus Metrics Exporter

Prometheus-compatible metrics exporter for monitoring RustChain nodes with Grafana.

**Bounty**: [#504](https://github.com/Scottcjn/rustchain-bounties/issues/504) - 40 RTC (+15 RTC bonus for Grafana dashboard)

## Features

- ✅ Real-time node health monitoring
- ✅ Active miner tracking
- ✅ Epoch and slot progress
- ✅ Hall of Fame statistics
- ✅ Miner balance tracking
- ✅ Fee collection metrics (RIP-301)
- ✅ Pre-built Grafana dashboard included

## Metrics Exposed

### Node Health
- `rustchain_node_up` - Node health status (1=up, 0=down)
- `rustchain_node_uptime_seconds` - Node uptime in seconds
- `rustchain_node_version` - Node version info

### Miners
- `rustchain_active_miners_total` - Total active miners
- `rustchain_enrolled_miners_total` - Total enrolled miners
- `rustchain_miner_last_attest_timestamp{miner, arch}` - Last attestation timestamp

### Epoch
- `rustchain_current_epoch` - Current epoch number
- `rustchain_current_slot` - Current slot number
- `rustchain_epoch_slot_progress` - Epoch slot progress (0-1)
- `rustchain_epoch_seconds_remaining` - Seconds remaining in epoch

### Hall of Fame
- `rustchain_total_machines` - Total machines
- `rustchain_total_attestations` - Total attestations
- `rustchain_oldest_machine_year` - Oldest machine year
- `rustchain_highest_rust_score` - Highest rust score
- `rustchain_balance_rtc{miner}` - Miner balance in RTC

### Fees (RIP-301)
- `rustchain_total_fees_collected_rtc` - Total fees collected
- `rustchain_fee_events_total` - Total fee events

## Installation

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Configure Environment

```bash
export RUSTCHAIN_NODE_URL=https://node.rustchain.io
export METRICS_PORT=9100
export SCRAPE_INTERVAL=60
```

### 3. Run Exporter

```bash
python3 rustchain_exporter.py
```

### 4. Install as Systemd Service

```bash
# Copy files
sudo cp rustchain_exporter.py /opt/rustchain-exporter/
sudo cp rustchain-exporter.service /etc/systemd/system/

# Create log directory
sudo mkdir -p /var/log/rustchain-exporter
sudo chown rustchain:rustchain /var/log/rustchain-exporter

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter

# Check status
sudo systemctl status rustchain-exporter
```

## Usage

### Access Metrics

Open `http://localhost:9100/metrics` in your browser or configure Prometheus to scrape it.

### Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'rustchain'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 60s
```

### Import Grafana Dashboard

1. Open Grafana
2. Go to Dashboards → Import
3. Upload `grafana-dashboard.json`
4. Select your Prometheus data source
5. Click Import

## Grafana Dashboard

The included dashboard provides:
- Node status overview
- Active miner count
- Epoch progress gauge
- Hall of Fame statistics
- Top miners by balance table
- Historical charts

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RUSTCHAIN_NODE_URL` | `https://node.rustchain.io` | RustChain node API URL |
| `METRICS_PORT` | `9100` | Port to expose metrics |
| `SCRAPE_INTERVAL` | `60` | Scrape interval in seconds |

## Health Check

- `/health` - Health check endpoint
- `/metrics` - Prometheus metrics endpoint
- `/` - Landing page with links

## Logging

Logs are written to stdout/stderr. When running as systemd service, check with:

```bash
journalctl -u rustchain-exporter -f
```

## Troubleshooting

### Node shows as DOWN
- Check `RUSTCHAIN_NODE_URL` is correct
- Verify network connectivity
- Check node API is accessible

### No metrics showing
- Wait for first scrape cycle (60s by default)
- Check logs for errors
- Verify Prometheus is scraping correctly

## License

MIT License

## Author

Created for RustChain Bounty #504
