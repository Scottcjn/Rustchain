# RustChain Prometheus Metrics Exporter

Prometheus-compatible metrics exporter for RustChain node monitoring.

## Features

- Scrapes RustChain node API every 60 seconds (configurable)
- Exposes metrics on `:9100/metrics` (configurable port)
- Pre-built Grafana dashboard with comprehensive panels
- Systemd service file for production deployment

## Metrics Exported

### Node Health
- `rustchain_node_up{version}` - Node health status (1=up, 0=down)
- `rustchain_node_uptime_seconds` - Node uptime in seconds

### Miners
- `rustchain_active_miners_total` - Total number of active miners
- `rustchain_enrolled_miners_total` - Total number of enrolled miners
- `rustchain_miner_last_attest_timestamp{miner,arch}` - Last attestation timestamp per miner

### Epoch
- `rustchain_current_epoch` - Current epoch number
- `rustchain_current_slot` - Current slot number
- `rustchain_epoch_slot_progress` - Epoch slot progress (0.0-1.0)
- `rustchain_epoch_seconds_remaining` - Seconds remaining in current epoch

### Balances
- `rustchain_balance_rtc{miner}` - Miner balance in RTC (top miners)

### Hall of Fame
- `rustchain_total_machines` - Total machines in Hall of Fame
- `rustchain_total_attestations` - Total attestations
- `rustchain_oldest_machine_year` - Oldest machine year
- `rustchain_highest_rust_score` - Highest Rust score

### Fees (RIP-301)
- `rustchain_total_fees_collected_rtc` - Total fees collected in RTC
- `rustchain_fee_events_total` - Total fee events

## Installation

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Configure Environment

Set environment variables (or edit the systemd service file):

```bash
export RUSTCHAIN_NODE_URL=https://rustchain.org
export EXPORTER_PORT=9100
export SCRAPE_INTERVAL=60
```

### 3. Run Manually

```bash
python3 rustchain_exporter.py
```

### 4. Install as Systemd Service (Production)

```bash
# Copy service file
sudo cp rustchain-exporter.service /etc/systemd/system/

# Create directories
sudo mkdir -p /opt/rustchain/tools/prometheus
sudo mkdir -p /var/log/rustchain

# Copy exporter
sudo cp rustchain_exporter.py /opt/rustchain/tools/prometheus/
sudo cp requirements.txt /opt/rustchain/tools/prometheus/

# Install dependencies
sudo pip3 install -r /opt/rustchain/tools/prometheus/requirements.txt

# Set permissions
sudo chown -R rustchain:rustchain /opt/rustchain/tools/prometheus
sudo chown -R rustchain:rustchain /var/log/rustchain

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter

# Check status
sudo systemctl status rustchain-exporter
```

## Grafana Dashboard

Import the provided `grafana_dashboard.json` into Grafana:

1. Open Grafana → Dashboards → Import
2. Upload `grafana_dashboard.json`
3. Select your Prometheus data source
4. Click Import

## Verification

Test that metrics are being exposed:

```bash
curl http://localhost:9100/metrics
```

Expected output:
```
# HELP rustchain_node_up Node health status (1=up, 0=down)
# TYPE rustchain_node_up gauge
rustchain_node_up{version="2.2.1-rip200"} 1.0
# HELP rustchain_node_uptime_seconds Node uptime in seconds
# TYPE rustchain_node_uptime_seconds gauge
rustchain_node_uptime_seconds 12345.0
...
```

## Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'rustchain'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 60s
```

## Troubleshooting

### Check logs
```bash
journalctl -u rustchain-exporter -f
```

### Test connectivity to node
```bash
curl -sk https://rustchain.org/health
```

### Verify Python dependencies
```bash
pip3 list | grep prometheus_client
```
