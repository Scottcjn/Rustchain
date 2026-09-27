# RustChain Node Operator Guide

> Complete step-by-step guide for running a RustChain node.

> **RustChain runs on Python / Flask — not Rust.** Despite the name, there is
> **no `Cargo.toml`, no `cargo build`, and no `rustchain-linux-x86_64` binary**.
> If you went looking for a release binary and could not find one, that is
> expected — it does not exist. You run the node with Python and `gunicorn`.
> (The only Rust in the repo is an unrelated `cross-chain-airdrop/` CLI.)

---

## Table of Contents

1. [Node roles: sync vs. settlement](#1-node-roles-sync-vs-settlement)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Starting the Node](#5-starting-the-node)
6. [Monitoring & Health Checks](#6-monitoring--health-checks)
7. [Troubleshooting](#7-troubleshooting)
8. [Running as a systemd service](#8-running-as-a-systemd-service)
9. [Backup & Updating](#9-backup--updating)

---

## 1. Node roles: sync vs. settlement

There are two roles. **Read this first** — picking the wrong one is the most
common way to get stuck.

| Role | What it does | Who it's for | Fleet secrets |
|------|--------------|--------------|---------------|
| **Sync node** *(default for new operators)* | Serves the public read API, accepts attestations. Does **not** settle epochs and does **not** join the authenticated P2P mesh. | New / unverified operators | **None** |
| **Full settlement node** | Everything a sync node does **plus** epoch settlement and authenticated P2P consensus. | Verified operators only | Yes — `RC_P2P_SECRET` and a fleet `RC_ADMIN_KEY`, **issued privately after verification** |

> **New operators start as a sync node.** A settlement node mints rewards and
> joins consensus, so its credentials (`RC_P2P_SECRET`, a fleet `RC_ADMIN_KEY`)
> are issued privately and are **never published**. Do not invent or copy these
> values — a self-generated `RC_P2P_SECRET` can never match the fleet's, and
> every `/p2p/*` call would answer `401 valid X-P2P-Key required`.

> **Set `RC_NODE_ROLE=sync` for a sync node.** The node's default role is
> `settlement`, which *refuses to start* without `RC_P2P_SECRET` (this is
> deliberate: a fleet node that loses its secret must fail loudly rather than
> silently degrade). An external operator who does not set `RC_NODE_ROLE=sync`
> will see `[P2P] FATAL: ... requires RC_P2P_SECRET` at startup.

---

## 2. System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | x86_64, 2 cores | 4+ cores |
| **RAM** | 2 GB | 4 GB+ |
| **Storage** | 10 GB SSD | 50 GB NVMe |
| **Network** | 10 Mbps | 100 Mbps+ |
| **OS** | Linux (Ubuntu 20.04+) | Linux (Ubuntu 22.04+) |
| **Python** | 3.10+ | 3.11+ |

### Network port

| Port | Purpose |
|------|---------|
| 8099 | HTTP API (the app binds here). In production, put nginx in front on 443 → 127.0.0.1:8099. |

There is no separate P2P port — the mesh runs over the same 8099 and is
fleet-only (settlement nodes).

---

## 3. Installation

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Create a virtualenv and install the node dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-node.txt
```

`requirements-node.txt` pins Flask, requests, psutil, PyNaCl, and gunicorn.
That is the entire toolchain — no Rust, no compiler, no downloaded binary.

---

## 4. Configuration

The node is configured entirely through **environment variables** (there is no
`config.yaml`).

| Variable | Sync node | Settlement node | Description |
|----------|-----------|-----------------|-------------|
| `RC_NODE_ROLE` | `sync` | `settlement` (default) | `sync` = run without fleet secrets and without the P2P mesh. `settlement` = refuse to start unless `RC_P2P_SECRET` is set. |
| `RC_NODE_ID` | ✅ a label | ✅ a label | A name for this node, e.g. `sync-yourname-1`. |
| `RC_ADMIN_KEY` | generate your own | fleet key (issued) | Admin API auth. For a sync node, generate your own: `openssl rand -hex 32`. |
| `RUSTCHAIN_DB_PATH` | ✅ | ✅ | SQLite DB path (fallback env `DB_PATH`; default `./rustchain_v2.db`). |
| `RC_P2P_SECRET` | — (omit) | issued privately | Authenticated P2P mesh HMAC (`X-P2P-Key`). Settlement nodes only. |

Addresses are `RTC` + 40 hex characters (for example
`RTCa1b2c3d4e5f6789012345678901234567890abcd`). They are **not** `rust1…`.

---

## 5. Starting the Node

### Quick test (foreground)

```bash
cd Rustchain/node
export RC_NODE_ROLE=sync
export RC_NODE_ID=sync-1
export RC_ADMIN_KEY=$(openssl rand -hex 32)     # your own admin key
export RUSTCHAIN_DB_PATH=$PWD/rustchain_v2.db
python3 rustchain_v2_integrated_v2.2.1_rip200.py
```

### Production (gunicorn)

```bash
cd Rustchain/node
export RC_NODE_ROLE=sync
export RC_NODE_ID=sync-1
export RC_ADMIN_KEY=$(openssl rand -hex 32)
export RUSTCHAIN_DB_PATH=/opt/rustchain/rustchain_v2.db
gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120
```

`node/wsgi.py` is the gunicorn entrypoint — it imports
`rustchain_v2_integrated_v2.2.1_rip200.py`, runs the mock-signature runtime
guard, and initializes the database.

On a sync node you will see this at startup, which is **correct, not an error**:

```
[P2P] RC_P2P_SECRET is not set: running as a SYNC node without the
authenticated P2P mesh (no /p2p mesh endpoints, no gossip). ...
```

---

## 6. Monitoring & Health Checks

```bash
# Your node's health
curl -s http://127.0.0.1:8099/health
# -> {"ok":true,"version":"2.2.1-rip200", ...}

# Current epoch
curl -s http://127.0.0.1:8099/epoch

# Active miners (public)
curl -s http://127.0.0.1:8099/api/miners
```

To compare against the public fleet:

```bash
curl -s https://rustchain.org/health
curl -s https://rustchain.org/api/miners
```

---

## 7. Troubleshooting

#### `error: could not find Cargo.toml` / no `rustchain-linux-x86_64` binary

**Cause:** You tried to build RustChain as a Rust project. It is a Python/Flask
app — there is no `Cargo.toml` and no release binary.

**Fix:** Follow [Installation](#3-installation) — `pip install -r
requirements-node.txt`, then run the node with Python/gunicorn per
[Starting the Node](#5-starting-the-node).

#### `[P2P] FATAL: ... requires RC_P2P_SECRET` and the process exits at startup

**Cause:** The default role is `settlement`, which requires the fleet
`RC_P2P_SECRET` you do not have.

**Fix:** Set `RC_NODE_ROLE=sync`. Never invent a placeholder secret.

#### `{"error":"unauthorized","message":"valid X-P2P-Key required"}` (HTTP 401)

**Cause:** You (or your node) called a fleet-only P2P endpoint — `/p2p/state`,
`/p2p/attestation_state`, `/p2p/peers`, `/p2p/gossip` — without the fleet's
shared `RC_P2P_SECRET`. The `X-P2P-Key` header must equal the *receiving*
node's secret; a secret you generated yourself can never match.

**This is expected for a sync node.** There is no key to request for it — the
mesh is fleet-only. Verify your node with the public endpoints instead
(`/health`, `/epoch`, `/api/miners`). If you were issued fleet credentials and
still see this, the secret in your config differs from the fleet's (check for
whitespace or a stale value). Never paste secrets into chat or issues.

#### "Address already in use" on port 8099

```bash
lsof -i :8099        # find what's using it
# stop that process, or change the -b port on the gunicorn command
```

#### "Database is locked"

**Cause:** Another instance is running against the same `RUSTCHAIN_DB_PATH`.

```bash
pkill -f rustchain_v2_integrated   # stop stray instances
# then restart
```

#### Attestation rejected: "Clock drift too high"

**Cause:** System clock not synchronized.

```bash
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
```

---

## 8. Running as a systemd service

`/etc/systemd/system/rustchain.service` (sync node):

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
Environment="RC_NODE_ROLE=sync"
Environment="RC_NODE_ID=sync-1"
Environment="RC_ADMIN_KEY=REPLACE_WITH_YOUR_OWN_32_BYTE_HEX"
Environment="RUSTCHAIN_DB_PATH=/opt/rustchain/rustchain_v2.db"
# Sync nodes do NOT set RC_P2P_SECRET — that is issued privately to
# verified settlement-node operators only. Leave RC_NODE_ROLE at sync.
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
sudo systemctl enable --now rustchain
sudo systemctl status rustchain
sudo journalctl -u rustchain -f
```

---

## 9. Backup & Updating

```bash
# Backup the database
cp "$RUSTCHAIN_DB_PATH" ./backup/rustchain-$(date +%Y%m%d).db

# Backup any encrypted wallet keystores
cp -r ~/.rustchain/*_wallets ./backup/wallets-$(date +%Y%m%d)/ 2>/dev/null || true

# Update the node
cd Rustchain
git pull origin main
source venv/bin/activate
pip install -r requirements-node.txt   # in case deps changed
sudo systemctl restart rustchain
```

---

## Related documentation

- `node/README.md` — node roles and the P2P secret, in brief
- `requirements-node.txt` — the pinned dependency set

> Note: some older sibling docs in this repo may still describe a Rust
> binary, `config.yaml`, or ports 3000/3001. **This guide and `node/README.md`
> reflect the running node.** If another doc disagrees, trust these.

---

*Node runs Python/Flask via `gunicorn wsgi:app` on port 8099. Version tag
`2.2.1-rip200`.*
