# RustChain Node Health Monitor

Low-dependency monitor that polls RustChain nodes/miners and sends alerts to a Discord webhook.

## Features

- Poll node `/health` and alert on down/recovery
- Poll `/api/miners` and alert on:
  - miner count drop (default: 2+)
  - stale miners (default: no attestation in 2h, best-effort based on API fields)
- Debounced alerts (cooldown) to avoid spam while a node stays down
- JSON snapshot output to disk
- Optional local status endpoint (`/status.json`)

## Run (one-shot)

```bash
python3 tools/node_health_monitor.py --once --insecure-ssl
```

## Run (daemon)

1. Copy example config:

```bash
cp tools/node_health_monitor_config.example.json tools/node_health_monitor_config.json
```

2. Edit `tools/node_health_monitor_config.json` and set `discord_webhook`.

3. Start:

```bash
python3 tools/node_health_monitor.py --config tools/node_health_monitor_config.json
```

## Local Status Endpoint

```bash
python3 tools/node_health_monitor.py --config tools/node_health_monitor_config.json --serve 8081
curl http://127.0.0.1:8081/status.json
```

## systemd

On a Linux host:

```bash
cp tools/node_health_monitor.service /etc/systemd/system/rustchain-node-monitor.service
systemctl daemon-reload
systemctl enable --now rustchain-node-monitor.service
```

## Notes

- The config is assumed to be trusted input. If you ever run this as a service that accepts untrusted config, the node URL polling becomes an SSRF risk.
- If nodes use self-signed TLS, set `"insecure_ssl": true` in config (or pass `--insecure-ssl`).
- The miner freshness check is best-effort and adapts to multiple likely `/api/miners` schemas.
- The local SQLite `samples` table is pruned by default (keeps 7 days). Configure via `sample_retention_days` / `--sample-retention-days`.
