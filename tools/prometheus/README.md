# RustChain Prometheus Exporter

Prometheus-compatible metrics exporter for RustChain nodes with Grafana dashboard.

## Features

- ✅ Real-time metrics collection from RustChain API
- ✅ Prometheus-compatible `/metrics` endpoint
- ✅ Pre-built Grafana dashboard
- ✅ Docker Compose setup with Prometheus + Grafana
- ✅ Alert rules for node health, miner status, and balances
- ✅ Systemd service file for production deployment

## Quick Start

### Docker Compose (Recommended)

```bash
# Start all services (exporter + Prometheus + Grafana)
docker-compose up -d

# Access Grafana at http://localhost:3000
# Default credentials: admin / admin
```

### Manual Installation

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run exporter
python3 rustchain_exporter.py

# Metrics available at http://localhost:9100/metrics
```

### Systemd Service

```bash
# Copy files
sudo cp rustchain_exporter.py /opt/rustchain-exporter/
sudo cp requirements.txt /opt/rustchain-exporter/
sudo cp rustchain-exporter.service /etc/systemd/system/

# Install dependencies
cd /opt/rustchain-exporter
pip3 install -r requirements.txt

# Start service
sudo systemctl daemon-reload
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter

# Check status
sudo systemctl status rustchain-exporter
```

## Configuration

Environment variables:

- `RUSTCHAIN_NODE_URL` - RustChain node URL (default: `https://rustchain.org`)
- `EXPORTER_PORT` - Metrics port (default: `9100`)
- `SCRAPE_INTERVAL` - Scrape interval in seconds (default: `60`)

## Metrics

### Node Health
- `rustchain_node_up` - Node is up and responding
- `rustchain_node_uptime_seconds` - Node uptime

### Miners
- `rustchain_active_miners_total` - Number of active miners
- `rustchain_enrolled_miners_total` - Number of enrolled miners
- `rustchain_miner_last_attest_timestamp` - Last attestation timestamp per miner

### Epoch
- `rustchain_current_epoch` - Current epoch number
- `rustchain_current_slot` - Current slot number
- `rustchain_epoch_slot_progress` - Epoch progress (0-1)
- `rustchain_epoch_seconds_remaining` - Estimated seconds until next epoch

### Balances
- `rustchain_balance_rtc` - Miner balance in RTC

### Hall of Fame
- `rustchain_total_machines` - Total machines
- `rustchain_total_attestations` - Total attestations
- `rustchain_oldest_machine_year` - Oldest machine year
- `rustchain_highest_rust_score` - Highest rust score

### Fees
- `rustchain_total_fees_collected_rtc` - Total fees collected
- `rustchain_fee_events_total` - Total fee events

## Grafana Dashboard

The included dashboard provides:
- Node status and uptime
- Epoch progress gauge
- Active vs enrolled miners chart
- Top 10 miner balances table
- Hall of Fame statistics
- Auto-refresh every 30 seconds

Import `grafana-dashboard.json` or use the Docker Compose setup for automatic provisioning.

## Alert Rules

Included alerts:
- **RustChainNodeDown** - Node offline for >5 minutes
- **MinerOffline** - Miner hasn't attested in >30 minutes
- **LowMinerBalance** - Balance below 10 RTC
- **FewActiveMiners** - Less than 5 active miners
- **EpochStalled** - No new slots in 10 minutes

## API Endpoints Used

- `/health` - Node health and version
- `/epoch` - Current epoch and slot info
- `/api/miners` - Miner list and attestations
- `/api/stats` - Top balances
- `/api/hall_of_fame` - Hall of Fame data
- `/api/fee_pool` - Fee pool statistics

## Requirements

- Python 3.7+
- `prometheus-client`
- `requests`

## License

MIT

## Author

Created for RustChain bounty #504
