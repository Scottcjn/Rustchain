# ──────────────────────────────────────────────────────────────
# RustChain Infrastructure — Input Variables
# ──────────────────────────────────────────────────────────────

# ── Provider Selection ──────────────────────────────────────

variable "cloud_provider" {
  description = "Cloud provider to deploy on: digitalocean or aws"
  type        = string
  default     = "digitalocean"

  validation {
    condition     = contains(["digitalocean", "aws"], var.cloud_provider)
    error_message = "cloud_provider must be 'digitalocean' or 'aws'."
  }
}

# ── DigitalOcean ────────────────────────────────────────────

variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  default     = ""
  sensitive   = true
}

variable "do_region" {
  description = "DigitalOcean region slug"
  type        = string
  default     = "nyc3"
}

variable "do_droplet_size" {
  description = "DigitalOcean droplet size slug"
  type        = string
  default     = "s-2vcpu-4gb"
}

# ── AWS ─────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_instance_type" {
  description = "AWS EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "aws_key_pair_name" {
  description = "Existing AWS key pair name for SSH access"
  type        = string
  default     = ""
}

# ── Common ──────────────────────────────────────────────────

variable "ssh_public_key" {
  description = "SSH public key for node access"
  type        = string
}

variable "node_count" {
  description = "Number of RustChain nodes to deploy"
  type        = number
  default     = 1

  validation {
    condition     = var.node_count >= 1 && var.node_count <= 10
    error_message = "node_count must be between 1 and 10."
  }
}

variable "enable_monitoring" {
  description = "Deploy Prometheus + Grafana monitoring stack"
  type        = bool
  default     = true
}

variable "domain_name" {
  description = "Domain name pointed at the node (optional, for TLS)"
  type        = string
  default     = ""
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  default     = "rustchain"
  sensitive   = true
}

variable "environment" {
  description = "Deployment environment tag (dev, staging, prod)"
  type        = string
  default     = "prod"
}
