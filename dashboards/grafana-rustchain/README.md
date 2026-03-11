# RustChain Grafana Dashboard

A comprehensive Grafana dashboard for monitoring RustChain network metrics, including node health, miner activity, epoch statistics, and hardware distribution.

![Dashboard Preview](./screenshot.png)

## Overview

This dashboard provides real-time visualization of RustChain blockchain metrics using Prometheus as the data source. It includes 19 panels covering:

- **Node Health**: Health status, uptime, database status
- **Network Statistics**: Active miners, enrolled miners, epoch info
- **Token Metrics**: Total RTC supply, epoch pot
- **Hardware Analytics**: Distribution by hardware type and architecture
- **Performance**: Scrape duration, error rates
- **Alerts**: Active alert list

## Datasource Assumptions

This dashboard expects a **Prometheus** data source with the following metrics exposed by the RustChain exporter:

| Metric Name | Type | Description |
|-------------|------|-------------|
| `rustchain_node_health` | Gauge | Node health status (1=healthy, 0=unhealthy) |
| `rustchain_node_uptime_seconds` | Gauge | Node uptime in seconds |
| `rustchain_node_db_status` | Gauge | Database status (1=ok, 0=error) |
| `rustchain_epoch_number` | Gauge | Current epoch number |
| `rustchain_epoch_slot` | Gauge | Current slot within epoch |
| `rustchain_epoch_pot` | Gauge | Epoch reward pool in RTC |
| `rustchain_enrolled_miners` | Gauge | Total enrolled miners |
| `rustchain_total_supply_rtc` | Gauge | Total RTC token supply |
| `rustchain_active_miners` | Gauge | Currently active miners |
| `rustchain_miners_by_hardware{hardware_type}` | Gauge | Miners grouped by hardware type |
| `rustchain_miners_by_arch{arch}` | Gauge | Miners grouped by CPU architecture |
| `rustchain_avg_antiquity_multiplier` | Gauge | Average antiquity multiplier |
| `rustchain_scrape_errors_total` | Counter | Total scrape errors |
| `rustchain_scrape_duration_seconds` | Gauge | Duration of last scrape |

## Prerequisites

- Grafana 9.x or 10.x
- Prometheus data source configured
- RustChain exporter running and being scraped by Prometheus

## Quick Start

### Option 1: Import via Grafana UI

1. Open Grafana in your browser
2. Navigate to **Dashboards** → **Import**
3. Click **Upload dashboard JSON file**
4. Select `rustchain-network-dashboard.json`
5. Choose your Prometheus data source from the dropdown
6. Click **Import**

### Option 2: Import via Grafana CLI

```bash
# Copy dashboard to Grafana provisioning directory
cp rustchain-network-dashboard.json /etc/grafana/provisioning/dashboards/

# Or use grafana-cli (if available)
grafana-cli --admin-user admin --admin-password <password> \
  dashboard import rustchain-network-dashboard.json
```

### Option 3: Import via API

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-api-key>" \
  -d @rustchain-network-dashboard.json \
  http://localhost:3000/api/dashboards/db
```

## Setup Instructions

### Step 1: Configure Prometheus Data Source

1. In Grafana, go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - **Name**: `Prometheus` (or update the dashboard's `__inputs` section)
   - **URL**: `http://prometheus:9090` (adjust for your setup)
   - **Access**: Server (default)
5. Click **Save & Test**

### Step 2: Import the Dashboard

Follow one of the import methods above.

### Step 3: Verify Panels

After import, verify that all panels display data:
- Check the time range (default: last 24 hours)
- Ensure Prometheus data source is selected
- Refresh the dashboard if needed

## Using with Docker Compose

If you're using the monitoring stack from `../../monitoring/`:

```bash
cd ../../monitoring
docker-compose up -d
```

Then import the dashboard into Grafana at `http://localhost:3000`:
- Username: `admin`
- Password: `rustchain`

## Dashboard Variables

The dashboard includes template variables for dynamic filtering:

| Variable | Description | Query |
|----------|-------------|-------|
| `DS_PROMETHEUS` | Prometheus data source | Datasource selector |
| `hardware_type` | Filter by hardware type | `label_values(rustchain_miners_by_hardware, hardware_type)` |

## Panel Descriptions

### Row 1: Quick Stats (8 panels)

| Panel | Type | Description |
|-------|------|-------------|
| Node Health | Stat | Health status with color-coded background |
| Active Miners | Stat | Current active miner count |
| Current Epoch | Stat | Blockchain epoch number |
| Epoch Pot (RTC) | Stat | Current epoch reward pool |
| Total Supply (RTC) | Stat | Total RTC token supply |
| Enrolled Miners | Stat | Total enrolled miners |
| Node Uptime | Stat | Uptime in hours |
| DB Status | Stat | Database read/write status |

### Row 2-3: Time Series (4 panels)

| Panel | Type | Description |
|-------|------|-------------|
| Active Miners (24h) | Time series | Miner count trend over 24 hours |
| RTC Total Supply | Time series | Token supply evolution |
| Node Uptime | Time series | Uptime progression |
| Scrape Duration | Time series | Metrics collection performance |

### Row 4: Distribution (3 panels)

| Panel | Type | Description |
|-------|------|-------------|
| Miners by Hardware Type | Pie chart | Hardware distribution |
| Miners by Architecture | Pie chart | CPU architecture distribution |
| Avg Antiquity Multiplier | Gauge | Average multiplier value |

### Row 5: Advanced Metrics (2 panels)

| Panel | Type | Description |
|-------|------|-------------|
| Epoch Pot Evolution | Time series | Reward pool changes |
| Scrape Errors Rate | Time series | Error rate per minute |

### Row 6: Detailed Views (2 panels)

| Panel | Type | Description |
|-------|------|-------------|
| Miner Hardware Distribution | Table | Detailed hardware breakdown |
| Active Alerts | Alert list | Currently firing alerts |

## Customization

### Changing Colors

Edit the dashboard JSON or use Grafana's UI to modify panel colors in the **Field** tab.

### Adding New Panels

1. Click **Add panel** → **Add new panel**
2. Write your PromQL query
3. Configure visualization type
4. Save to dashboard

### Modifying Refresh Rate

Click the refresh interval dropdown (top-right) and select your preferred interval:
- 5s, 10s, 30s, 1m, 5m, 15m, 30m, 1h, 2h, 1d

## Useful PromQL Queries

```promql
# Active miners with 5-minute moving average
avg_over_time(rustchain_active_miners[5m])

# Miner growth rate
deriv(rustchain_active_miners[1h])

# Hardware type percentage
rustchain_miners_by_hardware / ignoring(hardware_type) group_left() sum(rustchain_miners_by_hardware) * 100

# Node uptime in days
rustchain_node_uptime_seconds / 86400

# Scrape errors per hour
increase(rustchain_scrape_errors_total[1h])

# Epoch duration (time between epoch changes)
time() - (rustchain_epoch_number - ignoring() group_left() (rustchain_epoch_number offset 1h)) * 3600
```

## Alerts Configuration

The dashboard includes a pre-configured alert for slow scrape times. To add more alerts:

1. Go to **Alerting** → **Alert rules**
2. Click **New alert rule**
3. Configure your query and conditions
4. Set up notification channels

### Example Alert Rules

```yaml
# Node Down Alert
- alert: RustChainNodeDown
  expr: rustchain_node_health == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "RustChain node is down"
    description: "Node has been unhealthy for more than 2 minutes"

# Miner Drop Alert
- alert: RustChainMinerDrop
  expr: deriv(rustchain_active_miners[10m]) < -0.5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Significant miner drop detected"
    description: "Active miners decreasing rapidly"

# High Scrape Duration
- alert: RustChainHighScrapeDuration
  expr: rustchain_scrape_duration_seconds > 5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Exporter scrape taking too long"
    description: "Scrape duration exceeded 5 seconds"
```

## Troubleshooting

### No Data Showing

1. **Check data source**: Ensure Prometheus is selected and connected
2. **Verify metrics**: Query `rustchain_active_miners` in Prometheus directly
3. **Time range**: Expand the time range if no recent data exists
4. **Exporter status**: Confirm the RustChain exporter is running

### Panels Show Errors

1. **PromQL syntax**: Check query syntax in panel edit mode
2. **Metric names**: Verify metric names match your exporter
3. **Label names**: Ensure label names (e.g., `hardware_type`) exist

### Import Fails

1. **Grafana version**: Ensure Grafana 9.x or 10.x
2. **JSON validity**: Validate JSON syntax
3. **Permissions**: Check user has dashboard import permissions

## File Structure

```
grafana-rustchain/
├── rustchain-network-dashboard.json    # Importable dashboard
└── README.md                           # This file
```

## Related Files

- `../../monitoring/rustchain-exporter.py` - Prometheus metrics exporter
- `../../monitoring/prometheus.yml` - Prometheus configuration
- `../../monitoring/docker-compose.yml` - Full monitoring stack

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-11 | Initial dashboard for issue #1609 |

## License

MIT License - Same as RustChain

## Contributing

Contributions welcome! Please ensure any dashboard changes:
1. Include updated panel descriptions
2. Test with live Prometheus data
3. Document new metrics requirements

---

**Issue**: [#1609](https://github.com/Scottcjn/Rustchain/issues/1609)
**Author**: xiaoma
**RTC Wallet**: `xiaoma-miner`
