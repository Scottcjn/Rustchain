# Operational Runbook - Bounty #765

This runbook provides operational procedures for the RustChain Prometheus Exporter.

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Deployment](#deployment)
3. [Monitoring](#monitoring)
4. [Troubleshooting](#troubleshooting)
5. [Alert Response](#alert-response)
6. [Maintenance](#maintenance)

---

## Quick Reference

| Task | Command |
|------|---------|
| Start exporter | `python rustchain_exporter.py` |
| Check health | `curl http://localhost:9100/health` |
| View metrics | `curl http://localhost:9100/metrics` |
| Docker start | `docker-compose up -d` |
| Docker logs | `docker logs rustchain-exporter` |
| Restart service | `docker-compose restart` |

---

## Deployment

### Prerequisites

- Python 3.10+ or Docker 20.10+
- Network access to RustChain node
- 100MB disk space
- 256MB RAM

### Production Deployment Checklist

- [ ] Set `RUSTCHAIN_NODE` to production node URL
- [ ] Enable TLS verification (`TLS_VERIFY=true`)
- [ ] Configure admin key if needed (`RUSTCHAIN_ADMIN_KEY`)
- [ ] Set up alerting in Prometheus
- [ ] Configure log rotation
- [ ] Set resource limits (CPU/memory)
- [ ] Enable health checks
- [ ] Document runbook location

### Docker Deployment

```bash
# Create .env file
cat > .env << EOF
RUSTCHAIN_NODE=https://rustchain.org
EXPORTER_PORT=9100
SCRAPE_INTERVAL=30
TLS_VERIFY=true
EOF

# Start services
docker-compose up -d

# Verify deployment
docker-compose ps
curl http://localhost:9100/health
```

### Kubernetes Deployment (Example)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rustchain-exporter
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rustchain-exporter
  template:
    spec:
      containers:
      - name: exporter
        image: rustchain-exporter:latest
        env:
        - name: RUSTCHAIN_NODE
          value: "https://rustchain.org"
        ports:
        - containerPort: 9100
        livenessProbe:
          httpGet:
            path: /health
            port: 9100
          initialDelaySeconds: 10
          periodSeconds: 30
        resources:
          limits:
            memory: "256Mi"
            cpu: "500m"
```

---

## Monitoring

### Key Metrics to Watch

| Metric | Warning | Critical |
|--------|---------|----------|
| `rustchain_node_health` | - | = 0 for 2m |
| `rustchain_scrape_duration_seconds` | > 5s | > 30s |
| `rustchain_scrape_errors_total` | rate > 0.1/s | rate > 1/s |
| `rustchain_active_miners` | -20% vs 1h avg | = 0 for 10m |
| `rustchain_tip_age_slots` | > 10 | > 100 |

### Prometheus Queries

```promql
# Node health over time
rustchain_node_health

# Scrape error rate
rate(rustchain_scrape_errors_total[5m])

# Active miners trend
rustchain_active_miners

# 95th percentile scrape duration
histogram_quantile(0.95, rustchain_scrape_duration_seconds)

# Miner drop detection
(rustchain_active_miners - avg_over_time(rustchain_active_miners[1h])) 
/ avg_over_time(rustchain_active_miners[1h])
```

### Grafana Dashboard Panels

Recommended panels:

1. **Node Health** - Single stat with color coding
2. **Active Miners** - Time series graph
3. **Hardware Distribution** - Pie chart
4. **Scrape Duration** - Time series with threshold line
5. **Epoch Progress** - Graph of epoch number over time

---

## Troubleshooting

### Exporter Won't Start

**Symptoms**: Container exits immediately or process fails

**Diagnosis**:
```bash
# Check logs
docker logs rustchain-exporter

# Test Python directly
python rustchain_exporter.py --verbose
```

**Common Causes**:
- Port already in use: `lsof -i :9100`
- Missing dependencies: `pip install -r requirements.txt`
- Invalid configuration: Check environment variables

**Resolution**:
```bash
# Free up port
kill $(lsof -t -i :9100)

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Validate config
python -c "from rustchain_exporter import ExporterConfig; print(ExporterConfig())"
```

### No Metrics in Prometheus

**Symptoms**: Prometheus shows target as DOWN or no data

**Diagnosis**:
```bash
# Check if exporter is responding
curl -v http://localhost:9100/metrics

# Check Prometheus target status
# Visit: http://prometheus:9090/targets

# Check network connectivity
docker exec prometheus wget -q -O - rustchain-exporter:9100/metrics | head
```

**Common Causes**:
- Wrong target address in prometheus.yml
- Network isolation between containers
- Exporter not bound to 0.0.0.0

**Resolution**:
```bash
# Verify prometheus.yml
docker exec prometheus cat /etc/prometheus/prometheus.yml

# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload

# Check exporter binding
docker exec rustchain-exporter netstat -tlnp | grep 9100
```

### High Scrape Duration

**Symptoms**: `rustchain_scrape_duration_seconds` > 5s

**Diagnosis**:
```bash
# Check node response time
time curl -s http://rustchain-node:8080/api/miners | wc -c

# Check exporter CPU usage
docker stats rustchain-exporter --no-stream

# Check network latency
ping -c 3 rustchain-node
```

**Common Causes**:
- Node API is slow
- Large number of miners (>1000)
- Network latency
- Resource constraints

**Resolution**:
```bash
# Increase scrape interval
export SCRAPE_INTERVAL=60

# Add request timeout
export REQUEST_TIMEOUT=30

# Scale exporter resources
docker update --memory=512m rustchain-exporter
```

### TLS/Certificate Errors

**Symptoms**: SSL certificate verification failed

**Diagnosis**:
```bash
# Test TLS connection
curl -v https://rustchain.org/health

# Check certificate
openssl s_client -connect rustchain.org:443 -servername rustchain.org
```

**Resolution**:
```bash
# Option 1: Use proper CA (recommended)
export TLS_VERIFY=true
export TLS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Option 2: Disable verification (development only!)
export TLS_VERIFY=false

# Option 3: Custom CA bundle
export TLS_CA_BUNDLE=/path/to/custom-ca.crt
```

### Memory Leaks

**Symptoms**: Gradual memory increase over time

**Diagnosis**:
```bash
# Monitor memory usage
watch -n 5 'docker stats rustchain-exporter --no-stream'

# Check for growing data structures
# Add debug logging to MetricsRegistry
```

**Resolution**:
```bash
# Restart exporter (temporary)
docker-compose restart

# Check for known issues in GitHub
# Update to latest version if available

# Set memory limits
docker update --memory=256m --memory-swap=256m rustchain-exporter
```

---

## Alert Response

### RustChainNodeDown

**Severity**: Critical  
**Trigger**: `rustchain_node_health == 0` for 2m

**Response**:
1. Check node status directly: `curl https://rustchain.org/health`
2. Check exporter logs: `docker logs rustchain-exporter`
3. Verify network connectivity: `ping rustchain.org`
4. If node is down, notify infrastructure team
5. If exporter issue, restart exporter

### RustChainNoActiveMiners

**Severity**: Critical  
**Trigger**: `rustchain_active_miners == 0` for 10m

**Response**:
1. Verify with direct API call: `curl https://rustchain.org/api/miners`
2. Check if this is expected (maintenance window?)
3. Review recent changes to mining software
4. Check for network partition
5. Escalate to mining team if confirmed

### RustChainEpochStuck

**Severity**: Critical  
**Trigger**: No epoch change for 2h

**Response**:
1. Check current epoch: `curl https://rustchain.org/epoch`
2. Compare with other nodes (if available)
3. Check node logs for errors
4. Verify block production is working
5. May indicate consensus issue - escalate immediately

### RustChainSlowScrape

**Severity**: Warning  
**Trigger**: `rustchain_scrape_duration_seconds > 5` for 5m

**Response**:
1. Check node API response times
2. Review miner count (large fleet = slower)
3. Check exporter resource usage
4. Consider increasing scrape interval
5. If persistent, investigate node performance

### RustChainBackupOld

**Severity**: Warning  
**Trigger**: `rustchain_backup_age_hours > 24` for 1h

**Response**:
1. Check backup job status
2. Verify backup storage availability
3. Review backup logs
4. Manually trigger backup if needed
5. Update backup schedule if intentional

---

## Maintenance

### Regular Maintenance Tasks

| Task | Frequency | Command |
|------|-----------|---------|
| Check logs | Daily | `docker logs --tail 100 rustchain-exporter` |
| Verify metrics | Daily | `curl http://localhost:9100/metrics \| grep -c "^rustchain"` |
| Update image | Monthly | `docker-compose pull && docker-compose up -d` |
| Review alerts | Monthly | Check alert firing history in Alertmanager |
| Rotate logs | Weekly | Configure logrotate or use Docker log options |

### Log Rotation

```yaml
# docker-compose.yml
services:
  rustchain-exporter:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Backup Configuration

```bash
# Backup Prometheus data
docker cp rustchain-prometheus:/prometheus ./prometheus-backup-$(date +%Y%m%d)

# Backup Grafana dashboards
curl -u admin:rustchain http://localhost:3000/api/dashboards/export > grafana-backup.json

# Backup configuration files
tar -czf rustchain-monitoring-config-$(date +%Y%m%d).tar.gz \
    prometheus.yml rustchain_alerts.yml docker-compose.yml
```

### Version Upgrade

```bash
# 1. Review changelog
# 2. Backup current state
docker-compose down

# 3. Pull new image
docker-compose pull

# 4. Start with new version
docker-compose up -d

# 5. Verify health
curl http://localhost:9100/health

# 6. Check metrics
curl http://localhost:9100/metrics | head -20
```

### Disaster Recovery

**Complete System Failure**:

1. Restore from backup:
```bash
docker-compose up -d prometheus
docker cp prometheus-backup/ rustchain-prometheus:/prometheus
docker-compose up -d
```

2. Verify data integrity:
```bash
# Check Prometheus TSDB
docker exec rustchain-prometheus ls /prometheus

# Query last known data
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=rustchain_epoch_number'
```

---

## Contact

- **GitHub Issues**: https://github.com/Scottcjcn/RustChain/issues
- **Documentation**: https://github.com/Scottcjcn/RustChain/tree/main/bounties/issue-765/docs
- **Alert Runbook**: This document

---

*Last Updated: 2026-03-09*  
*Version: 1.0.0*
