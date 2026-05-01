# RustChain Node Operator Guide

This guide covers running a RustChain attestation node: hardware requirements,
installation, configuration, monitoring, and ongoing maintenance.

**Node endpoints (reference):**
- Primary: `http://rustchain.org:8088`
- Anchor:  `http://50.28.86.153:8088`

---

## Hardware Requirements

### Minimum (single-node, light traffic)

| Resource | Minimum |
|----------|---------|
| CPU | 2 cores, 2.0 GHz (x86_64 or ARM64) |
| RAM | 2 GB |
| Storage | 20 GB SSD |
| Network | 10 Mbps symmetric, static IP strongly recommended |
| OS | Ubuntu 20.04+, Debian 11+, Fedora 36+, or any systemd Linux |

### Recommended (production)

| Resource | Recommended |
|----------|------------|
| CPU | 4+ cores, 2.5+ GHz |
| RAM | 8 GB |
| Storage | 100 GB SSD (NVMe preferred) |
| Network | 100 Mbps symmetric, static IPv4, low-latency |
| OS | Ubuntu 22.04 LTS |

### Notes

- **Storage growth:** The SQLite database grows ~1 GB per 10 000 attestations.
  Monitor and add capacity before the disk fills.
- **RAM:** The node loads the full DB index into memory for fast attestation
  lookups. 2 GB minimum; 8 GB comfortable for a live network.
- **Static IP:** Required if you want other nodes to sync from yours via the
  P2P layer. A dynamic IP will cause peers to drop you after reconnect.

---

## Install the Beacon Node

### Step 1 — System dependencies

```bash
sudo apt update && sudo apt install -y \
    python3 python3-pip python3-venv git \
    sqlite3 curl jq
```

### Step 2 — Clone and set up

```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git /opt/rustchain
cd /opt/rustchain
python3 -m venv venv
source venv/bin/activate
pip install -r node/requirements.txt
```

### Step 3 — Configure

```bash
cp node/.env.example node/.env
nano node/.env
```

Key settings:

```ini
# Identity
NODE_ID=mynode-01
CHAIN_ID=rustchain-mainnet-v2

# Network
HOST=0.0.0.0
PORT=8088
P2P_PORT=9000

# Database
DB_PATH=/opt/rustchain/data/rustchain.db

# Security (generate with: python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_KEY=CHANGE_ME_GENERATE_A_REAL_SECRET

# Peers (comma-separated host:port pairs)
BOOTSTRAP_PEERS=50.28.86.131:9000,50.28.86.153:9000
```

### Step 4 — Initialize the database

```bash
cd /opt/rustchain
source venv/bin/activate
python3 node/rustchain_v2_integrated_v2.2.1_rip200.py --init-db
```

### Step 5 — Start (foreground test)

```bash
python3 node/rustchain_v2_integrated_v2.2.1_rip200.py
```

Verify with:

```bash
curl http://localhost:8088/health | jq .
```

Expected output:

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 12,
  "db_rw": true,
  "backup_age_hours": 0.0,
  "tip_age_slots": 0
}
```

Press `Ctrl-C`, then proceed to set up as a service.

### Step 6 — systemd service

```bash
sudo tee /etc/systemd/system/rustchain-node.service > /dev/null <<EOF
[Unit]
Description=RustChain Beacon Node
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/rustchain
EnvironmentFile=/opt/rustchain/node/.env
ExecStart=/opt/rustchain/venv/bin/python3 \
    node/rustchain_v2_integrated_v2.2.1_rip200.py
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rustchain-node

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-node
```

---

## Configure P2P and Open Ports

### Required ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8088 | TCP (HTTP) | REST API — miners, clients, monitoring |
| 9000 | TCP | P2P peer sync (block and attestation propagation) |

### UFW firewall (Ubuntu)

```bash
sudo ufw allow 8088/tcp comment "RustChain API"
sudo ufw allow 9000/tcp comment "RustChain P2P"
sudo ufw reload
sudo ufw status
```

### iptables (RHEL / minimal installs)

```bash
sudo iptables -A INPUT -p tcp --dport 8088 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 9000 -j ACCEPT
sudo iptables-save > /etc/iptables/rules.v4
```

### Peer configuration

Bootstrap peers are set in `.env`. The node connects to listed peers at
startup and discovers additional peers via the P2P handshake. To list current
peers:

```bash
curl http://localhost:8088/api/nodes | jq .
```

To add a peer at runtime (admin only):

```bash
curl -X POST http://localhost:8088/p2p/connect \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"peer": "203.0.113.50:9000"}'
```

---

## Monitoring

### Health checks

```bash
# One-shot health check
curl http://localhost:8088/health | jq .

# Watch every 30s
watch -n 30 'curl -s http://localhost:8088/health | jq .'
```

Healthy node shows `"ok": true` and `"tip_age_slots": 0`.  
If `tip_age_slots` > 10, the node is falling behind — check peers and network.

### Logs

```bash
# Follow live logs
sudo journalctl -u rustchain-node -f

# Last 200 lines
sudo journalctl -u rustchain-node -n 200 --no-pager

# Filter for errors only
sudo journalctl -u rustchain-node -p err -n 50 --no-pager
```

Key log patterns to watch:

| Pattern | Meaning |
|---------|---------|
| `Enrolled miner` | Attestation accepted |
| `VM_DETECTED` | Attestation rejected (normal) |
| `Epoch settled` | End-of-epoch reward distribution ran |
| `DB backup` | Scheduled backup completed |
| `Peer connected` | New P2P peer joined |
| `ERROR` | Investigate immediately |

### Prometheus metrics

The node exposes Prometheus-compatible metrics at `/metrics`:

```bash
curl http://localhost:8088/metrics
```

Scrape config (`/etc/prometheus/prometheus.yml`):

```yaml
scrape_configs:
  - job_name: rustchain
    static_configs:
      - targets: ["localhost:8088"]
    metrics_path: /metrics
```

Key metrics:

| Metric | Description |
|--------|-------------|
| `rustchain_epoch` | Current epoch number |
| `rustchain_enrolled_miners` | Miners enrolled this epoch |
| `rustchain_attestations_total` | Lifetime attestation counter |
| `rustchain_vm_rejections_total` | VM detection rejections |
| `rustchain_api_request_duration_seconds` | API latency histogram |

---

## Maintenance

### Software updates

```bash
cd /opt/rustchain
git fetch origin
git log HEAD..origin/main --oneline   # preview changes
git merge origin/main
source venv/bin/activate
pip install -r node/requirements.txt  # pick up new deps

sudo systemctl restart rustchain-node
sudo journalctl -u rustchain-node -f  # watch for startup errors
```

### Database backup

The node performs automatic SQLite backups. Manually trigger a backup:

```bash
# While node is stopped (safest)
sudo systemctl stop rustchain-node
cp /opt/rustchain/data/rustchain.db \
   /opt/rustchain/data/rustchain.db.$(date +%Y%m%d-%H%M%S).bak
sudo systemctl start rustchain-node
```

Hot backup (node running, SQLite WAL mode):

```bash
sqlite3 /opt/rustchain/data/rustchain.db ".backup /backups/rustchain-$(date +%Y%m%d).db"
```

Schedule nightly backups with cron:

```bash
sudo tee /etc/cron.d/rustchain-backup > /dev/null <<EOF
0 2 * * * ubuntu sqlite3 /opt/rustchain/data/rustchain.db \
  ".backup /backups/rustchain-\$(date +\%Y\%m\%d).db" && \
  find /backups -name "rustchain-*.db" -mtime +30 -delete
EOF
```

### Recovery from a corrupt database

1. Stop the node.
2. Restore the most recent backup:

```bash
sudo systemctl stop rustchain-node
cp /backups/rustchain-YYYYMMDD.db /opt/rustchain/data/rustchain.db
sudo systemctl start rustchain-node
curl http://localhost:8088/health | jq .
```

3. If no backup is available, re-sync from a peer:

```bash
# Download DB snapshot from a trusted peer (admin required on peer)
curl -H "X-Admin-Key: PEER_ADMIN_KEY" \
     http://rustchain.org:8088/admin/db-snapshot \
     -o /opt/rustchain/data/rustchain.db
sudo systemctl start rustchain-node
```

### Rotating the admin key

```bash
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s/^ADMIN_KEY=.*/ADMIN_KEY=$NEW_KEY/" /opt/rustchain/node/.env
sudo systemctl restart rustchain-node
echo "New admin key: $NEW_KEY"   # store securely
```

---

*Guide covers RustChain v2.2.1-rip200 · Reference nodes: http://rustchain.org:8088, http://50.28.86.153:8088*
