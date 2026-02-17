# RustChain Monitoring with Grafana & Prometheus

Complete monitoring solution for RustChain with Grafana dashboard and Prometheus alerts.

## 📊 Overview

This repository contains monitoring configurations for RustChain:

- **Grafana Dashboard** - Visual monitoring of network metrics
- **Prometheus Alerts** - Automated alerting for critical issues
- **Documentation** - Deployment and configuration guides

## 🚀 Quick Start

### Prerequisites

- RustChain node with Prometheus metrics enabled
- Grafana 8.0+ or later
- Prometheus server
- (Optional) Alertmanager for alert routing

### 1. Import Grafana Dashboard

#### Option A: Import from JSON

1. Open Grafana: `http://your-grafana:3000`
2. Go to **Dashboards** → **Import**
3. Upload `grafana/rustchain-dashboard.json`
4. Configure Prometheus datasource
5. Click **Import**

#### Option B: Import from URL

1. Copy dashboard JSON to Grafana-hosted URL
2. Import via URL in Grafana

### 2. Configure Prometheus Alerts

1. Copy `grafana/alerts.yml` to Prometheus config directory
2. Add to `prometheus.yml`:

```yaml
rule_files:
  - "alerts.yml"
```

3. Reload Prometheus:

```bash
kill -HUP $(cat /var/run/prometheus.pid)
```

4. Verify alerts loaded:

```bash
curl http://localhost:9090/api/v1/rules
```

## 📈 Dashboard Metrics

The dashboard includes 12 panels organized into 5 sections:

### Network Overview (Top Row)
- **Active Miners** - Current count with color coding
  - Green: > 100 miners
  - Yellow: 50-100 miners
  - Red: < 50 miners
- **Total Attestations** - Lifetime attestation count
- **Current Epoch** - Current epoch number

### Miner Metrics (Middle Row)
- **Miners Over Time** - Timeseries chart of active miners
- **Attestations Rate (Last 5m)** - Recent attestation rate (ops/sec)

### Token Metrics
- **RTC Balance (Total)** - Network-wide RTC balance with thresholds
- **RTC Transfers Volume** - Transfer volume per hour
- **Epoch Rewards Distributed** - Rewards per epoch

### Health Metrics
- **Node Health** - Overall health score (0-1)
- **API Response Time (p95)** - 95th percentile response time
- **API Request Rate** - Requests per second

### Hardware Distribution
- **Hardware Types** - Pie chart of hardware architecture distribution
  - PowerPC, 68K, SPARC, x86, etc.

## 🚨 Alert Rules

### Severity Levels

**Critical** - Immediate attention required:
- Node down
- Miner count < 10
- API latency > 10s
- Disk space < 10%
- Memory usage > 90%
- CPU usage > 90%

**Warning** - Investigation recommended:
- Node health < 80%
- Miner count < 50
- Sudden miner drop > 50%
- Attestation rate low
- API latency > 5s
- API error rate > 10%
- Disk space < 20%
- Memory usage > 80%
- CPU usage > 80%

### Alert Categories

#### 1. Node Health Alerts
- **NodeDown** - Node completely down
- **NodeDegraded** - Node health below 80%

#### 2. Miner Alerts
- **MinerCountCritical** - < 10 active miners
- **MinerCountLow** - < 50 active miners
- **MinerDropSudden** - > 50% drop in 5 minutes

#### 3. Attestation Alerts
- **AttestationRateZero** - Rate near zero
- **AttestationRateLow** - Rate < 0.1 ops/sec
- **AttestationDropSudden** - > 70% drop in rate

#### 4. API Performance Alerts
- **APILatencyCritical** - p95 > 10s
- **APILatencyWarning** - p95 > 5s
- **APIErrorRateHigh** - Error rate > 10%

#### 5. Token/Balance Alerts
- **BalanceLow** - Total balance < 1,000 RTC
- **TransferVolumeUnusual** - Volume deviation > 200% from 24h avg

#### 6. System Resource Alerts
- **DiskSpaceCritical** - < 10% disk available
- **DiskSpaceWarning** - < 20% disk available
- **MemoryUsageCritical** - > 90% memory usage
- **MemoryUsageWarning** - > 80% memory usage
- **CPUUsageCritical** - > 90% CPU usage
- **CPUUsageWarning** - > 80% CPU usage

## 🔧 Configuration

### Prometheus Configuration

**prometheus.yml**:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "grafana/alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - api_url: http://alertmanager:9093

scrape_configs:
  - job_name: 'rustchain'
    static_configs:
      - targets: ['localhost:8099']
    metrics_path: '/metrics'
```

### Grafana Datasource

**Grafana → Configuration → Datasources**:

```json
{
  "name": "RustChain-Prometheus",
  "type": "prometheus",
  "url": "http://prometheus:9090",
  "access": "proxy",
  "isDefault": true
}
```

### Alertmanager Configuration

**alertmanager.yml**:

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@rustchain.org'
        from: 'alertmanager@rustchain.org'
        smarthost: 'localhost'
        auth_username: 'your-username'
        auth_password: 'your-password'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK'
        channel: '#rustchain-alerts'
```

## 🐳 Docker Deployment

### Docker Compose (All-in-One)

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: rustchain-prometheus
    volumes:
      - ./grafana/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./grafana/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: rustchain-grafana
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/rustchain-dashboard.json:/etc/grafana/provisioning/dashboards/rustchain.json:ro
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    ports:
      - "3000:3000"
    depends_on:
      - prometheus:
        condition: service_healthy
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: rustchain-alertmanager
    volumes:
      - ./grafana/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager-data:/alertmanager
    ports:
      - "9093:9093"
    restart: unless-stopped
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'

volumes:
  prometheus-data:
  alertmanager-data:
  grafana-data:
```

### Start the Stack

```bash
cd grafana
docker-compose up -d

# Access Grafana
open http://localhost:3000

# Default credentials
# Username: admin
# Password: admin (change on first login)
```

## 🔒 Security Best Practices

### 1. Change Default Credentials

Change default Grafana credentials immediately:

```bash
# Method 1: Environment variables
export GF_SECURITY_ADMIN_PASSWORD=your_secure_password

# Method 2: Grafana UI
1. Login to Grafana
2. Go to Configuration → Users
3. Change admin password
```

### 2. Restrict Access

**Grafana Anonymous Access:**

```bash
# Disable anonymous access
export GF_ANONYMOUS_ENABLED=false

# Or in grafana.ini
[auth.anonymous]
enabled = false
```

**Prometheus Metrics Access:**

```nginx
# In nginx config
location /metrics {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

### 3. Use HTTPS

Expose Grafana and Prometheus via HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name monitoring.rustchain.org;

    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    location /grafana {
        proxy_pass http://localhost:3000;
    }

    location /prometheus {
        proxy_pass http://localhost:9090;
    }
}
```

### 4. Rate Limiting

Protect against abuse:

```bash
# In Prometheus
--web.max-connections-limit=256
--web.read-timeout=5m
```

## 📊 Dashboard Customization

### Adding New Panels

1. Edit dashboard in Grafana UI
2. Add new panel
3. Configure query
4. Save dashboard

### Modifying Alerts

Edit `grafana/alerts.yml`:

```yaml
- alert: CustomAlert
  expr: your_metric > threshold
  for: 5m
  labels:
    severity: warning
    component: custom
  annotations:
    summary: "Custom alert description"
```

### Panel Types Available

- **Time Series** - Line graphs for trends
- **Stat** - Single value displays
- **Pie Chart** - Distribution visualization
- **Heatmap** - Multi-dimensional data (future)
- **Gauge** - Progress indicators (future)

## 🔍 Troubleshooting

### Dashboard Not Showing Data

1. Check Prometheus datasource in Grafana
2. Verify Prometheus is scraping RustChain node:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```
3. Check `/metrics` endpoint on RustChain node:
   ```bash
   curl http://localhost:8099/metrics
   ```

### Alerts Not Firing

1. Check alert rules loaded:
   ```bash
   curl http://localhost:9090/api/v1/rules
   ```
2. Check alert history:
   ```bash
   curl http://localhost:9090/api/v1/alerts
   ```
3. Verify alert evaluation:
   ```bash
   curl http://localhost:9090/api/v1/alerts?eval=1
   ```

### High Resource Usage

1. Reduce scrape interval
2. Increase retention time (if disk space permits)
3. Add recording rules to store only needed metrics

## 📱 Mobile Access

Grafana is mobile-responsive. Access from mobile:

```
http://your-domain:3000
```

Kiosk mode for dedicated displays:

```
http://your-domain:3000/?kiosk
```

## 🔄 Updates

### Updating Dashboard

1. Edit `grafana/rustchain-dashboard.json`
2. Re-import to Grafana (or edit in UI)
3. Save new version

### Updating Alerts

1. Edit `grafana/alerts.yml`
2. Reload Prometheus:
   ```bash
   kill -HUP $(cat /var/run/prometheus.pid)
   ```
3. Verify new rules active

## 📦 Backup and Restore

### Export Dashboard

Grafana UI → Dashboard → Share → Export → Save to JSON

### Backup Alert Rules

```bash
cp grafana/alerts.yml grafana/alerts.backup.yml
```

### Restore from Backup

```bash
# Restore alerts
cp grafana/alerts.backup.yml grafana/alerts.yml

# Reload Prometheus
kill -HUP $(cat /var/run/prometheus.pid)
```

## 🧪 Testing

### Test Alerts

Force alert firing:

```bash
# Test node down alert
# Stop RustChain node temporarily
sudo systemctl stop rustchain

# Wait 1 minute, check Grafana for alert

# Restart node
sudo systemctl start rustchain
```

### Load Testing

Test dashboard under load:

```bash
# Generate load on RustChain node
for i in {1..100}; do
  curl -s http://localhost:8099/api/stats > /dev/null &
done

# Check dashboard handles requests
open http://localhost:3000
```

## 📞 Support

For issues and questions:
- GitHub Issues: https://github.com/Scottcjn/Rustchain/issues
- Discord: [RustChain Discord Server]
- Documentation: https://docs.rustchain.org

## 📚 Additional Resources

### Prometheus Documentation
- [Prometheus Docs](https://prometheus.io/docs/)
- [Alerting Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/)

### Grafana Documentation
- [Grafana Docs](https://grafana.com/docs/)
- [Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/json-model/)
- [Variable Syntax](https://grafana.com/docs/grafana/latest/variables/)

### Best Practices
- [Alerting Best Practices](https://prometheus.io/docs/practices/alerting/)
- [Dashboard Design](https://grafana.com/tutorials/)
- [Metrics Naming](https://prometheus.io/docs/practices/naming/)

## 📄 License

Same as RustChain project.
