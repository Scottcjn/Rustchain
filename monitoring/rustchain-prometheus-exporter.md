# RustChain Prometheus Metrics Exporter

A Prometheus-compatible metrics exporter for RustChain node monitoring.

## Installation

```bash
pip install git+https://github.com/sososonia-cyber/RustChain.git
```

Or run directly:

```bash
python rustchain_exporter.py
```

## Usage

### Run exporter

```bash
python rustchain_exporter.py --port 9090 --node-url https://50.28.86.131
```

### Add to Prometheus

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'rustchain'
    static_configs:
      - targets: ['localhost:9090']
```

## Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_node_up` | gauge | Node operational status |
| `rustchain_node_uptime_seconds` | counter | Node uptime |
| `rustchain_active_miners_total` | gauge | Number of active miners |
| `rustchain_current_epoch` | gauge | Current epoch number |
| `rustchain_current_slot` | gauge | Current slot |
| `rustchain_epoch_slot_progress` | gauge | Epoch progress (0-1) |
| `rustchain_miner_info` | gauge | Miner details |
| `rustchain_miner_antiquity_multiplier` | gauge | Miner antiquity multiplier |

## Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY rustchain_exporter.py .
RUN pip install prometheus-client
EXPOSE 9090
CMD ["python", "rustchain_exporter.py"]
```

## License

MIT

## Author

Built by Atlas (AI Agent) for RustChain Bounty #504
