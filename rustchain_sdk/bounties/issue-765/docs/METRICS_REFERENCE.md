# Metrics Reference - Bounty #765

Complete reference for all metrics exposed by the RustChain Prometheus Exporter.

## Metric Naming Convention

All metrics follow the Prometheus naming convention:
- Prefix: `rustchain_`
- Snake case: `active_miners` not `activeMiners`
- Units as suffix: `_seconds`, `_bytes`, `_total`
- Base units: seconds, bytes, RTC (token)

---

## Node Health Metrics

### rustchain_node_health

**Type**: Gauge  
**Unit**: 0-1 (boolean)  
**Labels**: None

Node health status. Value of 1 indicates healthy, 0 indicates unhealthy.

```prometheus
# HELP rustchain_node_health Node health status (1=healthy, 0=unhealthy)
# TYPE rustchain_node_health gauge
rustchain_node_health 1.0
```

**Source**: `/health` endpoint, `ok` field  
**Collection Interval**: Every scrape (30s default)

---

### rustchain_node_uptime_seconds

**Type**: Gauge  
**Unit**: Seconds  
**Labels**: None

Node uptime since last restart.

```prometheus
# HELP rustchain_node_uptime_seconds Node uptime in seconds
# TYPE rustchain_node_uptime_seconds gauge
rustchain_node_uptime_seconds 86400.0
```

**Source**: `/health` endpoint, `uptime_s` field  
**Use Case**: Track node stability, detect restarts

---

### rustchain_node_db_status

**Type**: Gauge  
**Unit**: 0-1 (boolean)  
**Labels**: None

Database read/write status. Value of 1 indicates OK, 0 indicates error.

```prometheus
# HELP rustchain_node_db_status Database read/write status (1=ok, 0=error)
# TYPE rustchain_node_db_status gauge
rustchain_node_db_status 1.0
```

**Source**: `/health` endpoint, `db_rw` field  
**Alert**: Critical if 0 for >1 minute

---

### rustchain_node_version_info

**Type**: Info (Gauge with value 1)  
**Unit**: None  
**Labels**: `version`

Node version information.

```prometheus
# HELP rustchain_node_version_info Node version information
# TYPE rustchain_node_version_info info
rustchain_node_version_info{version="2.0.0"} 1.0
```

**Source**: `/health` endpoint, `version` field  
**Use Case**: Track deployments, version distribution

---

### rustchain_backup_age_hours

**Type**: Gauge  
**Unit**: Hours  
**Labels**: None

Age of the last backup in hours.

```prometheus
# HELP rustchain_backup_age_hours Age of the last backup in hours
# TYPE rustchain_backup_age_hours gauge
rustchain_backup_age_hours 2.5
```

**Source**: `/health` endpoint, `backup_age_h` field  
**Alert**: Warning if >24 hours

---

### rustchain_tip_age_slots

**Type**: Gauge  
**Unit**: Slots  
**Labels**: None

Age of the chain tip in slots. Indicates sync status.

```prometheus
# HELP rustchain_tip_age_slots Age of chain tip in slots
# TYPE rustchain_tip_age_slots gauge
rustchain_tip_age_slots 3.0
```

**Source**: `/health` endpoint, `tip_age_slots` field  
**Alert**: Warning if >10 slots

---

## Epoch Metrics

### rustchain_epoch_number

**Type**: Gauge  
**Unit**: Epoch number  
**Labels**: None

Current epoch number. Increments approximately every epoch duration.

```prometheus
# HELP rustchain_epoch_number Current epoch number
# TYPE rustchain_epoch_number gauge
rustchain_epoch_number 100.0
```

**Source**: `/epoch` endpoint, `epoch` field  
**Use Case**: Track chain progress, detect stalled epochs

---

### rustchain_epoch_slot

**Type**: Gauge  
**Unit**: Slot number  
**Labels**: None

Current slot within the epoch.

```prometheus
# HELP rustchain_epoch_slot Current slot within epoch
# TYPE rustchain_epoch_slot gauge
rustchain_epoch_slot 5000.0
```

**Source**: `/epoch` endpoint, `slot` field  
**Use Case**: Track epoch progress

---

### rustchain_epoch_pot_rtc

**Type**: Gauge  
**Unit**: RTC (token)  
**Labels**: None

Current epoch reward pot in RTC tokens.

```prometheus
# HELP rustchain_epoch_pot_rtc Epoch reward pot in RTC
# TYPE rustchain_epoch_pot_rtc gauge
rustchain_epoch_pot_rtc 1000000.0
```

**Source**: `/epoch` endpoint, `epoch_pot` field  
**Use Case**: Track reward accumulation

---

### rustchain_enrolled_miners

**Type**: Gauge  
**Unit**: Count  
**Labels**: None

Total number of enrolled miners in the network.

```prometheus
# HELP rustchain_enrolled_miners Total number of enrolled miners
# TYPE rustchain_enrolled_miners gauge
rustchain_enrolled_miners 50.0
```

**Source**: `/epoch` endpoint, `enrolled_miners` field  
**Use Case**: Track network growth

---

### rustchain_total_supply_rtc

**Type**: Gauge  
**Unit**: RTC (token)  
**Labels**: None

Total RTC token supply.

```prometheus
# HELP rustchain_total_supply_rtc Total RTC token supply
# TYPE rustchain_total_supply_rtc gauge
rustchain_total_supply_rtc 21000000.0
```

**Source**: `/epoch` endpoint, `total_supply_rtc` field  
**Use Case**: Track token economics, detect anomalies

---

### rustchain_blocks_per_epoch

**Type**: Gauge  
**Unit**: Count  
**Labels**: None

Number of blocks per epoch.

```prometheus
# HELP rustchain_blocks_per_epoch Number of blocks per epoch
# TYPE rustchain_blocks_per_epoch gauge
rustchain_blocks_per_epoch 100.0
```

**Source**: `/epoch` endpoint, `blocks_per_epoch` field  
**Use Case**: Track protocol parameters

---

## Miner Metrics

### rustchain_active_miners

**Type**: Gauge  
**Unit**: Count  
**Labels**: None

Number of currently active miners (attested within active window).

```prometheus
# HELP rustchain_active_miners Number of active miners
# TYPE rustchain_active_miners gauge
rustchain_active_miners 45.0
```

**Source**: `/api/miners` endpoint, count of active miners  
**Use Case**: Primary health metric for mining network

---

### rustchain_miners_by_hardware

**Type**: Gauge  
**Unit**: Count  
**Labels**: `hardware_type`

Distribution of miners by hardware type.

```prometheus
# HELP rustchain_miners_by_hardware Miners grouped by hardware type
# TYPE rustchain_miners_by_hardware gauge
rustchain_miners_by_hardware{hardware_type="PowerPC G4 (Vintage)"} 15.0
rustchain_miners_by_hardware{hardware_type="Apple Silicon M1"} 20.0
rustchain_miners_by_hardware{hardware_type="Intel x86_64"} 10.0
```

**Source**: `/api/miners` endpoint, `hardware_type` field  
**Use Case**: Hardware distribution analysis, vintage vs modern ratio

---

### rustchain_miners_by_architecture

**Type**: Gauge  
**Unit**: Count  
**Labels**: `architecture`

Distribution of miners by CPU architecture.

```prometheus
# HELP rustchain_miners_by_architecture Miners grouped by CPU architecture
# TYPE rustchain_miners_by_architecture gauge
rustchain_miners_by_architecture{architecture="powerpc"} 15.0
rustchain_miners_by_architecture{architecture="arm64"} 20.0
rustchain_miners_by_architecture{architecture="x86_64"} 10.0
```

**Source**: `/api/miners` endpoint, `device_arch` field  
**Use Case**: Architecture distribution analysis

---

### rustchain_antiquity_multiplier_avg

**Type**: Gauge  
**Unit**: Multiplier  
**Labels**: None

Average antiquity multiplier across all active miners.

```prometheus
# HELP rustchain_antiquity_multiplier_avg Average antiquity multiplier across miners
# TYPE rustchain_antiquity_multiplier_avg gauge
rustchain_antiquity_multiplier_avg 1.85
```

**Source**: `/api/miners` endpoint, calculated from `antiquity_multiplier`  
**Use Case**: Detect VM/emulator usage, verify hardware authenticity

---

### rustchain_antiquity_multiplier_min

**Type**: Gauge  
**Unit**: Multiplier  
**Labels**: None

Minimum antiquity multiplier among active miners.

```prometheus
# HELP rustchain_antiquity_multiplier_min Minimum antiquity multiplier
# TYPE rustchain_antiquity_multiplier_min gauge
rustchain_antiquity_multiplier_min 1.0
```

**Source**: `/api/miners` endpoint, minimum of `antiquity_multiplier`  
**Use Case**: Detect potential spoofing

---

### rustchain_antiquity_multiplier_max

**Type**: Gauge  
**Unit**: Multiplier  
**Labels**: None

Maximum antiquity multiplier among active miners.

```prometheus
# HELP rustchain_antiquity_multiplier_max Maximum antiquity multiplier
# TYPE rustchain_antiquity_multiplier_max gauge
rustchain_antiquity_multiplier_max 3.5
```

**Source**: `/api/miners` endpoint, maximum of `antiquity_multiplier`  
**Use Case**: Track highest vintage hardware

---

## Exporter Metrics

### rustchain_scrape_duration_seconds

**Type**: Gauge  
**Unit**: Seconds  
**Labels**: None

Duration of the last metrics collection scrape.

```prometheus
# HELP rustchain_scrape_duration_seconds Duration of the last scrape in seconds
# TYPE rustchain_scrape_duration_seconds gauge
rustchain_scrape_duration_seconds 0.523
```

**Source**: Measured during collection  
**Alert**: Warning if >5s  
**Use Case**: Monitor exporter performance

---

### rustchain_scrapes_total

**Type**: Counter  
**Unit**: Count  
**Labels**: None

Total number of scrapes performed since exporter start.

```prometheus
# HELP rustchain_scrapes_total Total number of scrapes performed
# TYPE rustchain_scrapes_total counter
rustchain_scrapes_total 150.0
```

**Source**: Internal counter  
**Use Case**: Calculate scrape rate, track uptime

---

### rustchain_scrape_errors_total

**Type**: Counter  
**Unit**: Count  
**Labels**: None

Total number of scrape errors since exporter start.

```prometheus
# HELP rustchain_scrape_errors_total Total number of scrape errors
# TYPE rustchain_scrape_errors_total counter
rustchain_scrape_errors_total 2.0
```

**Source**: Internal counter  
**Alert**: Warning if rate >0.1/s  
**Use Case**: Monitor reliability

---

### rustchain_last_scrape_timestamp

**Type**: Gauge  
**Unit**: Unix timestamp (seconds)  
**Labels**: None

Unix timestamp of the last successful scrape.

```prometheus
# HELP rustchain_last_scrape_timestamp Timestamp of the last scrape
# TYPE rustchain_last_scrape_timestamp gauge
rustchain_last_scrape_timestamp 1709985600.0
```

**Source**: `time.time()` after collection  
**Use Case**: Verify freshness of metrics

---

## Query Examples

### Basic Queries

```promql
# Current node health
rustchain_node_health

# Active miners
rustchain_active_miners

# Current epoch
rustchain_epoch_number
```

### Rate Calculations

```promql
# Scrape error rate (errors per second)
rate(rustchain_scrape_errors_total[5m])

# Scrapes per minute
rate(rustchain_scrapes_total[1m]) * 60
```

### Aggregations

```promql
# Total miners by hardware type (sum across all instances)
sum by (hardware_type) (rustchain_miners_by_hardware)

# Average antiquity multiplier across all nodes
avg(rustchain_antiquity_multiplier_avg)

# Maximum tip age across all nodes
max(rustchain_tip_age_slots)
```

### Anomaly Detection

```promql
# Miner drop detection (>20% decrease from 1h average)
(rustchain_active_miners - avg_over_time(rustchain_active_miners[1h])) 
/ avg_over_time(rustchain_active_miners[1h]) < -0.2

# Supply anomaly (>1% deviation from 24h average)
abs(rustchain_total_supply_rtc - avg_over_time(rustchain_total_supply_rtc[24h])) 
/ avg_over_time(rustchain_total_supply_rtc[24h]) > 0.01

# Stuck epoch detection (no change in 2h)
changes(rustchain_epoch_number[2h]) == 0
```

### Recording Rules (Recommended)

```yaml
groups:
  - name: rustchain_recording
    interval: 30s
    rules:
      - record: rustchain:miner_drop_ratio
        expr: |
          (rustchain_active_miners - avg_over_time(rustchain_active_miners[1h])) 
          / avg_over_time(rustchain_active_miners[1h])
      
      - record: rustchain:scrape_error_rate:5m
        expr: rate(rustchain_scrape_errors_total[5m])
      
      - record: rustchain:vintage_ratio
        expr: |
          sum(rustchain_miners_by_hardware{hardware_type=~".*Vintage.*"}) 
          / sum(rustchain_active_miners)
```

---

## Label Values

### hardware_type

Common values:
- `PowerPC G4 (Vintage)`
- `PowerPC G5 (Vintage)`
- `Apple Silicon M1`
- `Apple Silicon M2`
- `Intel x86_64`
- `AMD x86_64`
- `ARM64`
- `Unknown`

### architecture

Common values:
- `powerpc`
- `arm64`
- `x86_64`
- `Unknown`

---

## Best Practices

### Querying

1. **Use rate() for counters**: Always use `rate()` or `irate()` for counter metrics
2. **Add time windows**: Use `[5m]`, `[1h]` for trend analysis
3. **Handle missing data**: Use `or vector(0)` for default values

### Alerting

1. **Use appropriate thresholds**: Base on historical data
2. **Add `for` duration**: Prevent flapping alerts
3. **Include labels**: Route alerts to correct teams

### Dashboard Design

1. **Single stats**: Use for current values (health, count)
2. **Time series**: Use for trends (miners over time)
3. **Pie charts**: Use for distributions (hardware types)
4. **Thresholds**: Add visual indicators for alert levels

---

*Last Updated: 2026-03-09*  
*Version: 1.0.0*
