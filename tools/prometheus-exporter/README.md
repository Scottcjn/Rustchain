# Enhanced RustChain Prometheus Exporter

Advanced Prometheus exporter for the RustChain network with deep per-miner
observability, transaction throughput analysis, API latency histograms,
fee pool growth rate tracking, and attestation success rate monitoring.

## Metrics

### Node Health
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_node_up{version}` | Gauge | Node health (1=up, 0=down) |
| `rustchain_node_uptime_seconds` | Gauge | Uptime in seconds |
| `rustchain_node_db_status` | Gauge | DB read/write health |

### Epoch
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_current_epoch` | Gauge | Current epoch number |
| `rustchain_current_slot` | Gauge | Current slot number |
| `rustchain_epoch_slot_progress` | Gauge | Fraction of epoch completed (0-1) |
| `rustchain_epoch_seconds_remaining` | Gauge | Seconds until epoch ends |
| `rustchain_epoch_pot_rtc` | Gauge | Epoch reward pot in RTC |
| `rustchain_enrolled_miners_total` | Gauge | Enrolled miners |
| `rustchain_total_supply_rtc` | Gauge | Total RTC supply |

### Per-Miner Metrics
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `rustchain_miner_balance_rtc` | Gauge | miner, arch, hardware_type | Individual balance |
| `rustchain_miner_antiquity_multiplier` | Gauge | miner, arch | Antiquity multiplier |
| `rustchain_miner_last_attest_timestamp` | Gauge | miner, arch | Last attestation unix time |
| `rustchain_miner_rust_score` | Gauge | miner | Rust score |
| `rustchain_miner_attestation_success_rate` | Gauge | miner | Per-miner attestation success rate |
| `rustchain_active_miners_total` | Gauge | | Active miners count |
| `rustchain_miners_by_hardware` | Gauge | hardware_type | Miners by hardware type |
| `rustchain_miners_by_arch` | Gauge | arch | Miners by CPU architecture |
| `rustchain_avg_antiquity_multiplier` | Gauge | | Average antiquity multiplier |

### Attestation Success Rates
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_attestations_total` | Gauge | Total attestations observed |
| `rustchain_attestations_successful` | Gauge | Successful attestations |
| `rustchain_attestations_failed` | Gauge | Failed attestations |
| `rustchain_attestation_success_rate` | Gauge | Network-wide success rate (0-1) |

### Transaction Throughput
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_transactions_total` | Gauge | Total transaction count |
| `rustchain_tx_throughput_per_second` | Gauge | Rolling throughput (tx/s) |
| `rustchain_tx_pending` | Gauge | Pending mempool transactions |
| `rustchain_tx_avg_fee_rtc` | Gauge | Average transaction fee |

### Fee Pool & Growth Rate
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_fee_pool_total_rtc` | Gauge | Total fees collected |
| `rustchain_fee_events_total` | Gauge | Total fee events |
| `rustchain_fee_pool_growth_rate_rtc_per_min` | Gauge | Fee pool growth (RTC/min) |
| `rustchain_fee_pool_epoch_delta_rtc` | Gauge | Fee change this epoch |

### API Latency
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `rustchain_api_latency_seconds` | Histogram | endpoint, status | Per-endpoint latency distribution |
| `rustchain_api_errors_total` | Counter | endpoint | Total API errors by endpoint |

### Scrape Internals
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_scrape_duration_seconds` | Summary | Time spent per collection cycle |
| `rustchain_scrape_errors_total` | Counter | Failed scrape cycles |

### Hall of Fame
| Metric | Type | Description |
|--------|------|-------------|
| `rustchain_hof_total_machines` | Gauge | Total machines |
| `rustchain_hof_total_attestations` | Gauge | Total attestations |
| `rustchain_hof_oldest_machine_year` | Gauge | Oldest machine year |
| `rustchain_hof_highest_rust_score` | Gauge | Highest rust score |

## API Endpoints Scraped

- `/health`
- `/epoch`
- `/api/miners`
- `/api/stats`
- `/api/attestations` (fallback)
- `/api/fee_pool`
- `/api/hall_of_fame`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_URL` | `https://rustchain.org` | RustChain node URL |
| `EXPORTER_PORT` | `9110` | HTTP port for `/metrics` |
| `SCRAPE_INTERVAL` | `30` | Collection interval in seconds |
| `REQUEST_TIMEOUT` | `15` | HTTP request timeout |
| `LOG_LEVEL` | `INFO` | Logging level |

## Run Locally

```bash
pip install prometheus_client requests
python exporter.py
```

Metrics available at `http://localhost:9110/metrics`.

## Docker

```bash
docker run -e NODE_URL=https://rustchain.org -p 9110:9110 rustchain-enhanced-exporter
```

## Example PromQL Queries

```promql
# Active miner trend (5m rate)
rate(rustchain_active_miners_total[5m])

# 95th percentile API latency per endpoint
histogram_quantile(0.95, rate(rustchain_api_latency_seconds_bucket[5m]))

# Fee pool growth rate
rustchain_fee_pool_growth_rate_rtc_per_min

# Attestation success rate
rustchain_attestation_success_rate

# Transaction throughput
rustchain_tx_throughput_per_second

# Miners with low attestation success (< 80%)
rustchain_miner_attestation_success_rate < 0.8
```
