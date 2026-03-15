# RustChain Ansible Deployment

Automated deployment playbooks for RustChain nodes and monitoring infrastructure.

## Structure

```
deploy/ansible/
  inventory.yml              # Target hosts
  playbook.yml               # Main entry point
  roles/
    rustchain-node/           # Node deployment
      tasks/main.yml          # Install deps, create user, deploy code, configure services
      handlers/main.yml       # Service restart/reload handlers
      defaults/main.yml       # Default variables
      templates/
        rustchain-node.service.j2    # systemd unit for gunicorn
        nginx-rustchain.conf.j2     # Reverse proxy with optional SSL
    rustchain-monitor/        # Prometheus + Grafana stack
      tasks/main.yml          # Install Prometheus, exporter, Grafana
      handlers/main.yml       # Service restart handlers
      defaults/main.yml       # Default variables
      templates/
        prometheus.yml.j2              # Scrape config
        prometheus.service.j2          # systemd unit
        rustchain-exporter.service.j2  # Exporter systemd unit
        grafana-datasource.yml.j2      # Auto-provision datasource
```

## Requirements

- Ansible 2.14+
- Target hosts running Ubuntu 22.04+ / Debian 12+
- SSH access with sudo privileges

## Quick Start

1. Copy and edit the inventory:

```bash
cp inventory.yml inventory.local.yml
# Edit hosts, IPs, and domain settings
```

2. Run the full playbook:

```bash
ansible-playbook -i inventory.local.yml playbook.yml
```

3. Deploy only nodes or only monitoring:

```bash
ansible-playbook -i inventory.local.yml playbook.yml --tags node
ansible-playbook -i inventory.local.yml playbook.yml --tags monitor
```

## Configuration

### Node Variables

| Variable | Default | Description |
|---|---|---|
| `rustchain_bind_port` | `8099` | Gunicorn listen port |
| `rustchain_workers` | `4` | Gunicorn worker count |
| `rustchain_enable_ssl` | `false` | Enable HTTPS via nginx |
| `rustchain_domain` | `localhost` | Server name for nginx |
| `rustchain_version` | `main` | Git branch/tag to deploy |

### Monitoring Variables

| Variable | Default | Description |
|---|---|---|
| `grafana_admin_password` | `changeme` | Grafana admin password |
| `prometheus_retention_days` | `30` | Metrics retention period |
| `rustchain_node_url` | `https://rustchain.org` | Node URL for the exporter |

### SSL Setup

Set `rustchain_enable_ssl: true` and provide certificate paths:

```yaml
rustchain_enable_ssl: true
rustchain_ssl_cert: /etc/letsencrypt/live/rustchain.example.com/fullchain.pem
rustchain_ssl_key: /etc/letsencrypt/live/rustchain.example.com/privkey.pem
```

## Services Deployed

**Node host:**
- `rustchain-node.service` — Gunicorn running the Flask app
- `nginx` — Reverse proxy with security headers

**Monitor host:**
- `prometheus.service` — Metrics collection
- `rustchain-exporter.service` — Scrapes RustChain API for Prometheus
- `grafana-server` — Dashboard UI (port 3000)

## Post-Deploy Verification

```bash
# Check node health
curl http://node-01/health

# Prometheus targets
curl http://monitor-01:9090/api/v1/targets

# Grafana
open http://monitor-01:3000  # admin / <grafana_admin_password>
```
