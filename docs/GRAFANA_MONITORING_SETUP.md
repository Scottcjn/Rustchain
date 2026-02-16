# RustChain Grafana Monitoring (Bounty #21)

This package adds Grafana + Prometheus monitoring for:
- Active miners & attestations
- RTC transfers & volume
- Epoch rewards
- Node health & API response latency
- Alerts for node down, unusual volume, miner drop

## Files
- `monitoring/docker-compose.monitoring.yml`
- `monitoring/prometheus.yml`
- `monitoring/alerts/rustchain-alerts.yml`
- `monitoring/grafana/dashboards/rustchain-overview.json`
- `monitoring/grafana/provisioning/*`

## Quick start

```bash
docker compose -f monitoring/docker-compose.monitoring.yml up -d
```

Open:
- Grafana: http://localhost:3000 (admin / admin)
- Prometheus: http://localhost:9090

## Important target setting
Default target is `host.docker.internal:8099` (RustChain node metrics endpoint).
If your node runs elsewhere, edit `monitoring/prometheus.yml` target.

## Alert rules
- `RustChainNodeDown`
- `RustChainHighApiLatencyP95`
- `MinerCountDrop`
- `UnusualTransferVolume`

## Ubuntu 22.04
- Install Docker + Compose plugin
- Ensure RustChain node is reachable on configured metrics target
- Run the compose command above
