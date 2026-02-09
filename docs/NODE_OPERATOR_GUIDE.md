# RustChain Node Operator Guide

Complete guide for running a RustChain attestation node.

---

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Node](#running-the-node)
- [Database Management](#database-management)
- [P2P Networking](#p2p-networking)
- [Ergo Anchoring](#ergo-anchoring)
- [Monitoring](#monitoring)
- [Security](#security)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

---

## Overview

RustChain nodes perform three critical functions:

1. **Attestation Validation** - Verify hardware fingerprints and enroll miners
2. **Epoch Settlement** - Distribute rewards based on RIP-200 consensus
3. **Ergo Anchoring** - Anchor settlement hashes to Ergo blockchain for immutability

**Node Types**:
- **Primary Node**: Full attestation + settlement + API (e.g., 50.28.86.131)
- **Relay Node**: P2P gossip + sync (community nodes)
- **Archive Node**: Full history + explorer (optional)

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **CPU** | 2 cores (4 recommended) |
| **RAM** | 2 GB (4 GB recommended) |
| **Disk** | 20 GB SSD |
| **Network** | 10 Mbps up/down, static IP |
| **OS** | Ubuntu 20.04+, Debian 11+, RHEL 8+ |
| **Python** | Python 3.8+ |
| **Database** | SQLite 3.35+ |

### Recommended Production Setup

| Component | Specification |
|-----------|---------------|
| **CPU** | 4+ cores (Intel Xeon, AMD EPYC) |
| **RAM** | 8 GB |
| **Disk** | 50 GB NVMe SSD |
| **Network** | 100 Mbps, static IP, DDoS protection |
| **OS** | Ubuntu 22.04 LTS |
| **Backup** | Daily automated backups |

---

## Installation

### Step 1: System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv git sqlite3 nginx certbot

# Create rustchain user (optional but recommended)
sudo useradd -m -s /bin/bash rustchain
sudo su - rustchain
```

### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

### Step 3: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Key dependencies**:
```
Flask==2.3.0
requests==2.31.0
PyNaCl==1.5.0
prometheus-client==0.17.0
```

### Step 5: Initialize Database

```bash
cd node
python3 rustchain_v2_integrated_v2.2.1_rip200.py --init-db
```

**Expected output**:
```
[INIT] Creating database schema...
[INIT] ✓ Table: balances
[INIT] ✓ Table: ledger
[INIT] ✓ Table: epoch_state
[INIT] ✓ Table: miner_registry
[INIT] ✓ Table: attestations
[INIT] ✓ Table: nonces
[INIT] Database initialized successfully
```

---

## Configuration

### Environment Variables

Create `.env` file in `node/` directory:

```bash
# Node Configuration
RUSTCHAIN_NODE_URL=https://your-node-domain.com
RUSTCHAIN_DB=/root/rustchain/rustchain_v2.db
FLASK_ENV=production
FLASK_SECRET_KEY=your-secret-key-here

# P2P Configuration
RC_P2P_SECRET=your-p2p-secret-here
RC_P2P_PORT=8545
RC_PEER_NODES=50.28.86.131,76.8.228.245

# Ergo Anchoring
ERGO_NODE_URL=https://50.28.86.153
ERGO_WALLET_ADDRESS=your-ergo-wallet-address
ERGO_API_KEY=your-ergo-api-key

# Security
ADMIN_API_KEY=your-admin-key-here
RATE_LIMIT_PER_MINUTE=100

# Monitoring
PROMETHEUS_PORT=9090
LOG_LEVEL=INFO
```

### Database Configuration

**Default path**: `/root/rustchain/rustchain_v2.db`

**Schema**:
```sql
-- Balances table
CREATE TABLE balances (
    miner_id TEXT PRIMARY KEY,
    balance_urtc INTEGER DEFAULT 0,
    last_updated INTEGER
);

-- Ledger table (transaction history)
CREATE TABLE ledger (
    tx_id TEXT PRIMARY KEY,
    from_address TEXT,
    to_address TEXT,
    amount_urtc INTEGER,
    timestamp INTEGER,
    signature TEXT,
    nonce INTEGER
);

-- Epoch state table
CREATE TABLE epoch_state (
    epoch INTEGER PRIMARY KEY,
    pot_urtc INTEGER,
    enrolled_miners INTEGER,
    settled BOOLEAN DEFAULT 0,
    settlement_hash TEXT,
    ergo_tx_id TEXT
);

-- Miner registry table
CREATE TABLE miner_registry (
    miner_id TEXT PRIMARY KEY,
    cpu_model TEXT,
    architecture TEXT,
    release_year INTEGER,
    tier TEXT,
    multiplier REAL,
    serial TEXT UNIQUE,
    fingerprint_hash TEXT,
    last_attestation INTEGER,
    enrolled_epochs INTEGER DEFAULT 0
);

-- Attestations table
CREATE TABLE attestations (
    attestation_id TEXT PRIMARY KEY,
    miner_id TEXT,
    timestamp INTEGER,
    fingerprint TEXT,
    signature TEXT,
    checks_passed TEXT,
    valid BOOLEAN
);

-- Nonces table (replay protection)
CREATE TABLE nonces (
    nonce INTEGER PRIMARY KEY,
    miner_id TEXT,
    used_at INTEGER
);
```

### Nginx Configuration

Create `/etc/nginx/sites-available/rustchain`:

```nginx
server {
    listen 80;
    server_name your-node-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-node-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-node-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-node-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Proxy to Flask app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
    limit_req zone=api burst=20 nodelay;
    
    # Access logs
    access_log /var/log/nginx/rustchain_access.log;
    error_log /var/log/nginx/rustchain_error.log;
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/rustchain /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL Certificate (Let's Encrypt)

```bash
sudo certbot --nginx -d your-node-domain.com
```

---

## Running the Node

### Development Mode

```bash
cd ~/Rustchain/node
source ../venv/bin/activate
python3 rustchain_v2_integrated_v2.2.1_rip200.py
```

**Output**:
```
[INIT] RustChain Node v2.2.1-rip200
[INIT] Database: /root/rustchain/rustchain_v2.db
[INIT] ✓ Hardware proof validation module loaded
[INIT] ✓ Rewards module loaded (RIP-200)
[INIT] ✓ P2P gossip module loaded
[INIT] Starting Flask server on 0.0.0.0:5000
 * Running on http://0.0.0.0:5000
```

### Production Mode (systemd)

Create `/etc/systemd/system/rustchain-node.service`:

```ini
[Unit]
Description=RustChain Attestation Node
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/home/rustchain/Rustchain/node
Environment="PATH=/home/rustchain/Rustchain/venv/bin"
EnvironmentFile=/home/rustchain/Rustchain/node/.env
ExecStart=/home/rustchain/Rustchain/venv/bin/python3 rustchain_v2_integrated_v2.2.1_rip200.py
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/root/rustchain

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-node
sudo systemctl start rustchain-node
```

**Service management**:
```bash
# Check status
sudo systemctl status rustchain-node

# View logs
sudo journalctl -u rustchain-node -f

# Restart
sudo systemctl restart rustchain-node

# Stop
sudo systemctl stop rustchain-node
```

---

## Database Management

### Backup

**Automated daily backup script** (`/home/rustchain/backup.sh`):

```bash
#!/bin/bash
DB_PATH="/root/rustchain/rustchain_v2.db"
BACKUP_DIR="/root/rustchain/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# SQLite backup
sqlite3 $DB_PATH ".backup $BACKUP_DIR/rustchain_$DATE.db"

# Compress
gzip $BACKUP_DIR/rustchain_$DATE.db

# Keep only last 30 days
find $BACKUP_DIR -name "rustchain_*.db.gz" -mtime +30 -delete

echo "Backup completed: rustchain_$DATE.db.gz"
```

**Add to crontab**:
```bash
crontab -e
# Add line:
0 2 * * * /home/rustchain/backup.sh
```

### Restore

```bash
# Stop node
sudo systemctl stop rustchain-node

# Restore from backup
gunzip -c /root/rustchain/backups/rustchain_20260209_020000.db.gz > /root/rustchain/rustchain_v2.db

# Start node
sudo systemctl start rustchain-node
```

### Database Maintenance

```bash
# Vacuum database (reclaim space)
sqlite3 /root/rustchain/rustchain_v2.db "VACUUM;"

# Analyze (optimize query planner)
sqlite3 /root/rustchain/rustchain_v2.db "ANALYZE;"

# Check integrity
sqlite3 /root/rustchain/rustchain_v2.db "PRAGMA integrity_check;"
```

---

## P2P Networking

### Peer Discovery

Nodes discover peers through:
1. **Bootstrap nodes** (hardcoded in config)
2. **Peer announcements** (gossip protocol)
3. **Manual configuration** (RC_PEER_NODES env var)

### Gossip Protocol

RustChain uses Bitcoin-style INV/GETDATA gossip:

```
Node A                    Node B
  |                         |
  |--- INV (attestation) -->|
  |                         |
  |<-- GETDATA -------------|
  |                         |
  |--- DATA (full attest) ->|
  |                         |
```

### Configure Peers

Edit `.env`:
```bash
RC_PEER_NODES=50.28.86.131,76.8.228.245,your-peer-ip
```

### Monitor P2P Status

```bash
curl -sk https://your-node/api/p2p/status
```

**Response**:
```json
{
  "peers": [
    {
      "address": "50.28.86.131",
      "last_seen": "2026-02-09T14:23:45Z",
      "messages_sent": 1234,
      "messages_received": 5678,
      "latency_ms": 45
    }
  ],
  "total_peers": 3,
  "sync_status": "synced"
}
```

---

## Ergo Anchoring

### Setup Ergo Wallet

1. Install Ergo node or use public API
2. Create wallet address
3. Fund wallet with ERG for transaction fees

### Configure Anchoring

Edit `.env`:
```bash
ERGO_NODE_URL=https://50.28.86.153
ERGO_WALLET_ADDRESS=9f4QF8AD1nQ3nJahQVkMj8hFSVVzVom77b52JU7EW71Zexg6N8v
ERGO_API_KEY=your-api-key
```

### Anchor Settlement

Settlements are automatically anchored every epoch:

```python
# In node/rustchain_ergo_anchor.py
def anchor_settlement(epoch: int, settlement_hash: str):
    """Anchor epoch settlement to Ergo blockchain."""
    # Create Ergo transaction with settlement hash in metadata
    tx = create_ergo_tx(
        data=settlement_hash,
        metadata={"epoch": epoch, "chain": "rustchain"}
    )
    
    # Broadcast to Ergo
    tx_id = broadcast_ergo_tx(tx)
    
    # Store in database
    update_epoch_anchor(epoch, tx_id)
```

### Verify Anchoring

```bash
curl -sk "https://your-node/api/epoch/61/anchor"
```

**Response**:
```json
{
  "epoch": 61,
  "settlement_hash": "a1b2c3d4e5f6...",
  "ergo_tx_id": "7h8i9j0k1l2m...",
  "ergo_explorer": "https://explorer.ergoplatform.com/en/transactions/7h8i9j0k1l2m...",
  "anchored_at": "2026-02-09T14:30:00Z"
}
```

---

## Monitoring

### Prometheus Metrics

Node exposes Prometheus metrics on port 9090:

```bash
curl http://localhost:9090/metrics
```

**Key metrics**:
```
# Attestations
rustchain_attestations_total{status="valid"} 1234
rustchain_attestations_total{status="invalid"} 56

# Epochs
rustchain_current_epoch 61
rustchain_epoch_pot_rtc 1.5
rustchain_enrolled_miners 47

# Balances
rustchain_total_balance_rtc 5213.41835243

# API
rustchain_api_requests_total{endpoint="/health",status="200"} 9876
rustchain_api_request_duration_seconds{endpoint="/attest/submit"} 0.234
```

### Grafana Dashboard

Import dashboard from `monitoring/grafana-dashboard.json`:

**Panels**:
- Total RTC in circulation
- Active miners
- Attestations per hour
- API request rate
- Database size
- P2P peer count

### Health Checks

```bash
# Node health
curl -sk https://your-node/health

# Database connectivity
curl -sk https://your-node/api/stats

# P2P status
curl -sk https://your-node/api/p2p/status
```

### Alerting

**Example alert rules** (Prometheus):

```yaml
groups:
  - name: rustchain
    rules:
      - alert: NodeDown
        expr: up{job="rustchain-node"} == 0
        for: 5m
        annotations:
          summary: "RustChain node is down"
      
      - alert: HighInvalidAttestations
        expr: rate(rustchain_attestations_total{status="invalid"}[5m]) > 10
        for: 10m
        annotations:
          summary: "High rate of invalid attestations"
      
      - alert: DatabaseSizeHigh
        expr: rustchain_database_size_bytes > 10e9
        annotations:
          summary: "Database size exceeds 10 GB"
```

---

## Security

### Firewall Configuration

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Allow P2P (if running relay node)
sudo ufw allow 8545/tcp

# Enable firewall
sudo ufw enable
```

### Rate Limiting

Configured in Nginx (see [Configuration](#configuration)):
- 100 requests/minute per IP
- Burst of 20 requests

### API Key Protection

Admin endpoints require API key:

```bash
curl -sk https://your-node/admin/settle-epoch \
  -H "X-Admin-Key: your-admin-key"
```

### SSL/TLS

- Use Let's Encrypt for free SSL certificates
- Enforce TLS 1.2+ only
- Disable weak ciphers

### Database Security

```bash
# Set proper permissions
chmod 600 /root/rustchain/rustchain_v2.db

# Encrypt backups
gpg --encrypt /root/rustchain/backups/rustchain_20260209.db.gz
```

---

## Maintenance

### Update Node Software

```bash
# Stop node
sudo systemctl stop rustchain-node

# Backup database
/home/rustchain/backup.sh

# Pull latest code
cd ~/Rustchain
git pull origin main

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart node
sudo systemctl start rustchain-node

# Verify
curl -sk https://your-node/health
```

### Database Optimization

Run weekly:
```bash
sqlite3 /root/rustchain/rustchain_v2.db <<EOF
VACUUM;
ANALYZE;
PRAGMA optimize;
EOF
```

### Log Rotation

Create `/etc/logrotate.d/rustchain`:

```
/var/log/rustchain/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 rustchain rustchain
    sharedscripts
    postrotate
        systemctl reload rustchain-node
    endscript
}
```

---

## Troubleshooting

### Node Won't Start

**Check logs**:
```bash
sudo journalctl -u rustchain-node -n 100
```

**Common issues**:
1. **Port already in use**: Change port in config
2. **Database locked**: Stop other processes accessing DB
3. **Missing dependencies**: `pip install -r requirements.txt`

### Database Corruption

```bash
# Check integrity
sqlite3 /root/rustchain/rustchain_v2.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
sudo systemctl stop rustchain-node
cp /root/rustchain/backups/rustchain_latest.db.gz .
gunzip rustchain_latest.db.gz
mv rustchain_latest.db /root/rustchain/rustchain_v2.db
sudo systemctl start rustchain-node
```

### P2P Sync Issues

```bash
# Check peer connectivity
curl -sk https://your-node/api/p2p/status

# Manually trigger sync
curl -sk https://your-node/admin/sync-now \
  -H "X-Admin-Key: your-admin-key"
```

### High CPU Usage

**Possible causes**:
1. **Database vacuum running**: Wait for completion
2. **High attestation rate**: Normal during epoch start
3. **P2P sync**: Normal during initial sync

**Monitor**:
```bash
top -p $(pgrep -f rustchain_v2)
```

### Memory Leaks

**Monitor memory**:
```bash
ps aux | grep rustchain_v2
```

**Restart if needed**:
```bash
sudo systemctl restart rustchain-node
```

---

## Additional Resources

- **API Reference**: `docs/API_REFERENCE.md`
- **Protocol Specification**: `docs/PROTOCOL.md`
- **Architecture Overview**: `docs/ARCHITECTURE_OVERVIEW.md`
- **Community Support**: [GitHub Discussions](https://github.com/Scottcjn/Rustchain/discussions)

---

**Last Updated**: February 9, 2026  
**Node Version**: 2.2.1-rip200
