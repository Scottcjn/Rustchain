# RustChain Prometheus Exporter

Prometheus exporter for the RustChain node API.

This implementation closes issue `#504` in `Scottcjn/rustchain-bounties`.

## Files

- `rustchain_exporter.py` - exporter process
- `requirements.txt` - Python dependencies
- `rustchain-exporter.service` - systemd unit
- `docker-compose.yml` - exporter + Prometheus + Grafana stack
- `prometheus.yml` - Prometheus scrape config
- `dashboard.json` - Grafana dashboard
- `alerts.yml` - Prometheus alert rules

## Metrics

Implemented metrics:

- `rustchain_node_up{version}`
- `rustchain_node_uptime_seconds`
- `rustchain_active_miners_total`
- `rustchain_enrolled_miners_total`
- `rustchain_miner_last_attest_timestamp{miner,arch}`
- `rustchain_current_epoch`
- `rustchain_current_slot`
- `rustchain_epoch_slot_progress`
- `rustchain_epoch_seconds_remaining`
- `rustchain_balance_rtc{miner}`
- `rustchain_total_machines`
- `rustchain_total_attestations`
- `rustchain_oldest_machine_year`
- `rustchain_highest_rust_score`
- `rustchain_total_fees_collected_rtc`
- `rustchain_fee_events_total`
- `rustchain_p2p_up`
- `rustchain_p2p_peer_count`
- `rustchain_p2p_attestation_count`
- `rustchain_p2p_settled_epochs`
- `rustchain_p2p_message_rate_per_second`
- `rustchain_p2p_messages_total`
- `rustchain_p2p_health_latency_seconds`

## API Endpoints Scraped (every 60s)

- `/health`
- `/epoch`
- `/api/miners`
- `/api/hall_of_fame`
- `/api/fee_pool`
- `/api/stats`
- `/p2p/health` from `P2P_NODE_URL`

## Configuration

Environment variables:

- `NODE_URL` (default: `https://rustchain.org`)
- `P2P_NODE_URL` (default: `https://50.28.86.131`, the public node currently exposing `/p2p/health`)
- `EXPORTER_PORT` (default: `9100`)
- `SCRAPE_INTERVAL` (default: `60`)
- `REQUEST_TIMEOUT` (default: `15`)

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python rustchain_exporter.py
```

Metrics endpoint:

- `http://localhost:9100/metrics`

## Docker Stack

```bash
docker compose up -d
```

Services:

- Exporter: `http://localhost:9100/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (`admin` / `admin`)

## Systemd

```bash
sudo cp rustchain_exporter.py /opt/rustchain-exporter/
sudo cp requirements.txt /opt/rustchain-exporter/
sudo cp rustchain-exporter.service /etc/systemd/system/

cd /opt/rustchain-exporter
pip3 install -r requirements.txt

sudo systemctl daemon-reload
sudo systemctl enable rustchain-exporter
sudo systemctl start rustchain-exporter
```
