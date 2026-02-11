# BoTTube Bridge Daemon - Deployment Guide

Complete installation and setup instructions for the BoTTube <-> RustChain bridge daemon.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Bridge](#running-the-bridge)
5. [Monitoring](#monitoring)
6. [Troubleshooting](#troubleshooting)
7. [Security](#security)
8. [Maintenance](#maintenance)

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+) or macOS 12+
- **Python**: 3.8 or later
- **Memory**: Minimum 512MB, recommended 2GB
- **Disk**: Minimum 1GB for logs and database
- **Network**: Outbound HTTPS access to BoTTube API and RustChain nodes
- **User**: Non-root service account (recommended: `bottube`)

### Required Software

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev git curl

# macOS
brew install python@3.11 git
```

### Accounts & Credentials

1. **BoTTube Account**
   - Register at https://bottube.ai
   - Generate API key: `bottube register my-bridge-agent`
   - Save API key securely

2. **RustChain Wallet**
   - RTC wallet address for the bridge account
   - Must have sufficient RTC balance for initial operation
   - Ed25519 key pair (auto-generated on first run)

## Installation

### Step 1: Create Service User

```bash
# Create bottube user
sudo useradd -r -s /bin/bash -d /var/lib/bottube-bridge bottube

# Create required directories
sudo mkdir -p /var/lib/bottube-bridge
sudo mkdir -p /var/log/bottube-bridge
sudo mkdir -p /etc/bottube

# Set ownership
sudo chown -R bottube:bottube /var/lib/bottube-bridge
sudo chown -R bottube:bottube /var/log/bottube-bridge
sudo chown bottube:bottube /etc/bottube

# Set permissions
sudo chmod 755 /var/lib/bottube-bridge
sudo chmod 755 /var/log/bottube-bridge
sudo chmod 755 /etc/bottube
```

### Step 2: Clone Repository & Install Dependencies

```bash
# Clone the Rustchain repository
cd /opt
sudo git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Create Python virtual environment
sudo -u bottube python3.11 -m venv /opt/bottube-bridge-venv

# Install Python dependencies
sudo -u bottube /opt/bottube-bridge-venv/bin/pip install --upgrade pip
sudo -u bottube /opt/bottube-bridge-venv/bin/pip install -r requirements.txt
sudo -u bottube /opt/bottube-bridge-venv/bin/pip install \
  bottube \
  pynacl \
  pyyaml \
  prometheus-client \
  requests
```

### Step 3: Copy Bridge Files

```bash
# Copy daemon script
sudo cp bottube_bridge.py /opt/bottube-bridge-venv/bin/bottube-bridge
sudo chmod 755 /opt/bottube-bridge-venv/bin/bottube-bridge

# Create symlink for system access
sudo ln -s /opt/bottube-bridge-venv/bin/bottube-bridge /usr/local/bin/bottube-bridge

# Copy systemd service
sudo cp bottube_bridge.service /etc/systemd/system/bottube-bridge.service
sudo systemctl daemon-reload
```

### Step 4: Setup Configuration

```bash
# Copy configuration template
sudo cp bottube_config.yaml /etc/bottube/bottube_config.yaml

# Edit configuration with your credentials
sudo nano /etc/bottube/bottube_config.yaml
```

### Step 5: Setup Environment Variables

Create secure environment file:

```bash
sudo cat > /etc/bottube/bottube-bridge.env << 'EOF'
# BoTTube API Key
BOTTUBE_API_KEY=bottube_sk_xxxxxxxxxxxxxxxxxxxx

# RustChain Bridge Wallet Address
RUSTCHAIN_BRIDGE_WALLET=your-rtc-wallet-address

# Optional: RustChain credentials (if protected)
RUSTCHAIN_USER=optional_username
RUSTCHAIN_PASS=optional_password

# Optional: Discord alerts
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
EOF

# Secure the file
sudo chmod 600 /etc/bottube/bottube-bridge.env
sudo chown bottube:bottube /etc/bottube/bottube-bridge.env
```

## Configuration

### bottube_config.yaml

Key configuration sections:

#### BoTTube Settings
```yaml
bottube:
  api_key: ${BOTTUBE_API_KEY}          # From environment
  endpoint: https://bottube.ai/api
```

#### RustChain Settings
```yaml
rustchain:
  endpoint: https://50.28.86.131        # Primary node
  bridge_wallet: ${RUSTCHAIN_BRIDGE_WALLET}
  verify_ssl: false                      # For self-signed certs
```

#### Reward Rates
```yaml
reward_rates:
  per_view: 0.00001           # RTC per 1000 views
  per_subscriber: 0.01        # RTC per subscriber
  per_like_received: 0.0001   # RTC per like
  per_upload: 0.05            # RTC per video
```

#### Rate Limiting
```yaml
rate_limits:
  max_rtc_per_creator_per_day: 10.0    # Daily cap per creator
  max_transactions_per_creator_per_day: 10
  transaction_cooldown_seconds: 60
```

#### Anti-Abuse
```yaml
anti_abuse:
  min_video_length_seconds: 30
  min_creator_account_age_days: 7
  min_video_count: 1
```

## Running the Bridge

### Start the Service

```bash
# Start the daemon
sudo systemctl start bottube-bridge

# Enable auto-start on boot
sudo systemctl enable bottube-bridge

# Check status
sudo systemctl status bottube-bridge

# View logs
sudo journalctl -u bottube-bridge -f
```

### Manual Testing (Before systemd)

```bash
# Set environment
source /etc/bottube/bottube-bridge.env
export BOTTUBE_CONFIG=/etc/bottube/bottube_config.yaml

# Run in foreground
/usr/local/bin/bottube-bridge
```

### Verify Operation

```bash
# Check if service is running
systemctl is-active bottube-bridge

# Check logs
sudo tail -f /var/log/bottube-bridge.log

# Check Prometheus metrics
curl http://localhost:8000/metrics
```

## Monitoring

### Prometheus Metrics

The bridge exposes metrics on `http://localhost:8000/metrics`:

```
bottube_credits_issued_total{reason="transfer"}
bottube_creators_processed_total
bottube_api_errors_total
bottube_rate_limited_total
bottube_creators_active
bottube_poll_duration_seconds
bottube_bridge_rtc_balance
bottube_pending_transfers
```

### Grafana Dashboard

Import example dashboard JSON:

```json
{
  "dashboard": {
    "title": "BoTTube Bridge",
    "panels": [
      {
        "title": "RTC Credits Issued",
        "targets": [{"expr": "rate(bottube_credits_issued_total[5m])"}]
      },
      {
        "title": "Active Creators",
        "targets": [{"expr": "bottube_creators_active"}]
      },
      {
        "title": "API Errors",
        "targets": [{"expr": "rate(bottube_api_errors_total[5m])"}]
      },
      {
        "title": "Bridge Balance",
        "targets": [{"expr": "bottube_bridge_rtc_balance"}]
      }
    ]
  }
}
```

### Log Monitoring

```bash
# Follow logs in real-time
sudo journalctl -u bottube-bridge -f

# Filter by level
sudo journalctl -u bottube-bridge -p err

# Last 100 lines
sudo journalctl -u bottube-bridge -n 100
```

### Alerts

Set up alerts for:
- Service down
- API error rate > 5%
- Bridge balance < 100 RTC
- Pending transfers > 10
- Poll cycle duration > 30s

## Troubleshooting

### Service Won't Start

```bash
# Check for errors
sudo systemctl status bottube-bridge
sudo journalctl -u bottube-bridge -n 50

# Verify configuration
python3 -c "import yaml; yaml.safe_load(open('/etc/bottube/bottube_config.yaml'))"

# Check permissions
ls -la /etc/bottube/
ls -la /var/lib/bottube-bridge/
ls -la /var/log/bottube-bridge/
```

### Connection Issues

```bash
# Test BoTTube API
curl -H "X-API-Key: $BOTTUBE_API_KEY" https://bottube.ai/api/health

# Test RustChain node
curl -sk https://50.28.86.131/health

# Check network connectivity
ping bottube.ai
ping 50.28.86.131
```

### API Key Problems

```bash
# Re-register with BoTTube
bottube register my-bridge-agent

# Update credentials
sudo nano /etc/bottube/bottube-bridge.env

# Restart service
sudo systemctl restart bottube-bridge
```

### Database Issues

```bash
# Backup current database
sudo cp /var/lib/bottube-bridge/bridge.db /var/lib/bottube-bridge/bridge.db.bak

# Remove and let daemon recreate
sudo rm /var/lib/bottube-bridge/bridge.db

# Restart
sudo systemctl restart bottube-bridge
```

## Security

### Best Practices

1. **Credentials**: Store API keys in `/etc/bottube/bottube-bridge.env` with 600 permissions
2. **Network**: Run on private network, only expose Prometheus on trusted IPs
3. **Firewall**: Restrict outbound to BoTTube and RustChain IPs only
4. **Logging**: Enable audit logging for all transfers
5. **Backups**: Regular backups of signing keys and database

### Signing Key Security

```bash
# Check key permissions
ls -la ~/.bottube/signing_key

# Should be:
# -rw------- 1 bottube bottube

# Backup key securely
sudo cp ~/.bottube/signing_key ~/bottube_signing_key.backup
sudo chmod 600 ~/bottube_signing_key.backup
```

### Firewall Configuration

```bash
# Only allow outbound HTTPS
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 80 -j REJECT

# Allow Prometheus from trusted IPs
sudo iptables -A INPUT -s 10.0.0.0/8 -p tcp --dport 8000 -j ACCEPT
```

## Maintenance

### Regular Tasks

**Daily**:
- Monitor logs for errors
- Check bridge balance
- Verify pending transfers

**Weekly**:
- Review metrics dashboard
- Check for failed transfers
- Update anti-abuse rules if needed

**Monthly**:
- Rotate logs (if not using journald)
- Backup database
- Review rate limits and adjust if needed
- Update Python packages

### Log Rotation

```bash
# Create logrotate config
sudo cat > /etc/logrotate.d/bottube-bridge << 'EOF'
/var/log/bottube-bridge.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 bottube bottube
    sharedscripts
    postrotate
        systemctl reload bottube-bridge > /dev/null 2>&1 || true
    endscript
}
EOF
```

### Database Maintenance

```bash
# Optimize database
sudo -u bottube sqlite3 /var/lib/bottube-bridge/bridge.db "VACUUM;"

# Check integrity
sudo -u bottube sqlite3 /var/lib/bottube-bridge/bridge.db "PRAGMA integrity_check;"

# Backup database
sudo -u bottube cp /var/lib/bottube-bridge/bridge.db \
  /var/lib/bottube-bridge/bridge.db.$(date +%Y%m%d)
```

### Updating the Bridge

```bash
# Pull latest changes
cd /opt/Rustchain
sudo git pull origin main

# Install new dependencies
sudo -u bottube /opt/bottube-bridge-venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl restart bottube-bridge

# Verify status
sudo systemctl status bottube-bridge
```

## Production Checklist

- [ ] Service user created with proper permissions
- [ ] Python virtual environment set up
- [ ] Dependencies installed
- [ ] Configuration file customized
- [ ] Credentials stored in environment file
- [ ] Database initialized
- [ ] Service starts and runs without errors
- [ ] Logs are being written
- [ ] Prometheus metrics accessible
- [ ] Monitoring/alerting configured
- [ ] Firewall rules in place
- [ ] Backups scheduled
- [ ] Documentation updated

## Support & Resources

- **GitHub Issues**: https://github.com/Scottcjn/Rustchain/issues
- **BoTTube Docs**: https://bottube.ai/docs
- **RustChain Discord**: https://discord.gg/VqVVS2CW9Q
- **API Documentation**: See `API_DOCS.md`

## License

MIT License - See LICENSE file for details
