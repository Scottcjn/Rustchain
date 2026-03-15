# ──────────────────────────────────────────────────────────────
# RustChain Node Module
# Provisions a single VPS on DigitalOcean or AWS
# ──────────────────────────────────────────────────────────────

terraform {
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

locals {
  node_name = "rustchain-node-${var.node_index}"
}

# ── DigitalOcean ────────────────────────────────────────────

resource "digitalocean_ssh_key" "rustchain" {
  count      = var.cloud_provider == "digitalocean" ? 1 : 0
  name       = "${local.node_name}-key"
  public_key = var.ssh_public_key
}

resource "digitalocean_droplet" "node" {
  count     = var.cloud_provider == "digitalocean" ? 1 : 0
  name      = local.node_name
  region    = var.do_region
  size      = var.do_droplet_size
  image     = "ubuntu-22-04-x64"
  ssh_keys  = [digitalocean_ssh_key.rustchain[0].fingerprint]
  user_data = var.cloud_init_script

  tags = ["rustchain", var.environment]
}

# ── AWS ─────────────────────────────────────────────────────

data "aws_ami" "ubuntu" {
  count       = var.cloud_provider == "aws" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "rustchain" {
  count       = var.cloud_provider == "aws" ? 1 : 0
  name        = "${local.node_name}-sg"
  description = "RustChain node security group"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "RustChain Dashboard"
    from_port   = 8099
    to_port     = 8099
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "RustChain API"
    from_port   = 8088
    to_port     = 8088
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Grafana"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Prometheus"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = local.node_name
    Environment = var.environment
  }
}

resource "aws_key_pair" "rustchain" {
  count      = var.cloud_provider == "aws" && var.aws_key_pair_name == "" ? 1 : 0
  key_name   = "${local.node_name}-key"
  public_key = var.ssh_public_key
}

resource "aws_instance" "node" {
  count                  = var.cloud_provider == "aws" ? 1 : 0
  ami                    = data.aws_ami.ubuntu[0].id
  instance_type          = var.aws_instance_type
  key_name               = var.aws_key_pair_name != "" ? var.aws_key_pair_name : aws_key_pair.rustchain[0].key_name
  vpc_security_group_ids = [aws_security_group.rustchain[0].id]
  user_data              = var.cloud_init_script

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
  }

  tags = {
    Name        = local.node_name
    Environment = var.environment
    Project     = "rustchain"
  }
}
