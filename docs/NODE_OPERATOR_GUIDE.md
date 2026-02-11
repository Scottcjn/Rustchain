# RustChain Node Operator Guide

A comprehensive guide to running and maintaining a RustChain attestation node.

## Table of Contents

- [Overview](#overview)
- [Hardware Requirements](#hardware-requirements)
- [Network Requirements](#network-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Node](#running-the-node)
- [Monitoring](#monitoring)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Performance Optimization](#performance-optimization)
- [Backup & Recovery](#backup--recovery)

---

## Overview

A RustChain node is a critical component of the proof-of-antiquity blockchain network. Nodes serve as:

1. **Attestation Validators** - Verify that miners are running on real hardware
2. **Block Producers** - Create and validate blocks
3. **State Keepers** - Maintain the complete blockchain state
4. **Reward Distributors** - Process epoch rewards and transfers
5. **API Servers** - Provide REST endpoints for miners and clients

### Node Types

| Type | Role | Hardware | Consensus |
|------|------|----------|-----------|
| **Attestation Node** | Verify hardware, manage rewards | Mid-range | RIP-200 |
| **Archive Node** | Full historical data | High spec | RIP-200 |
| **Validator Node** | Block production (3 active) | High spec | RIP-200 |
| **RPC Node** | Public API only | Low-mid spec | Read-only |

This guide focuses on **Attestation Nodes**, which are suitable for most operators.

### RIP-200 Consensus

RustChain uses RIP-200 (RustChain Improvement Proposal 200):
- **Round-robin block production** - Each miner produces blocks in turn
- **1 CPU = 1 vote** - Hardware binding prevents Sybil attacks
- **Antiquity multipliers** - Older hardware gets higher rewards (2.5x for PowerPC G4)
- **Hardware attestation** - 6-point fingerprint validation
- **Ergo blockchain anchoring** - Cross-chain finality

---

## Hardware Requirements

### Minimum Specifications for Attestation Node

| Component | Minimum | Recommended | Maximum |
|-----------|---------|-------------|---------|
| **CPU** | 2 cores | 4+ cores | 16+ cores |
| **RAM** | 2 GB | 8 GB | 32+ GB |
| **Storage** | 50 GB | 200 GB | 1 TB+ |
| **Bandwidth** | 5 Mbps | 25 Mbps | 100+ Mbps |
| **OS** | Ubuntu 20.04+ | Ubuntu 22.04+ | Ubuntu 24.04+ |

### Storage Breakdown

```
RustChain Node Storage Usage:
├── SQLite Database
│   ├── Blockchain state    ~30 GB
│   ├── Miner registry      ~5 GB
│   ├── Rewards ledger      ~10 GB
│   └── Transaction history ~5 GB
├── Application files       ~500 MB
├── Logs                    ~1 GB/month
└── Backup/snapshot         ~50 GB
```

### Bandwidth Requirements

**Outbound:**
- Miner attestation submissions: ~100 KB/day
- Block production: ~10 MB/day
- Consensus communication: ~50 MB/day

**Inbound:**
- API requests from miners: ~1 MB/day
- HTTP from clients: ~500 MB/day
- Ergo blockchain sync: ~50 MB/day

### CPU Considerations

- **At minimum load:** 1-2% CPU
- **During block production:** 5-10% CPU
- **During epoch settlement:** 20-30% CPU
- **Peak (rare):** 50% for short periods

---

## Network Requirements

### Network Architecture

```
Internet
    │
    ├─ Port 443 (HTTPS)  ← Public API for miners & clients
    │
    └─ Port 8080         ← Metrics/monitoring (internal)

                    Miner Network
                         │
        ┌────────────┬────┼────┬────────────┐
        │            │         │            │
    Miner-1      Miner-2   Miner-3    Miner-N
```

### Required Ports

| Port | Protocol | Purpose | Access |
|------|----------|---------|--------|
| **443** | HTTPS | Public API (REST) | Public |
| **80** | HTTP | Auto-redirect to HTTPS | Public (optional) |
| **8080** | HTTP | Prometheus metrics | Internal only |

### Firewall Configuration

**Linux (ufw):**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8080/tcp from 127.0.0.1
sudo ufw enable
```

**Linux (iptables):**
```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -s 127.0.0.1 -j ACCEPT
```

### SSL/TLS Certificates

**Self-signed certificate (development):**
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

**Let's Encrypt (production):**
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --standalone -d your-domain.com
```

**Update node config:**
```python
# In node configuration
SSL_CERT = "/path/to/cert.pem"
SSL_KEY = "/path/to/key.pem"
```

### DNS Setup

For stable operation, configure a DNS A record:
```
node.rustchain.local  →  your.ip.address
```

Or use a dynamic DNS service if your IP changes:
```bash
sudo apt-get install ddclient
# Configure with your provider (Cloudflare, Route53, etc.)
```

---

## Installation

### Prerequisites

**System packages:**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.10 python3-pip python3-venv \
    sqlite3 git curl wget htop \
    nginx certbot python3-certbot-nginx \
    build-essential libssl-dev libffi-dev
```

**Python version:**
```bash
python3 --version  # Should be 3.8+
python3 -m venv /opt/rustchain/venv
```

### Step 1: Clone the Repository

```bash
# Clone RustChain
git clone https://github.com/Scottcjn/Rustchain.git /opt/rustchain
cd /opt/rustchain

# Or use your fork
git clone https://github.com/your-username/Rustchain.git /opt/rustchain
cd /opt/rustchain

# Verify important files exist
ls -la node/rustchain_v2_integrated_v2.2.1_rip200.py
ls -la node/rewards_implementation_rip200.py
ls -la node/hardware_binding_v2.py
```

### Step 2: Create Virtual Environment

```bash
# Create virtualenv at system location
python3 -m venv /opt/rustchain/venv

# Activate
source /opt/rustchain/venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 3: Install Dependencies

```bash
# Navigate to node directory
cd /opt/rustchain/node

# Install Python dependencies
pip install -r requirements.txt

# Common dependencies
pip install flask requests nacl prometheus-client sqlite3
```

If `requirements.txt` doesn't exist, create it:

```bash
cat > requirements.txt << 'EOF'
flask==2.3.0
requests==2.31.0
pynacl==1.5.0
prometheus-client==0.17.0
cryptography==41.0.0
EOF

pip install -r requirements.txt
```

### Step 4: Initialize Database

```bash
# Create database directory
mkdir -p /opt/rustchain/data

# Run node initialization (creates/migrates database)
cd /opt/rustchain/node
source /opt/rustchain/venv/bin/activate
python3 rustchain_v2_integrated_v2.2.1_rip200.py --init-db
```

Expected output:
```
[INIT] Creating RustChain database...
[INIT] ✓ Database initialized at /opt/rustchain/data/rustchain.db
[INIT] ✓ Genesis block created
```

### Step 5: Configure Systemd Service

Create service file:

```bash
sudo tee /etc/systemd/system/rustchain-node.service > /dev/null << 'EOF'
[Unit]
Description=RustChain Attestation Node
After=network.target

[Service]
Type=simple
User=rustchain
Group=rustchain
WorkingDirectory=/opt/rustchain
Environment="PYTHONUNBUFFERED=1"
Environment="RUSTCHAIN_DB=/opt/rustchain/data/rustchain.db"
Environment="RUSTCHAIN_PORT=443"
Environment="RUSTCHAIN_THREADS=4"
ExecStart=/opt/rustchain/venv/bin/python3 /opt/rustchain/node/rustchain_v2_integrated_v2.2.1_rip200.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryMax=8G
CPUQuota=400%
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
```

### Step 6: Create User Account

```bash
# Create dedicated user for node
sudo useradd -r -s /bin/bash -m -d /opt/rustchain rustchain

# Set permissions
sudo chown -R rustchain:rustchain /opt/rustchain
sudo chmod -R 755 /opt/rustchain

# Allow rustchain user to bind to privileged ports
sudo setcap cap_net_bind_service=ep /opt/rustchain/venv/bin/python3
```

### Step 7: Start the Node

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable rustchain-node

# Start the node
sudo systemctl start rustchain-node

# Check status
sudo systemctl status rustchain-node
```

### Step 8: Verify Node is Running

```bash
# Check process
ps aux | grep rustchain

# Check port
sudo netstat -tuln | grep 443

# Test API
curl -sk https://localhost/health

# Check logs
sudo journalctl -u rustchain-node -f
```

---

## Configuration

### Environment Variables

Edit `/opt/rustchain/.env` (or set in systemd service):

```bash
# Node identity
RUSTCHAIN_NODE_ID=node-001
RUSTCHAIN_NETWORK=mainnet

# Database
RUSTCHAIN_DB=/opt/rustchain/data/rustchain.db
RUSTCHAIN_DB_BACKUP=/opt/rustchain/backups

# Network
RUSTCHAIN_PORT=443
RUSTCHAIN_HOST=0.0.0.0
RUSTCHAIN_WORKERS=4

# SSL/TLS
RUSTCHAIN_SSL_CERT=/etc/letsencrypt/live/your-domain.com/fullchain.pem
RUSTCHAIN_SSL_KEY=/etc/letsencrypt/live/your-domain.com/privkey.pem

# Performance
RUSTCHAIN_CACHE_SIZE=1000
RUSTCHAIN_MAX_BLOCK_SIZE=10485760

# Logging
RUSTCHAIN_LOG_LEVEL=INFO
RUSTCHAIN_LOG_FILE=/opt/rustchain/logs/node.log

# Metrics
RUSTCHAIN_METRICS_PORT=8080
PROMETHEUS_ENABLED=true
```

### Performance Tuning

**For high-load nodes:**

```bash
# Increase system limits
echo "fs.file-max = 2097152" | sudo tee -a /etc/sysctl.conf
echo "net.core.somaxconn = 65535" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Optimize database
sqlite3 /opt/rustchain/data/rustchain.db << 'EOF'
PRAGMA cache_size = -64000;  -- 64 MB cache
PRAGMA synchronous = NORMAL;  -- Faster writes
PRAGMA journal_mode = WAL;    -- Write-ahead logging
PRAGMA temp_store = MEMORY;
EOF
```

### Nginx Reverse Proxy (Optional)

For better performance and SSL handling:

```bash
sudo tee /etc/nginx/sites-available/rustchain > /dev/null << 'EOF'
upstream rustchain_backend {
    server localhost:5000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Proxy settings
    location / {
        proxy_pass https://rustchain_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Metrics (internal only)
    location /metrics {
        allow 127.0.0.1;
        allow 192.168.0.0/16;  # Your network
        deny all;
        proxy_pass https://rustchain_backend;
    }
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/rustchain /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Running the Node

### Starting the Node

```bash
# Using systemd (recommended)
sudo systemctl start rustchain-node

# Check status
sudo systemctl status rustchain-node

# View real-time logs
sudo journalctl -u rustchain-node -f

# View last 100 lines
sudo journalctl -u rustchain-node -n 100
```

### Manual Operation (Development/Testing)

```bash
# Activate virtualenv
cd /opt/rustchain
source venv/bin/activate

# Run with debug output
cd node
python3 -u rustchain_v2_integrated_v2.2.1_rip200.py --debug

# Run with specific config
python3 rustchain_v2_integrated_v2.2.1_rip200.py \
    --db /custom/path/rustchain.db \
    --port 8443 \
    --workers 2
```

### First Boot Checklist

After starting, verify:

```bash
# 1. Process is running
ps aux | grep rustchain

# 2. Port is listening
sudo netstat -tuln | grep 443

# 3. API responds
curl -sk https://localhost/health

# 4. No errors in logs
sudo journalctl -u rustchain-node --grep="ERROR"

# 5. Database was created
ls -lh /opt/rustchain/data/rustchain.db

# 6. Can reach from miner
# On a miner machine:
curl -sk https://your-node-ip/health
```

### Stopping the Node

```bash
# Stop gracefully
sudo systemctl stop rustchain-node

# Kill forcefully (if stuck)
sudo systemctl kill -s KILL rustchain-node

# Wait for shutdown
sleep 5
```

---

## Monitoring

### Health Checks

**Node health endpoint:**
```bash
curl -sk https://localhost/health | jq .

# Expected response:
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 86400,
  "db_rw": true,
  "tip_age_slots": 0,
  "backup_age_hours": 6.75
}
```

**Key metrics to monitor:**
- `ok`: Node operational status
- `uptime_s`: Seconds since node start
- `db_rw`: Database readable/writable
- `tip_age_slots`: Blocks behind the tip (should be 0)
- `backup_age_hours`: Time since last backup

### Prometheus Metrics

If Prometheus is enabled, access metrics:

```bash
curl http://localhost:8080/metrics

# Key metrics
rustchain_node_blocks_total        # Total blocks produced
rustchain_node_attestations_total  # Total attestations verified
rustchain_node_miners_active       # Currently enrolled miners
rustchain_node_rewards_distributed # Total RTC distributed
rustchain_node_api_requests_total  # API request count
```

### System Monitoring

**Monitor resource usage:**

```bash
# CPU and memory
watch -n 5 'ps aux | grep "[r]ustchain_v2"'

# Disk usage
df -h /opt/rustchain/data/

# Network I/O
iftop -i eth0

# Database size
du -sh /opt/rustchain/data/rustchain.db

# Log file size
du -sh /opt/rustchain/logs/
```

### Create Monitoring Dashboard

**Simple monitoring script:**

```bash
#!/bin/bash
# save as /opt/rustchain/monitor.sh

while true; do
    clear
    echo "RustChain Node Monitoring - $(date)"
    echo "=================================="
    
    # Health status
    echo -e "\n[HEALTH]"
    curl -sk https://localhost/health 2>/dev/null | jq . || echo "ERROR: Node unreachable"
    
    # System resources
    echo -e "\n[RESOURCES]"
    ps aux | grep "[r]ustchain_v2" | awk '{print "CPU: " $3 "% MEM: " $4 "% PID: " $2}'
    
    # Database
    echo -e "\n[DATABASE]"
    echo "Size: $(du -sh /opt/rustchain/data/rustchain.db 2>/dev/null | cut -f1)"
    
    # Recent logs
    echo -e "\n[RECENT ERRORS]"
    journalctl -u rustchain-node -n 5 --grep="ERROR" 2>/dev/null || echo "None"
    
    sleep 10
done
```

Run it:
```bash
chmod +x /opt/rustchain/monitor.sh
/opt/rustchain/monitor.sh
```

---

## Maintenance

### Regular Tasks

#### Daily

- Check node health status
- Review error logs
- Verify disk space

#### Weekly

- Check database integrity
- Verify miner attestation rates
- Check network connectivity

#### Monthly

- Backup database
- Review performance metrics
- Update SSL certificates (if needed)
- Check for security updates

### Database Maintenance

**Check database integrity:**

```bash
sqlite3 /opt/rustchain/data/rustchain.db "PRAGMA integrity_check;"

# Output should be: ok
```

**Optimize database:**

```bash
sqlite3 /opt/rustchain/data/rustchain.db << 'EOF'
PRAGMA vacuum;
PRAGMA analyze;
EOF
```

**View database statistics:**

```bash
sqlite3 /opt/rustchain/data/rustchain.db << 'EOF'
.mode column
SELECT name, COUNT(*) as rows FROM sqlite_master 
WHERE type='table' GROUP BY name;
EOF
```

### Log Rotation

Configure logrotate:

```bash
sudo tee /etc/logrotate.d/rustchain > /dev/null << 'EOF'
/opt/rustchain/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 rustchain rustchain
    postrotate
        sudo systemctl reload rustchain-node > /dev/null 2>&1 || true
    endscript
}
EOF
```

### Update Procedures

```bash
# Stop the node
sudo systemctl stop rustchain-node

# Backup current state
cp -r /opt/rustchain/data /opt/rustchain/data.backup.$(date +%s)

# Update code
cd /opt/rustchain
git fetch origin
git pull origin main

# Reinstall dependencies (if changed)
source venv/bin/activate
cd node
pip install -r requirements.txt

# Restart
sudo systemctl start rustchain-node

# Verify
sleep 5
curl -sk https://localhost/health
```

---

## Troubleshooting

### Node won't start

**Check logs:**
```bash
sudo journalctl -u rustchain-node -n 50
```

**Common issues:**

1. **Port already in use:**
   ```bash
   sudo lsof -i :443
   # Kill conflicting process or change RUSTCHAIN_PORT
   ```

2. **Permission denied:**
   ```bash
   sudo chown -R rustchain:rustchain /opt/rustchain
   ```

3. **Python not found:**
   ```bash
   # Verify Python path
   which python3
   # Update ExecStart in systemd service
   ```

4. **Database locked:**
   ```bash
   # Wait and retry (usually temporary)
   sudo systemctl restart rustchain-node
   ```

### High CPU usage

**Check what's consuming CPU:**
```bash
top -p $(pgrep -f rustchain_v2)
# Press 'H' to show threads
```

**Solutions:**
- Reduce number of workers (RUSTCHAIN_WORKERS)
- Increase database cache
- Check for attestation queue buildup

### High memory usage

**Check memory breakdown:**
```bash
ps aux | grep rustchain_v2
# Check if memory keeps growing
```

**Solutions:**
- Restart the node (memory leak fix)
- Reduce RUSTCHAIN_CACHE_SIZE
- Check for attestation queue issues

### Database errors

**SQLite is locked:**
```bash
# Find locks
lsof | grep rustchain.db

# Restart node
sudo systemctl restart rustchain-node
```

**Corruption:**
```bash
# Check integrity
sqlite3 /opt/rustchain/data/rustchain.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
cp /opt/rustchain/data.backup.*/rustchain.db /opt/rustchain/data/
```

### Network connectivity issues

**Test connectivity:**
```bash
# Test node accessibility from miner machine
curl -sk https://your-node-ip/health

# Check firewall
sudo ufw status
sudo iptables -L -n

# Test DNS (if using domain)
nslookup your-domain.com
```

### Slow response times

**Check database performance:**
```bash
# Enable query logging
sqlite3 /opt/rustchain/data/rustchain.db << 'EOF'
PRAGMA query_only = false;
.mode line
SELECT * FROM sqlite_stat1;
EOF
```

**Solutions:**
- Increase workers (RUSTCHAIN_WORKERS)
- Optimize indexes (run ANALYZE)
- Increase database cache
- Check for slow queries in logs

---

## Security

### Access Control

**Restrict metrics endpoint:**

```bash
# Only allow localhost
sudo ufw allow 8080/tcp from 127.0.0.1
```

**Restrict admin API calls:**
- Use environment variables for secrets
- Never log sensitive data
- Audit all administrative access

### Database Security

**Encrypt sensitive data:**

```bash
# Enable SQLite encryption (if compiled with support)
# For production, consider:
# - Database replication to secure location
# - Regular backups to encrypted storage
# - File-level encryption (LUKS)
```

**Restrict database file permissions:**

```bash
sudo chmod 600 /opt/rustchain/data/rustchain.db
sudo chown rustchain:rustchain /opt/rustchain/data/rustchain.db
```

### Network Security

**Use firewall effectively:**

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP (redirect)
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 8080/tcp from 127.0.0.1  # Metrics
```

**Enable SSL/TLS:**

```bash
# Verify certificate
openssl s_client -connect localhost:443

# Check certificate expiry
openssl x509 -in /etc/letsencrypt/live/your-domain.com/fullchain.pem -noout -dates
```

### Regular Security Updates

```bash
# Check for updates
sudo apt-get update
sudo apt-get upgrade --simulate

# Install critical updates
sudo apt-get install --only-upgrade openssh-server

# Update Python packages
pip list --outdated
pip install --upgrade requests flask
```

---

## Performance Optimization

### Database Optimization

**Create indexes for common queries:**

```bash
sqlite3 /opt/rustchain/data/rustchain.db << 'EOF'
CREATE INDEX IF NOT EXISTS idx_miner_id ON miners(miner_id);
CREATE INDEX IF NOT EXISTS idx_wallet_address ON wallets(address);
CREATE INDEX IF NOT EXISTS idx_transaction_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_block_height ON blocks(height);
EOF
```

**Enable Write-Ahead Logging:**

```bash
sqlite3 /opt/rustchain/data/rustchain.db << 'EOF'
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
EOF
```

### System Optimization

**Increase file descriptors:**

```bash
# Permanently
echo "fs.file-max = 2097152" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Per-user
echo "rustchain soft nofile 65535" | sudo tee -a /etc/security/limits.conf
echo "rustchain hard nofile 65535" | sudo tee -a /etc/security/limits.conf
```

**Network optimization:**

```bash
echo "net.core.somaxconn = 65535" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.ip_local_port_range = 1024 65535" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Application Optimization

**Tune worker processes:**

```bash
# For CPU-bound work
WORKERS = CPU_CORES * 2

# For I/O-bound work
WORKERS = CPU_CORES * 4
```

**Connection pooling:**

```python
# In application config
DB_POOL_SIZE = 10
DB_POOL_TIMEOUT = 30
```

---

## Backup & Recovery

### Automated Backup

**Create backup script:**

```bash
#!/bin/bash
# save as /opt/rustchain/backup.sh

BACKUP_DIR="/opt/rustchain/backups"
DB_PATH="/opt/rustchain/data/rustchain.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp $DB_PATH $BACKUP_DIR/rustchain_$DATE.db

# Compress
gzip $BACKUP_DIR/rustchain_$DATE.db

# Keep last 7 days
find $BACKUP_DIR -name "rustchain_*.db.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/rustchain_$DATE.db.gz"
```

**Setup cron job:**

```bash
# Daily backup at 2 AM
echo "0 2 * * * /opt/rustchain/backup.sh" | sudo tee /etc/cron.d/rustchain-backup

# Verify
sudo crontab -l | grep rustchain
```

### Full Node Snapshot

```bash
#!/bin/bash
# save as /opt/rustchain/snapshot.sh

SNAPSHOT_DIR="/opt/rustchain/snapshots"
DATE=$(date +%Y%m%d_%H%M%S)

# Stop node
sudo systemctl stop rustchain-node

# Create snapshot
mkdir -p $SNAPSHOT_DIR
tar -czf $SNAPSHOT_DIR/rustchain-snapshot-$DATE.tar.gz \
    /opt/rustchain/data \
    /opt/rustchain/.env

# Start node
sudo systemctl start rustchain-node

echo "Snapshot created: $SNAPSHOT_DIR/rustchain-snapshot-$DATE.tar.gz"
```

### Recovery Procedures

**Restore database backup:**

```bash
# Stop node
sudo systemctl stop rustchain-node

# Restore from backup
gunzip -c /opt/rustchain/backups/rustchain_YYYYMMDD_HHMMSS.db.gz \
    > /opt/rustchain/data/rustchain.db

# Fix permissions
sudo chown rustchain:rustchain /opt/rustchain/data/rustchain.db
sudo chmod 600 /opt/rustchain/data/rustchain.db

# Start node
sudo systemctl start rustchain-node

# Verify
sleep 5
curl -sk https://localhost/health
```

**Restore from snapshot:**

```bash
# Stop node
sudo systemctl stop rustchain-node

# Extract snapshot
tar -xzf /opt/rustchain/snapshots/rustchain-snapshot-YYYYMMDD_HHMMSS.tar.gz \
    -C /

# Start node
sudo systemctl start rustchain-node
```

---

## Checklist: New Node Setup

- [ ] System prerequisites installed
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Database initialized
- [ ] Systemd service configured
- [ ] Dedicated user created
- [ ] Firewall rules configured
- [ ] SSL/TLS certificates installed
- [ ] Node started successfully
- [ ] Health endpoint responds
- [ ] Logs monitored for errors
- [ ] Backup system configured
- [ ] Performance baselines recorded
- [ ] Monitoring dashboard setup

---

## Quick Reference Commands

```bash
# Service management
sudo systemctl start rustchain-node
sudo systemctl stop rustchain-node
sudo systemctl restart rustchain-node
sudo systemctl status rustchain-node

# Logging
sudo journalctl -u rustchain-node -f
sudo journalctl -u rustchain-node --since "1 hour ago"
sudo journalctl -u rustchain-node -p err

# Health checks
curl -sk https://localhost/health
curl -sk https://localhost/epoch
curl -sk https://localhost/api/miners

# Database
sqlite3 /opt/rustchain/data/rustchain.db
PRAGMA integrity_check;
PRAGMA analyze;
VACUUM;

# System info
ps aux | grep rustchain
top -p $(pgrep -f rustchain_v2)
df -h /opt/rustchain

# Backups
/opt/rustchain/backup.sh
ls -lh /opt/rustchain/backups/
```

---

## Resources

- **GitHub:** https://github.com/Scottcjn/Rustchain
- **Node Code:** `node/rustchain_v2_integrated_v2.2.1_rip200.py`
- **API Docs:** `docs/api-reference.md`
- **RIP-200:** Consensus specification
- **Community:** https://github.com/Scottcjn/rustchain-bounties

---

## Support

For issues, questions, or improvements:

1. Check logs: `journalctl -u rustchain-node -f`
2. Verify connectivity: `curl -sk https://localhost/health`
3. Review configuration: `cat /opt/rustchain/.env`
4. Check system resources: `top`, `df`, `netstat`
5. Search GitHub issues
6. Open new issue with:
   - Node version
   - System info (`uname -a`)
   - Last 50 lines of logs
   - Steps to reproduce

---

**Version:** 1.0  
**Last Updated:** February 2026  
**RustChain Version:** 2.2.1-rip200  
**License:** MIT
