#!/bin/bash
# ──────────────────────────────────────────────────────────────
# RustChain Node — Cloud-Init Bootstrap Script
# ──────────────────────────────────────────────────────────────
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

LOG_FILE="/var/log/rustchain-bootstrap.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "[$(date -u)] RustChain bootstrap starting..."

# ── System Updates ──────────────────────────────────────────
apt-get update -y
apt-get upgrade -y
apt-get install -y \
  docker.io \
  docker-compose \
  git \
  curl \
  ufw \
  fail2ban \
  sqlite3 \
  python3 \
  python3-pip \
  certbot

# ── Docker ──────────────────────────────────────────────────
systemctl enable docker
systemctl start docker

# ── Firewall ────────────────────────────────────────────────
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw allow 8099/tcp   # RustChain dashboard
ufw allow 8088/tcp   # RustChain API
${MONITORING_FIREWALL_RULES}
ufw --force enable

# ── Fail2Ban ────────────────────────────────────────────────
systemctl enable fail2ban
systemctl start fail2ban

# ── Clone RustChain ─────────────────────────────────────────
RUSTCHAIN_DIR="/opt/rustchain"
mkdir -p "$RUSTCHAIN_DIR"
git clone --depth 1 https://github.com/Scottcjn/Rustchain.git "$RUSTCHAIN_DIR"
cd "$RUSTCHAIN_DIR"

# ── Build & Start Node ─────────────────────────────────────
docker-compose up -d --build

echo "[$(date -u)] RustChain node is running."

# ── Monitoring Stack ────────────────────────────────────────
${MONITORING_BLOCK}

# ── TLS (optional) ──────────────────────────────────────────
${TLS_BLOCK}

# ── Systemd Watchdog ────────────────────────────────────────
cat > /etc/systemd/system/rustchain-watchdog.service <<'UNIT'
[Unit]
Description=RustChain container watchdog
After=docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'cd /opt/rustchain && docker-compose up -d'

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/rustchain-watchdog.timer <<'TIMER'
[Unit]
Description=Check RustChain containers every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable rustchain-watchdog.timer
systemctl start rustchain-watchdog.timer

echo "[$(date -u)] RustChain bootstrap complete."
