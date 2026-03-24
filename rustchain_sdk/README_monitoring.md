# SPDX-License-Identifier: MIT

# RustChain Monitoring Guide

## Overview

This guide covers setting up Prometheus metrics collection and Grafana monitoring for RustChain nodes. The monitoring stack provides visibility into node health, epoch state, miner activity, and chain statistics.

## Prometheus Exporter Setup

### Installation

The RustChain Prometheus exporter is a standalone Python service that scrapes node API endpoints and exposes metrics in Prometheus format.

```bash
# Install dependencies
pip install prometheus_client requests

# Run the exporter
python rustchain_exporter.py --node-url http://localhost:5000 --port 9090
```

### Configuration Options

```
--node-url    RustChain node API endpoint (default: http://localhost:5000)
--port        Exporter listen port (default: 9090)
--interval    Scrape interval in seconds (default: 30)
--timeout     Request timeout in seconds (default: 10)
```

## Systemd Service Installation

### Create Service File

Create `/etc/systemd/system/rustchain-exporter.service`:

```ini
[Unit]
Description=RustChain Prometheus Exporter
After=network.target
Requires=network.target

[Service]
Type=simple
User=rustchain
Group=rustchain
WorkingDirectory=/opt/rustchain
ExecStart=/usr/bin/python3 /opt/rustchain/rustchain_exporter.py --node-url http://localhost:5000 --port 9090
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter
sudo systemctl status rustchain-exporter
```

## Metric Descriptions

### Node Health Metrics

- `rustchain_node_up` - Node availability (1=up, 0=down)
- `rustchain_node_response_time` - API response time in seconds
- `rustchain_node_last_seen` - Unix timestamp of last successful scrape

### Blockchain Metrics

- `rustchain_block_height` - Current block height
- `rustchain_chain_difficulty` - Current chain difficulty
- `rustchain_chain_hashrate` - Estimated network hashrate
- `rustchain_pending_transactions` - Number of pending transactions

### Epoch Metrics

- `rustchain_epoch_current` - Current epoch number
- `rustchain_epoch_progress` - Epoch completion percentage (0-100)
- `rustchain_epoch_blocks_remaining` - Blocks remaining in current epoch
- `rustchain_epoch_time_remaining` - Estimated seconds until next epoch

### Miner Activity Metrics

- `rustchain_active_miners` - Number of active miners
- `rustchain_miner_hashrate` - Individual miner hashrate by miner ID
- `rustchain_blocks_mined` - Total blocks mined by miner ID
- `rustchain_mining_rewards` - Total rewards earned by miner ID

### Transaction Metrics

- `rustchain_transaction_pool_size` - Current transaction pool size
- `rustchain_transactions_per_second` - Recent transaction throughput
- `rustchain_transaction_fees_total` - Cumulative transaction fees

## Prometheus Configuration

### Add Scrape Target

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'rustchain-nodes'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s
    scrape_timeout: 10s
    metrics_path: '/metrics'
```

### Multi-Node Setup

For monitoring multiple nodes:

```yaml
scrape_configs:
  - job_name: 'rustchain-nodes'
    static_configs:
      - targets: 
          - 'node1:9090'
          - 'node2:9090'
          - 'node3:9090'
    scrape_interval: 30s
    scrape_timeout: 10s
    metrics_path: '/metrics'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        regex: '([^:]+):\d+'
        replacement: '${1}'
```

### Service Discovery

Using file-based service discovery:

```yaml
scrape_configs:
  - job_name: 'rustchain-nodes'
    file_sd_configs:
      - files:
          - '/etc/prometheus/rustchain_targets.json'
    scrape_interval: 30s
```

Create `/etc/prometheus/rustchain_targets.json`:

```json
[
  {
    "targets": ["node1:9090", "node2:9090"],
    "labels": {
      "environment": "production",
      "region": "us-east-1"
    }
  }
]
```

## Docker Deployment

### Exporter Dockerfile

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY rustchain_exporter.py .
EXPOSE 9090
CMD ["python", "rustchain_exporter.py"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  rustchain-exporter:
    build: .
    ports:
      - "9090:9090"
    environment:
      - NODE_URL=http://rustchain-node:5000
    depends_on:
      - rustchain-node
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
    restart: unless-stopped

volumes:
  grafana-storage:
```

## Alerting Rules

### Critical Alerts

```yaml
groups:
  - name: rustchain.rules
    rules:
      - alert: RustChainNodeDown
        expr: rustchain_node_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "RustChain node is down"
          description: "RustChain node {{ $labels.instance }} has been down for more than 1 minute"

      - alert: RustChainHighResponseTime
        expr: rustchain_node_response_time > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "RustChain node high response time"
          description: "RustChain node {{ $labels.instance }} response time is {{ $value }}s"

      - alert: RustChainEpochStalled
        expr: increase(rustchain_epoch_current[10m]) == 0
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "RustChain epoch progression stalled"
          description: "No epoch progression detected for 10 minutes on {{ $labels.instance }}"
```

## Health Check Endpoint

The exporter exposes a health check endpoint at `/health`:

```bash
curl http://localhost:9090/health
```

Returns:
- 200 OK if exporter is healthy
- 503 Service Unavailable if unable to reach RustChain node

## Troubleshooting

### Common Issues

1. **Connection refused**: Check if RustChain node is running on specified port
2. **Permission denied**: Ensure exporter user has network access
3. **Timeout errors**: Increase timeout value or check network latency
4. **Missing metrics**: Verify RustChain node API endpoints are available

### Debug Mode

Run exporter with debug logging:

```bash
python rustchain_exporter.py --debug --node-url http://localhost:5000
```

### Log Locations

- Systemd service logs: `journalctl -u rustchain-exporter -f`
- Docker logs: `docker logs rustchain-exporter`

## Performance Considerations

- Default scrape interval: 30 seconds (adjustable)
- Memory usage: ~10-20MB per node
- CPU impact: minimal (<1% on modern systems)
- Network: ~1KB per scrape per node

Adjust scrape intervals based on your monitoring requirements and node capacity.