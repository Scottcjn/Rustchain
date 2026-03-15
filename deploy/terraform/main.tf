# ──────────────────────────────────────────────────────────────
# RustChain Infrastructure — Root Module
# Deploys RustChain nodes with optional monitoring on
# DigitalOcean or AWS.
# ──────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── Providers ───────────────────────────────────────────────

provider "digitalocean" {
  token = var.do_token
}

provider "aws" {
  region = var.aws_region
}

# ── Monitoring (generates cloud-init fragments) ────────────

module "monitoring" {
  count  = var.enable_monitoring ? 1 : 0
  source = "./modules/monitoring"

  node_ips               = [for i in range(var.node_count) : "localhost"]
  grafana_admin_password = var.grafana_admin_password
}

# ── Cloud-Init Rendering ───────────────────────────────────

locals {
  monitoring_block = var.enable_monitoring ? module.monitoring[0].cloud_init_monitoring_block : "echo 'Monitoring disabled.'"
  monitoring_fw    = var.enable_monitoring ? module.monitoring[0].cloud_init_firewall_rules : ""

  tls_block = var.domain_name != "" ? <<-BASH
echo "[$(date -u)] Obtaining TLS certificate for ${var.domain_name}..."
certbot certonly --standalone --non-interactive --agree-tos \
  --register-unsafely-without-email \
  -d ${var.domain_name}
BASH
  : "echo 'No domain configured; skipping TLS.'"

  cloud_init_rendered = templatefile("${path.module}/cloud-init.sh", {
    MONITORING_BLOCK          = local.monitoring_block
    MONITORING_FIREWALL_RULES = local.monitoring_fw
    TLS_BLOCK                 = local.tls_block
  })
}

# ── Node Instances ──────────────────────────────────────────

module "node" {
  count  = var.node_count
  source = "./modules/node"

  cloud_provider    = var.cloud_provider
  node_index        = count.index
  ssh_public_key    = var.ssh_public_key
  cloud_init_script = local.cloud_init_rendered
  environment       = var.environment

  # DigitalOcean
  do_region       = var.do_region
  do_droplet_size = var.do_droplet_size

  # AWS
  aws_region        = var.aws_region
  aws_instance_type = var.aws_instance_type
  aws_key_pair_name = var.aws_key_pair_name
}
