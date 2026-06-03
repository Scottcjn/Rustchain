# RustChain Node Operator Guide

> Complete step-by-step guide for running RustChain attestation nodes and miners.

**Part of the [Documentation Sprint #72](https://github.com/Scottcjn/rustchain-bounties/issues/72)**

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Wallet Setup](#4-wallet-setup)
5. [Starting the Node](#5-starting-the-node)
6. [Starting a Miner](#6-starting-a-miner)
7. [Monitoring & Health Checks](#7-monitoring--health-checks)
8. [Troubleshooting](#8-troubleshooting)
9. [Performance Tuning](#9-performance-tuning)
10. [Advanced Topics](#10-advanced-topics)

---

## 1. System Requirements

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | x86_64, 2 cores | 4+ cores |
| **RAM** | 2 GB | 4 GB+ |
| **Storage** | 10 GB SSD | 50 GB NVMe |
| **Network** | 10 Mbps | 100 Mbps+ |
| **OS** | Linux, macOS, Windows | Linux (Ubuntu 20.04+) |

### Supported Architectures
- **x86_64** (Linux, macOS, Windows)
- **ARM64** (Raspberry Pi 4+, Apple Silicon)
- **PowerPC** (G4, G5) — native vintage mining
- **SPARC** — native vintage mining
- **68K** — native vintage mining
- **15+ total architectures** supported

### Network Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 3000 | HTTPS | REST API & Attestation |
| 3001 | TCP | P2P peer communication |
| 80 | HTTP | Optional redirect to HTTPS |

---

## 2. Installation

### Option A: From Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Build
cargo build --release

# Binary will be at ./target/release/rustchain
```

### Option B: Pre-built Binary

```bash
# Download the latest release
# For Linux x86_64:
curl -L https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-linux-x86_64 -o rustchain
chmod +x rustchain

# For macOS (Apple Silicon):
curl -L https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-macos-aarch64 -o rustchain
chmod +x rustchain

# For Windows (x86_64):
# Download from GitHub Releases
```

### Option C: Docker

```bash
docker pull scottcjn/rustchain:latest

docker run -d \
  --name rustchain-node \
  -p 3000:3000 \
  -p 3001:3001 \
  -v $(pwd)/data:/data \
  -v $(pwd)/config:/config \
  scottcjn/rustchain:latest \
  --config /config/config.yaml
```

### Verify Installation

```bash
./rustchain --version
# Expected output: rustchain v2.2.1-rip200
```

---

## 3. Configuration

### Configuration File

Create `config.yaml`:

```yaml
# Node configuration
node:
  # Node type: "attestation" or "miner"
  type: attestation

  # HTTP API settings
  api:
    host: "0.0.0.0"
    port: 3000

  # P2P network settings
  p2p:
    port: 3001
    # Bootstrap nodes for initial peer discovery
    bootstrap_nodes:
      - "https://50.28.86.131"

  # Database path
  db_path: "./data/rustchain.db"

  # Logging
  logging:
    level: "info"  # debug, info, warn, error
    file: "./data/rustchain.log"

# Attestation settings (only for attestation nodes)
attestation:
  # Enable hardware fingerprinting
  fingerprinting_enabled: true

  # Accepted CPU architectures
  accepted_architectures:
    - ppc
    - sparc
    - m68k
    - x86
    - arm
    - mips
    - alpha

# Mining settings (only for miners)
mining:
  # Wallet address for receiving rewards
  wallet_address: "YOUR_WALLET_ADDRESS"

  # Attestation node URL
  attestation_node_url: "https://50.28.86.131"

  # Work cycle interval (seconds)
  cycle_interval: 3600
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RUSTCHAIN_CONFIG` | Path to config file | `./config.yaml` |
| `RUSTCHAIN_LOG_LEVEL` | Logging level | `info` |
| `RUSTCHAIN_DB_PATH` | Database path | `./data/rustchain.db` |
| `RUSTCHAIN_API_HOST` | API bind host | `0.0.0.0` |
| `RUSTCHAIN_API_PORT` | API port | `3000` |
| `RUSTCHAIN_ADMIN_KEY` | Admin API key | (required for admin endpoints) |

---

## 4. Wallet Setup

### Create a New Wallet

```bash
./rustchain wallet create
```

Output:
```
Wallet created successfully!
Address: rust1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Pubkey:  ed25519:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

⚠️  IMPORTANT: Save your private key securely. It cannot be recovered.
```

### Import an Existing Wallet

```bash
./rustchain wallet import <private-key>
```

### Check Wallet Balance

```bash
# Using the CLI
./rustchain wallet balance

# Using the API
curl -sk https://50.28.86.131/wallet/balance?address=rust1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Wallet Security Best Practices
- Store private key in a secure location (hardware wallet, encrypted file)
- Never share your private key
- Use a separate wallet for mining vs. personal holdings
- Regularly check balance via API

---

## 5. Starting the Node

### Start an Attestation Node

```bash
# Using config file
./rustchain --config config.yaml

# Using environment variables
RUSTCHAIN_CONFIG=config.yaml ./rustchain

# In background (Linux)
nohup ./rustchain --config config.yaml > rustchain.log 2>&1 &
```

### Verify Node is Running

```bash
# Health check
curl -sk https://localhost:3000/health
# Expected: {"status":"ok","epoch":1234,...}

# Ready check
curl -sk https://localhost:3000/ready
# Expected: {"ready":true}

# Network info
curl -sk https://localhost:3000/api/network
# Expected: {"peers":3,"epoch":1234,...}
```

### Start as Systemd Service (Linux)

Create `/etc/systemd/system/rustchain.service`:

```ini
[Unit]
Description=RustChain Attestation Node
After=network.target

[Service]
Type=simple
User=rustchain
Group=rustchain
WorkingDirectory=/opt/rustchain
ExecStart=/opt/rustchain/rustchain --config /opt/rustchain/config.yaml
Restart=on-failure
RestartSec=10

# Security
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/rustchain/data

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable rustchain
sudo systemctl start rustchain

# Check status
sudo systemctl status rustchain

# View logs
sudo journalctl -u rustchain -f
```

---

## 6. Starting a Miner

### Configure the Miner

Edit your `config.yaml`:

```yaml
node:
  type: miner

mining:
  wallet_address: "rust1your_wallet_address"
  attestation_node_url: "https://50.28.86.131"
  cycle_interval: 3600
```

### Start Mining

```bash
./rustchain --config config.yaml
```

### Console Mining Setup

For real-time mining output:

```bash
# Run with verbose logging
RUSTCHAIN_LOG_LEVEL=debug ./rustchain --config config.yaml

# Or use the mining console
./rustchain mine --console --config config.yaml
```

### Verify Mining Status

```bash
# Check if your miner appears in the active miners list
curl -sk https://50.28.86.131/api/miners
```

### Check Mining Earnings

```bash
# Check wallet balance
curl -sk "https://50.28.86.131/wallet/balance?address=rust1your_wallet"

# Check epoch settlement
curl -sk "https://50.28.86.131/api/settlement/1234"
```

---

## 7. Monitoring & Health Checks

### Health Endpoints

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/health` | Node health status | `{"status":"ok"}` |
| `/ready` | Ready to serve requests | `{"ready":true}` |
| `/epoch` | Current epoch info | `{"epoch":1234,...}` |
| `/api/miners` | Active miners list | `[...]` |
| `/api/network` | Network status | `{"peers":3,...}` |

### Prometheus Metrics

If your node exposes Prometheus metrics, scrape `/metrics` for:
- `rustchain_epoch_current` — Current epoch number
- `rustchain_miners_active` — Number of active miners
- `rustchain_attestations_total` — Total attestations processed
- `rustchain_attestations_rejected` — Rejected attestations
- `rustchain_peers_connected` — Connected peer count

### Simple Monitoring Script

```bash
#!/bin/bash
# monitor.sh — Simple RustChain node monitoring

NODE_URL="https://localhost:3000"

# Health check
HEALTH=$(curl -sk $NODE_URL/health 2>/dev/null)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  echo "✅ Node is healthy"
else
  echo "❌ Node health check FAILED"
  echo "Response: $HEALTH"
fi

# Peer count
PEERS=$(curl -sk $NODE_URL/api/network 2>/dev/null)
echo "Network: $PEERS"

# Epoch
EPOCH=$(curl -sk $NODE_URL/epoch 2>/dev/null)
echo "Epoch: $EPOCH"

# Miner count
MINERS=$(curl -sk $NODE_URL/api/miners 2>/dev/null)
echo "Active miners: $(echo $MINERS | grep -o '"id"' | wc -l)"
```

---

## 8. Troubleshooting

### Common Issues

#### "Connection refused" on startup

**Cause:** Port 3000 is already in use.

**Fix:**
```bash
# Check what's using port 3000
lsof -i :3000  # Linux/macOS
netstat -ano | findstr :3000  # Windows

# Kill the process or change the port in config.yaml
```

#### "Database locked" error

**Cause:** Another instance is running or database file is corrupted.

**Fix:**
```bash
# Kill any running instances
pkill rustchain

# Check for stale lock file
rm -f ./data/rustchain.db.lock

# Restart
./rustchain --config config.yaml
```

#### Attestation rejected: "Clock drift too high"

**Cause:** System clock is not synchronized.

**Fix:**
```bash
# Linux: enable NTP
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd

# macOS: enable time sync
sudo sntp -sS time.apple.com

# Windows: sync time
w32tm /resync
```

#### Attestation rejected: "Unknown architecture"

**Cause:** Your CPU architecture is not in the accepted list.

**Fix:**
- Check `config.yaml` → `attestation.accepted_architectures`
- Add your architecture to the list
- Restart the attestation node

#### "No peers connected"

**Cause:** Bootstrap nodes are unreachable or firewall blocking port 3001.

**Fix:**
```bash
# Check firewall
sudo ufw allow 3001/tcp  # Linux

# Verify bootstrap node is reachable
curl -sk https://50.28.86.131/health

# Check config.yaml bootstrap_nodes list
```

#### Low mining rewards

**Possible causes:**
1. Hardware not properly attested
2. Low antiquity multiplier
3. Missed work cycles

**Diagnosis:**
```bash
# Check attestation status
curl -sk "https://50.28.86.131/attest/status?miner=YOUR_MINER_ID"

# Check epoch settlement details
curl -sk "https://50.28.86.131/api/settlement/CURRENT_EPOCH"
```

### Log Analysis

```bash
# Search for errors
grep -i "error" ./data/rustchain.log | tail -20

# Search for rejection reasons
grep -i "reject" ./data/rustchain.log | tail -20

# Monitor live logs
tail -f ./data/rustchain.log
```

---

## 9. Performance Tuning

### Database Optimization

```yaml
# In config.yaml
database:
  # Increase cache size (MB)
  cache_size: 1024

  # Enable WAL mode for better concurrent performance
  journal_mode: wal

  # Synchronous mode (off = faster, full = safer)
  synchronous: normal
```

### Network Tuning

```yaml
# In config.yaml
network:
  # Increase max peer connections
  max_peers: 50

  # Connection timeout (seconds)
  connection_timeout: 30

  # Enable keepalive
  keepalive_interval: 60
```

### Memory Optimization

For systems with limited RAM:

```yaml
# In config.yaml
performance:
  # Reduce memory cache
  cache_size: 256  # MB

  # Disable verbose logging
  logging:
    level: warn
```

### Nginx Reverse Proxy (Optional)

For production deployments, put Nginx in front:

```nginx
server {
    listen 443 ssl;
    server_name rustchain.example.com;

    ssl_certificate /etc/ssl/certs/rustchain.crt;
    ssl_certificate_key /etc/ssl/private/rustchain.key;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 10. Advanced Topics

### Multiple Miners on One Machine

```yaml
# miner-1.yaml
node:
  type: miner
mining:
  wallet_address: "rust1wallet_1_address"
  attestation_node_url: "https://50.28.86.131"

# miner-2.yaml
node:
  type: miner
mining:
  wallet_address: "rust1wallet_2_address"
  attestation_node_url: "https://50.28.86.131"
```

```bash
# Run both miners
./rustchain --config miner-1.yaml &
./rustchain --config miner-2.yaml &
```

### Updating RustChain

```bash
# From source
git pull origin main
cargo build --release

# Pre-built binary
curl -L https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-linux-x86_64 -o rustchain
chmod +x rustchain

# Docker
docker pull scottcjn/rustchain:latest
docker stop rustchain-node
docker rm rustchain-node
# Then re-run the docker run command
```

### Backup & Recovery

```bash
# Backup database
cp ./data/rustchain.db ./backup/rustchain-$(date +%Y%m%d).db

# Backup wallet keys
cp ~/.rustchain/wallet.json ./backup/wallet-$(date +%Y%m%d).json

# Restore from backup
cp ./backup/rustchain-20260527.db ./data/rustchain.db
```

### Payout Preflight Checklist

Before expecting rewards, verify:

- [ ] Wallet address is correctly configured
- [ ] Attestation submissions are accepted (check `/attest/status`)
- [ ] Node is connected to peers (check `/api/network`)
- [ ] Epoch settlement is complete (check `/api/settlement/{epoch}`)
- [ ] No rejected attestations (check logs)

---

## Command Reference

| Command | Description |
|---------|-------------|
| `rustchain --config config.yaml` | Start node |
| `rustchain --version` | Show version |
| `rustchain wallet create` | Create new wallet |
| `rustchain wallet balance` | Check balance |
| `rustchain wallet import <key>` | Import wallet |
| `rustchain mine --console` | Start mining with console output |

---

## Related Documentation

- [Quick Start](docs/QUICKSTART.md) — Get mining in 5 minutes
- [Installation Walkthrough](docs/INSTALLATION_WALKTHROUGH.md) — Detailed installation guide
- [Console Mining Setup](docs/CONSOLE_MINING_SETUP.md) — Mining via console
- [Mastering the Miner](docs/MASTERING_THE_MINER.md) — Advanced mining techniques
- [DevNet](docs/DEVNET.md) — Development network setup
- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md) — System architecture
- [API Reference](docs/API_REFERENCE.md) — Complete REST API docs
- [CLI Reference](docs/CLI.md) — Command-line interface
- [Build Guide](docs/BUILD.md) — Build from source
- [Payout Preflight](docs/PAYOUT_PREFLIGHT.md) — Before expecting rewards

---

*Last updated: 2026-05-27 | Part of [Documentation Sprint #72](https://github.com/Scottcjn/rustchain-bounties/issues/72)*