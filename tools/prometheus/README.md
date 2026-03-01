# RustChain Prometheus Exporter

Prometheus metrics exporter for RustChain node monitoring.

## Quick Start

```bash
# Install dependencies
cd tools/prometheus
pip install -r requirements.txt

# Run exporter
export RUSTCHAIN_NODE_URL="http://localhost:8080"
python3 rustchain_exporter.py
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_NODE_URL` | `http://localhost:8080` | RustChain node URL |
| `EXPORTER_PORT` | `9100` | Prometheus exporter port |
| `SCRAPE_INTERVAL` | `60` | Scrape interval in seconds |

## Metrics

- `rustchain_node_up` - Node health status
- `rustchain_node_uptime_seconds` - Node uptime
- `rustchain_active_miners_total` - Active miners count
- `rustchain_enrolled_miners_total` - Enrolled miners count
- `rustchain_miner_last_attest_timestamp` - Last attestation per miner
- `rustchain_current_epoch` - Current epoch
- `rustchain_current_slot` - Current slot
- `rustchain_epoch_slot_progress` - Epoch progress (0-1)
- `rustchain_epoch_seconds_remaining` - Seconds remaining in epoch
- `rustchain_balance_rtc` - Miner balances
- `rustchain_total_machines` - Hall of Fame machines
- `rustchain_total_attestations` - Total attestations
- `rustchain_oldest_machine_year` - Oldest machine year
- `rustchain_highest_rust_score` - Highest rust score
- `rustchain_total_fees_collected_rtc` - Total fees collected
- `rustchain_fee_events_total` - Total fee events

## Systemd Installation

```bash
sudo cp rustchain-exporter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter
```

## Docker Compose (Bonus)

```yaml
version: '3.8'
services:
  rustchain-exporter:
    build: .
    ports:
      - "9100:9100"
    environment:
      - RUSTCHAIN_NODE_URL=http://node:8080
      - EXPORTER_PORT=9100

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```
