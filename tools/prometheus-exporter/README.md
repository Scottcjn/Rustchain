# RustChain Prometheus Exporter

Prometheus exporter for monitoring RustChain blockchain nodes.

## Features

- Scrapes RustChain node RPC endpoints periodically
- Exposes node health, epoch, miner counts, and per-miner antiquity multipliers
- Configurable scrape interval and target node URL
- Built-in `/health` endpoint for liveness probes

## Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_node_up` | gauge | 1 if node is reachable, 0 otherwise |
| `rustchain_node_version_info` | info | Node version string |
| `rustchain_epoch` | gauge | Current epoch number |
| `rustchain_miners_total` | gauge | Total registered miners |
| `rustchain_miners_active` | gauge | Currently active miners |
| `rustchain_miner_antiquity_multiplier` | gauge | Per-miner antiquity reward multiplier (label: `miner`) |
| `rustchain_last_scrape_timestamp` | gauge | Unix timestamp of last successful scrape |

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Start with defaults (scrapes localhost:8080, exports on port 9200)
python rustchain_exporter.py

# Custom configuration
RUSTCHAIN_NODE_URL=http://10.0.0.5:8080 \
PROMETHEUS_EXPORTER_PORT=9200 \
SCRAPE_INTERVAL=30 \
python rustchain_exporter.py
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RUSTCHAIN_NODE_URL` | `http://localhost:8080` | RustChain node base URL |
| `PROMETHEUS_EXPORTER_HOST` | `0.0.0.0` | Exporter listen address |
| `PROMETHEUS_EXPORTER_PORT` | `9200` | Exporter listen port |
| `SCRAPE_INTERVAL` | `15` | Scrape interval in seconds |

## Prometheus Configuration

```yaml
scrape_configs:
  - job_name: rustchain
    static_configs:
      - targets:
          - localhost:9200
    scrape_interval: 15s
```

## Docker

```bash
docker build -t rustchain-exporter .
docker run -e RUSTCHAIN_NODE_URL=http://node:8080 -p 9200:9200 rustchain-exporter
```
