# RustChain Terraform Deployment

Terraform modules for provisioning RustChain Proof-of-Antiquity blockchain infrastructure on DigitalOcean or AWS.

## Architecture

```
deploy/terraform/
  main.tf              Root module — wires providers, modules, and cloud-init
  variables.tf         All configurable inputs
  outputs.tf           Node IPs, dashboard URLs, monitoring endpoints
  cloud-init.sh        Bootstrap script (templated by Terraform)
  modules/
    node/              VPS provisioning (DO droplet / AWS EC2)
    monitoring/        Prometheus + Grafana stack generation
```

## Prerequisites

- Terraform >= 1.5
- A DigitalOcean API token **or** AWS credentials configured
- An SSH public key

## Quick Start

### DigitalOcean

```bash
cd deploy/terraform

terraform init

terraform apply \
  -var 'cloud_provider=digitalocean' \
  -var 'do_token=dop_v1_xxx' \
  -var 'ssh_public_key=ssh-ed25519 AAAA...'
```

### AWS

```bash
cd deploy/terraform

export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

terraform init

terraform apply \
  -var 'cloud_provider=aws' \
  -var 'ssh_public_key=ssh-ed25519 AAAA...'
```

## Variables

| Name | Default | Description |
|------|---------|-------------|
| `cloud_provider` | `digitalocean` | `digitalocean` or `aws` |
| `do_token` | — | DigitalOcean API token |
| `do_region` | `nyc3` | DO region |
| `do_droplet_size` | `s-2vcpu-4gb` | DO droplet size |
| `aws_region` | `us-east-1` | AWS region |
| `aws_instance_type` | `t3.medium` | EC2 instance type |
| `aws_key_pair_name` | — | Existing AWS key pair (optional) |
| `ssh_public_key` | — | SSH public key for access |
| `node_count` | `1` | Number of nodes (1-10) |
| `enable_monitoring` | `true` | Deploy Prometheus + Grafana |
| `domain_name` | — | Domain for TLS (optional) |
| `grafana_admin_password` | `rustchain` | Grafana admin password |
| `environment` | `prod` | Environment tag |

## Outputs

| Output | Description |
|--------|-------------|
| `node_ips` | Public IPs of all deployed nodes |
| `dashboard_urls` | RustChain dashboard URLs |
| `grafana_url` | Grafana dashboard URL |
| `prometheus_url` | Prometheus URL |
| `api_endpoints` | RustChain API endpoints |
| `ssh_commands` | Ready-to-use SSH commands |

## What Gets Deployed

Each node receives via cloud-init:

1. **RustChain node** — cloned from GitHub, built and run with Docker Compose
2. **Nginx reverse proxy** — fronts the node on ports 80/443
3. **Firewall** — UFW with only required ports open
4. **Fail2Ban** — SSH brute-force protection
5. **Systemd watchdog** — auto-restarts containers every 5 minutes if down
6. **Prometheus + Grafana** (optional) — scrapes node metrics on the primary node
7. **TLS** (optional) — auto-provisions Let's Encrypt certificate if `domain_name` is set

## Multi-Node

```bash
terraform apply \
  -var 'node_count=3' \
  -var 'cloud_provider=digitalocean' \
  -var 'do_token=dop_v1_xxx' \
  -var 'ssh_public_key=ssh-ed25519 AAAA...'
```

## Tear Down

```bash
terraform destroy
```
