# RustChain Node Operator Guide

> Complete step-by-step guide for running RustChain attestation nodes and miners.
>
> **Corrected 2026-08-30 to match the real deployment.** RustChain nodes are a **Python/Flask** app served by **gunicorn** on port **8099** — not a Rust binary. New operators run a **sync node** (no fleet secrets); settlement-node credentials are issued privately after verification.

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
| 8099 | HTTP | REST API & attestation (bind localhost; put nginx/TLS in front for public) |
| 443 | HTTPS | Public endpoint — nginx reverse-proxies to 8099 (recommended for public nodes) |
| 80 | HTTP | Optional redirect to HTTPS |

> **Note:** RustChain nodes are a **Python/Flask** application served by **gunicorn**. There is no Rust binary or `cargo build` step — earlier drafts of this guide were incorrect.

---

## 2. Installation

RustChain nodes run a **Python 3.8+** application (Flask app served by gunicorn). No compiler or Rust toolchain is required.

### Step 1 — Clone the repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/node
```

### Step 2 — Install Python dependencies

```bash
# System python3 (3.8+) or a virtualenv, your choice:
python3 -m venv venv && source venv/bin/activate     # optional but recommended
pip install -r ../requirements-node.txt
# Installs: Flask, requests, psutil, PyNaCl, gunicorn
```

### Step 3 — Verify

```bash
python3 -c "import flask, nacl, psutil, requests; print('deps ok')"
python3 -c "import ast; ast.parse(open('rustchain_v2_integrated_v2.2.1_rip200.py').read()); print('node source ok')"
```

### Option: Docker (miner)

The published Docker image is a **Python miner**, not a full node:

```bash
docker pull scottcjn/rustchain:latest   # RustChain Python miner
# See README_DOCKER_MINER.md for miner usage.
```

---

## 3. Configuration

RustChain nodes are configured entirely through **environment variables** (set them in the systemd unit or your shell). There is no `config.yaml`.

### Node roles

| Role | What it does | Who it's for | Fleet secrets needed |
|------|--------------|--------------|----------------------|
| **Sync node** *(default for new operators)* | Serves the API, syncs chain state from the public network, accepts attestations, but does **not** settle epochs | New / unverified operators | **None** |
| **Full settlement node** | Everything a sync node does **plus** epoch settlement and authenticated P2P consensus | Verified operators only | Yes — issued privately by the RustChain team |

> **New operators start as a sync node.** A settlement node mints rewards and joins consensus, so its credentials (`RC_SETTLEMENT_PUBKEY`, `RC_P2P_SECRET`, a fleet `RC_ADMIN_KEY`) are **issued privately after verification** and are never published. Do not invent or copy these values.

### Environment variables

| Variable | Sync node | Settlement node | Description |
|----------|-----------|-----------------|-------------|
| `RC_DB_PATH` | ✅ | ✅ | SQLite DB path, e.g. `/opt/rustchain/rustchain_v2.db` |
| `RC_NODE_ID` | ✅ | ✅ | A label for this node, e.g. `sync-hardik-1` |
| `RC_ADMIN_KEY` | generate your own (32-byte hex) for your own admin endpoints | fleet key (issued) | Admin API auth. `openssl rand -hex 32` for a sync node. |
| `RC_SETTLEMENT_PUBKEY` | — (omit) | issued | Grants settlement authority — settlement nodes only |
| `RC_P2P_SECRET` | — (omit) | issued | Authenticated P2P mesh HMAC — settlement nodes only |
| `BOOTSTRAP` / peer endpoint | `https://rustchain.org` | fleet peers | Where the node pulls chain state to sync |

A sync node syncs read-only from the public network (`https://rustchain.org`) — it does **not** need the authenticated P2P secret.

---

## 4. Wallet Setup

RustChain addresses are `RTC` followed by 40 hex characters (e.g. `RTCc5449fe1b93385961152720c864c0f073dae5855`). Wallets are managed with the Python wallet tools in this repo — see the dedicated **[Wallet Setup guide](WALLET_SETUP.md)** for full details.

### Create a wallet (self-custody)

```bash
# GUI wallet (BIP39 seed + Ed25519, encrypted keystore)
python3 wallet/rustchain_wallet_secure.py

# Or the CLI for scripted use
python3 tools/rustchain_wallet_cli.py create
```

Save the 24-word seed phrase offline — it is the only recovery path.

### Check a balance (public API, no key needed)

```bash
curl -s "https://rustchain.org/wallet/balance?address=RTC...your_address"
```

### Security
- Never share your seed phrase or private key; never paste them into a form or chat.
- Keep a separate wallet for node/mining rewards vs. personal holdings.
- Back up the encrypted keystore files.

---

## 5. Starting the Node

### Quick start (development / first run)

Run the app directly with Python. This uses the built-in Flask dev server and runs `init_db()` automatically:

```bash
cd Rustchain/node
export RC_DB_PATH=$PWD/rustchain_v2.db
export RC_NODE_ID=sync-1
export RC_ADMIN_KEY=$(openssl rand -hex 32)   # your own admin key for a sync node
python3 rustchain_v2_integrated_v2.2.1_rip200.py
```

### Production (gunicorn — recommended)

Production nodes are served by **gunicorn** via `wsgi.py` (which imports the app and calls `init_db()`):

```bash
cd Rustchain/node
export RC_DB_PATH=/opt/rustchain/rustchain_v2.db
export RC_NODE_ID=sync-1
export RC_ADMIN_KEY=$(openssl rand -hex 32)
gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120
```

### Verify the node is running

```bash
# Health check (note: port 8099, and the field is "ok")
curl -s http://127.0.0.1:8099/health
# Expected: {"ok":true,"version":"2.2.1-rip200","db_rw":true,...}

# Ready check
curl -s http://127.0.0.1:8099/ready

# Current epoch
curl -s http://127.0.0.1:8099/epoch
```

### Run as a systemd service (sync node)

Create `/etc/systemd/system/rustchain-sync.service`:

```ini
[Unit]
Description=RustChain Sync Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rustchain
Group=rustchain
WorkingDirectory=/opt/rustchain/node
Environment="RC_NODE_ID=sync-1"
Environment="RC_DB_PATH=/opt/rustchain/rustchain_v2.db"
Environment="RC_ADMIN_KEY=REPLACE_WITH_YOUR_OWN_32_BYTE_HEX"
# Sync nodes do NOT set RC_SETTLEMENT_PUBKEY or RC_P2P_SECRET —
# those are issued privately to verified settlement-node operators only.
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120 \
  --access-logfile /var/log/rustchain_access.log \
  --error-logfile /var/log/rustchain_error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-sync
sudo systemctl start rustchain-sync
sudo systemctl status rustchain-sync
```

> **Public exposure:** bind gunicorn to `127.0.0.1:8099` and put **nginx + TLS (certbot)** in front on 443 if you want the node reachable publicly. Do not expose admin endpoints (`X-Admin-Key`) to the internet.

---

## 6. Starting a Miner

A **miner** is separate from a node: it attests your hardware to the network and earns RTC. Most contributors want this, not a full node. The miner is a Python client — the authoritative install is **[INSTALL.md](../INSTALL.md)**.

### One-line install (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
# Flags: --dry-run (preview), --wallet YOUR_WALLET, --test-only (fingerprint test only)
```

The installer auto-installs Python 3.8+, sets up a systemd user service, runs your first attestation, and points at `https://rustchain.org` by default.

### Manual run

```bash
cd Rustchain/node
python3 rustchain_linux_miner.py            # attests to https://rustchain.org
```

### Verify your miner is attesting

```bash
curl -s https://rustchain.org/api/miners            # your miner should appear here
curl -s "https://rustchain.org/wallet/balance?address=RTC...your_wallet"
```

VMs are detected by the fingerprint checks and earn ~a billionth of real-hardware rewards by design — run on real silicon.

---

## 7. Monitoring & Health Checks

### Health Endpoints

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/health` | Node health status | `{"ok":true}` |
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

NODE_URL="http://127.0.0.1:8099"

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
lsof -i :8099  # Linux/macOS
netstat -ano | findstr :8099  # Windows

# Kill the process, or change the gunicorn -b bind port
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
gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120
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
- Architecture acceptance is server-side (`derive_verified_device()`); no client config controls it
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

# Confirm the node can reach its sync source (https://rustchain.org)
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
# via environment variables (see Section 3)
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
# via environment variables (see Section 3)
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
# via environment variables (see Section 3)
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
        proxy_pass http://127.0.0.1:8099;
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

Run one miner process per wallet, each with its own `MINER_WALLET`:

```bash
cd Rustchain/node
MINER_WALLET=RTC...wallet_1 NODE_URL=https://rustchain.org python3 rustchain_linux_miner.py &
MINER_WALLET=RTC...wallet_2 NODE_URL=https://rustchain.org python3 rustchain_linux_miner.py &
```

Note: the hardware fingerprint binds one physical machine to one wallet, so multiple miners on the *same* box share one hardware identity — this is by design (one machine = one vote).

### Updating RustChain

```bash
# Pull the latest node code and restart the service
cd Rustchain
git pull origin main
pip install -r requirements-node.txt   # in case deps changed
sudo systemctl restart rustchain-sync  # (or your service name)

# Verify it came back healthy
curl -s http://127.0.0.1:8099/health
```

### Backup & Recovery

```bash
# Backup database
cp $RC_DB_PATH ./backup/rustchain-$(date +%Y%m%d).db   # e.g. /opt/rustchain/rustchain_v2.db

# Backup wallet keys
cp -r ~/.rustchain/*_wallets ./backup/wallets-$(date +%Y%m%d)/   # encrypted keystores

# Restore from backup
cp ./backup/rustchain-20260527.db $RC_DB_PATH
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
| `gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120` | Start node (production) |
| `python3 rustchain_v2_integrated_v2.2.1_rip200.py` | Start node (dev, runs init_db) |
| `curl -s http://127.0.0.1:8099/health` | Health / version check |
| `python3 wallet/rustchain_wallet_secure.py` | Create / manage a wallet |
| `python3 tools/rustchain_wallet_cli.py balance` | Check balance |
| `python3 rustchain_linux_miner.py` | Start a miner |
| `bash install-miner.sh` | One-line miner install |

---

## Related Documentation

- [Quick Start](QUICKSTART.md) — Get mining in 5 minutes
- [Installation Walkthrough](INSTALLATION_WALKTHROUGH.md) — Detailed installation guide
- [Console Mining Setup](CONSOLE_MINING_SETUP.md) — Mining via console
- [Mastering the Miner](MASTERING_THE_MINER.md) — Advanced mining techniques
- [DevNet](DEVNET.md) — Development network setup
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md) — System architecture
- [API Reference](API_REFERENCE.md) — Complete REST API docs
- [CLI Reference](CLI.md) — Command-line interface
- [Build Guide](BUILD.md) — Build from source
- [Payout Preflight](PAYOUT_PREFLIGHT.md) — Before expecting rewards

---

*Last updated: 2026-05-27 | Part of [Documentation Sprint #72](https://github.com/Scottcjn/rustchain-bounties/issues/72)*
