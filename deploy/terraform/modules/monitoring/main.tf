# ──────────────────────────────────────────────────────────────
# RustChain Monitoring Module
# Generates Prometheus + Grafana configuration rendered into
# the cloud-init script of the primary node.
# ──────────────────────────────────────────────────────────────

locals {
  # Build Prometheus scrape targets from all node IPs
  scrape_targets = join(", ", [for ip in var.node_ips : "'${ip}:9100'"])

  prometheus_config = <<-YAML
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: 'rustchain-exporter'
    static_configs:
      - targets: [${local.scrape_targets}]

  - job_name: 'rustchain-nodes'
    static_configs:
      - targets: [${join(", ", [for ip in var.node_ips : "'${ip}:8099'"])}]
    metrics_path: /health
YAML

  monitoring_compose = <<-YAML
version: '3.8'

services:
  rustchain-exporter:
    build:
      context: ./monitoring
      dockerfile: Dockerfile.exporter
    container_name: rustchain-exporter
    restart: unless-stopped
    environment:
      - RUSTCHAIN_NODE=http://localhost:8099
      - EXPORTER_PORT=9100
      - SCRAPE_INTERVAL=30
    ports:
      - "9100:9100"
    network_mode: host

  prometheus:
    image: prom/prometheus:latest
    container_name: rustchain-prometheus
    restart: unless-stopped
    volumes:
      - /opt/rustchain/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'

  grafana:
    image: grafana/grafana:latest
    container_name: rustchain-grafana
    restart: unless-stopped
    volumes:
      - grafana-data:/var/lib/grafana
      - /opt/rustchain/monitoring/grafana-dashboard.json:/etc/grafana/provisioning/dashboards/rustchain.json:ro
      - /opt/rustchain/monitoring/grafana-datasource.yml:/etc/grafana/provisioning/datasources/prometheus.yml:ro
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${var.grafana_admin_password}

volumes:
  prometheus-data:
  grafana-data:
YAML

  # Firewall rules to open monitoring ports
  firewall_rules = <<-BASH
ufw allow 9090/tcp   # Prometheus
ufw allow 9100/tcp   # Node exporter
ufw allow 3000/tcp   # Grafana
BASH

  # Shell block for cloud-init to start monitoring stack
  cloud_init_block = <<-BASH
echo "[$(date -u)] Starting monitoring stack..."
cd /opt/rustchain

# Write generated Prometheus config
cat > monitoring/prometheus.yml <<'PROMCFG'
${local.prometheus_config}
PROMCFG

# Start monitoring containers
cd monitoring
docker-compose up -d --build
echo "[$(date -u)] Monitoring stack running."
BASH
}

output "cloud_init_monitoring_block" {
  description = "Shell commands to insert into cloud-init for monitoring setup"
  value       = local.cloud_init_block
}

output "cloud_init_firewall_rules" {
  description = "UFW rules for monitoring ports"
  value       = local.firewall_rules
}
