# RustChain Prometheus Exporter

Prometheus-compatible metrics exporter for RustChain nodes with Grafana dashboard.

## Features

- ✅ Real-time metrics collection from RustChain API
- ✅ Built-in `/metrics` endpoint in node (no separate exporter needed)
- ✅ Standalone exporter for external monitoring
- ✅ Pre-built Grafana dashboard
- ✅ Docker Compose setup with Prometheus + Grafana
- ✅ Alert rules for node health, miner status, and balances
- ✅ Systemd service file for production deployment

## Deployment Options

### Option 1: Built-in Node Metrics (Recommended)

The RustChain node includes a built-in `/metrics` endpoint at `http://localhost:8099/metrics`.

**Configure Prometheus to scrape directly:**

```yaml
scrape_configs:
  - job_name: 'rustchain-node'
    static_configs:
      - targets: ['localhost:8099']
```

**Benefits:**
- No additional processes
- Real-time metrics from database
- Lower latency
- Simpler deployment

### Option 2: Standalone Exporter

Use the standalone exporter for external monitoring or when you can't modify the node.

```bash
# Start exporter + Prometheus + Grafana
docker-compose up -d

# Access Grafana at http://localhost:3000 (admin/admin)
```

### Option 3: Node + Monitoring (Recommended for Self-Hosted)

If you're running the node yourself, use the built-in metrics endpoint:

```bash
# Start only Prometheus + Grafana (node provides metrics)
docker-compose -f docker-compose.node.yml up -d

# Node metrics available at http://localhost:8099/metrics
# Grafana available at http://localhost:3000
```

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
- `rustchain_node_up{version="..."}` - Node is up and responding (1=up, 0=down)
- `rustchain_node_uptime_seconds` - Node uptime in seconds
- `rustchain_node_info` - Node version information

### Miners
- `rustchain_active_miners_total` - Number of active miners (attested in last 30 min)
- `rustchain_enrolled_miners_total` - Number of enrolled miners in current epoch
- `rustchain_miner_last_attest_timestamp{miner,arch,device_family}` - Last attestation timestamp per miner

### Epoch
- `rustchain_current_epoch` - Current epoch number
- `rustchain_current_slot` - Current slot number
- `rustchain_epoch_slot_progress` - Epoch progress (0.0-1.0)
- `rustchain_epoch_seconds_remaining` - Estimated seconds until next epoch
- `rustchain_blocks_per_epoch` - Configured blocks per epoch
- `rustchain_epoch_pot_rtc` - Current epoch reward pot in RTC

### Hall of Fame
- `rustchain_total_machines` - Total machines in Hall of Fame
- `rustchain_total_attestations` - Total attestations across all machines
- `rustchain_oldest_machine_year` - Manufacturing year of oldest machine
- `rustchain_highest_rust_score` - Highest rust score achieved

### Fees (RIP-301)
- `rustchain_total_fees_collected_rtc` - Total fees collected and recycled to mining pool
- `rustchain_fee_events_total` - Total number of fee events

### Supply
- `rustchain_total_supply_rtc` - Total RTC token supply (8,388,608)

### Withdrawals
- `rustchain_withdrawal_requests` - Total withdrawal requests
- `rustchain_withdrawal_completed` - Completed withdrawals
- `rustchain_withdrawal_failed` - Failed withdrawals
- `rustchain_miner_balance{miner_pk}` - Individual miner balance
- `rustchain_withdrawal_queue` - Pending withdrawals in queue

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
